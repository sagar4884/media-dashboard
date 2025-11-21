from .. import db
from ..models import Movie, Show, ServiceSettings, AISettings
from ..ai_service import AIService
from rq import get_current_job
from sqlalchemy import func
import time
import logging
import json
import uuid

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
    
    # Fetch samples using random ordering
    # Include 'Tautulli Keep' as a positive signal along with 'Keep'
    kept_items = ModelClass.query.filter(
        ModelClass.score.in_(['Keep', 'Tautulli Keep'])
    ).order_by(func.random()).limit(batch_size).all()
    
    deleted_items = ModelClass.query.filter_by(score='Delete').order_by(func.random()).limit(batch_size).all()
    
    print(f"Found {len(kept_items)} kept/tautulli-kept items and {len(deleted_items)} deleted items")

    if not kept_items and not deleted_items:
        print("No history found to learn from.")
        return {'error': 'No history found to learn from.'}

    # Prepare data for AI
    def serialize(item):
        return {
            'title': item.title,
            'year': item.year,
            'overview': item.overview,
            'labels': item.labels,
            'status': item.score # Include status so AI knows if it was explicit Keep or Tautulli Keep
        }
        
    kept_data = [serialize(item) for item in kept_items]
    deleted_data = [serialize(item) for item in deleted_items]
    
    current_rules = service_settings.ai_rules or ""
    
    try:
        print("Calling AI service to generate rule proposals...")
        # Now returns a JSON string representing the proposals
        proposals_json = ai_service.generate_rules(kept_data, deleted_data, current_rules)
        print(f"Generated proposals: {proposals_json}")
        
        # Validate that it's valid JSON and add IDs
        try:
            proposals = json.loads(proposals_json)
            # Ensure structure
            if 'refinements' not in proposals: proposals['refinements'] = []
            if 'new_rules' not in proposals: proposals['new_rules'] = []
            
            # Add IDs
            for item in proposals['refinements']:
                item['id'] = str(uuid.uuid4())
            for item in proposals['new_rules']:
                item['id'] = str(uuid.uuid4())
                
            proposals_json = json.dumps(proposals)
            
        except json.JSONDecodeError:
             # Fallback if AI returns plain text (should be handled in ai_service but double check)
             print("AI returned invalid JSON, attempting to wrap...")
             proposals_json = json.dumps({
                 "refinements": [],
                 "new_rules": [{"id": str(uuid.uuid4()), "rule": line, "reason": "Generated from plain text output"} for line in proposals_json.split('\n') if line.strip()]
             })

        service_settings.ai_rule_proposals = proposals_json
        db.session.commit()
        print("Rule proposals saved to database.")
        return {'status': 'success', 'message': 'Rule proposals generated. Please review them in the dashboard.'}
        
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
    
    excluded_scores = ['Keep', 'Delete', 'Tautulli Keep', 'Seasonal', 'Archived']
    
    # Get total count of items to score
    total_items = ModelClass.query.filter(
        (ModelClass.score.notin_(excluded_scores)) | (ModelClass.score == None)
    ).count()
    
    print(f"Found {total_items} total items to score")

    if total_items == 0:
        return {'status': 'success', 'message': 'No unscored items found'}

    processed_count = 0
    start_time = time.time()
    
    while processed_count < total_items:
        # Fetch next batch
        # We can't use offset reliably if we are updating scores and the query filters by score
        # But here we filter by score NOT IN excluded. If we update the score to a number (e.g. 85), 
        # it is still NOT IN excluded (Keep, Delete, etc), so it would be fetched again!
        # Wait, the query is: score NOT IN ['Keep', 'Delete'...] OR score is None.
        # If we update score to '85', it is NOT 'Keep'/'Delete', so it matches the filter.
        # So we need to be careful not to re-process the same items in this run.
        # A simple way is to fetch items where ai_score is NULL or we need a way to mark them as processed in this run.
        # OR, we can just fetch all IDs first, then process in chunks.
        
        # Let's fetch all IDs first to be safe and stable
        if processed_count == 0:
            all_items = ModelClass.query.filter(
                (ModelClass.score.notin_(excluded_scores)) | (ModelClass.score == None)
            ).all()
            # We'll process this list in chunks
            
        # Calculate current batch slice
        batch_items = all_items[processed_count : processed_count + batch_size]
        if not batch_items:
            break
            
        print(f"Processing batch of {len(batch_items)} items ({processed_count}/{total_items})")
        
        # Prepare data
        items_map = {}
        items_data = []
        
        for item in batch_items:
            key = str(item.radarr_id) if service_name == 'Radarr' else str(item.sonarr_id)
            items_map[key] = item
            items_data.append({
                'id': item.radarr_id if service_name == 'Radarr' else item.sonarr_id,
                'title': item.title,
                'year': item.year,
                'overview': item.overview,
                'labels': item.labels
            })
            
        try:
            batch_start = time.time()
            print("Calling AI service to score items...")
            scores = ai_service.score_items(items_data, service_settings.ai_rules)
            
            count = 0
            for item_id, score in scores.items():
                item_id_str = str(item_id)
                if item_id_str in items_map:
                    try:
                        items_map[item_id_str].ai_score = int(score)
                        count += 1
                    except (ValueError, TypeError):
                        print(f"Invalid score value for item {item_id_str}: {score}")
            
            db.session.commit()
            processed_count += len(batch_items)
            
            # Update Progress
            progress = int((processed_count / total_items) * 100)
            job.meta['progress'] = progress
            
            # Calculate ETA
            batch_duration = time.time() - batch_start
            avg_time_per_item = batch_duration / len(batch_items)
            remaining_items = total_items - processed_count
            eta_seconds = int(remaining_items * avg_time_per_item)
            
            job.meta['status'] = f"Scoring... {progress}% (ETA: {eta_seconds}s)"
            job.save_meta()
            
            print(f"Batch complete. Scored {count}/{len(batch_items)}. Progress: {progress}%")
            
            # Sleep briefly to be nice to the API if needed, though ai_service handles retries
            time.sleep(1)
            
        except Exception as e:
            print(f"Error scoring batch: {str(e)}")
            # Continue to next batch instead of failing completely?
            # If AI service fails completely (e.g. quota), we might want to stop.
            # But ai_service retries 5 times. If it raises exception here, it's serious.
            return {'error': f"Scoring failed at {processed_count}/{total_items}: {str(e)}"}

    total_duration = int(time.time() - start_time)
    return {'status': 'success', 'message': f'Scored {total_items} items in {total_duration}s'}
