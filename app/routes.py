from flask import render_template, request, jsonify, current_app, redirect, url_for, flash
import os
import requests
from sqlalchemy import text
from . import db
from .models import ServiceSettings, Movie, Show, TautulliHistory
from .tasks import sync_radarr_movies, sync_sonarr_shows, sync_tautulli_history, update_service_tags, get_retry_session, vacuum_database
from rq.job import Job
from rq.exceptions import NoSuchJobError
from rq.registry import StartedJobRegistry
from datetime import datetime, timedelta

@current_app.route('/')
def dashboard():
    # Radarr stats
    radarr_total = Movie.query.count()
    radarr_unscored = Movie.query.filter(Movie.score.in_(['Not Scored', None])).count()
    radarr_keep = Movie.query.filter_by(score='Keep').count()
    radarr_delete = Movie.query.filter_by(score='Delete').count()

    # Sonarr stats
    sonarr_total = Show.query.count()
    sonarr_unscored = Show.query.filter(Show.score.in_(['Not Scored', None])).count()
    sonarr_keep = Show.query.filter_by(score='Keep').count()
    sonarr_delete = Show.query.filter_by(score='Delete').count()
    sonarr_seasonal = Show.query.filter_by(score='Seasonal').count()

    stats = {
        'radarr': {
            'total': radarr_total,
            'unscored': radarr_unscored,
            'keep': radarr_keep,
            'delete': radarr_delete
        },
        'sonarr': {
            'total': sonarr_total,
            'unscored': sonarr_unscored,
            'keep': sonarr_keep,
            'delete': sonarr_delete,
            'seasonal': sonarr_seasonal
        }
    }
    return render_template('dashboard.html', stats=stats)

@current_app.route('/radarr')
def radarr_page():
    view = request.args.get('view', 'table')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 100, type=int)
    
    # Filter and sort parameters
    score_filter = request.args.get('score_filter', 'all')
    sort_by = request.args.get('sort_by', 'title')
    sort_order = request.args.get('sort_order', 'asc')

    # Base query
    query = Movie.query

    # Apply filter
    if score_filter and score_filter != 'all':
        if score_filter == 'Not Scored':
            query = query.filter(Movie.score.in_(['Not Scored', None]))
        else:
            query = query.filter(Movie.score == score_filter)

    # Apply sorting
    sortable_columns = ['title', 'size_gb', 'score', 'year']
    if sort_by not in sortable_columns:
        sort_by = 'title'
        
    column = getattr(Movie, sort_by)
    if sort_order == 'desc':
        query = query.order_by(column.desc())
    else:
        query = query.order_by(column.asc())
    
    movies = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('radarr.html',
                           movies=movies,
                           view=view,
                           score_filter=score_filter,
                           sort_by=sort_by,
                           sort_order=sort_order)

@current_app.route('/sonarr')
def sonarr_page():
    view = request.args.get('view', 'table')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 100, type=int)
    
    # Filter and sort parameters
    score_filter = request.args.get('score_filter', 'all')
    sort_by = request.args.get('sort_by', 'title')
    sort_order = request.args.get('sort_order', 'asc')

    # Base query
    query = Show.query

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

    return render_template('sonarr.html',
                           shows=shows,
                           view=view,
                           score_filter=score_filter,
                           sort_by=sort_by,
                           sort_order=sort_order)

@current_app.route('/tautulli')
def tautulli_page():
    history = db.session.query(
        TautulliHistory,
        Movie.local_poster_path,
        Movie.overview,
        Show.local_poster_path.label('show_local_poster_path'),
        Show.overview.label('show_overview'),
        Show.title.label('show_title')
    ).outerjoin(Movie, TautulliHistory.title == Movie.title)\
     .outerjoin(Show, TautulliHistory.title.startswith(Show.title))\
     .order_by(TautulliHistory.date.desc())\
     .all()
    return render_template('tautulli.html', history=history)

@current_app.route('/deletion')
def deletion_page():
    radarr_items = Movie.query.filter(Movie.score == 'Delete').order_by(Movie.marked_for_deletion_at.asc()).all()
    sonarr_items = Show.query.filter(Show.score == 'Delete').order_by(Show.marked_for_deletion_at.asc()).all()

    radarr_space = sum(item.size_gb for item in radarr_items)
    sonarr_space = sum(item.size_gb for item in sonarr_items)

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
                           now=datetime.utcnow())

