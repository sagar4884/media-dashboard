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
import yaml

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
    sortable_columns = ['title', 'size_gb', 'score', 'year'
    ]
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

@current_app.route('/stop-job', methods=['POST'])
def stop_job():
    redis_conn = current_app.queue.connection
    redis_conn.set('stop-job-flag', 'true')
    return jsonify({'status': 'Stop signal sent'})

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
        item.marked_for_deletion_at = None
        item.delete_at = None
        tags_to_add.append('ai-keep')
        tags_to_remove.extend(['ai-delete', 'ai-rolling-keep', 'ai-tautulli-keep'])
    elif action == 'delete':
        item.score = 'Delete'
        item.marked_for_deletion_at = datetime.utcnow()
        settings = ServiceSettings.query.filter_by(service_name=service_name).first()
        grace_days = settings.grace_days if settings else 30
        item.delete_at = item.marked_for_deletion_at + timedelta(days=grace_days)
        tags_to_add.append('ai-delete')
        tags_to_remove.extend(['ai-keep', 'ai-rolling-keep', 'ai-tautulli-keep'])
    elif action == 'seasonal' and media_type == 'show':
        item.score = 'Seasonal'
        item.marked_for_deletion_at = None
        item.delete_at = None
        tags_to_add.append('ai-rolling-keep')
        tags_to_remove.extend(['ai-delete', 'ai-keep', 'ai-tautulli-keep'])
    elif action == 'not_scored':
        item.score = 'Not Scored'
        item.marked_for_deletion_at = None
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

@current_app.route('/media/bulk_action', methods=['POST'])
def bulk_action():
    data = request.get_json()
    media_type = data.get('media_type')
    action = data.get('action')
    ids = data.get('ids', [])

    if not ids:
        return jsonify({'status': 'success', 'message': 'No items selected'})

    if media_type == 'movie':
        model = Movie
        service_name = 'Radarr'
        id_key = 'movieIds'
        item_id_attr = 'radarr_id'
    elif media_type == 'show':
        model = Show
        service_name = 'Sonarr'
        id_key = 'seriesIds'
        item_id_attr = 'sonarr_id'
    else:
        return jsonify({'error': 'Invalid media type'}), 400

    items = model.query.filter(model.id.in_(ids)).all()
    
    tags_to_add = []
    tags_to_remove = []
    service_ids_to_update = []

    # For delete_now, we need settings
    settings = None
    session = None
    if action == 'delete_now':
        settings = ServiceSettings.query.filter_by(service_name=service_name).first()
        session = get_retry_session()

    # For delete/reset_grace_period, we need settings for grace days
    if action in ['delete', 'reset_grace_period']:
        if not settings:
            settings = ServiceSettings.query.filter_by(service_name=service_name).first()
        grace_days = settings.grace_days if settings else 30

    count = 0
    for item in items:
        if action == 'keep':
            item.score = 'Keep'
            item.marked_for_deletion_at = None
            item.delete_at = None
            tags_to_add = ['ai-keep']
            tags_to_remove = ['ai-delete', 'ai-rolling-keep', 'ai-tautulli-keep']
            service_ids_to_update.append(getattr(item, item_id_attr))
        
        elif action == 'delete':
            item.score = 'Delete'
            item.marked_for_deletion_at = datetime.utcnow()
            item.delete_at = item.marked_for_deletion_at + timedelta(days=grace_days)
            tags_to_add = ['ai-delete']
            tags_to_remove = ['ai-keep', 'ai-rolling-keep', 'ai-tautulli-keep']
            service_ids_to_update.append(getattr(item, item_id_attr))

        elif action == 'seasonal' and media_type == 'show':
            item.score = 'Seasonal'
            item.marked_for_deletion_at = None
            item.delete_at = None
            tags_to_add = ['ai-rolling-keep']
            tags_to_remove = ['ai-delete', 'ai-keep', 'ai-tautulli-keep']
            service_ids_to_update.append(getattr(item, item_id_attr))

        elif action == 'not_scored':
            item.score = 'Not Scored'
            item.marked_for_deletion_at = None
            item.delete_at = None
            tags_to_add = [] # No tags to add
            tags_to_remove = ['ai-delete', 'ai-keep', 'ai-rolling-keep', 'ai-tautulli-keep']
            service_ids_to_update.append(getattr(item, item_id_attr))

        elif action == 'reset_grace_period':
            if item.score == 'Delete':
                item.marked_for_deletion_at = datetime.utcnow()
                item.delete_at = item.marked_for_deletion_at + timedelta(days=grace_days)
        
        elif action == 'delete_now':
            # This is destructive and interacts with external API
            if settings:
                headers = {'X-Api-Key': settings.api_key}
                base_url = settings.url.rstrip('/')
                
                if media_type == 'movie':
                    url = f"{base_url}/api/v3/movie/{item.radarr_id}"
                    params = {'deleteFiles': 'true', 'addImportListExclusion': 'false'}
                else:
                    url = f"{base_url}/api/v3/series/{item.sonarr_id}"
                    params = {'deleteFiles': 'true', 'addExclusion': 'false'}
                
                try:
                    session.delete(url, headers=headers, params=params)
                except Exception as e:
                    print(f"Error deleting {media_type} {item.id}: {e}")
                    continue # Skip DB delete if API fails? Or delete anyway? Better to skip.
            
            db.session.delete(item)
            count += 1
            continue # Skip the db.session.add(item) below

        db.session.add(item)
        count += 1

    db.session.commit()

    # Batch update tags if needed
    if service_ids_to_update and action in ['keep', 'delete', 'seasonal', 'not_scored']:
        payload = {
            id_key: service_ids_to_update,
            'tagsToAdd': tags_to_add,
            'tagsToRemove': tags_to_remove
        }
        update_service_tags(service_name, payload)

    return jsonify({'status': 'success', 'count': count})

