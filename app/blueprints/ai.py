from flask import Blueprint, render_template, request, jsonify, current_app
from .. import db
from ..models import ServiceSettings, AISettings
from ..tasks.ai import learn_user_preferences, score_media_items
from rq import Queue
from redis import Redis
import os

bp = Blueprint('ai', __name__)

@bp.route('/ai')
def ai_dashboard():
    radarr_settings = ServiceSettings.query.filter_by(service_name='Radarr').first()
    sonarr_settings = ServiceSettings.query.filter_by(service_name='Sonarr').first()
    
    return render_template('ai_dashboard.html', 
                           radarr_rules=radarr_settings.ai_rules if radarr_settings else "",
                           sonarr_rules=sonarr_settings.ai_rules if sonarr_settings else "")

@bp.route('/ai/save_rules', methods=['POST'])
def save_rules():
    data = request.get_json()
    service_name = data.get('service')
    rules = data.get('rules')
    
    settings = ServiceSettings.query.filter_by(service_name=service_name).first()
    if settings:
        settings.ai_rules = rules
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Service not found'})

@bp.route('/ai/learn/<service>', methods=['POST'])
def start_learning(service):
    # Increase timeout to 10 minutes (600s) for learning tasks
    job = current_app.queue.enqueue(learn_user_preferences, service, job_timeout=600)
    return jsonify({'status': 'started', 'job_id': job.get_id()})

@bp.route('/ai/score/<service>', methods=['POST'])
def start_scoring(service):
    # Increase timeout to 20 minutes (1200s) for scoring tasks to handle large batches and retries
    job = current_app.queue.enqueue(score_media_items, service, job_timeout=1200)
    return jsonify({'status': 'started', 'job_id': job.get_id()})
