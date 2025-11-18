import time
from rq import get_current_job
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

    # Fetch all tags to create a mapping from ID to Label
    tags_response = session.get(f"{settings.url}/api/v3/tag", headers=headers)
    tags_response.raise_for_status()
    tag_map = {tag['id']: tag['label'] for tag in tags_response.json()}

    response = session.get(f"{settings.url}/api/v3/movie", headers=headers)
    response.raise_for_status()
    movies_data = response.json()

    total_movies = len(movies_data)
    for i, movie_data in enumerate(movies_data):
        movie = Movie.query.filter_by(radarr_id=movie_data['id']).first()
        if not movie:
            movie = Movie(radarr_id=movie_data['id'], score='Not Scored')
        
        movie.tmdb_id = movie_data.get('tmdbId')
        movie.title = movie_data.get('title')
        movie.year = movie_data.get('year')
        movie.size_gb = movie_data.get('sizeOnDisk', 0) / (1024**3)
        movie.overview = movie_data.get('overview')
        tag_ids = movie_data.get('tags', [])
        movie.labels = ",".join([tag_map.get(tag_id) for tag_id in tag_ids if tag_id in tag_map])

        # Set score based on tags
        if 'ai-delete' in movie.labels:
            movie.score = 'Delete'
        elif 'ai-keep' in movie.labels:
            movie.score = 'Keep'
        else:
            movie.score = 'Not Scored'

        if (full_sync or not movie.local_poster_path) and movie.tmdb_id:
            poster_path = fetch_tmdb_assets(movie.tmdb_id, 'movie')
            movie.local_poster_path = poster_path

        db.session.add(movie)
        db.session.commit()

        # ETA calculation
        elapsed_time = time.time() - start_time
        progress = (i + 1) / total_movies
        if progress > 0:
            eta_seconds = (elapsed_time / progress) * (1 - progress)
            job.meta['eta'] = time.strftime("%M:%S", time.gmtime(eta_seconds))
        
        job.meta['progress'] = int(progress * 100)
        job.save_meta()

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

    total_shows = len(shows_data)
    for i, show_data in enumerate(shows_data):
        show = Show.query.filter_by(sonarr_id=show_data['id']).first()
        if not show:
            show = Show(sonarr_id=show_data['id'], score='Not Scored')

        show.tvdb_id = show_data.get('tvdbId')
        show.title = show_data.get('title')
        show.year = show_data.get('year')
        show.size_gb = show_data.get('statistics', {}).get('sizeOnDisk', 0) / (1024**3)
        show.overview = show_data.get('overview')
        tag_ids = show_data.get('tags', [])
        show.labels = ",".join([tag_map.get(tag_id) for tag_id in tag_ids if tag_id in tag_map])

        # Set score based on tags
        if 'ai-delete' in show.labels:
            show.score = 'Delete'
        elif 'ai-keep' in show.labels:
            show.score = 'Keep'
        elif 'ai-rolling-keep' in show.labels:
            show.score = 'Seasonal'
        else:
            show.score = 'Not Scored'

        if (full_sync or not show.local_poster_path) and show.tvdb_id:
            poster_path = fetch_tmdb_assets(show.tvdb_id, 'tv')
            show.local_poster_path = poster_path
        
        db.session.add(show)
        db.session.commit()

        # ETA calculation
        elapsed_time = time.time() - start_time
        progress = (i + 1) / total_shows
        if progress > 0:
            eta_seconds = (elapsed_time / progress) * (1 - progress)
            job.meta['eta'] = time.strftime("%M:%S", time.gmtime(eta_seconds))

        job.meta['progress'] = int(progress * 100)
        job.save_meta()

    return {'status': 'Completed', 'shows_synced': total_shows}

def sync_tautulli_history(full_sync=False):
    job = get_current_job()
    job.meta['progress'] = 0
    job.save_meta()
    start_time = time.time()

    settings = ServiceSettings.query.filter_by(service_name='Tautulli').first()
    if not settings:
        return {'error': 'Tautulli settings not found'}
    
    headers = {'X-Api-Key': settings.api_key}
    session = get_retry_session()
    params = {
        'cmd': 'get_history',
        'length': 1000, # Adjust as needed
        'after': (datetime.now() - timedelta(days=settings.retention_days)).strftime('%Y-%m-%d')
    }
    response = session.get(f"{settings.url}/api/v2", headers=headers, params=params)
    response.raise_for_status()
    history_data = response.json()['response']['data']['data']

    rescued_movies = []
    rescued_shows = []
    total_items = len(history_data)

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
    
    if service_name == 'Radarr':
        url = f"{settings.url}/api/v3/movie/editor"
    elif service_name == 'Sonarr':
        url = f"{settings.url}/api/v3/series/editor"
    else:
        return {'error': 'Invalid service name for tag update'}
        
    response = session.put(url, headers=headers, json=payload)
    response.raise_for_status()

    return response.json()
