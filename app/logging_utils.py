import logging
import traceback
from datetime import datetime
from flask import current_app
from . import db
from .models import SystemLog, AISettings

class SQLAlchemyHandler(logging.Handler):
    def emit(self, record):
        try:
            # We need an app context to access the DB
            if not current_app:
                return

            # Determine category
            category = getattr(record, 'category', 'System')
            
            # Create log entry
            log_entry = SystemLog(
                timestamp=datetime.fromtimestamp(record.created),
                level=record.levelname,
                category=category,
                message=self.format(record)
            )
            
            # We use a separate context to ensure logs are committed even if the main transaction fails
            # However, creating a new app context inside an existing one might share the session if not careful.
            # The safest way in Flask-SQLAlchemy is to just add and commit. 
            # If the session is broken, this will fail, which is acceptable for now.
            db.session.add(log_entry)
            db.session.commit()
                
        except Exception:
            # If DB logging fails, fall back to stderr (handled by StreamHandler usually)
            self.handleError(record)

def register_logger(app):
    """Registers the SQLAlchemy logger with the Flask app."""
    handler = SQLAlchemyHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.DEBUG) # We capture everything, filter at display or emit time if needed

def log_message(level, message, category='System'):
    """Helper to log messages with a category."""
    logger = logging.getLogger('media_dashboard') # Use the app's logger name
    # We pass 'category' in the extra dict, but standard Logger doesn't support arbitrary kwargs in .info()
    # So we use the 'extra' parameter.
    getattr(logger, level.lower())(message, extra={'category': category})

def task_wrapper(category):
    """Decorator to wrap background tasks with logging and exception handling."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            log_message('INFO', f"Task Started: {func.__name__}", category)
            try:
                result = func(*args, **kwargs)
                log_message('INFO', f"Task Finished: {func.__name__}", category)
                return result
            except Exception as e:
                log_message('CRITICAL', f"Task Failed: {func.__name__}\nError: {str(e)}\nTraceback:\n{traceback.format_exc()}", category)
                raise e
        return wrapper
    return decorator
