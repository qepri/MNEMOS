from flask import Blueprint, jsonify, request
import requests
import logging
from config.settings import settings
from app.services.model_manager import model_manager
from app.extensions import db, celery_app
from app.models.user_preferences import UserPreferences, SystemPrompt
from app.models.llm_connection import LLMConnection
from datetime import datetime

bp = Blueprint('settings', __name__, url_prefix='/api/settings')

def _list_gguf_models():
    """Scan the models/ directory for GGUF files served by llama.cpp."""
    import os
    import glob

    models_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'models'
    )
    if not os.path.exists(models_dir):
        return []

    models = []
    for file_path in glob.glob(os.path.join(models_dir, '*.gguf')):
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        models.append({
            'name': filename,
            'filename': filename,
            'size': file_size,
            'size_mb': round(file_size / (1024 * 1024), 2),
            'path': f'/models/{filename}',
            'description': 'Local GGUF model (llama.cpp)',
        })
    models.sort(key=lambda x: x['size'])
    return models


@bp.route('/models', methods=['GET'])
def get_models():
    """List locally available GGUF models served by llama.cpp."""
    try:
        models = _list_gguf_models()
        return jsonify({
            'status': 'success',
            'is_running': True,
            'has_vision': False,
            'models': models
        })
    except Exception as e:
        logging.error(f"Error listing models: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'models': []
        }), 500


@bp.route('/models', methods=['DELETE'])
def delete_model():
    """Delete a GGUF model file from the models/ directory."""
    import os

    data = request.json or {}
    model_name = data.get('model')
    if not model_name:
        return jsonify({"error": "Model name required"}), 400

    # Reject path traversal - only a bare filename inside models/ is valid.
    if os.path.basename(model_name) != model_name:
        return jsonify({"error": "Invalid model name"}), 400

    models_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'models'
    )
    target = os.path.join(models_dir, model_name)
    if not os.path.isfile(target):
        return jsonify({"error": "Model not found"}), 404

    try:
        os.remove(target)
        return jsonify({"success": True, "model": model_name})
    except OSError as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/llamacpp/models', methods=['GET'])
def get_llamacpp_models():
    """List available GGUF models in the models/ directory for llamacpp."""
    try:
        models = _list_gguf_models()
        return jsonify({
            'models': models,
            'count': len(models)
        })
    except Exception as e:
        logging.error(f"Error listing llamacpp models: {e}")
        return jsonify({
            'error': str(e),
            'models': []
        }), 500

@bp.route('/library/search', methods=['GET'])
def search_library():
    """Search Hugging Face for GGUF models compatible with llama.cpp."""
    query = request.args.get('q', '').strip()
    sort = request.args.get('sort', 'downloads')  # downloads, trending, created
    limit = int(request.args.get('limit', '30'))

    try:
        # Build Hugging Face API URL
        hf_api_url = "https://huggingface.co/api/models"

        params = {
            'filter': 'gguf',  # Only GGUF models (llama.cpp compatible)
            'sort': sort,
            'limit': limit,
            'full': 'true'  # Get full model info including tags
        }

        if query:
            params['search'] = query

        # Fetch from Hugging Face
        response = requests.get(hf_api_url, params=params, timeout=10)
        response.raise_for_status()
        hf_models = response.json()

        # Transform HF data to our format
        catalog = []
        for model in hf_models:
            # Extract model info
            model_id = model.get('modelId', model.get('id', ''))
            author = model_id.split('/')[0] if '/' in model_id else ''
            name = model_id.split('/')[-1] if '/' in model_id else model_id

            # Get tags and determine capabilities
            tags = model.get('tags', [])
            capabilities = extract_capabilities(tags)

            # Estimate size and requirements from model name/tags
            size_info = estimate_model_size(name, tags)

            # Get downloads count
            downloads = model.get('downloads', 0)
            likes = model.get('likes', 0)

            # Build model entry
            catalog.append({
                "name": name,
                "full_name": model_id,  # Use full HF model ID
                "author": author,
                "description": extract_description(model, name),
                "size_gb": size_info['size_gb'],
                "params": size_info['params'],
                "tags": extract_tags(tags),
                "capabilities": capabilities,
                "min_ram_gb": size_info['min_ram_gb'],
                "min_vram_gb": size_info['min_vram_gb'],
                "downloads": downloads,
                "likes": likes,
                "updated_at": model.get('lastModified', ''),
                "hf_url": f"https://huggingface.co/{model_id}",
                "is_hf_only": True
            })

        return jsonify({"models": catalog, "total": len(catalog)})

    except requests.RequestException as e:
        # Fallback to curated list if HF API fails
        logger = logging.getLogger(__name__)
        logger.warning(f"HF API failed, using fallback catalog: {e}")
        return get_fallback_catalog(query)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def extract_capabilities(tags):
    """Extract capabilities from model tags."""
    capabilities = []
    tag_to_capability = {
        'text-generation': 'text generation',
        'conversational': 'chat',
        'code': 'coding',
        'vision': 'image understanding',
        'multimodal': 'multimodal',
        'translation': 'translation',
        'summarization': 'summarization',
        'question-answering': 'Q&A'
    }

    for tag in tags:
        if tag in tag_to_capability:
            capabilities.append(tag_to_capability[tag])

    if not capabilities:
        capabilities = ['text generation']

    return capabilities