@current_app.route('/database')
def database_page():
    db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '/')
    db_info = {
        'type': 'SQLite',
        'path': db_path,
        'size_mb': os.path.getsize(db_path) / (1024 * 1024) if os.path.exists(db_path) else 0
    }
    return render_template('database.html', db_info=db_info)

@current_app.route('/database/integrity_check', methods=['POST'])
def integrity_check():
    try:
        result = db.session.execute(text('PRAGMA integrity_check')).fetchone()
        return f"Integrity Check: {result[0]}"
    except Exception as e:
        return f"Error: {e}"

@current_app.route('/database/optimize', methods=['POST'])
def optimize_db():
    try:
        db.session.execute(text('PRAGMA optimize'))
        db.session.commit()
        return "Database optimization complete."
    except Exception as e:
        return f"Error: {e}"

@current_app.route('/database/vacuum', methods=['POST'])
def vacuum_db():
    registry = StartedJobRegistry(queue=current_app.queue)
    if registry.get_job_ids():
        return jsonify({'error': 'A job is already running'}), 409
        
    job = current_app.queue.enqueue(vacuum_database, job_timeout='15m')
    return jsonify({'job_id': job.get_id()})



@current_app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        services = ['Radarr', 'Sonarr', 'Tautulli']
        for service_name in services:
            settings = ServiceSettings.query.filter_by(service_name=service_name).first()
            if not settings:
                settings = ServiceSettings(service_name=service_name)
            
            settings.url = request.form.get(f'{service_name}_url')
            settings.api_key = request.form.get(f'{service_name}_api_key')
            if service_name != 'Tautulli':
                settings.grace_days = int(request.form.get(f'{service_name}_grace_days', 30))
            settings.retention_days = int(request.form.get(f'{service_name}_retention_days', 365))
            if service_name == 'Radarr': # Centralized TMDB key
                settings.tmdb_api_key = request.form.get('tmdb_api_key')

            db.session.add(settings)
        db.session.commit()
        flash('Settings saved successfully!', 'success')
        return redirect(url_for('settings'))
    
    radarr_settings = ServiceSettings.query.filter_by(service_name='Radarr').first()
    sonarr_settings = ServiceSettings.query.filter_by(service_name='Sonarr').first()
    tautulli_settings = ServiceSettings.query.filter_by(service_name='Tautulli').first()

    return render_template('settings.html',
                           radarr_settings=radarr_settings,
                           sonarr_settings=sonarr_settings,
                           tautulli_settings=tautulli_settings)

@current_app.route('/sync/<service>')
def sync(service):
    registry = StartedJobRegistry(queue=current_app.queue)
    if registry.get_job_ids():
        return jsonify({'error': 'A job is already running'}), 409

    mode = request.args.get('mode', 'quick')
    full_sync = mode == 'full'

    if service == 'radarr':
        job = current_app.queue.enqueue(sync_radarr_movies, job_timeout='3h', args=(full_sync,))
    elif service == 'sonarr':
        job = current_app.queue.enqueue(sync_sonarr_shows, job_timeout='3h', args=(full_sync,))
    elif service == 'tautulli':
        job = current_app.queue.enqueue(sync_tautulli_history, job_timeout='5m', args=(full_sync,))
    else:
        return jsonify({'error': 'Invalid service'}), 400
    
    return jsonify({'job_id': job.get_id()})

@current_app.route('/task_status/<job_id>')
def task_status(job_id):
    try:
        job = Job.fetch(job_id, connection=current_app.queue.connection)
    except NoSuchJobError:
        # The job is no longer in the registry, which means it's finished or failed and cleaned up.
        # Tell the frontend to stop polling.
        return jsonify({'status': 'finished'})

    response = {
        'status': job.get_status(),
        'progress': job.meta.get('progress', 0) if job.is_started else 0,
        'eta': job.meta.get('eta', None)
    }
    if job.is_finished:
        response['result'] = job.result
    elif job.is_failed:
        response['error'] = job.exc_info
    
    return jsonify(response)

