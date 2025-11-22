import os
import json
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from rq import Queue
from rq.registry import StartedJobRegistry
import redis
from datetime import timedelta

db = SQLAlchemy()

# Enforce foreign key constraints for SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()

def create_app():
    app = Flask(__name__)

    # Logging Configuration
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    from logging.handlers import RotatingFileHandler
    import logging
    
    file_handler = RotatingFileHandler('logs/media_dashboard.log', maxBytes=10*1024*1024, backupCount=10)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    file_handler.setLevel(logging.DEBUG) # Allow DEBUG logs to be written if a logger permits it
    
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO) # Default application log level
    app.logger.info('Media Dashboard startup')

    # Register Database Logger
    from .logging_utils import register_logger
    register_logger(app)

    # Configuration
    app.config.from_mapping(
        SECRET_KEY='a_very_secret_key',  # Change this!
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'sqlite:////appdata/database/app.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False
    )

    db.init_app(app)

    # Redis and RQ setup
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    redis_conn = redis.from_url(redis_url)
    app.queue = Queue(connection=redis_conn)

    # Make timedelta available in templates
    app.jinja_env.globals['timedelta'] = timedelta
    app.jinja_env.filters['from_json'] = json.loads

    @app.context_processor
    def inject_active_job_id():
        registry = StartedJobRegistry(queue=app.queue)
        running_job_ids = registry.get_job_ids()
        active_job_id = running_job_ids[0] if running_job_ids else None
        return dict(active_job_id=active_job_id)

    with app.app_context():
        # Register Blueprints
        from .blueprints.main import bp as main_bp
        from .blueprints.radarr import bp as radarr_bp
        from .blueprints.sonarr import bp as sonarr_bp
        from .blueprints.tautulli import bp as tautulli_bp
        from .blueprints.deletion import bp as deletion_bp
        from .blueprints.settings import bp as settings_bp
        from .blueprints.api import bp as api_bp
        from .blueprints.ai import bp as ai_bp
        from .blueprints.logs import bp as logs_bp

        app.register_blueprint(main_bp)
        app.register_blueprint(radarr_bp)
        app.register_blueprint(sonarr_bp)
        app.register_blueprint(tautulli_bp)
        app.register_blueprint(deletion_bp)
        app.register_blueprint(settings_bp)
        app.register_blueprint(api_bp)
        app.register_blueprint(ai_bp)
        app.register_blueprint(logs_bp)

        run_migrations(app)

    return app

def run_migrations(app):
    with app.app_context():
        # Migration for v0.8: Add seasonal_min_episodes
        try:
            with db.engine.connect() as conn:
                # Check if column exists to avoid error log spam (optional, but cleaner)
                # SQLite doesn't support IF NOT EXISTS for columns in older versions, 
                # so we just try and catch.
                conn.execute(text("ALTER TABLE service_settings ADD COLUMN seasonal_min_episodes INTEGER DEFAULT 1"))
                conn.commit()
                print("Migrated database: Added seasonal_min_episodes column.")
        except Exception as e:
            pass
        
        # Migration for SystemLog
        try:
            with db.engine.connect() as conn:
                conn.execute(text("CREATE TABLE IF NOT EXISTS system_log (id INTEGER PRIMARY KEY, timestamp DATETIME, level VARCHAR(20), category VARCHAR(50), message TEXT)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_system_log_timestamp ON system_log (timestamp)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_system_log_category ON system_log (category)"))
                conn.commit()
                print("Migrated database: Created system_log table.")
        except Exception as e:
            print(f"Migration error: {e}")
            # Column likely exists or table doesn't exist yet (fresh install handled by entrypoint)
            pass

        # Migration for v0.9: Add cast column to Movie and Show
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE movie ADD COLUMN cast TEXT"))
                conn.commit()
                print("Migrated database: Added cast column to Movie.")
        except Exception as e:
            pass

        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE show ADD COLUMN cast TEXT"))
                conn.commit()
                print("Migrated database: Added cast column to Show.")
        except Exception as e:
            pass

        # Migration for v0.8: Add overlay_template
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE service_settings ADD COLUMN overlay_template TEXT"))
                conn.commit()
                print("Migrated database: Added overlay_template column.")
        except Exception as e:
            pass

        # Migration for v0.8: Add overlay_movie_template
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE service_settings ADD COLUMN overlay_movie_template TEXT"))
                conn.commit()
                print("Migrated database: Added overlay_movie_template column.")
        except Exception as e:
            pass

        # Migration for v0.8: Add overlay_show_template
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE service_settings ADD COLUMN overlay_show_template TEXT"))
                conn.commit()
                print("Migrated database: Added overlay_show_template column.")
        except Exception as e:
            pass

        # Migration for v0.8: Add overlay_use_tmdb_for_shows
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE service_settings ADD COLUMN overlay_use_tmdb_for_shows BOOLEAN DEFAULT 0"))
                conn.commit()
                print("Migrated database: Added overlay_use_tmdb_for_shows column.")
        except Exception as e:
            pass

        # Migration for v0.8: Add tmdb_id to Show
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE show ADD COLUMN tmdb_id INTEGER"))
                conn.commit()
                print("Migrated database: Added tmdb_id column to Show.")
        except Exception as e:
            pass

        # Migration for AI Features
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE service_settings ADD COLUMN ai_rules TEXT"))
                conn.commit()
                print("Migrated database: Added ai_rules column.")
        except Exception as e:
            pass

        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE movie ADD COLUMN ai_score INTEGER"))
                conn.commit()
                print("Migrated database: Added ai_score column to Movie.")
        except Exception as e:
            pass

        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE show ADD COLUMN ai_score INTEGER"))
                conn.commit()
                print("Migrated database: Added ai_score column to Show.")
        except Exception as e:
            pass
        
        # Migration for v0.909: Add ai_rule_proposals
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE service_settings ADD COLUMN ai_rule_proposals TEXT"))
                conn.commit()
                print("Migrated database: Added ai_rule_proposals column.")
        except Exception as e:
            pass

        # Migration for v0.920: Add verbose_logging, log_retention, max_items_limit to AISettings
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE ai_settings ADD COLUMN verbose_logging BOOLEAN DEFAULT 0"))
                conn.commit()
                print("Migrated database: Added verbose_logging column.")
        except Exception:
            pass
        
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE ai_settings ADD COLUMN log_retention INTEGER DEFAULT 7"))
                conn.commit()
                print("Migrated database: Added log_retention column.")
        except Exception:
            pass

        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE ai_settings ADD COLUMN max_items_limit INTEGER DEFAULT 0"))
                conn.commit()
                print("Migrated database: Added max_items_limit column.")
        except Exception:
            pass

        # Create AISettings table if it doesn't exist
        try:
            db.create_all()
        except Exception as e:
            print(f"Error creating tables: {e}")

    return app