def extract_tags(hf_tags):
    """Extract relevant tags for display."""
    relevant_tags = []
    keywords = ['chat', 'instruct', 'code', 'vision', 'multilingual',
                'uncensored', 'roleplay', 'creative', 'reasoning']

    for tag in hf_tags:
        tag_lower = tag.lower()
        for keyword in keywords:
            if keyword in tag_lower and keyword not in relevant_tags:
                relevant_tags.append(keyword)

    # Limit to 5 tags
    return relevant_tags[:5] if relevant_tags else ['general']


def extract_description(model, name):
    """Extract or generate description from model metadata."""
    # Try to get description from model card
    card_data = model.get('cardData', {})
    if card_data and isinstance(card_data, dict):
        desc = card_data.get('description', '')
        if desc:
            return desc[:200]  # Limit length

    # Fallback: generate from name and tags
    return f"GGUF model: {name}"


def estimate_model_size(name, tags):
    """Estimate model size and requirements from name/tags."""
    name_lower = name.lower()

    # Extract parameter count from name
    if '70b' in name_lower or '72b' in name_lower:
        return {'size_gb': 40.0, 'params': '70B', 'min_ram_gb': 64, 'min_vram_gb': 40}
    elif '34b' in name_lower:
        return {'size_gb': 20.0, 'params': '34B', 'min_ram_gb': 32, 'min_vram_gb': 20}
    elif '13b' in name_lower or '14b' in name_lower:
        return {'size_gb': 8.0, 'params': '13B', 'min_ram_gb': 16, 'min_vram_gb': 8}
    elif '8b' in name_lower:
        return {'size_gb': 4.7, 'params': '8B', 'min_ram_gb': 8, 'min_vram_gb': 4}
    elif '7b' in name_lower:
        return {'size_gb': 4.1, 'params': '7B', 'min_ram_gb': 8, 'min_vram_gb': 4}
    elif '3b' in name_lower or '4b' in name_lower:
        return {'size_gb': 2.3, 'params': '3-4B', 'min_ram_gb': 4, 'min_vram_gb': 2}
    elif '1b' in name_lower or '2b' in name_lower:
        return {'size_gb': 1.3, 'params': '1-2B', 'min_ram_gb': 2, 'min_vram_gb': 1}
    else:
        # Default medium size
        return {'size_gb': 4.0, 'params': '7B (est)', 'min_ram_gb': 8, 'min_vram_gb': 4}


def get_fallback_catalog(query=None):
    """Fallback curated catalog if HF API fails."""
    catalog = [
        {
            "name": "llama3.2",
            "full_name": "llama3.2:latest",
            "author": "Meta",
            "description": "Meta's Llama 3.2 - Fast and efficient for general tasks",
            "size_gb": 2.0,
            "params": "3B",
            "tags": ["general", "chat", "fast"],
            "capabilities": ["text generation", "chat", "coding"],
            "min_ram_gb": 4,
            "min_vram_gb": 2,
            "downloads": 0,
            "likes": 0
        },
        {
            "name": "mistral",
            "full_name": "mistral:latest",
            "author": "Mistral AI",
            "description": "Mistral 7B - Excellent performance-to-size ratio",
            "size_gb": 4.1,
            "params": "7B",
            "tags": ["efficient", "chat", "coding"],
            "capabilities": ["text generation", "chat", "coding"],
            "min_ram_gb": 8,
            "min_vram_gb": 4,
            "downloads": 0,
            "likes": 0
        },
        {
            "name": "qwen2.5",
            "full_name": "qwen2.5:latest",
            "author": "Alibaba",
            "description": "Alibaba's Qwen 2.5 - Strong multilingual support",
            "size_gb": 4.4,
            "params": "7B",
            "tags": ["multilingual", "chat", "coding"],
            "capabilities": ["text generation", "chat", "coding", "multilingual"],
            "min_ram_gb": 8,
            "min_vram_gb": 4,
            "downloads": 0,
            "likes": 0
        }
    ]

    # Filter by query if provided
    if query:
        query_lower = query.lower()
        catalog = [
            m for m in catalog
            if query_lower in m['name'].lower()
            or query_lower in m['description'].lower()
            or any(query_lower in tag for tag in m['tags'])
        ]

    return jsonify({"models": catalog, "total": len(catalog), "fallback": True})

