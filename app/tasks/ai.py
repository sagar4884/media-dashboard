from .. import db
from ..models import Movie, Show, ServiceSettings, AISettings
from ..ai_service import AIService
from rq import get_current_job
import time
import logging

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def learn_user_preferences(service_name):
    print(f"Starting learning task for {service_name}")
    job = get_current_job()
    job.meta['progress'] = 0
    job.save_meta()
    
    ai_settings = AISettings.query.first()
    if not ai_settings or not ai_settings.api_key:
        print("Error: AI not configured")
        return {'error': 'AI not configured'}
        
    service_settings = ServiceSettings.query.filter_by(service_name=service_name).first()
    if not service_settings:
        print(f"Error: {service_name} settings not found")
        return {'error': f'{service_name} settings not found'}

    ai_service = AIService(ai_settings)
    
    # Determine batch size and model class
    if service_name == 'Radarr':
        ModelClass = Movie
        batch_size = ai_settings.batch_size_movies_learn
    else:
        ModelClass = Show
        batch_size = ai_settings.batch_size_shows_learn

    print(f"Fetching samples with batch size {batch_size}")
    # Fetch samples
    kept_items = ModelClass.query.filter_by(score='Keep').order_by(ModelClass.id.desc()).limit(batch_size).all()
    deleted_items = ModelClass.query.filter_by(score='Delete').order_by(ModelClass.id.desc()).limit(batch_size).all()
    
    print(f"Found {len(kept_items)} kept items and {len(deleted_items)} deleted items")

    if not kept_items and not deleted_items:
        print("No history found to learn from.")
        return {'error': 'No history found to learn from.'}

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
        print("Calling AI service to generate rules...")
        new_rules = ai_service.generate_rules(kept_data, deleted_data, current_rules)
        print(f"Generated rules: {new_rules}")
        
        service_settings.ai_rules = new_rules
        db.session.commit()
        print("Rules saved to database.")
        return {'status': 'success', 'message': 'Rules updated'}
        
    except Exception as e:
        print(f"Error generating rules: {str(e)}")
        return {'error': str(e)}

def score_media_items(service_name):
    print(f"Starting scoring task for {service_name}")
    job = get_current_job()
    job.meta['progress'] = 0
    job.save_meta()
    
    ai_settings = AISettings.query.first()
    if not ai_settings or not ai_settings.api_key:
        print("Error: AI not configured")
        return {'error': 'AI not configured'}
        
    service_settings = ServiceSettings.query.filter_by(service_name=service_name).first()
    if not service_settings or not service_settings.ai_rules:
        print(f"Error: {service_name} rules not found. Please run Learn first.")
        return {'error': f'{service_name} rules not found. Please run Learn first.'}

    ai_service = AIService(ai_settings)
    
    if service_name == 'Radarr':
        ModelClass = Movie
        batch_size = ai_settings.batch_size_movies_score
    else:
        ModelClass = Show
        batch_size = ai_settings.batch_size_shows_score

    print(f"Fetching unscored items with batch size {batch_size}")
    # Fetch items that are not in a final state (Keep, Delete, Tautulli Keep, Seasonal)
    # This includes 'Not Scored' and None, regardless of whether they have an ai_score already.
    # We want to re-score them as rules might have changed.
    
    excluded_scores = ['Keep', 'Delete', 'Tautulli Keep', 'Seasonal', 'Archived']
    
    unscored_items = ModelClass.query.filter(
        (ModelClass.score.notin_(excluded_scores)) | (ModelClass.score == None)
    ).limit(batch_size).all()
    
    print(f"Found {len(unscored_items)} items to score")

    if not unscored_items:
        return {'status': 'success', 'message': 'No unscored items found'}

    # Prepare data
    # Map using the correct ID type (int vs str) to ensure matching works
    items_map = {}
    for item in unscored_items:
        key = str(item.radarr_id) if service_name == 'Radarr' else str(item.sonarr_id)
        items_map[key] = item

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
        print("Calling AI service to score items...")
        scores = ai_service.score_items(items_data, service_settings.ai_rules)
        print(f"Received scores: {scores}")
        
        count = 0
        for item_id, score in scores.items():
            # Ensure item_id is string for lookup
            item_id_str = str(item_id)
            
            if item_id_str in items_map:
                try:
                    items_map[item_id_str].ai_score = int(score)
                    count += 1
                except (ValueError, TypeError):
                    print(f"Invalid score value for item {item_id_str}: {score}")
            else:
                print(f"Warning: Received score for unknown item ID: {item_id_str}")
        
        db.session.commit()
        print(f"Successfully scored {count} items.")
        return {'status': 'success', 'message': f'Scored {count} items'}
        
    except Exception as e:
        print(f"Error scoring items: {str(e)}")
        return {'error': str(e)}
