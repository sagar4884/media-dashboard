from flask import Blueprint, render_template, request, jsonify
from .. import db
from ..models import Movie, Show, ServiceSettings
import yaml
import os

bp = Blueprint('radarr', __name__)

@bp.route('/radarr')
def radarr_page():
    view = request.args.get('view', 'table')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 100, type=int)
    
    # Filter and sort parameters
    score_filter = request.args.get('score_filter', 'all')
    sort_by = request.args.get('sort_by', 'title')
    sort_order = request.args.get('sort_order', 'asc')
    search_query = request.args.get('search', '')

    # Base query
    query = Movie.query

    # Apply search
    if search_query:
        query = query.filter(Movie.title.ilike(f'%{search_query}%'))

    # Apply filter
    if score_filter and score_filter != 'all':
        if score_filter == 'Not Scored':
            query = query.filter(Movie.score.in_(['Not Scored', None]))
        else:
            query = query.filter(Movie.score == score_filter)

    # Apply sorting
    sortable_columns = ['title', 'size_gb', 'score', 'year', 'ai_score']
    if sort_by not in sortable_columns:
        sort_by = 'title'
        
    column = getattr(Movie, sort_by)
    if sort_by == 'ai_score':
        # Custom sorting for AI Score:
        # 1. Group by Score Status (Not Scored, Keep, Tautulli Keep, Delete, etc.)
        # 2. Then sort by AI Score
        
        # Define a custom ordering for the 'score' column to group similar statuses
        # We want 'Not Scored' first (or last depending on order), then the others.
        # But the user asked to sort "Not Scored, Keep, Tautulli Keep, Delete, and Scored together"
        # which implies a primary sort on the AI Score itself, but handling NULLs (Not Scored) correctly.
        
        if sort_order == 'desc':
             # High scores first. NULLs (Not Scored) last.
             query = query.order_by(column.desc().nullslast(), Movie.title.asc())
        else:
             # Low scores first. NULLs (Not Scored) last.
             query = query.order_by(column.asc().nullslast(), Movie.title.asc())
    else:
        if sort_order == 'desc':
             query = query.order_by(column.desc())
        else:
             query = query.order_by(column.asc())
    
    movies = query.paginate(page=page, per_page=per_page, error_out=False)

    if request.headers.get('HX-Request'):
        return render_template('_radarr_list.html',
                               movies=movies,
                               view=view,
                               score_filter=score_filter,
                               sort_by=sort_by,
                               sort_order=sort_order,
                               search=search_query)

    return render_template('radarr.html',
                           movies=movies,
                           view=view,
                           score_filter=score_filter,
                           sort_by=sort_by,
                           sort_order=sort_order,
                           search=search_query)

@bp.route('/overlays')
def overlays_page():
    settings = ServiceSettings.query.filter_by(service_name='Radarr').first()
    
    movie_template = ""
    show_template = ""
    use_tmdb_for_shows = False
    
    if settings:
        movie_template = settings.overlay_movie_template or settings.overlay_template or ""
        show_template = settings.overlay_show_template or settings.overlay_template or ""
        use_tmdb_for_shows = settings.overlay_use_tmdb_for_shows
    
    return render_template('overlays.html', movie_template=movie_template, show_template=show_template, use_tmdb_for_shows=use_tmdb_for_shows)

@bp.route('/overlays/save_template', methods=['POST'])
def save_overlay_template():
    data = request.get_json()
    movie_template = data.get('movie_template')
    show_template = data.get('show_template')
    use_tmdb_for_shows = data.get('use_tmdb_for_shows', False)
    
    # Store in Radarr settings for now as a global place
    settings = ServiceSettings.query.filter_by(service_name='Radarr').first()
    if not settings:
        return jsonify({'status': 'error', 'message': 'Radarr settings not found (used for storage)'})
        
    settings.overlay_movie_template = movie_template
    settings.overlay_show_template = show_template
    settings.overlay_use_tmdb_for_shows = use_tmdb_for_shows
    db.session.commit()
    return jsonify({'status': 'success'})