from app.tasks.processing import download_gguf_task
from app.utils.hf_downloader import HFDownloader
import uuid
import os
import json
from celery.result import AsyncResult

# Persistence for Active Downloads
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


# ============= Chat Settings Endpoints =============

@bp.route('/chat', methods=['GET'])
def get_chat_settings():
    """Get chat behavior settings."""
    prefs = db.session.query(UserPreferences).first()

    if not prefs:
        # Return defaults
        return jsonify({
            "use_conversation_context": True,
            "max_context_messages": 10,
            "selected_system_prompt_id": None,
            "chunk_size": 1024,
            "chunk_overlap": 100,
            "whisper_model": "base",
            "archive_enabled": False,
        })

    return jsonify({
        "use_conversation_context": prefs.use_conversation_context,
        "max_context_messages": prefs.max_context_messages,
        "selected_system_prompt_id": str(prefs.selected_system_prompt_id) if prefs.selected_system_prompt_id else None,
        "chunk_size": prefs.chunk_size,
        "chunk_overlap": prefs.chunk_overlap,
        "whisper_model": prefs.whisper_model or "base",
        "llm_provider": prefs.llm_provider or "lm_studio",
        "openai_api_key": prefs.openai_api_key or "",
        "anthropic_api_key": prefs.anthropic_api_key or "",
        "groq_api_key": prefs.groq_api_key or "",
        "custom_api_key": prefs.custom_api_key or "",
        "local_llm_base_url": prefs.local_llm_base_url or "http://host.docker.internal:1234/v1",
        "transcription_provider": getattr(prefs, 'transcription_provider', 'local'),
        "selected_llm_model": prefs.selected_llm_model or "",
        "memory_enabled": getattr(prefs, 'memory_enabled', False),
        "memory_provider": getattr(prefs, 'memory_provider', 'llamacpp'),
        "memory_llm_model": getattr(prefs, 'memory_llm_model', 'llama3:8b'),
        "max_memories": getattr(prefs, 'max_memories', 50),
        "active_connection_id": str(prefs.active_connection_id) if prefs.active_connection_id else None,
        "web_search_provider": getattr(prefs, 'web_search_provider', 'duckduckgo'),
        "tavily_api_key": getattr(prefs, 'tavily_api_key', ''),
        "brave_search_api_key": getattr(prefs, 'brave_search_api_key', ''),
        "deepgram_api_key": getattr(prefs, 'deepgram_api_key', ''),
        "tts_provider": getattr(prefs, 'tts_provider', 'browser'),
        "stt_provider": getattr(prefs, 'stt_provider', 'browser'),
        "tts_voice": getattr(prefs, 'tts_voice', None),
        "tts_enabled": getattr(prefs, 'tts_enabled', False),
        "openai_tts_model": getattr(prefs, 'openai_tts_model', 'tts-1'),
        "openai_stt_model": getattr(prefs, 'openai_stt_model', 'whisper-1'),
        "llm_max_tokens": getattr(prefs, 'llm_max_tokens', 4096),
        "llm_temperature": getattr(prefs, 'llm_temperature', 0.7),
        "llm_top_p": getattr(prefs, 'llm_top_p', 0.9),
        "llm_frequency_penalty": getattr(prefs, 'llm_frequency_penalty', 0.3),
        "llm_presence_penalty": getattr(prefs, 'llm_presence_penalty', 0.1),
        "retrieval_top_k": getattr(prefs, 'retrieval_top_k', 10),
        "hypergraph_llm_provider": getattr(prefs, 'hypergraph_llm_provider', '') or '',
        "hypergraph_llm_model": getattr(prefs, 'hypergraph_llm_model', '') or '',
        "archive_enabled": getattr(prefs, 'archive_enabled', False),
    })


from app.services.llm_client import reset_client

