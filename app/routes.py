from flask import render_template, request, jsonify, current_app, redirect, url_for, flash
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
    return render_template('dashboard.html', stats=stats, active_job_id=active_job_id)

@current_app.route('/radarr')
def radarr_page():
    view = request.args.get('view', 'table')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 100, type=int)
    movies = Movie.query.order_by(Movie.title).paginate(page=page, per_page=per_page)
    return render_template('radarr.html', movies=movies, view=view)

@current_app.route('/sonarr')
def sonarr_page():
    view = request.args.get('view', 'table')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 100, type=int)
    shows = Show.query.order_by(Show.title).paginate(page=page, per_page=per_page)
    return render_template('sonarr.html', shows=shows, view=view)

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