def generate_overlay_yaml(movie_template=None, show_template=None, use_tmdb_for_shows=None, target_type='all'):
    settings = ServiceSettings.query.filter_by(service_name='Radarr').first()
    
    default_template = """overlay:
  name: text(Leaving <DATE>)
  horizontal_align: center
  vertical_align: bottom
  vertical_offset: 50
  font_size: 65
  font_color: '#FF0000'
  weight: 25"""

    if movie_template is None:
        movie_template = settings.overlay_movie_template if settings and settings.overlay_movie_template else (settings.overlay_template if settings and settings.overlay_template else default_template)
    
    if show_template is None:
        show_template = settings.overlay_show_template if settings and settings.overlay_show_template else (settings.overlay_template if settings and settings.overlay_template else default_template)
    
    if use_tmdb_for_shows is None:
        use_tmdb_for_shows = settings.overlay_use_tmdb_for_shows if settings else False

    overlays_data = {'overlays': {}}

    # Process Movies
    if target_type in ['all', 'movies']:
        movies = Movie.query.filter(Movie.delete_at.isnot(None)).all()
        grouped_movies = {}
        for item in movies:
            date_str = item.delete_at.strftime('%b %d')
            if date_str not in grouped_movies:
                grouped_movies[date_str] = []
            if item.tmdb_id:
                grouped_movies[date_str].append(item.tmdb_id)

        for date_str, ids in grouped_movies.items():
            if not ids: continue
            key = f"MEDIADASHBOARD_LEAVING_MOVIES_{date_str.upper().replace(' ', '_')}"
            
            try:
                current_template = yaml.safe_load(movie_template.replace('<DATE>', date_str))
                if 'overlay' not in current_template:
                    current_template = {'overlay': current_template}
            except yaml.YAMLError:
                current_template = {'overlay': {'name': f'text(Leaving {date_str})'}}

            current_template['tmdb_movie'] = ids
            overlays_data['overlays'][key] = current_template

    # Process Shows
    if target_type in ['all', 'shows']:
        shows = Show.query.filter(Show.delete_at.isnot(None)).all()
        grouped_shows = {}
        for item in shows:
            date_str = item.delete_at.strftime('%b %d')
            if date_str not in grouped_shows:
                grouped_shows[date_str] = []
            
            if use_tmdb_for_shows:
                if item.tmdb_id:
                    grouped_shows[date_str].append(item.tmdb_id)
            else:
                if item.tvdb_id:
                    grouped_shows[date_str].append(item.tvdb_id)

        for date_str, ids in grouped_shows.items():
            if not ids: continue
            key = f"MEDIADASHBOARD_LEAVING_SHOWS_{date_str.upper().replace(' ', '_')}"
            
            try:
                current_template = yaml.safe_load(show_template.replace('<DATE>', date_str))
                if 'overlay' not in current_template:
                    current_template = {'overlay': current_template}
            except yaml.YAMLError:
                current_template = {'overlay': {'name': f'text(Leaving {date_str})'}}

            if use_tmdb_for_shows:
                current_template['tmdb_show'] = ids
            else:
                current_template['tvdb_show'] = ids
                
            overlays_data['overlays'][key] = current_template

    return yaml.dump(overlays_data, sort_keys=False)

@bp.route('/overlays/preview', methods=['GET', 'POST'])
def preview_overlay():
    if request.method == 'POST':
        data = request.get_json()
        movie_template = data.get('movie_template')
        show_template = data.get('show_template')
        use_tmdb_for_shows = data.get('use_tmdb_for_shows')
        yaml_content = generate_overlay_yaml(movie_template, show_template, use_tmdb_for_shows)
    else:
        yaml_content = generate_overlay_yaml()
        
    return jsonify({'content': yaml_content})

@bp.route('/overlays/generate', methods=['POST'])
def generate_overlay_file():
    # Ensure directory exists
    output_dir = '/appdata/kometa'
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # Generate and write Movies YAML
        movies_yaml = generate_overlay_yaml(target_type='movies')
        movies_path = os.path.join(output_dir, 'media_dashboard_overlays_movies.yaml')
        with open(movies_path, 'w') as f:
            f.write(movies_yaml)

        # Generate and write Shows YAML
        shows_yaml = generate_overlay_yaml(target_type='shows')
        shows_path = os.path.join(output_dir, 'media_dashboard_overlays_shows.yaml')
        with open(shows_path, 'w') as f:
            f.write(shows_yaml)
            
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
