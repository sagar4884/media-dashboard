from . import db
from datetime import datetime

class SystemLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    level = db.Column(db.String(20), nullable=False) # INFO, DEBUG, ERROR, CRITICAL
    category = db.Column(db.String(50), nullable=False, index=True) # Radarr, Sonarr, AI, System, etc.
    message = db.Column(db.Text, nullable=False)

class ServiceSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_name = db.Column(db.String(50), unique=True, nullable=False)
    url = db.Column(db.String(200), nullable=False)
    api_key = db.Column(db.String(100), nullable=False)
    grace_days = db.Column(db.Integer, default=30)
    retention_days = db.Column(db.Integer, default=365)
    tmdb_api_key = db.Column(db.String(100))
    seasonal_min_episodes = db.Column(db.Integer, default=1)
    overlay_template = db.Column(db.Text) # Deprecated
    overlay_movie_template = db.Column(db.Text)
    overlay_show_template = db.Column(db.Text)
    overlay_use_tmdb_for_shows = db.Column(db.Boolean, default=False)
    ai_rules = db.Column(db.Text)
    ai_rule_proposals = db.Column(db.Text) # Stores JSON proposals for rule updates

class AISettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), default='Gemini')
    api_key = db.Column(db.String(200))
    learning_model = db.Column(db.String(100), default='gemini-1.5-pro')
    scoring_model = db.Column(db.String(100), default='gemini-1.5-flash')
    batch_size_movies_learn = db.Column(db.Integer, default=20)
    batch_size_movies_score = db.Column(db.Integer, default=50)
    batch_size_shows_learn = db.Column(db.Integer, default=10)
    batch_size_shows_score = db.Column(db.Integer, default=20)
    verbose_logging = db.Column(db.Boolean, default=False)
    log_retention = db.Column(db.Integer, default=7)
    max_items_limit = db.Column(db.Integer, default=0)

class ScheduledTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    time = db.Column(db.String(5), nullable=False) # HH:MM format
    days = db.Column(db.String(50), nullable=False) # JSON list of days [0,1,2...] or "Mon,Tue..."
    tasks = db.Column(db.Text, nullable=False) # JSON list of task identifiers
    enabled = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.DateTime(timezone=True))

class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    radarr_id = db.Column(db.Integer, unique=True)
    tmdb_id = db.Column(db.Integer)
    title = db.Column(db.String(200))
    year = db.Column(db.Integer)
    size_gb = db.Column(db.Float)
    labels = db.Column(db.String(200))
    score = db.Column(db.String(50))
    ai_score = db.Column(db.Integer)
    marked_for_deletion_at = db.Column(db.DateTime(timezone=True))
    delete_at = db.Column(db.DateTime(timezone=True))
    overview = db.Column(db.Text)
    local_poster_path = db.Column(db.String(200))
    cast = db.Column(db.Text)

class Show(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sonarr_id = db.Column(db.Integer, unique=True)
    tvdb_id = db.Column(db.Integer)
    tmdb_id = db.Column(db.Integer)
    title = db.Column(db.String(200))
    year = db.Column(db.Integer)
    size_gb = db.Column(db.Float)
    labels = db.Column(db.String(200))
    score = db.Column(db.String(50))
    ai_score = db.Column(db.Integer)
    marked_for_deletion_at = db.Column(db.DateTime(timezone=True))
    delete_at = db.Column(db.DateTime(timezone=True))
    overview = db.Column(db.Text)
    local_poster_path = db.Column(db.String(200))
    cast = db.Column(db.Text)

class TautulliHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    row_id = db.Column(db.Integer, unique=True)
    title = db.Column(db.String(200))
    user = db.Column(db.String(100))
    date = db.Column(db.DateTime)
    state = db.Column(db.String(50))
    duration_mins = db.Column(db.Integer)
