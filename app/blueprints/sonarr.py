from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from .. import db
from ..models import Show, ServiceSettings
from ..tasks import get_retry_session

bp = Blueprint('sonarr', __name__)

@bp.route('/sonarr')
def sonarr_page():
    view = request.args.get('view', 'table')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 100, type=int)
    
    # Filter and sort parameters
    score_filter = request.args.get('score_filter', 'all')
    sort_by = request.args.get('sort_by', 'title')
    sort_order = request.args.get('sort_order', 'asc')
    search_query = request.args.get('search', '')

    # Base query
    query = Show.query

    # Apply search
    if search_query:
        query = query.filter(Show.title.ilike(f'%{search_query}%'))

    # Apply filter
    if score_filter and score_filter != 'all':
        if score_filter == 'Not Scored':
            query = query.filter(Show.score.in_(['Not Scored', None]))
        else:
            query = query.filter(Show.score == score_filter)

    # Apply sorting
    sortable_columns = ['title', 'size_gb', 'score', 'year']
    if sort_by not in sortable_columns:
        sort_by = 'title'
        
    column = getattr(Show, sort_by)
    if sort_order == 'desc':
        query = query.order_by(column.desc())
    else:
        query = query.order_by(column.asc())
    
    shows = query.paginate(page=page, per_page=per_page, error_out=False)

    if request.headers.get('HX-Request'):
        return render_template('_sonarr_list.html',
                               shows=shows,
                               view=view,
                               score_filter=score_filter,
                               sort_by=sort_by,
                               sort_order=sort_order,
                               search=search_query)

    return render_template('sonarr.html',
                           shows=shows,
                           view=view,
                           score_filter=score_filter,
                           sort_by=sort_by,
                           sort_order=sort_order,
                           search=search_query)

@bp.route('/seasonal')
def seasonal_page():
    seasonal_shows = Show.query.filter_by(score='Seasonal').all()
    settings = ServiceSettings.query.filter_by(service_name='Sonarr').first()
    return render_template('seasonal.html', seasonal_shows=seasonal_shows, settings=settings)

@bp.route('/seasonal/settings', methods=['POST'])
def seasonal_settings():
    settings = ServiceSettings.query.filter_by(service_name='Sonarr').first()
    if not settings:
        flash('Sonarr settings not found. Please configure Sonarr first.', 'error')
        return redirect(url_for('sonarr.seasonal_page'))
    
    try:
        min_episodes = int(request.form.get('seasonal_min_episodes', 1))
        settings.seasonal_min_episodes = min_episodes
        db.session.commit()
        flash('Seasonal settings updated.', 'success')
    except ValueError:
        flash('Invalid input for minimum episodes.', 'error')
        
    return redirect(url_for('sonarr.seasonal_page'))

@bp.route('/seasonal/scan', methods=['POST'])
def seasonal_scan():
    settings = ServiceSettings.query.filter_by(service_name='Sonarr').first()
    if not settings:
        return jsonify({'status': 'error', 'message': 'Sonarr settings not configured'})

    min_episodes = settings.seasonal_min_episodes or 1
    seasonal_shows = Show.query.filter_by(score='Seasonal').all()
    
    session = get_retry_session()
    headers = {'X-Api-Key': settings.api_key}
    base_url = settings.url.rstrip('/')

    results = []

    for show in seasonal_shows:
        try:
            # Fetch series details from Sonarr to get season stats
            response = session.get(f"{base_url}/api/v3/series/{show.sonarr_id}", headers=headers)
            response.raise_for_status()
            series_data = response.json()
            
            seasons = series_data.get('seasons', [])
            # Filter out Season 0 and find the newest season
            valid_seasons = [s for s in seasons if s['seasonNumber'] > 0]
            if not valid_seasons:
                continue
                
            newest_season = max(valid_seasons, key=lambda x: x['seasonNumber'])
            downloaded_count = newest_season.get('statistics', {}).get('episodeFileCount', 0)
            
            if downloaded_count >= min_episodes:
                # Condition met! Identify previous seasons to delete
                seasons_to_delete = []
                for s in valid_seasons:
                    if s['seasonNumber'] < newest_season['seasonNumber']:
                        # Only add if it has files or is monitored (worth cleaning up)
                        if s.get('statistics', {}).get('episodeFileCount', 0) > 0 or s.get('monitored'):
                            seasons_to_delete.append(s['seasonNumber'])
                
                if seasons_to_delete:
                    results.append({
                        'sonarr_id': show.sonarr_id,
                        'title': show.title,
                        'newest_season_number': newest_season['seasonNumber'],
                        'downloaded_episodes': downloaded_count,
                        'seasons_to_delete': sorted(seasons_to_delete)
                    })

        except Exception as e:
            print(f"Error scanning show {show.title}: {e}")
            continue

    return jsonify({'status': 'success', 'data': results})

@bp.route('/seasonal/execute', methods=['POST'])
def seasonal_execute():
    data = request.get_json()
    items = data.get('items', [])
    
    settings = ServiceSettings.query.filter_by(service_name='Sonarr').first()
    if not settings:
        return jsonify({'status': 'error', 'message': 'Sonarr settings not configured'})

    session = get_retry_session()
    headers = {'X-Api-Key': settings.api_key}
    base_url = settings.url.rstrip('/')
    
    processed_count = 0
    
    for item in items:
        sonarr_id = item.get('sonarr_id')
        seasons_to_delete = item.get('seasons_to_delete', [])
        
        if not sonarr_id or not seasons_to_delete:
            continue
            
        try:
            # 1. Unmonitor Seasons
            # We need to fetch the series first to get the full object, modify it, and PUT it back
            series_resp = session.get(f"{base_url}/api/v3/series/{sonarr_id}", headers=headers)
            series_resp.raise_for_status()
            series_data = series_resp.json()
            
            modified = False
            for season in series_data['seasons']:
                if season['seasonNumber'] in seasons_to_delete and season['monitored']:
                    season['monitored'] = False
                    modified = True
            
            if modified:
                put_resp = session.put(f"{base_url}/api/v3/series/{sonarr_id}", headers=headers, json=series_data)
                put_resp.raise_for_status()

            # 2. Delete Files
            # Fetch all episode files for the series
            files_resp = session.get(f"{base_url}/api/v3/episodefile?seriesId={sonarr_id}", headers=headers)
            files_resp.raise_for_status()
            files = files_resp.json()
            
            for file in files:
                if file['seasonNumber'] in seasons_to_delete:
                    try:
                        del_resp = session.delete(f"{base_url}/api/v3/episodefile/{file['id']}", headers=headers)
                        del_resp.raise_for_status()
                    except Exception as e:
                        print(f"Error deleting file {file['id']} for series {sonarr_id}: {e}")
            
            processed_count += 1

        except Exception as e:
            print(f"Error processing cleanup for series {sonarr_id}: {e}")
            continue

    return jsonify({'status': 'success', 'count': processed_count})
