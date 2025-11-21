import json
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
    
    # Parse proposals if they exist
    radarr_proposals = None
    if radarr_settings and radarr_settings.ai_rule_proposals:
        try:
            radarr_proposals = json.loads(radarr_settings.ai_rule_proposals)
        except json.JSONDecodeError:
            pass

    sonarr_proposals = None
    if sonarr_settings and sonarr_settings.ai_rule_proposals:
        try:
            sonarr_proposals = json.loads(sonarr_settings.ai_rule_proposals)
        except json.JSONDecodeError:
            pass

    return render_template('ai_dashboard.html', 
                           radarr_rules=radarr_settings.ai_rules if radarr_settings else "",
                           sonarr_rules=sonarr_settings.ai_rules if sonarr_settings else "",
                           radarr_proposals=radarr_proposals,
                           sonarr_proposals=sonarr_proposals)

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

@bp.route('/ai/proposal/apply', methods=['POST'])
def apply_proposal():
    data = request.get_json()
    service_name = data.get('service_name')
    proposal_type = data.get('type') # 'refinement' or 'new'
    proposal_id = data.get('id')
    action = data.get('action') # 'confirm' or 'decline'
    
    settings = ServiceSettings.query.filter_by(service_name=service_name).first()
    if not settings or not settings.ai_rule_proposals:
        return jsonify({'status': 'error', 'message': 'No proposals found'})
        
    try:
        proposals = json.loads(settings.ai_rule_proposals)
        current_rules = settings.ai_rules or ""
        
        target_list = proposals['refinements'] if proposal_type == 'refinement' else proposals['new_rules']
        
        # Find item by ID
        item_index = -1
        item = None
        for i, p in enumerate(target_list):
            if p.get('id') == proposal_id:
                item_index = i
                item = p
                break
        
        if item_index == -1:
            return jsonify({'status': 'error', 'message': 'Proposal not found'})

        if action == 'confirm':
            if proposal_type == 'refinement':
                # Replace the original rule with the new rule
                if item['original_rule'] in current_rules:
                    current_rules = current_rules.replace(item['original_rule'], item['new_rule'])
                else:
                    # Fallback if exact string match fails
                    current_rules += f"\n{item['new_rule']}"
            elif proposal_type == 'new':
                current_rules += f"\n{item['rule']}"
            
            settings.ai_rules = current_rules.strip()
            
        # Remove the processed proposal
        target_list.pop(item_index)
            
        # If no proposals left, clear the field
        if not proposals['refinements'] and not proposals['new_rules']:
            settings.ai_rule_proposals = None
        else:
            settings.ai_rule_proposals = json.dumps(proposals)
            
        db.session.commit()
        return jsonify({'status': 'success', 'rules': settings.ai_rules})
        
    except (ValueError, IndexError, KeyError) as e:
        return jsonify({'status': 'error', 'message': str(e)})

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
