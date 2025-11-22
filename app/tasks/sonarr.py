import time
from rq import get_current_job
from .. import db
from ..models import ServiceSettings, Show
from .utils import get_retry_session, fetch_tmdb_assets, update_service_tags
from ..logging_utils import task_wrapper

@task_wrapper('Sonarr')
def sync_sonarr_shows(full_sync=False):
    job = get_current_job()
    job.meta['progress'] = 0
    job.save_meta()
    start_time = time.time()

    redis_conn = job.connection
    redis_conn.delete('stop-job-flag')

    settings = ServiceSettings.query.filter_by(service_name='Sonarr').first()
    if not settings:
        return {'error': 'Sonarr settings not found'}

    headers = {'X-Api-Key': settings.api_key}
    session = get_retry_session(category='Sonarr')

    # Fetch all tags to create a mapping from ID to Label
    tags_response = session.get(f"{settings.url}/api/v3/tag", headers=headers)
    tags_response.raise_for_status()
    tag_map = {tag['id']: tag['label'] for tag in tags_response.json()}

    response = session.get(f"{settings.url}/api/v3/series", headers=headers)
    response.raise_for_status()
    shows_data = response.json()

    shows_to_update = {}  # Groups shows by tag changes required

    total_shows = len(shows_data)
    for i, show_data in enumerate(shows_data):
        if redis_conn.exists('stop-job-flag'):
            break
        show = Show.query.filter_by(sonarr_id=show_data['id']).first()
        
        # Bootstrap score for new shows from existing tags
        if not show:
            show = Show(sonarr_id=show_data['id'])
            current_labels = {tag_map.get(tag_id, '').lower() for tag_id in show_data.get('tags', [])}
            if 'ai-keep' in current_labels:
                show.score = 'Keep'
            elif 'ai-delete' in current_labels:
                show.score = 'Delete'
            elif 'ai-rolling-keep' in current_labels:
                show.score = 'Seasonal'
            elif 'ai-tautulli-keep' in current_labels:
                show.score = 'Tautulli Keep'
            else:
                show.score = 'Not Scored'

        show.tvdb_id = show_data.get('tvdbId')
        show.title = show_data.get('title')
        show.year = show_data.get('year')
        if 'statistics' in show_data:
            show.size_gb = show_data['statistics'].get('sizeOnDisk', 0) / (1024**3)
        show.overview = show_data.get('overview')
        tag_ids = show_data.get('tags', [])
        show.labels = ",".join([tag_map.get(tag_id) for tag_id in tag_ids if tag_id in tag_map])

        # Sync tags based on score
        current_labels = {tag_map.get(tag_id, '').lower() for tag_id in tag_ids}
        tags_to_add_labels = set()
        tags_to_remove_labels = set()

        if show.score == 'Keep':
            tags_to_add_labels.add('ai-keep')
            tags_to_remove_labels.update(['ai-delete', 'ai-rolling-keep', 'ai-tautulli-keep'])
        elif show.score == 'Delete':
            tags_to_add_labels.add('ai-delete')
            tags_to_remove_labels.update(['ai-keep', 'ai-rolling-keep', 'ai-tautulli-keep'])
        elif show.score == 'Seasonal':
            tags_to_add_labels.add('ai-rolling-keep')
            tags_to_remove_labels.update(['ai-keep', 'ai-delete', 'ai-tautulli-keep'])
        elif show.score == 'Tautulli Keep':
            tags_to_add_labels.add('ai-tautulli-keep')
            tags_to_remove_labels.update(['ai-keep', 'ai-delete', 'ai-rolling-keep'])
        elif show.score == 'Not Scored':
            tags_to_remove_labels.update(['ai-keep', 'ai-delete', 'ai-rolling-keep', 'ai-tautulli-keep'])

        final_tags_to_add = tuple(sorted([tag for tag in tags_to_add_labels if tag not in current_labels]))
        final_tags_to_remove = tuple(sorted([tag for tag in tags_to_remove_labels if tag in current_labels]))

        if final_tags_to_add or final_tags_to_remove:
            change_key = (final_tags_to_add, final_tags_to_remove)
            if change_key not in shows_to_update:
                shows_to_update[change_key] = []
            shows_to_update[change_key].append(show.sonarr_id)
        
        if (full_sync or not show.local_poster_path) and show.tvdb_id:
            assets = fetch_tmdb_assets(show.tvdb_id, 'tv')
            if assets and isinstance(assets, tuple):
                show.local_poster_path = assets[0]
                if assets[1]:
                    show.tmdb_id = assets[1]
        
        db.session.add(show)
        
        # ETA calculation
        elapsed_time = time.time() - start_time
        progress = (i + 1) / total_shows
        if progress > 0:
            eta_seconds = (elapsed_time / progress) * (1 - progress)
            job.meta['eta'] = time.strftime("%M:%S", time.gmtime(eta_seconds))

        job.meta['progress'] = int(progress * 100)
        job.save_meta()
        
    db.session.commit()
        
    # After loop, apply tag changes in batches
    for (tags_to_add, tags_to_remove), series_ids in shows_to_update.items():
        payload = {
            'seriesIds': series_ids,
            'tagsToAdd': list(tags_to_add),
            'tagsToRemove': list(tags_to_remove)
        }
        update_service_tags('Sonarr', payload)

    return {'status': 'Completed', 'shows_synced': total_shows}
