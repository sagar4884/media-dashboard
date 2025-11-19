import time
from rq import get_current_job
from flask import current_app
from sqlalchemy import text
from . import db
from .models import ServiceSettings, Movie, Show, TautulliHistory
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
from datetime import datetime, timedelta

def get_retry_session():
    session = requests.Session()
    retry = Retry(
        total=5,
        read=5,
        connect=5,
        backoff_factor=0.3,
        status_forcelist=(500, 502, 503, 504, 429),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def sync_radarr_movies(full_sync=False):
    job = get_current_job()
    job.meta['progress'] = 0
    job.save_meta()
    start_time = time.time()

    settings = ServiceSettings.query.filter_by(service_name='Radarr').first()
    if not settings:
        return {'error': 'Radarr settings not found'}

    headers = {'X-Api-Key': settings.api_key}
    session = get_retry_session()

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
            poster_path = fetch_tmdb_assets(movie.tmdb_id, 'movie')
            movie.local_poster_path = poster_path

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

def sync_sonarr_shows(full_sync=False):
    job = get_current_job()
    job.meta['progress'] = 0
    job.save_meta()
    start_time = time.time()

    settings = ServiceSettings.query.filter_by(service_name='Sonarr').first()
    if not settings:
        return {'error': 'Sonarr settings not found'}

    headers = {'X-Api-Key': settings.api_key}
    session = get_retry_session()

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
            poster_path = fetch_tmdb_assets(show.tvdb_id, 'tv')
            show.local_poster_path = poster_path
        
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

def sync_tautulli_history(full_sync=False):
    job = get_current_job()
    job.meta['progress'] = 0
    job.save_meta()
    start_time = time.time()

    settings = ServiceSettings.query.filter_by(service_name='Tautulli').first()
    if not settings:
        return {'error': 'Tautulli settings not found'}
    
    session = get_retry_session()
    params = {
        'cmd': 'get_history',
        'apikey': settings.api_key,
        'length': 1000, # Adjust as needed
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

def fetch_tmdb_assets(media_id, media_type='movie'):
    settings = ServiceSettings.query.first()
    if not settings or not settings.tmdb_api_key:
        return None
        
    tmdb_api_key = settings.tmdb_api_key
    session = get_retry_session()
    
    tmdb_id = None
    if media_type == 'movie':
        tmdb_id = media_id
    elif media_type == 'tv':
        # Find the TMDB ID from the TVDB ID
        find_url = f"https://api.themoviedb.org/3/find/{media_id}?api_key={tmdb_api_key}&external_source=tvdb_id"
        try:
            find_response = session.get(find_url)
            find_response.raise_for_status()
            find_data = find_response.json()
            if find_data['tv_results']:
                tmdb_id = find_data['tv_results'][0]['id']
        except requests.exceptions.RequestException as e:
            print(f"Error finding TMDB ID for TVDB ID {media_id}: {e}")
            return None

    if not tmdb_id:
        print(f"No TMDB ID found for {media_type} {media_id}")
        return None

    url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}?api_key={tmdb_api_key}"
        
    try:
        response = session.get(url)
        response.raise_for_status()
        data = response.json()
        
        poster_path = data.get('poster_path')
        if poster_path:
            poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
            poster_response = session.get(poster_url)
            poster_response.raise_for_status()
            
            local_filename = f"{media_type}_{tmdb_id}.jpg"
            local_filepath = os.path.join('app', 'static', 'posters', local_filename)
            
            os.makedirs(os.path.dirname(local_filepath), exist_ok=True)

            with open(local_filepath, 'wb') as f:
                f.write(poster_response.content)
            
            if media_type == 'movie':
                item = Movie.query.filter_by(tmdb_id=media_id).first()
                if item:
                    item.overview = data.get('overview')
                    db.session.commit()

            return f"posters/{local_filename}"

    except requests.exceptions.RequestException as e:
        print(f"Error fetching TMDB assets for {media_type} {media_id}: {e}")

    return None

def update_service_tags(service_name, payload):
    settings = ServiceSettings.query.filter_by(service_name=service_name).first()
    if not settings:
        return {'error': f'{service_name} settings not found'}

    headers = {'X-Api-Key': settings.api_key}
    session = get_retry_session()
    
    tags_url = f"{settings.url}/api/v3/tag"
    
    if service_name == 'Radarr':
        id_key = 'movieIds'
        editor_url = f"{settings.url}/api/v3/movie/editor"
    elif service_name == 'Sonarr':
        id_key = 'seriesIds'
        editor_url = f"{settings.url}/api/v3/series/editor"
    else:
        return {'error': 'Invalid service name for tag update'}

    try:
        tags_response = session.get(tags_url, headers=headers)
        tags_response.raise_for_status()
        tags_data = tags_response.json()
        label_to_id_map = {tag['label'].lower(): tag['id'] for tag in tags_data}
    except requests.exceptions.RequestException as e:
        print(f"Error fetching tags for {service_name}: {e}")
        return {'error': f'Could not fetch tags for {service_name}'}

    # Process tags to add
    if payload.get('tagsToAdd'):
        labels_to_add = payload['tagsToAdd']
        ids_to_add = []
        for label in labels_to_add:
            if label.lower() not in label_to_id_map:
                try:
                    print(f"Tag '{label}' not found for {service_name}. Creating it.")
                    create_tag_response = session.post(tags_url, headers=headers, json={'label': label})
                    create_tag_response.raise_for_status()
                    new_tag = create_tag_response.json()
                    label_to_id_map[new_tag['label'].lower()] = new_tag['id']
                    ids_to_add.append(new_tag['id'])
                except requests.exceptions.RequestException as e:
                    print(f"Error creating tag '{label}' for {service_name}: {e}")
            else:
                ids_to_add.append(label_to_id_map[label.lower()])
        
        if ids_to_add:
            add_payload = {id_key: payload[id_key], "tags": ids_to_add, "applyTags": "add"}
            session.put(editor_url, headers=headers, json=add_payload)

    # Process tags to remove
    if payload.get('tagsToRemove'):
        labels_to_remove = payload['tagsToRemove']
        ids_to_remove = [label_to_id_map[label.lower()] for label in labels_to_remove if label.lower() in label_to_id_map]
        
        if ids_to_remove:
            remove_payload = {id_key: payload[id_key], "tags": ids_to_remove, "applyTags": "remove"}
            session.put(editor_url, headers=headers, json=remove_payload)

    return {'status': 'Tag update process completed'}

def vacuum_database():
    job = get_current_job()
    job.meta['progress'] = 0
    job.save_meta()

    # This is a blocking operation, so we'll simulate progress
    # In a real scenario, you might break this down if possible,
    # but for VACUUM, it's a single command.
    
    # Simulate work starting
    time.sleep(1) 
    job.meta['progress'] = 25
    job.save_meta()

    with current_app.app_context():
        db.session.execute(text('VACUUM'))
        db.session.commit()
    
    # Simulate more work
    time.sleep(1)
    job.meta['progress'] = 75
    job.save_meta()
    
    # Finalize
    time.sleep(1)
    job.meta['progress'] = 100
    job.save_meta()
    
    return {'status': 'Database vacuum completed'}
