import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import event
from sqlalchemy.engine import Engine
from rq import Queue
import redis
from datetime import timedelta

db = SQLAlchemy()
migrate = Migrate()

# Enforce foreign key constraints for SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()

def create_app():
    app = Flask(__name__, instance_relative_config=True)

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Configuration
    app.config.from_mapping(
        SECRET_KEY='a_very_secret_key',  # Change this!
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(app.instance_path, "app.db")}'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False
    )

    db.init_app(app)
    migrate.init_app(app, db)

    # Redis and RQ setup
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    redis_conn = redis.from_url(redis_url)
    app.queue = Queue(connection=redis_conn)

    # Make timedelta available in templates
    app.jinja_env.globals['timedelta'] = timedelta

    with app.app_context():
        from . import routes

    return app
