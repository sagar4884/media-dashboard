import time
from datetime import datetime, timedelta
from rq import get_current_job
from .. import db
from ..models import ServiceSettings, Movie, Show, TautulliHistory
from .utils import get_retry_session, update_service_tags
from ..logging_utils import task_wrapper

@task_wrapper('Tautulli')
def sync_tautulli_history(full_sync=False):
    job = get_current_job()
    job.meta['progress'] = 0
    job.save_meta()
    start_time = time.time()

    redis_conn = job.connection
    redis_conn.delete('stop-job-flag')

    settings = ServiceSettings.query.filter_by(service_name='Tautulli').first()
    if not settings:
        return {'error': 'Tautulli settings not found'}
    
    session = get_retry_session(category='Tautulli')
    
    # Determine fetch length based on sync type
    # Full sync: Fetch a large number (effectively all relevant history)
    # Quick sync: Fetch last 1000 items
    fetch_length = 100000 if full_sync else 1000
    
    params = {
        'cmd': 'get_history',
        'apikey': settings.api_key,
        'length': fetch_length,
        'after': (datetime.now() - timedelta(days=settings.retention_days)).strftime('%Y-%m-%d')
    }
    response = session.get(f"{settings.url}/api/v2", params=params)
    response.raise_for_status()
    history_data = response.json()['response']['data']['data']

    rescued_movies = []
    rescued_shows = []
    total_items = len(history_data)

    # Get all movie and show titles that have been watched recently
    watched_titles = {item['full_title'] for item in history_data}

    # Process all movies
    all_movies = Movie.query.all()
    for movie in all_movies:
        if movie.score in ['Keep']:
            continue
        
        if movie.title in watched_titles:
            if movie.score != 'Tautulli Keep':
                movie.score = 'Tautulli Keep'
                rescued_movies.append(movie.radarr_id)
        elif movie.score == 'Tautulli Keep':
            movie.score = 'Not Scored'
            # Tag removal will be handled by the next sync with Radarr

    # Process all shows
    all_shows = Show.query.all()
    for show in all_shows:
        if redis_conn.exists('stop-job-flag'):
            break
        if show.score in ['Keep', 'Seasonal']:
            continue

        if show.title in watched_titles:
            if show.score != 'Tautulli Keep':
                show.score = 'Tautulli Keep'
                rescued_shows.append(show.sonarr_id)
        elif show.score == 'Tautulli Keep':
            show.score = 'Not Scored'
            # Tag removal will be handled by the next sync with Sonarr

    for i, item in enumerate(history_data):
        history_entry = TautulliHistory.query.filter_by(row_id=item['id']).first()
        if not history_entry:
            history_entry = TautulliHistory(
                row_id=item['id'],
                title=item['full_title'],
                user=item['user'],
                date=datetime.fromtimestamp(item['date']),
                state=item.get('state'),
                duration_mins=item.get('duration_in_seconds', 0) // 60
            )
            db.session.add(history_entry)

        # Rescue logic
        movie_to_rescue = Movie.query.filter_by(title=item['full_title'], score='Delete').first()
        if movie_to_rescue:
            movie_to_rescue.score = 'Tautulli Keep'
            rescued_movies.append(movie_to_rescue.radarr_id)
        
        show_to_rescue = Show.query.filter_by(title=item['full_title'], score='Delete').first()
        if show_to_rescue:
            show_to_rescue.score = 'Tautulli Keep'
            rescued_shows.append(show_to_rescue.sonarr_id)
        
        # ETA calculation
        elapsed_time = time.time() - start_time
        progress = (i + 1) / total_items
        if progress > 0:
            eta_seconds = (elapsed_time / progress) * (1 - progress)
            job.meta['eta'] = time.strftime("%M:%S", time.gmtime(eta_seconds))

        job.meta['progress'] = int(progress * 100)
        job.save_meta()

    db.session.commit()

    if rescued_movies:
        update_service_tags('Radarr', {'movieIds': rescued_movies, 'tagsToAdd': ['ai-tautulli-keep'], 'tagsToRemove': ['ai-delete']})
    if rescued_shows:
        update_service_tags('Sonarr', {'seriesIds': rescued_shows, 'tagsToAdd': ['ai-tautulli-keep'], 'tagsToRemove': ['ai-delete']})

    return {'status': 'Completed', 'history_synced': len(history_data), 'rescued_movies': len(rescued_movies), 'rescued_shows': len(rescued_shows)}
