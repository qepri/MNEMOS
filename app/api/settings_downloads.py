"""Settings endpoints for model downloads, imports and hardware info.

Tracks Celery download tasks and exposes GGUF import/upload plus hardware
capability probing. Registers on the blueprint owned by app/api/settings.py.
"""

import json
import logging
import os
import uuid

import requests
from flask import jsonify, request
from celery.result import AsyncResult

from app.extensions import db, celery_app
from app.models.user_preferences import UserPreferences
from app.services.model_manager import model_manager
from config.settings import settings

from app.api.settings import bp

# Persisted so in-flight downloads survive an app restart.
ACTIVE_DOWNLOADS_FILE = os.path.join(os.path.dirname(__file__), '..', 'active_downloads.json')

def load_downloads_file():
    if not os.path.exists(ACTIVE_DOWNLOADS_FILE):
        return {}
    try:
        with open(ACTIVE_DOWNLOADS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_downloads_file(data):
    try:
        with open(ACTIVE_DOWNLOADS_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logging.error(f"Error saving downloads file: {e}")

def add_active_download(task_id, model_name):
    data = load_downloads_file()
    data[task_id] = {
        'task_id': task_id,
        'model_name': model_name,
        'started_at': datetime.utcnow().isoformat(),
        'status': 'started'
    }
    save_downloads_file(data)

def remove_active_download(task_id):
    data = load_downloads_file()
    if task_id in data:
        del data[task_id]
        save_downloads_file(data)

@bp.route('/downloads', methods=['GET'])
def get_active_downloads():
    """Get list of active downloads."""
    data = load_downloads_file()
    tasks = []
    
    # Check status of each task
    for task_id, info in data.items():
        res = AsyncResult(task_id, app=celery_app)
        
        # Start with stored info
        task_info = info.copy()
        
        if res.state == 'PROGRESS':
             meta = res.info or {}
             if isinstance(meta, dict):
                 task_info['status'] = meta.get('status', 'downloading')
                 task_info['progress'] = meta.get('progress', 0)
        elif res.state == 'SUCCESS':
            task_info['status'] = 'completed'
            task_info['progress'] = 100
        elif res.state == 'FAILURE':
            task_info['status'] = 'failed'
            task_info['error'] = str(res.info)
            
        tasks.append(task_info)
        
    return jsonify({"tasks": tasks})

# Dictionary to keep track of active downloads (in a real app, this might be in Redis)
# For now, we'll use browser storage to remember active downloads between page reloads
# This is stored client-side, but in a real system, you might want to track this server-side

@bp.route('/pull/status/<task_id>', methods=['GET'])
def get_pull_status(task_id):
    """Get the status of a model pull task."""
    try:
        from celery.result import AsyncResult
        task_result = AsyncResult(task_id, app=celery_app)

        response = {
            'task_id': task_id,
            'status': task_result.status,
        }

        if task_result.status == 'PROGRESS':
            progress_line = task_result.info.get('progress_line', '')
            # Parse the progress JSON from the line
            import json
            try:
                progress_data = json.loads(progress_line)
                response.update(progress_data)
                response['model_name'] = task_result.info.get('model_name', '')
            except json.JSONDecodeError:
                # If it's not valid JSON, return the raw line
                response['progress_line'] = progress_line
                response['model_name'] = task_result.info.get('model_name', '')
        elif task_result.status == 'SUCCESS':
            response['result'] = task_result.result
        elif task_result.status == 'FAILURE':
            response['error'] = str(task_result.info)

        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/pull/active', methods=['GET'])
def get_active_pulls():
    """Get all active model pull tasks and clean up completed ones."""
    active_map = load_downloads_file()
    active_list = []
    ids_to_remove = []

    for task_id, info in active_map.items():
        try:
            task_result = AsyncResult(task_id, app=celery_app)
            status = task_result.status
            
            task_info = info.copy()
            task_info['status'] = status
            
            if status == 'SUCCESS':
                task_info['result'] = task_result.result
                task_info['progress'] = 100
                
                # Check for nested error in a successful result payload
                if task_result.result and 'last_progress' in task_result.result:
                    try:
                        lp = json.loads(task_result.result['last_progress'])
                        if 'error' in lp:
                            task_info['status'] = 'FAILURE'
                            task_info['error'] = lp['error']
                    except:
                        pass
                        
            elif status == 'FAILURE':
                task_info['error'] = str(task_result.info)
            elif status == 'PROGRESS':
                # Populate progress info
                if task_result.info:
                    task_info.update(task_result.info)
                    
                    # Also parse progress line for error
                    if 'progress_line' in task_result.info:
                        try:
                            pl = json.loads(task_result.info['progress_line'])
                            if 'error' in pl:
                                task_info['status'] = 'FAILURE'
                                task_info['error'] = pl['error']
                        except:
                            pass

            active_list.append(task_info)

            # Cleanup logic: Remove if finished AND older than 1 hour
            # (Users can also manually delete via DELETE /pull/<id>)
            if status in ['SUCCESS', 'FAILURE', 'REVOKED']:
                started_at_str = info.get('started_at')
                if started_at_str:
                    try:
                        started_at = datetime.fromisoformat(started_at_str)
                        if datetime.utcnow() - started_at > timedelta(hours=1):
                            ids_to_remove.append(task_id)
                    except:
                        pass 
        except Exception as e:
            logger.error(f"Error checking task {task_id}: {e}")
            # If we can't check it, maybe it's stale? Keep it for now.
            active_list.append(info)
    
    # Clean up old finished tasks
    if ids_to_remove:
        for tid in ids_to_remove:
             if tid in active_map:
                 del active_map[tid]
        save_downloads_file(active_map)

    return jsonify({"active_tasks": active_list})


@bp.route('/pull/<task_id>', methods=['DELETE'])
def delete_pull_task(task_id):
    """Cancel/Delete a download task."""
    try:
        # 1. Remove from our persistent list
        remove_active_download(task_id)
        
        # 2. Revoke the celery task (stop it if running)
        celery_app.control.revoke(task_id, terminate=True)
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
import os
import psutil
import json

@bp.route('/hardware', methods=['GET'])
def get_hardware_info():
    """Get system hardware info (RAM & VRAM)."""
    import subprocess
    
    info = {
        "ram_total": 0,
        "ram_available": 0,
        "vram_total": 0,
        "vram_available": 0,
        "gpu_name": None
    }
    
    try:
        # RAM
        mem = psutil.virtual_memory()
        info["ram_total"] = mem.total
        info["ram_available"] = mem.available
        
        # VRAM (NVIDIA)
        try:
            # Check for nvidia-smi
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name,memory.total,memory.free', '--format=csv,noheader,nounits'], 
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if lines:
                    # Take first GPU
                    parts = lines[0].split(',')
                    if len(parts) >= 3:
                        info['gpu_name'] = parts[0].strip()
                        # Convert MB to Bytes for consistency with psutil
                        info['vram_total'] = int(parts[1].strip()) * 1024 * 1024
                        info['vram_available'] = int(parts[2].strip()) * 1024 * 1024
        except Exception:
            pass # No GPU or error checking
            
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/import/scan', methods=['GET'])
def scan_imports():
    """Scan models directory for GGUF files."""
    try:
        # Path inside APP container - using new models/ folder
        models_dir = "/app/models"
        if not os.path.exists(models_dir):
            return jsonify({"files": []})

        files = [f for f in os.listdir(models_dir) if f.endswith('.gguf')]
        return jsonify({"files": files})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/import/upload', methods=['POST'])
def upload_gguf():
    """Upload a GGUF model file."""
    try:
        models_dir = "/app/models"
        if not os.path.exists(models_dir):
            os.makedirs(models_dir)
            
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
            
        if not file.filename.lower().endswith('.gguf'):
            return jsonify({"error": "Only .gguf files are allowed"}), 400

        filename = os.path.basename(file.filename) # sanitize?
        save_path = os.path.join(models_dir, filename)
        
        # Save file (chunked to avoid memory issues)
        file.save(save_path) # Flask's save uses shutil.copyfileobj which is efficient
        
        return jsonify({"success": True, "filename": filename})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/import', methods=['POST'])
def import_model():
    """
    Import a GGUF model for llama.cpp.
    Note: For llama.cpp, models just need to exist in /models directory - no import step needed.
    This endpoint now simply verifies the file exists and is valid.
    """
    data = request.json
    filename = data.get('filename')
    model_name = data.get('model_name') # User defined name (for UI purposes)

    if not filename or not model_name:
        return jsonify({"error": "Filename and Model Name required"}), 400

    try:
        # For llama.cpp: Just verify the GGUF file exists in the models directory
        models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'models')
        file_path = os.path.join(models_dir, filename)

        if not os.path.exists(file_path):
            return jsonify({"error": f"GGUF file not found: {filename}"}), 404

        if not filename.lower().endswith('.gguf'):
            return jsonify({"error": "File must be a .gguf file"}), 400

        # Get file info
        file_size = os.path.getsize(file_path)
        size_gb = round(file_size / (1024**3), 2)

        # For llama.cpp, the model is ready to use immediately
        # The server will load it when selected via the model selector
        return jsonify({
            "success": True,
            "details": f"Model {filename} ({size_gb} GB) is ready for llama.cpp. Select it from the model list to use it.",
            "filename": filename,
            "size_gb": size_gb,
            "path": f"/models/{filename}"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/models/lookup', methods=['POST'])
def lookup_models():
    """Fetch available models from a provider using provided credentials."""
    data = request.json
    provider = data.get('provider')
    api_key = data.get('api_key')
    
    if not provider or not api_key:
        return jsonify({"error": "Provider and API Key required"}), 400
        
    try:
        if provider == 'groq':
            url = "https://api.groq.com/openai/v1/models"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            
            data = resp.json()
            # Groq returns standard OpenAI format: {"data": [{"id": "...", ...}]}
            models = []
            for m in data.get('data', []):
                model_id = m.get('id')
                if model_id:
                     # Detect vision capability 
                     # (Groq currently labels vision models with 'vision' in ID sometimes, or we check known ones)
                     is_vision = 'vision' in model_id.lower() or 'llava' in model_id.lower() \
                                 or 'scout' in model_id.lower() or 'maverick' in model_id.lower()
                     models.append({
                         "name": model_id,
                         "vision": is_vision
                     })
            
            return jsonify({"models": models})
            
        return jsonify({"error": f"Provider {provider} lookup not supported"}), 400
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/current-model', methods=['GET'])
def get_current_model():
    """Get the currently selected LLM model."""
    
    # KISS: Read directly from DB as source of truth
    prefs = db.session.query(UserPreferences).first()
    
    db_model = prefs.selected_llm_model if prefs else None
    provider = prefs.llm_provider if prefs and prefs.llm_provider else settings.LLM_PROVIDER
    
    # Sync in-memory manager if DB has a value (ensures LLMClient gets it too)
    if db_model:
        if model_manager.get_model() != db_model:
             # We set the private var directly to avoid triggering another DB write loop
             from app.services.model_manager import ModelManager
             ModelManager._current_model = db_model
    
    current = db_model or model_manager.get_model()
    
    # Fallback to default if not set
    if not current:
         # Try global settings default
         if provider == 'llamacpp':
             current = settings.LOCAL_LLM_MODEL
         elif provider == 'openai':
             current = settings.OPENAI_MODEL
         elif provider == 'anthropic':
             current = settings.ANTHROPIC_MODEL
             
    return jsonify({
        "model": current,
        "provider": provider,
        "has_model": current is not None
    })

@bp.route('/current-model', methods=['POST'])
def set_current_model():
    """Set the current LLM model."""
    data = request.json
    model_name = data.get('model')

    if not model_name:
        return jsonify({"error": "Model name required"}), 400

    model_manager.set_model(model_name)
    
    # Explicitly persist to DB to ensure it survives reload
    # (ModelManager tries to do this but might fail if context is tricky, so we double down)
    try:
        prefs = db.session.query(UserPreferences).first()
        if not prefs:
            prefs = UserPreferences()
            db.session.add(prefs)
        
        prefs.selected_llm_model = model_name
        # Also ensure provider matches if we know it? 
        # For now just save model.
        db.session.commit()
    except Exception as e:
        pass
        
    return jsonify({
        "success": True,
        "model": model_name
    })