@current_app.route('/seasonal')
def seasonal_page():
    seasonal_shows = Show.query.filter_by(score='Seasonal').all()
    settings = ServiceSettings.query.filter_by(service_name='Sonarr').first()
    return render_template('seasonal.html', seasonal_shows=seasonal_shows, settings=settings)

@current_app.route('/seasonal/settings', methods=['POST'])
def seasonal_settings():
    settings = ServiceSettings.query.filter_by(service_name='Sonarr').first()
    if not settings:
        flash('Sonarr settings not found. Please configure Sonarr first.', 'error')
        return redirect(url_for('seasonal_page'))
    
    try:
        min_episodes = int(request.form.get('seasonal_min_episodes', 1))
        settings.seasonal_min_episodes = min_episodes
        db.session.commit()
        flash('Seasonal settings updated.', 'success')
    except ValueError:
        flash('Invalid input for minimum episodes.', 'error')
        
    return redirect(url_for('seasonal_page'))

@current_app.route('/seasonal/scan', methods=['POST'])
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

@current_app.route('/seasonal/execute', methods=['POST'])
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

@current_app.route('/overlays')
def overlays_page():
    settings = ServiceSettings.query.filter_by(service_name='Radarr').first() # Use Radarr settings to store template for now, or create a generic one
    # If we don't have a generic settings row, let's use the first one we find or create a dummy one if needed.
    # Actually, let's stick to the plan: add column to ServiceSettings.
    # We can just pick one service to store it, say 'Radarr' since it's usually present.
    
    template = ""
    if settings and settings.overlay_template:
        template = settings.overlay_template
    
    return render_template('overlays.html', template=template)

@current_app.route('/overlays/save_template', methods=['POST'])
def save_overlay_template():
    data = request.get_json()
    template = data.get('template')
    
    # Store in Radarr settings for now as a global place
    settings = ServiceSettings.query.filter_by(service_name='Radarr').first()
    if not settings:
        # Should not happen in a configured app, but handle it
        return jsonify({'status': 'error', 'message': 'Radarr settings not found (used for storage)'})
        
    settings.overlay_template = template
    db.session.commit()
    return jsonify({'status': 'success'})

def generate_overlay_yaml():
    # 1. Get Template
    settings = ServiceSettings.query.filter_by(service_name='Radarr').first()
    raw_template = settings.overlay_template if settings and settings.overlay_template else """overlay:
  name: text(Leaving <DATE>)
  horizontal_align: center
  vertical_align: bottom
  vertical_offset: 50
  font_size: 65
  font_color: '#FF0000'
  weight: 25"""

    # 2. Get Items
    movies = Movie.query.filter(Movie.delete_at.isnot(None)).all()
    shows = Show.query.filter(Show.delete_at.isnot(None)).all()
    
    # 3. Group by Date
    grouped_items = {}
    
    for item in movies:
        date_str = item.delete_at.strftime('%b %d') # e.g. Nov 24
        if date_str not in grouped_items:
            grouped_items[date_str] = {'tmdb_movie': [], 'tvdb_show': []}
        if item.tmdb_id:
            grouped_items[date_str]['tmdb_movie'].append(item.tmdb_id)

    for item in shows:
        date_str = item.delete_at.strftime('%b %d')
        if date_str not in grouped_items:
            grouped_items[date_str] = {'tmdb_movie': [], 'tvdb_show': []}
        if item.tvdb_id:
            grouped_items[date_str]['tvdb_show'].append(item.tvdb_id)

    # 4. Build YAML Structure
    overlays_data = {'overlays': {}}
    
    for date_str, ids in grouped_items.items():
        key = f"MEDIADASHBOARD_LEAVING_{date_str.upper().replace(' ', '_')}"
        
        # Parse the raw template to a dict
        try:
            # Replace placeholder in the raw string first
            current_template_str = raw_template.replace('<DATE>', date_str)
            current_template = yaml.safe_load(current_template_str)
            
            # If the user pasted "overlay: ...", use it. If they pasted just the content, wrap it.
            if 'overlay' not in current_template:
                current_template = {'overlay': current_template}
                
        except yaml.YAMLError:
            # Fallback if template is invalid YAML
            current_template = {'overlay': {'name': f'text(Leaving {date_str})'}}

        entry = current_template
        
        if ids['tmdb_movie']:
            entry['tmdb_movie'] = ids['tmdb_movie']
        if ids['tvdb_show']:
            entry['tvdb_show'] = ids['tvdb_show']
            
        overlays_data['overlays'][key] = entry

    return yaml.dump(overlays_data, sort_keys=False)

@current_app.route('/overlays/preview')
def preview_overlay():
    yaml_content = generate_overlay_yaml()
    return jsonify({'content': yaml_content})

@current_app.route('/overlays/generate', methods=['POST'])
def generate_overlay_file():
    yaml_content = generate_overlay_yaml()
    
    # Ensure directory exists
    output_dir = '/appdata/kometa'
    os.makedirs(output_dir, exist_ok=True)
    
    file_path = os.path.join(output_dir, 'media_dashboard_overlays.yaml')
    
    try:
        with open(file_path, 'w') as f:
            f.write(yaml_content)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})