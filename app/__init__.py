import os
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

    @app.context_processor
    def inject_active_job_id():
        registry = StartedJobRegistry(queue=app.queue)
        running_job_ids = registry.get_job_ids()
        active_job_id = running_job_ids[0] if running_job_ids else None
        return dict(active_job_id=active_job_id)

    with app.app_context():
        from . import routes
        
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
            # Column likely exists or table doesn't exist yet (fresh install handled by entrypoint)
            pass

    return app
