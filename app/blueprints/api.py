from flask import Blueprint, request, jsonify, redirect, url_for, flash
from .. import db
from ..models import Movie, Show, ServiceSettings
from ..tasks import update_service_tags, get_retry_session
from datetime import datetime, timedelta
import requests

bp = Blueprint('api', __name__)

@bp.route('/media/action/<media_type>/<int:media_id>/<action>')
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
        return redirect(url_for('radarr.radarr_page', view=request.args.get('view', 'table')))
    else:
        return redirect(url_for('sonarr.sonarr_page', view=request.args.get('view', 'table')))

@bp.route('/media/bulk_action', methods=['POST'])
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

@bp.route('/delete/<media_type>/<int:media_id>')
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
                return redirect(url_for('deletion.deletion_page'))
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
                return redirect(url_for('deletion.deletion_page'))
        db.session.delete(item)
        flash(f'Deleted show: {item.title}', 'success')

    db.session.commit()
    return redirect(url_for('deletion.deletion_page'))
