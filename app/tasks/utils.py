import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
from flask import current_app
from .. import db
from ..models import ServiceSettings, Movie, Show, AISettings
from ..logging_utils import log_message

def get_retry_session(category='System'):
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

    def response_hook(response, *args, **kwargs):
        try:
            if current_app:
                # We need to ensure we are in a context where we can query DB
                # If this hook is called, we are likely in a request or task context
                settings = AISettings.query.first()
                if settings and settings.verbose_logging:
                    req = response.request
                    log_message('DEBUG', f"[OUTGOING] {req.method} {req.url}", category)
                    # Log body if present and not too large? For now just URL.
                    
                    log_message('DEBUG', f"[INCOMING] Status: {response.status_code} | URL: {response.url}", category)
        except Exception:
            pass

    session.hooks['response'].append(response_hook)
    return session

def fetch_tmdb_assets(media_id, media_type='movie'):
    settings = ServiceSettings.query.filter_by(service_name='Radarr').first()
    if not settings or not settings.tmdb_api_key:
        return None, None
        
    tmdb_api_key = settings.tmdb_api_key
    session = get_retry_session(category='System')
    
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
            return None, None

    if not tmdb_id:
        print(f"No TMDB ID found for {media_type} {media_id}")
        return None, None

    url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}?api_key={tmdb_api_key}&append_to_response=credits"
        
    try:
        response = session.get(url)
        response.raise_for_status()
        data = response.json()
        
        # Extract cast
        cast_list = []
        if 'credits' in data and 'cast' in data['credits']:
            # Get top 5 cast members
            cast_list = [actor['name'] for actor in data['credits']['cast'][:5]]
        
        cast_str = ", ".join(cast_list)

        poster_path = data.get('poster_path')
        if poster_path:
            poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
            poster_response = session.get(poster_url)
            poster_response.raise_for_status()
            
            local_filename = f"{media_type}_{tmdb_id}.jpg"
            local_filepath = os.path.join('/appdata', 'posters', local_filename)
            
            os.makedirs(os.path.dirname(local_filepath), exist_ok=True)

            with open(local_filepath, 'wb') as f:
                f.write(poster_response.content)
            
            if media_type == 'movie':
                item = Movie.query.filter_by(tmdb_id=media_id).first()
                if item:
                    item.overview = data.get('overview')
                    item.cast = cast_str
                    db.session.commit()
            elif media_type == 'tv':
                item = Show.query.filter_by(tvdb_id=media_id).first()
                if item:
                    item.overview = data.get('overview')
                    item.cast = cast_str
                    db.session.commit()

            return f"posters/{local_filename}", tmdb_id

    except requests.exceptions.RequestException as e:
        print(f"Error fetching TMDB assets for {media_type} {media_id}: {e}")

    return None, None

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
