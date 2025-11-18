from flask import render_template, request, jsonify, current_app, redirect, url_for, flash
import requests
from . import db
from .models import ServiceSettings, Movie, Show, TautulliHistory
from .tasks import sync_radarr_movies, sync_sonarr_shows, sync_tautulli_history, update_service_tags, get_retry_session
from rq.job import Job
from rq.exceptions import NoSuchJobError
from rq.exceptions import NoSuchJobError
from rq.registry import StartedJobRegistry
from datetime import datetime, timedelta

@current_app.route('/')
def dashboard():
    # Check for a running job
    registry = StartedJobRegistry(queue=current_app.queue)
    running_job_ids = registry.get_job_ids()
    active_job_id = running_job_ids[0] if running_job_ids else None

    # Radarr stats
    radarr_total = Movie.query.count()
    radarr_unscored = Movie.query.filter(Movie.score.in_(['Not Scored', None])).count()
    radarr_keep = Movie.query.filter_by(score='Keep').count()
    radarr_delete = Movie.query.filter_by(score='Delete').count()
    radarr_archived = Movie.query.filter_by(score='Archived').count()

    # Sonarr stats
    sonarr_total = Show.query.count()
    sonarr_unscored = Show.query.filter(Show.score.in_(['Not Scored', None])).count()
    sonarr_keep = Show.query.filter_by(score='Keep').count()
    sonarr_delete = Show.query.filter_by(score='Delete').count()
    sonarr_seasonal = Show.query.filter_by(score='Seasonal').count()
    sonarr_archived = Show.query.filter_by(score='Archived').count()

    stats = {
        'radarr': {
            'total': radarr_total,
            'unscored': radarr_unscored,
            'keep': radarr_keep,
            'delete': radarr_delete,
            'archived': radarr_archived
        },
        'sonarr': {
            'total': sonarr_total,
            'unscored': sonarr_unscored,
            'keep': sonarr_keep,
            'delete': sonarr_delete,
            'seasonal': sonarr_seasonal,
            'archived': sonarr_archived
        }
    }
    return render_template('dashboard.html', stats=stats, active_job_id=active_job_id)

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
    history = TautulliHistory.query.order_by(TautulliHistory.date.desc()).all()
    return render_template('tautulli.html', history=history)

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
    mode = request.args.get('mode', 'quick')
    full_sync = mode == 'full'

    if service == 'radarr':
        job = current_app.queue.enqueue(sync_radarr_movies, job_timeout='15m', args=(full_sync,))
    elif service == 'sonarr':
        job = current_app.queue.enqueue(sync_sonarr_shows, job_timeout='15m', args=(full_sync,))
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
        item.marked_for_deletion_at = None
        tags_to_add.append('ai-keep')
        tags_to_remove.extend(['ai-delete', 'ai-rolling-keep', 'ai-tautulli-keep'])
    elif action == 'delete':
        item.score = 'Delete'
        item.marked_for_deletion_at = datetime.utcnow()
        tags_to_add.append('ai-delete')
        tags_to_remove.extend(['ai-keep', 'ai-rolling-keep', 'ai-tautulli-keep'])
    elif action == 'seasonal' and media_type == 'show':
        item.score = 'Seasonal'
        item.marked_for_deletion_at = None
        tags_to_add.append('ai-rolling-keep')
        tags_to_remove.extend(['ai-delete', 'ai-keep', 'ai-tautulli-keep'])
    elif action == 'not_scored':
        item.score = 'Not Scored'
        item.marked_for_deletion_at = None
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
        for movie in movies_to_delete:
            url = f"{radarr_settings.url}/api/v3/movie/{movie.radarr_id}?deleteFiles=true"
            session.delete(url, headers=headers)
            db.session.delete(movie)
            deleted_movies_count += 1

    deleted_shows_count = 0
    if sonarr_settings:
        headers = {'X-Api-Key': sonarr_settings.api_key}
        for show in shows_to_delete:
            url = f"{sonarr_settings.url}/api/v3/series/{show.sonarr_id}?deleteFiles=true"
            session.delete(url, headers=headers)
            db.session.delete(show)
            deleted_shows_count += 1
            
    db.session.commit()

    flash(f'Purged {deleted_movies_count} movies and {deleted_shows_count} shows.', 'success')
    return redirect(url_for('dashboard'))


