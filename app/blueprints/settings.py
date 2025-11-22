from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app
from sqlalchemy import text
from .. import db, run_migrations
from ..models import ServiceSettings, AISettings, ScheduledTask
from ..tasks import sync_radarr_movies, sync_sonarr_shows, sync_tautulli_history, get_retry_session, vacuum_database
from rq.job import Job
from rq.exceptions import NoSuchJobError
from rq.registry import StartedJobRegistry
import os
import requests
import shutil
import sqlite3
import json
from datetime import datetime

bp = Blueprint('settings', __name__)

@bp.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        # Handle Service Settings
        if 'save_settings' in request.form:
            services = ['Radarr', 'Sonarr', 'Tautulli']
            for service_name in services:
                settings = ServiceSettings.query.filter_by(service_name=service_name).first()
                if not settings:
                    settings = ServiceSettings(service_name=service_name)
                
                settings.url = request.form.get(f'{service_name}_url')
                settings.api_key = request.form.get(f'{service_name}_api_key')
                if service_name != 'Tautulli':
                    settings.grace_days = int(request.form.get(f'{service_name}_grace_days', 30))
                settings.retention_days = int(request.form.get(f'{service_name}_retention_days', 365))
                if service_name == 'Radarr': # Centralized TMDB key
                    settings.tmdb_api_key = request.form.get('tmdb_api_key')

                db.session.add(settings)
            
            # Handle AI Settings
            ai_settings = AISettings.query.first()
            if not ai_settings:
                ai_settings = AISettings()
            
            ai_settings.provider = request.form.get('ai_provider')
            ai_settings.api_key = request.form.get('ai_api_key')
            ai_settings.learning_model = request.form.get('ai_learning_model')
            ai_settings.scoring_model = request.form.get('ai_scoring_model')
            ai_settings.batch_size_movies_learn = int(request.form.get('batch_size_movies_learn', 20))
            ai_settings.batch_size_movies_score = int(request.form.get('batch_size_movies_score', 50))
            ai_settings.batch_size_shows_learn = int(request.form.get('batch_size_shows_learn', 10))
            ai_settings.batch_size_shows_score = int(request.form.get('batch_size_shows_score', 20))
            # verbose_logging is now handled in the Logs page
            ai_settings.log_retention = int(request.form.get('log_retention', 7))
            ai_settings.max_items_limit = int(request.form.get('max_items_limit', 0))
            
            db.session.add(ai_settings)
            db.session.commit()
            flash('Settings updated successfully.', 'success')
            return redirect(url_for('settings.settings'))

    # Fetch Settings
    radarr_settings = ServiceSettings.query.filter_by(service_name='Radarr').first()
    sonarr_settings = ServiceSettings.query.filter_by(service_name='Sonarr').first()
    tautulli_settings = ServiceSettings.query.filter_by(service_name='Tautulli').first()
    ai_settings = AISettings.query.first()
    schedules = ScheduledTask.query.all()

    return render_template('settings.html',
                           radarr_settings=radarr_settings,
                           sonarr_settings=sonarr_settings,
                           tautulli_settings=tautulli_settings,
                           ai_settings=ai_settings,
                           schedules=schedules)

@bp.route('/settings/schedule/add', methods=['POST'])
def add_schedule():
    try:
        name = request.form.get('name')
        time = request.form.get('time')
        days = request.form.getlist('days') # List of strings "0", "1", etc.
        tasks = request.form.getlist('tasks') # List of task IDs
        
        if not name or not time or not days or not tasks:
            flash('All fields are required.', 'error')
            return redirect(url_for('settings.settings'))
            
        # Convert days to integers
        days = [int(d) for d in days]
        
        schedule = ScheduledTask(
            name=name,
            time=time,
            days=json.dumps(days),
            tasks=json.dumps(tasks),
            enabled=True
        )
        db.session.add(schedule)
        db.session.commit()
        flash('Schedule added successfully.', 'success')
    except Exception as e:
        flash(f'Error adding schedule: {str(e)}', 'error')
        
    return redirect(url_for('settings.settings'))

@bp.route('/settings/schedule/delete/<int:id>', methods=['POST'])
def delete_schedule(id):
    schedule = ScheduledTask.query.get_or_404(id)
    db.session.delete(schedule)
    db.session.commit()
    flash('Schedule deleted.', 'success')
    return redirect(url_for('settings.settings'))

@bp.route('/settings/schedule/toggle/<int:id>', methods=['POST'])
def toggle_schedule(id):
    schedule = ScheduledTask.query.get_or_404(id)
    schedule.enabled = not schedule.enabled
    db.session.commit()
    return jsonify({'status': 'success', 'enabled': schedule.enabled})

@bp.route('/test_connection/<service>', methods=['POST'])
def test_connection(service):
    session = get_retry_session()
    service_name = service.capitalize()
    
    url = request.form.get(f'{service_name}_url')
    api_key = request.form.get(f'{service_name}_api_key')

    try:
        if service == 'radarr' or service == 'sonarr':
            headers = {'X-Api-Key': api_key}
            response = session.get(f"{url}/api/v3/system/status", headers=headers, timeout=10)
        elif service == 'tautulli':
            params = {'cmd': 'get_history', 'apikey': api_key, 'length': 1}
            response = session.get(f"{url}/api/v2", params=params, timeout=10)
        elif service == 'tmdb':
            tmdb_api_key = request.form.get('tmdb_api_key')
            response = session.get(f"https://api.themoviedb.org/3/configuration?api_key={tmdb_api_key}", timeout=10)
        else:
            return f'<span class="text-red-400">Invalid service specified.</span>'

        response.raise_for_status()
        return f'<span class="text-green-400">Successful Connection</span>'
    except requests.exceptions.Timeout:
        return f'<span class="text-red-400">Connection Failed: The request timed out.</span>'
    except requests.exceptions.RequestException as e:
        return f'<span class="text-red-400">Connection Failed: {e}</span>'