@current_app.route('/media/action/<media_type>/<int:media_id>/<action>')
def media_action(media_type, media_id, action):
    if media_type == 'movie':
        item = Movie.query.get_or_404(media_id)
        service_name = 'Radarr'
        id_key = 'movieIds'
        item_id = item.radarr_id
    elif media_type == 'show':
        item = Show.query.get_or_404(media_id)
        service_name = 'Sonarr'
        id_key = 'seriesIds'
        item_id = item.sonarr_id
    else:
        return jsonify({'error': 'Invalid media type'}), 400

    tags_to_add = []
    tags_to_remove = []

    if action == 'keep':
        item.score = 'Keep'
        item.delete_at = None
        tags_to_add.append('ai-keep')
        tags_to_remove.extend(['ai-delete', 'ai-rolling-keep', 'ai-tautulli-keep'])
    elif action == 'delete':
        item.score = 'Delete'
        settings = ServiceSettings.query.filter_by(service_name=service_name).first()
        grace_days = settings.grace_days if settings else 30
        item.delete_at = datetime.utcnow() + timedelta(days=grace_days)
        tags_to_add.append('ai-delete')
        tags_to_remove.extend(['ai-keep', 'ai-rolling-keep', 'ai-tautulli-keep'])
    elif action == 'seasonal' and media_type == 'show':
        item.score = 'Seasonal'
        item.delete_at = None
        tags_to_add.append('ai-rolling-keep')
        tags_to_remove.extend(['ai-delete', 'ai-keep', 'ai-tautulli-keep'])
    elif action == 'not_scored':
        item.score = 'Not Scored'
        item.delete_at = None
        tags_to_remove.extend(['ai-delete', 'ai-keep', 'ai-rolling-keep', 'ai-tautulli-keep'])
    
    db.session.commit()

    payload = {
        id_key: [item_id],
        'tagsToAdd': tags_to_add,
        'tagsToRemove': tags_to_remove
    }
    update_service_tags(service_name, payload)
    
    if media_type == 'movie':
        return redirect(url_for('radarr_page', view=request.args.get('view', 'table')))
    else:
        return redirect(url_for('sonarr_page', view=request.args.get('view', 'table')))


@current_app.route('/purge')
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
    return redirect(url_for('dashboard'))

@current_app.route('/delete/<media_type>/<int:media_id>')
def delete_media(media_type, media_id):
    session = get_retry_session()
    
    if media_type == 'movie':
        item = Movie.query.get_or_404(media_id)
        settings = ServiceSettings.query.filter_by(service_name='Radarr').first()
        if settings:
            headers = {'X-Api-Key': settings.api_key}
            base_url = settings.url.rstrip('/')
            url = f"{base_url}/api/v3/movie/{item.radarr_id}"
            params = {'deleteFiles': 'true', 'addImportListExclusion': 'false'}
            try:
                response = session.delete(url, headers=headers, params=params)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                flash(f'Error deleting movie from Radarr: {e}', 'error')
                return redirect(url_for('deletion_page'))
        db.session.delete(item)
        flash(f'Deleted movie: {item.title}', 'success')

    elif media_type == 'show':
        item = Show.query.get_or_404(media_id)
        settings = ServiceSettings.query.filter_by(service_name='Sonarr').first()
        if settings:
            headers = {'X-Api-Key': settings.api_key}
            base_url = settings.url.rstrip('/')
            url = f"{base_url}/api/v3/series/{item.sonarr_id}"
            params = {'deleteFiles': 'true', 'addExclusion': 'false'}
            try:
                response = session.delete(url, headers=headers, params=params)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                flash(f'Error deleting show from Sonarr: {e}', 'error')
                return redirect(url_for('deletion_page'))
        db.session.delete(item)
        flash(f'Deleted show: {item.title}', 'success')

    db.session.commit()
    return redirect(url_for('deletion_page'))

@current_app.route('/test_connection/<service>', methods=['POST'])
def test_connection(service):
    session = get_retry_session()
    service_name = service.capitalize()
    
    url = request.form.get(f'{service_name}_url')
    api_key = request.form.get(f'{service_name}_api_key')

    try:
        if service == 'radarr' or service == 'sonarr':
            headers = {'X-Api-Key': api_key}
            response = session.get(f"{url}/api/v3/system/status", headers=headers, timeout=10)
        elif service == 'tautulli':
            params = {'cmd': 'get_history', 'apikey': api_key, 'length': 1}
            response = session.get(f"{url}/api/v2", params=params, timeout=10)
        elif service == 'tmdb':
            tmdb_api_key = request.form.get('tmdb_api_key')
            response = session.get(f"https://api.themoviedb.org/3/configuration?api_key={tmdb_api_key}", timeout=10)
        else:
            return f'<span class="text-red-400">Invalid service specified.</span>'

        response.raise_for_status()
        return f'<span class="text-green-400">Successful Connection</span>'
    except requests.exceptions.Timeout:
        return f'<span class="text-red-400">Connection Failed: The request timed out.</span>'
    except requests.exceptions.RequestException as e:
        return f'<span class="text-red-400">Connection Failed: {e}</span>'