@current_app.route('/deletion')
def deletion_page():
    now = datetime.utcnow()
    
    radarr_settings = ServiceSettings.query.filter_by(service_name='Radarr').first()
    sonarr_settings = ServiceSettings.query.filter_by(service_name='Sonarr').first()

    # Backfill missing dates for items marked as delete
    items_to_fix = Movie.query.filter(Movie.score == 'Delete', Movie.marked_for_deletion_at == None).all()
    items_to_fix += Show.query.filter(Show.score == 'Delete', Show.marked_for_deletion_at == None).all()
    if items_to_fix:
        for item in items_to_fix:
            item.marked_for_deletion_at = now
        db.session.commit()

    radarr_items = Movie.query.filter(Movie.score == 'Delete').order_by(Movie.marked_for_deletion_at.asc()).all()
    sonarr_items = Show.query.filter(Show.score == 'Delete').order_by(Show.marked_for_deletion_at.asc()).all()

    radarr_space = sum(item.size_gb for item in radarr_items if item.size_gb)
    sonarr_space = sum(item.size_gb for item in sonarr_items if item.size_gb)

    stats = {
        'radarr': {'pending': len(radarr_items)},
        'sonarr': {'pending': len(sonarr_items)},
        'total_space': radarr_space + sonarr_space
    }

    return render_template('deletion.html',
                           radarr_items=radarr_items,
                           sonarr_items=sonarr_items,
                           stats=stats,
                           now=now,
                           radarr_settings=radarr_settings,
                           sonarr_settings=sonarr_settings)

@current_app.route('/delete_media/<media_type>/<int:media_id>')
def delete_media(media_type, media_id):
    if media_type == 'movie':
        item = Movie.query.get_or_404(media_id)
        settings = ServiceSettings.query.filter_by(service_name='Radarr').first()
        if settings:
            headers = {'X-Api-Key': settings.api_key}
            url = f"{settings.url}/api/v3/movie/{item.radarr_id}?deleteFiles=true"
            requests.delete(url, headers=headers)
            item.score = 'Archived'
            db.session.commit()
            flash(f"Deleted movie '{item.title}' and marked as archived.", 'success')
    elif media_type == 'show':
        item = Show.query.get_or_404(media_id)
        settings = ServiceSettings.query.filter_by(service_name='Sonarr').first()
        if settings:
            headers = {'X-Api-Key': settings.api_key}
            url = f"{settings.url}/api/v3/series/{item.sonarr_id}?deleteFiles=true"
            requests.delete(url, headers=headers)
            item.score = 'Archived'
            db.session.commit()
            flash(f"Deleted show '{item.title}' and marked as archived.", 'success')
    else:
        flash("Invalid media type.", 'error')

    return redirect(url_for('deletion_page'))

@current_app.route('/purge_expired')
def purge_expired():
    now = datetime.utcnow()
    radarr_settings = ServiceSettings.query.filter_by(service_name='Radarr').first()
    sonarr_settings = ServiceSettings.query.filter_by(service_name='Sonarr').first()

    movies_to_delete = []
    if radarr_settings and radarr_settings.grace_days is not None:
        purge_before_date = now - timedelta(days=radarr_settings.grace_days)
        movies_to_delete = Movie.query.filter(Movie.score == 'Delete', Movie.marked_for_deletion_at <= purge_before_date).all()

    shows_to_delete = []
    if sonarr_settings and sonarr_settings.grace_days is not None:
        purge_before_date = now - timedelta(days=sonarr_settings.grace_days)
        shows_to_delete = Show.query.filter(Show.score == 'Delete', Show.marked_for_deletion_at <= purge_before_date).all()

    deleted_movies_count = 0
    if radarr_settings and movies_to_delete:
        headers = {'X-Api-Key': radarr_settings.api_key}
        for movie in movies_to_delete:
            url = f"{radarr_settings.url}/api/v3/movie/{movie.radarr_id}?deleteFiles=true"
            requests.delete(url, headers=headers)
            movie.score = 'Archived'
            deleted_movies_count += 1

    deleted_shows_count = 0
    if sonarr_settings and shows_to_delete:
        headers = {'X-Api-Key': sonarr_settings.api_key}
        for show in shows_to_delete:
            url = f"{sonarr_settings.url}/api/v3/series/{show.sonarr_id}?deleteFiles=true"
            requests.delete(url, headers=headers)
            show.score = 'Archived'
            deleted_shows_count += 1
            
    db.session.commit()

    flash(f'Purged {deleted_movies_count} expired movies and {deleted_shows_count} expired shows.', 'success')
    return redirect(url_for('deletion_page'))
