import time
from rq import get_current_job
from .. import db
from ..models import ServiceSettings, Movie
from .utils import get_retry_session, fetch_tmdb_assets, update_service_tags
from ..logging_utils import task_wrapper

@task_wrapper('Radarr')
def sync_radarr_movies(full_sync=False):
    job = get_current_job()
    job.meta['progress'] = 0
    job.save_meta()
    start_time = time.time()
    
    redis_conn = job.connection
    redis_conn.delete('stop-job-flag')

    settings = ServiceSettings.query.filter_by(service_name='Radarr').first()
    if not settings:
        return {'error': 'Radarr settings not found'}

    headers = {'X-Api-Key': settings.api_key}
    session = get_retry_session(category='Radarr')

    # Fetch all tags to create a mapping from ID to Label and vice-versa
    tags_response = session.get(f"{settings.url}/api/v3/tag", headers=headers)
    tags_response.raise_for_status()
    tag_map = {tag['id']: tag['label'] for tag in tags_response.json()}

    response = session.get(f"{settings.url}/api/v3/movie", headers=headers)
    response.raise_for_status()
    movies_data = response.json()

    movies_to_update = {}  # Groups movies by tag changes required

    total_movies = len(movies_data)
    for i, movie_data in enumerate(movies_data):
        if redis_conn.exists('stop-job-flag'):
            break
        movie = Movie.query.filter_by(radarr_id=movie_data['id']).first()
        
        # Bootstrap score for new movies from existing tags
        if not movie:
            movie = Movie(radarr_id=movie_data['id'])
            current_labels = {tag_map.get(tag_id, '').lower() for tag_id in movie_data.get('tags', [])}
            if 'ai-keep' in current_labels:
                movie.score = 'Keep'
            elif 'ai-delete' in current_labels:
                movie.score = 'Delete'
            elif 'ai-tautulli-keep' in current_labels:
                movie.score = 'Tautulli Keep'
            else:
                movie.score = 'Not Scored'
        
        movie.tmdb_id = movie_data.get('tmdbId')
        movie.title = movie_data.get('title')
        movie.year = movie_data.get('year')
        movie.size_gb = movie_data.get('sizeOnDisk', 0) / (1024**3)
        movie.overview = movie_data.get('overview')
        tag_ids = movie_data.get('tags', [])
        movie.labels = ",".join([tag_map.get(tag_id) for tag_id in tag_ids if tag_id in tag_map])

        # Sync tags based on score
        current_labels = {tag_map.get(tag_id, '').lower() for tag_id in tag_ids}
        tags_to_add_labels = set()
        tags_to_remove_labels = set()

        if movie.score == 'Keep':
            tags_to_add_labels.add('ai-keep')
            tags_to_remove_labels.update(['ai-delete', 'ai-tautulli-keep'])
        elif movie.score == 'Delete':
            tags_to_add_labels.add('ai-delete')
            tags_to_remove_labels.update(['ai-keep', 'ai-tautulli-keep'])
        elif movie.score == 'Tautulli Keep':
            tags_to_add_labels.add('ai-tautulli-keep')
            tags_to_remove_labels.update(['ai-keep', 'ai-delete'])
        elif movie.score == 'Not Scored':
            tags_to_remove_labels.update(['ai-keep', 'ai-delete', 'ai-tautulli-keep', 'ai-rolling-keep'])
        
        final_tags_to_add = tuple(sorted([tag for tag in tags_to_add_labels if tag not in current_labels]))
        final_tags_to_remove = tuple(sorted([tag for tag in tags_to_remove_labels if tag in current_labels]))

        if final_tags_to_add or final_tags_to_remove:
            change_key = (final_tags_to_add, final_tags_to_remove)
            if change_key not in movies_to_update:
                movies_to_update[change_key] = []
            movies_to_update[change_key].append(movie.radarr_id)

        if (full_sync or not movie.local_poster_path) and movie.tmdb_id:
            assets = fetch_tmdb_assets(movie.tmdb_id, 'movie')
            if assets and isinstance(assets, tuple):
                movie.local_poster_path = assets[0]

        db.session.add(movie)

        # ETA calculation
        elapsed_time = time.time() - start_time
        progress = (i + 1) / total_movies
        if progress > 0:
            eta_seconds = (elapsed_time / progress) * (1 - progress)
            job.meta['eta'] = time.strftime("%M:%S", time.gmtime(eta_seconds))
        
        job.meta['progress'] = int(progress * 100)
        job.save_meta()

    db.session.commit()

    # After loop, apply tag changes in batches
    for (tags_to_add, tags_to_remove), movie_ids in movies_to_update.items():
        payload = {
            'movieIds': movie_ids,
            'tagsToAdd': list(tags_to_add),
            'tagsToRemove': list(tags_to_remove)
        }
        update_service_tags('Radarr', payload)

    return {'status': 'Completed', 'movies_synced': total_movies}