@bp.route('/database')
def database_page():
    db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '/')
    db_info = {
        'type': 'SQLite',
        'path': db_path,
        'size_mb': os.path.getsize(db_path) / (1024 * 1024) if os.path.exists(db_path) else 0
    }
    return render_template('database.html', db_info=db_info)

@bp.route('/database/integrity_check', methods=['POST'])
def integrity_check():
    try:
        result = db.session.execute(text('PRAGMA integrity_check')).fetchone()
        return f"Integrity Check: {result[0]}"
    except Exception as e:
        return f"Error: {e}"

@bp.route('/database/optimize', methods=['POST'])
def optimize_db():
    try:
        db.session.execute(text('PRAGMA optimize'))
        db.session.commit()
        return "Database optimization complete."
    except Exception as e:
        return f"Error: {e}"

@bp.route('/database/vacuum', methods=['POST'])
def vacuum_db():
    registry = StartedJobRegistry(queue=current_app.queue)
    if registry.get_job_ids():
        return jsonify({'error': 'A job is already running'}), 409
        
    job = current_app.queue.enqueue(vacuum_database, job_timeout='15m')
    return jsonify({'job_id': job.get_id()})

@bp.route('/database/backup', methods=['POST'])
def backup_database():
    backup_dir = '/appdata/Backup'
    imports_dir = '/appdata/Imports'
    os.makedirs(backup_dir, exist_ok=True)
    os.makedirs(imports_dir, exist_ok=True)
    
    db_path = '/appdata/database/app.db'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"backup_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    try:
        # Use SQLite Online Backup API
        # This is safer than copying files while the DB is in use
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(backup_path)
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
        
        return jsonify({'status': 'success', 'message': f'Backup created: {backup_filename}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@bp.route('/database/import', methods=['POST'])
def import_database():
    imports_dir = '/appdata/Imports'
    db_path = '/appdata/database/app.db'
    
    if not os.path.exists(imports_dir):
        return jsonify({'status': 'error', 'message': 'Imports directory not found'})
        
    # Find valid DB files
    files = [f for f in os.listdir(imports_dir) if f.endswith('.db')]
    if not files:
        return jsonify({'status': 'error', 'message': 'No .db files found in /appdata/Imports'})
        
    # Sort by modification time, newest first
    files.sort(key=lambda x: os.path.getmtime(os.path.join(imports_dir, x)), reverse=True)
    target_file = files[0]
    source_path = os.path.join(imports_dir, target_file)
    
    try:
        # 1. Close current connections (best effort)
        db.session.remove()
        db.engine.dispose()
        
        # 2. Replace the file
        # We also need to remove WAL/SHM files if they exist to avoid corruption
        if os.path.exists(db_path + '-wal'):
            os.remove(db_path + '-wal')
        if os.path.exists(db_path + '-shm'):
            os.remove(db_path + '-shm')
            
        shutil.copy2(source_path, db_path)
        
        # Check for and copy WAL/SHM files if they exist in source
        # This supports importing manual raw backups
        source_wal = source_path + '-wal'
        source_shm = source_path + '-shm'
        if os.path.exists(source_wal):
            shutil.copy2(source_wal, db_path + '-wal')
        if os.path.exists(source_shm):
            shutil.copy2(source_shm, db_path + '-shm')
        
        # 3. Re-initialize and Migrate
        # We need to reconnect to the new DB file
        # Calling run_migrations will attempt to apply any schema updates
        run_migrations(current_app)
        
        return jsonify({'status': 'success', 'message': f'Imported {target_file} successfully. Please refresh the page.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@bp.route('/sync/<service>')
def sync(service):
    registry = StartedJobRegistry(queue=current_app.queue)
    if registry.get_job_ids():
        return jsonify({'error': 'A job is already running'}), 409

    mode = request.args.get('mode', 'quick')
    full_sync = mode == 'full'

    if service == 'radarr':
        job = current_app.queue.enqueue(sync_radarr_movies, job_timeout='3h', args=(full_sync,))
    elif service == 'sonarr':
        job = current_app.queue.enqueue(sync_sonarr_shows, job_timeout='3h', args=(full_sync,))
    elif service == 'tautulli':
        job = current_app.queue.enqueue(sync_tautulli_history, job_timeout='5m', args=(full_sync,))
    else:
        return jsonify({'error': 'Invalid service'}), 400
    
    return jsonify({'job_id': job.get_id()})

@bp.route('/stop-job', methods=['POST'])
def stop_job():
    redis_conn = current_app.queue.connection
    redis_conn.set('stop-job-flag', 'true')
    return jsonify({'status': 'Stop signal sent'})

@bp.route('/task_status/<job_id>')
def task_status(job_id):
    try:
        job = Job.fetch(job_id, connection=current_app.queue.connection)
    except NoSuchJobError:
        # The job is no longer in the registry, which means it's finished or failed and cleaned up.
        # Tell the frontend to stop polling.
        return jsonify({'status': 'finished'})

    response = {
        'status': job.get_status(),
        'progress': job.meta.get('progress', 0) if job.is_started else 0,
        'eta': job.meta.get('eta', None),
        'func_name': job.func_name
    }
    if job.is_finished:
        response['result'] = job.result
    elif job.is_failed:
        response['error'] = job.exc_info
    
    return jsonify(response)