@bp.route('/chat', methods=['POST'])
def save_chat_settings():
    """Save chat behavior settings."""
    data = request.json

    prefs = db.session.query(UserPreferences).first()
    if not prefs:
        prefs = UserPreferences()
        db.session.add(prefs)

    # Update fields
    if 'use_conversation_context' in data:
        prefs.use_conversation_context = data['use_conversation_context']

    if 'max_context_messages' in data:
        prefs.max_context_messages = max(0, min(20, int(data['max_context_messages'])))

    if 'selected_system_prompt_id' in data:
        prompt_id = data['selected_system_prompt_id']
        prefs.selected_system_prompt_id = prompt_id if prompt_id else None
        
    if 'chunk_size' in data:
        # Validate logic limits (e.g. 100 to 2000 chars)
        prefs.chunk_size = max(100, min(2000, int(data['chunk_size'])))
        
    if 'chunk_overlap' in data:
        prefs.chunk_overlap = max(0, min(500, int(data['chunk_overlap'])))

    if 'transcription_provider' in data:
        prefs.transcription_provider = data['transcription_provider']

    if 'whisper_model' in data:
        model = data['whisper_model']
        # Expanded validation for local + groq models
        valid_models = [
            'tiny', 'base', 'small', 'medium', 'large', 'large-v3', 
            'whisper-large-v3', 'whisper-large-v3-turbo'
        ]
        if model in valid_models:
            prefs.whisper_model = model

    # Memory Config
    if 'memory_enabled' in data:
        prefs.memory_enabled = data['memory_enabled']
    if 'memory_provider' in data:
        prefs.memory_provider = data['memory_provider']
    if 'memory_llm_model' in data:
        if data['memory_llm_model']: # Only update if not empty, similar to selected_llm_model
            prefs.memory_llm_model = data['memory_llm_model']
    if 'max_memories' in data:
        prefs.max_memories = int(data['max_memories'])

    # LLM Config
    if 'llm_provider' in data:
        # Normalize provider string
        provider = data['llm_provider']
        if provider:
             prefs.llm_provider = provider
             # Explicitly set active model based on provider defaults if not set?
             # No, let the UI handle that or fallback logic in LLMClient.
    
    if 'openai_api_key' in data:
        prefs.openai_api_key = data['openai_api_key']
    if 'anthropic_api_key' in data:
        prefs.anthropic_api_key = data['anthropic_api_key']
    if 'local_llm_base_url' in data:
        prefs.local_llm_base_url = data['local_llm_base_url']
    if 'groq_api_key' in data:
        prefs.groq_api_key = data['groq_api_key']
    if 'custom_api_key' in data:
        prefs.custom_api_key = data['custom_api_key']
    
    if 'active_connection_id' in data:
        # data['active_connection_id'] can be None or a UUID string
        val = data['active_connection_id']
        prefs.active_connection_id = val if val else None
    
    if 'selected_llm_model' in data:
        new_model = data['selected_llm_model']
        
        # Prevent overwriting a properly set model with an empty string when the
        # frontend hides the input field for local providers.
        current_provider = data.get('llm_provider', prefs.llm_provider)
        should_update = not (current_provider == 'llamacpp' and not new_model)

        if should_update:
            prefs.selected_llm_model = new_model
            # Also update the ModelManager singleton to reflect immediate change
            from app.services.model_manager import model_manager
            model_manager.set_model(new_model)

    # Web Search Config
    if 'web_search_provider' in data:
        prefs.web_search_provider = data['web_search_provider']
    if 'tavily_api_key' in data:
        prefs.tavily_api_key = data['tavily_api_key']
    if 'brave_search_api_key' in data:
        prefs.brave_search_api_key = data['brave_search_api_key']
    if 'deepgram_api_key' in data:
        prefs.deepgram_api_key = data['deepgram_api_key']

    # Voice Config
    if 'tts_provider' in data:
        prefs.tts_provider = data['tts_provider']
    if 'stt_provider' in data:
        prefs.stt_provider = data['stt_provider']
    if 'tts_voice' in data:
        prefs.tts_voice = data['tts_voice']
    if 'tts_enabled' in data:
        prefs.tts_enabled = data['tts_enabled']
    if 'openai_tts_model' in data:
        prefs.openai_tts_model = data['openai_tts_model']
    if 'openai_stt_model' in data:
        prefs.openai_stt_model = data['openai_stt_model']

    # LLM Generation Parameters
    if 'llm_max_tokens' in data:
        prefs.llm_max_tokens = int(data['llm_max_tokens'])
    if 'llm_temperature' in data:
        prefs.llm_temperature = float(data['llm_temperature'])
    if 'llm_top_p' in data:
        prefs.llm_top_p = float(data['llm_top_p'])
    if 'llm_frequency_penalty' in data:
        prefs.llm_frequency_penalty = float(data['llm_frequency_penalty'])
    if 'llm_presence_penalty' in data:
        prefs.llm_presence_penalty = float(data['llm_presence_penalty'])

    if 'retrieval_top_k' in data:
        prefs.retrieval_top_k = max(1, min(50, int(data['retrieval_top_k'])))

    if 'hypergraph_llm_provider' in data:
        prefs.hypergraph_llm_provider = data['hypergraph_llm_provider'] or ""
    if 'hypergraph_llm_model' in data:
        prefs.hypergraph_llm_model = data['hypergraph_llm_model'] or ""

    if 'archive_enabled' in data:
        prefs.archive_enabled = bool(data['archive_enabled'])

    prefs.updated_at = datetime.utcnow()
    db.session.commit()
    
    # Reload LLM Client with new settings
    reset_client()

    return jsonify({"success": True})


