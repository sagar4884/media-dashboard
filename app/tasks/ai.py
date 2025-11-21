from .. import db
from ..models import Movie, Show, ServiceSettings, AISettings
from ..ai_service import AIService
from rq import get_current_job
import time

def learn_user_preferences(service_name):
    job = get_current_job()
    job.meta['progress'] = 0
    job.save_meta()
    
    ai_settings = AISettings.query.first()
    if not ai_settings or not ai_settings.api_key:
        return {'error': 'AI not configured'}
        
    service_settings = ServiceSettings.query.filter_by(service_name=service_name).first()
    if not service_settings:
        return {'error': f'{service_name} settings not found'}

    ai_service = AIService(ai_settings)
    
    # Determine batch size and model class
    if service_name == 'Radarr':
        ModelClass = Movie
        batch_size = ai_settings.batch_size_movies_learn
    else:
        ModelClass = Show
        batch_size = ai_settings.batch_size_shows_learn

    # Fetch samples
    kept_items = ModelClass.query.filter_by(score='Keep').order_by(ModelClass.id.desc()).limit(batch_size).all()
    deleted_items = ModelClass.query.filter_by(score='Delete').order_by(ModelClass.id.desc()).limit(batch_size).all()
    
    # Prepare data for AI
    def serialize(item):
        return {
            'title': item.title,
            'year': item.year,
            'overview': item.overview,
            'labels': item.labels
        }
        
    kept_data = [serialize(item) for item in kept_items]
    deleted_data = [serialize(item) for item in deleted_items]
    
    current_rules = service_settings.ai_rules or ""
    
    try:
        new_rules = ai_service.generate_rules(kept_data, deleted_data, current_rules)
        
        # Append new rules (or replace? User said "learn on each run", implying accumulation or refinement)
        # The prompt asks for a "concise list". Let's append with a separator if rules exist, 
        # or maybe just replace? The prompt says "Current Rules (if any)" are passed in.
        # So the AI sees the old rules. It should output the *refined* set of rules.
        # So we should probably replace the text area with the new output.
        
        service_settings.ai_rules = new_rules
        db.session.commit()
        return {'status': 'success', 'message': 'Rules updated'}
        
    except Exception as e:
        return {'error': str(e)}

def score_media_items(service_name):
    job = get_current_job()
    job.meta['progress'] = 0
    job.save_meta()
    
    ai_settings = AISettings.query.first()
    if not ai_settings or not ai_settings.api_key:
        return {'error': 'AI not configured'}
        
    service_settings = ServiceSettings.query.filter_by(service_name=service_name).first()
    if not service_settings or not service_settings.ai_rules:
        return {'error': f'{service_name} rules not found. Please run Learn first.'}

    ai_service = AIService(ai_settings)
    
    if service_name == 'Radarr':
        ModelClass = Movie
        batch_size = ai_settings.batch_size_movies_score
    else:
        ModelClass = Show
        batch_size = ai_settings.batch_size_shows_score

    # Fetch unscored items
    # We only score items that are "Not Scored" OR have no ai_score yet?
    # User said "score Unscored Items".
    unscored_items = ModelClass.query.filter(
        (ModelClass.score == 'Not Scored') | (ModelClass.score == None)
    ).limit(batch_size).all()
    
    if not unscored_items:
        return {'status': 'success', 'message': 'No unscored items found'}

    # Prepare data
    items_map = {str(item.radarr_id if service_name == 'Radarr' else item.sonarr_id): item for item in unscored_items}
    items_data = []
    for item in unscored_items:
        items_data.append({
            'id': item.radarr_id if service_name == 'Radarr' else item.sonarr_id,
            'title': item.title,
            'year': item.year,
            'overview': item.overview,
            'labels': item.labels
        })
        
    try:
        scores = ai_service.score_items(items_data, service_settings.ai_rules)
        
        count = 0
        for item_id, score in scores.items():
            item_id_str = str(item_id)
            if item_id_str in items_map:
                items_map[item_id_str].ai_score = int(score)
                count += 1
        
        db.session.commit()
        return {'status': 'success', 'message': f'Scored {count} items'}
        
    except Exception as e:
        return {'error': str(e)}
