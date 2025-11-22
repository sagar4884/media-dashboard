from flask import Blueprint, render_template, jsonify, request
from ..models import SystemLog, AISettings
from .. import db
from datetime import datetime, timedelta

bp = Blueprint('logs', __name__)

@bp.route('/logs')
def index():
    return render_template('logs.html')

@bp.route('/api/logs')
def get_logs():
    category = request.args.get('category')
    last_id = request.args.get('last_id', 0, type=int)
    
    query = SystemLog.query.filter(SystemLog.id > last_id)
    
    if category and category != 'Overview':
        query = query.filter_by(category=category)
        
    # Limit to last 1000 logs to prevent browser crash on initial load
    # But if last_id is provided, we just want new ones.
    if last_id == 0:
        logs = query.order_by(SystemLog.id.desc()).limit(1000).all()
        logs.reverse() # Return in chronological order
    else:
        logs = query.order_by(SystemLog.id.asc()).limit(1000).all()
    
    return jsonify([{
        'id': log.id,
        'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'level': log.level,
        'category': log.category,
        'message': log.message
    } for log in logs])

@bp.route('/api/logs/clear', methods=['POST'])
def clear_logs():
    try:
        SystemLog.query.delete()
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@bp.route('/api/logs/verbose', methods=['POST'])
def toggle_verbose():
    data = request.get_json()
    enabled = data.get('enabled')
    settings = AISettings.query.first()
    if not settings:
        settings = AISettings()
        db.session.add(settings)
    
    settings.verbose_logging = enabled
    db.session.commit()
    return jsonify({'status': 'success'})

@bp.route('/api/logs/verbose/status')
def get_verbose_status():
    settings = AISettings.query.first()
    enabled = settings.verbose_logging if settings else False
    return jsonify({'enabled': enabled})