# ============= System Prompts Endpoints =============

@bp.route('/prompts', methods=['GET'])
def get_system_prompts():
    """List all system prompts."""
    prompts = db.session.query(SystemPrompt).order_by(
        SystemPrompt.is_default.desc(),
        SystemPrompt.created_at.desc()
    ).all()

    return jsonify({
        "prompts": [p.to_dict() for p in prompts]
    })


@bp.route('/prompts', methods=['POST'])
def create_system_prompt():
    """Create a new custom system prompt."""
    data = request.json

    title = data.get('title', '').strip()
    content = data.get('content', '').strip()

    if not title or not content:
        return jsonify({"error": "Title and content are required"}), 400

    prompt = SystemPrompt(
        title=title,
        content=content,
        is_default=False,
        is_editable=True
    )

    db.session.add(prompt)
    db.session.commit()

    return jsonify(prompt.to_dict()), 201


@bp.route('/prompts/<string:prompt_id>', methods=['PUT'])
def update_system_prompt(prompt_id):
    """Update an existing system prompt."""
    prompt = db.session.query(SystemPrompt).get(prompt_id)

    if not prompt:
        return jsonify({"error": "Prompt not found"}), 404


    if not prompt.is_editable:
        return jsonify({"error": "Cannot edit default prompt"}), 403

    data = request.json

    if 'title' in data:
        prompt.title = data['title'].strip()

    if 'content' in data:
        prompt.content = data['content'].strip()

    prompt.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify(prompt.to_dict())


@bp.route('/prompts/<string:prompt_id>', methods=['DELETE'])
def delete_system_prompt(prompt_id):
    """Delete a custom system prompt."""
    prompt = db.session.query(SystemPrompt).get(prompt_id)

    if not prompt:
        return jsonify({"error": "Prompt not found"}), 404

    if not prompt.is_editable:
        return jsonify({"error": "Cannot delete default prompt"}), 403

    db.session.delete(prompt)
    db.session.commit()

    return jsonify({"success": True})



@bp.route('/files/<path:repo_id>', methods=['GET'])
def list_repo_files(repo_id):
    """List GGUF files for a given HF repo."""
    try:
        files = HFDownloader.list_gguf_files(repo_id)
        return jsonify({"files": files})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/pull_gguf', methods=['POST'])
def pull_model_gguf():
    """Trigger a direct GGUF download and import."""
    data = request.json
    repo_id = data.get('repo_id')
    filename = data.get('filename')
    model_name = data.get('model_name')
    
    if not all([repo_id, filename, model_name]):
        return jsonify({"error": "Missing required fields: repo_id, filename, model_name"}), 400

    task = download_gguf_task.delay(repo_id, filename, model_name)
    
    # Track it
    add_active_download(task.id, model_name)
    
    return jsonify({
        "status": "started",
        "task_id": task.id,
        "model": model_name
    })



# ---------------------------------------------------------------------------
# Re-embed library (after hardware/preset change)
# ---------------------------------------------------------------------------

@bp.route('/reembed', methods=['POST'])
def reembed_library():
    """Kick off a re-embed of every chunk and concept with the current EMBEDDING_MODEL."""
    from app.tasks.reembed import reembed_all
    task = reembed_all.delay()
    return jsonify({
        "status": "started",
        "task_id": task.id,
        "target_model": settings.EMBEDDING_MODEL,
        "target_dimension": settings.EMBEDDING_DIMENSION,
    })


@bp.route('/reembed/status/<task_id>', methods=['GET'])
def reembed_status(task_id):
    """Poll re-embed task progress."""
    res = AsyncResult(task_id, app=celery_app)
    payload = {"task_id": task_id, "state": res.state}
    if res.state == "PROGRESS" and isinstance(res.info, dict):
        payload.update(res.info)
    elif res.state == "SUCCESS":
        payload["result"] = res.result
    elif res.state == "FAILURE":
        payload["error"] = str(res.info)
    return jsonify(payload)
