import time
import json
import schedule
import logging
from datetime import datetime
from app import create_app, db
from app.models import ScheduledTask
from app.tasks import (
    sync_radarr_movies, 
    sync_sonarr_shows, 
    vacuum_database
)
from app.tasks.ai import learn_user_preferences, score_media_items

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/scheduler.log')
    ]
)
logger = logging.getLogger(__name__)

app = create_app()

TASK_MAPPING = {
    'radarr_quick_sync': lambda: app.queue.enqueue(sync_radarr_movies),
    'radarr_full_sync': lambda: app.queue.enqueue(sync_radarr_movies, full_sync=True),
    'radarr_analyze': lambda: app.queue.enqueue(learn_user_preferences, 'Radarr'),
    'radarr_continue_scoring': lambda: app.queue.enqueue(score_media_items, 'Radarr', resume_mode=True),
    'radarr_rescore': lambda: app.queue.enqueue(score_media_items, 'Radarr', resume_mode=False),
    
    'sonarr_quick_sync': lambda: app.queue.enqueue(sync_sonarr_shows),
    'sonarr_full_sync': lambda: app.queue.enqueue(sync_sonarr_shows, full_sync=True),
    'sonarr_analyze': lambda: app.queue.enqueue(learn_user_preferences, 'Sonarr'),
    'sonarr_continue_scoring': lambda: app.queue.enqueue(score_media_items, 'Sonarr', resume_mode=True),
    'sonarr_rescore': lambda: app.queue.enqueue(score_media_items, 'Sonarr', resume_mode=False),
    
    'system_vacuum': lambda: app.queue.enqueue(vacuum_database)
}

def run_scheduled_tasks():
    """Checks for pending tasks and queues them."""
    with app.app_context():
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_day = now.weekday() # 0=Mon, 6=Sun
        
        # Find tasks that match current time and day
        # We need to be careful not to run the same task multiple times in the same minute
        # So we check if last_run was today and within the last minute? 
        # Or just rely on the minute check and update last_run.
        
        tasks = ScheduledTask.query.filter_by(enabled=True, time=current_time).all()
        
        for task in tasks:
            try:
                days = json.loads(task.days)
                if current_day in days:
                    # Check if already run today (to prevent duplicate runs if the loop is fast)
                    # Actually, if we sleep 60s, we might miss it or hit it twice.
                    # Better to check if last_run was < 1 minute ago.
                    if task.last_run and (now - task.last_run).total_seconds() < 60:
                        continue
                        
                    logger.info(f"Triggering Schedule: {task.name}")
                    
                    # Queue the tasks
                    task_ids = json.loads(task.tasks)
                    for task_id in task_ids:
                        if task_id in TASK_MAPPING:
                            logger.info(f"  - Queuing task: {task_id}")
                            TASK_MAPPING[task_id]()
                        else:
                            logger.warning(f"  - Unknown task ID: {task_id}")
                            
                    task.last_run = now
                    db.session.commit()
            except Exception as e:
                logger.error(f"Error processing schedule {task.name}: {e}")

if __name__ == "__main__":
    logger.info("Scheduler started")
    while True:
        try:
            run_scheduled_tasks()
        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")
        
        # Sleep for 60 seconds to check every minute
        # Align to the start of the next minute for better precision
        time.sleep(60 - datetime.now().second)
