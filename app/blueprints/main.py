from flask import Blueprint, render_template, current_app, jsonify
from sqlalchemy import func
from .. import db
from ..models import Movie, Show, ServiceSettings
from ..tasks import get_retry_session
import time

bp = Blueprint('main', __name__)

@bp.route('/')
def dashboard():
    # Radarr stats
    radarr_total = Movie.query.count()
    radarr_unscored = Movie.query.filter(Movie.score.in_(['Not Scored', None])).count()
    radarr_keep = Movie.query.filter_by(score='Keep').count()
    radarr_delete = Movie.query.filter_by(score='Delete').count()
    radarr_archived = Movie.query.filter_by(score='Archived').count()
    radarr_size = db.session.query(func.sum(Movie.size_gb)).scalar() or 0

    # Sonarr stats
    sonarr_total = Show.query.count()
    sonarr_unscored = Show.query.filter(Show.score.in_(['Not Scored', None])).count()
    sonarr_keep = Show.query.filter_by(score='Keep').count()
    sonarr_delete = Show.query.filter_by(score='Delete').count()
    sonarr_seasonal = Show.query.filter_by(score='Seasonal').count()
    sonarr_archived = Show.query.filter_by(score='Archived').count()
    sonarr_size = db.session.query(func.sum(Show.size_gb)).scalar() or 0

    stats = {
        'radarr': {
            'total': radarr_total,
            'unscored': radarr_unscored,
            'keep': radarr_keep,
            'delete': radarr_delete,
            'archived': radarr_archived,
            'size': round(radarr_size, 2)
        },
        'sonarr': {
            'total': sonarr_total,
            'unscored': sonarr_unscored,
            'keep': sonarr_keep,
            'delete': sonarr_delete,
            'seasonal': sonarr_seasonal,
            'archived': sonarr_archived,
            'size': round(sonarr_size, 2)
        }
    }
    return render_template('dashboard.html', stats=stats)

@bp.route('/health/<service>')
def health_check(service):
    service_name = service.capitalize()
    session = get_retry_session(category=service_name)
    settings = ServiceSettings.query.filter_by(service_name=service_name).first()
    
    if not settings:
        return jsonify({'status': 'offline', 'latency': 0, 'message': 'Not Configured'})

    start_time = time.time()
    try:
        if service == 'radarr' or service == 'sonarr':
            headers = {'X-Api-Key': settings.api_key}
            response = session.get(f"{settings.url}/api/v3/system/status", headers=headers, timeout=5)
        elif service == 'tautulli':
            params = {'cmd': 'get_history', 'apikey': settings.api_key, 'length': 1}
            response = session.get(f"{settings.url}/api/v2", params=params, timeout=5)
        else:
            return jsonify({'status': 'error', 'message': 'Invalid Service'})

        response.raise_for_status()
        latency = int((time.time() - start_time) * 1000)
        return jsonify({'status': 'online', 'latency': latency})
        
    except Exception as e:
        return jsonify({'status': 'offline', 'latency': 0, 'message': str(e)})
