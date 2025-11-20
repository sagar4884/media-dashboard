from flask import Blueprint, render_template, request, redirect, url_for, flash
from .. import db
from ..models import Movie, Show, ServiceSettings
from ..tasks import get_retry_session
from datetime import datetime

bp = Blueprint('deletion', __name__)

@bp.route('/deletion')
def deletion_page():
    sort_by = request.args.get('sort_by', 'title')
    sort_order = request.args.get('sort_order', 'asc')

    sortable_columns = ['title', 'size_gb', 'marked_for_deletion_at']
    if sort_by not in sortable_columns:
        sort_by = 'title'

    radarr_query = Movie.query.filter(Movie.score == 'Delete')
    sonarr_query = Show.query.filter(Show.score == 'Delete')

    radarr_column = getattr(Movie, sort_by)
    sonarr_column = getattr(Show, sort_by)

    if sort_order == 'desc':
        radarr_items = radarr_query.order_by(radarr_column.desc()).all()
        sonarr_items = sonarr_query.order_by(sonarr_column.desc()).all()
    else:
        radarr_items = radarr_query.order_by(radarr_column.asc()).all()
        sonarr_items = sonarr_query.order_by(sonarr_column.asc()).all()

    radarr_space = sum(item.size_gb for item in radarr_items if item.size_gb is not None)
    sonarr_space = sum(item.size_gb for item in sonarr_items if item.size_gb is not None)

    stats = {
        'radarr': {'pending': len(radarr_items)},
        'sonarr': {'pending': len(sonarr_items)},
        'total_space': radarr_space + sonarr_space
    }
    
    radarr_settings = ServiceSettings.query.filter_by(service_name='Radarr').first()
    sonarr_settings = ServiceSettings.query.filter_by(service_name='Sonarr').first()

    return render_template('deletion.html', 
                           radarr_items=radarr_items, 
                           sonarr_items=sonarr_items, 
                           stats=stats,
                           radarr_settings=radarr_settings,
                           sonarr_settings=sonarr_settings,
                           now=datetime.utcnow(),
                           sort_by=sort_by,
                           sort_order=sort_order)

@bp.route('/purge')
def purge():
    now = datetime.utcnow()
    movies_to_delete = Movie.query.filter(Movie.delete_at <= now).all()
    shows_to_delete = Show.query.filter(Show.delete_at <= now).all()

    radarr_settings = ServiceSettings.query.filter_by(service_name='Radarr').first()
    sonarr_settings = ServiceSettings.query.filter_by(service_name='Sonarr').first()

    session = get_retry_session()

    deleted_movies_count = 0
    if radarr_settings:
        headers = {'X-Api-Key': radarr_settings.api_key}
        base_url = radarr_settings.url.rstrip('/')
        for movie in movies_to_delete:
            url = f"{base_url}/api/v3/movie/{movie.radarr_id}"
            params = {'deleteFiles': 'true', 'addImportListExclusion': 'false'}
            session.delete(url, headers=headers, params=params)
            db.session.delete(movie)
            deleted_movies_count += 1

    deleted_shows_count = 0
    if sonarr_settings:
        headers = {'X-Api-Key': sonarr_settings.api_key}
        base_url = sonarr_settings.url.rstrip('/')
        for show in shows_to_delete:
            url = f"{base_url}/api/v3/series/{show.sonarr_id}"
            params = {'deleteFiles': 'true', 'addExclusion': 'false'}
            session.delete(url, headers=headers, params=params)
            db.session.delete(show)
            deleted_shows_count += 1
            
    db.session.commit()

    flash(f'Purged {deleted_movies_count} movies and {deleted_shows_count} shows.', 'success')
    return redirect(url_for('main.dashboard'))
