from flask import Blueprint, jsonify, request
import requests
import logging
from config.settings import settings
from app.services.model_manager import model_manager
from app.extensions import db, celery_app
from app.models.user_preferences import UserPreferences, SystemPrompt
from datetime import datetime

bp = Blueprint('settings', __name__, url_prefix='/api/settings')

@bp.route('/models', methods=['GET'])
def get_models():
    """List available models from Ollama."""
    try:
        # Use the internal docker URL
        base_url = settings.OLLAMA_BASE_URL.replace("/v1", "") # Strip /v1 for native API
        resp = requests.get(f"{base_url}/api/tags", timeout=5)
        resp.raise_for_status()
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/models', methods=['DELETE'])
def delete_model():
    """Delete a model from Ollama."""
    data = request.json
    model_name = data.get('model')
    if not model_name:
        return jsonify({"error": "Model name required"}), 400

    try:
        base_url = settings.OLLAMA_BASE_URL.replace("/v1", "")
        # Ollama API: DELETE /api/delete {"name": "model:tag"}
        resp = requests.delete(f"{base_url}/api/delete", json={"name": model_name}, timeout=30)
        resp.raise_for_status()
        return jsonify({"success": True, "model": model_name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/library/search', methods=['GET'])
def search_library():
    """Search Hugging Face for GGUF models compatible with Ollama."""
    query = request.args.get('q', '').strip()
    sort = request.args.get('sort', 'downloads')  # downloads, trending, created
    limit = int(request.args.get('limit', '30'))

    try:
        # Build Hugging Face API URL
        hf_api_url = "https://huggingface.co/api/models"

        params = {
            'filter': 'gguf',  # Only GGUF models (Ollama compatible)
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

            # Map HF model to Ollama-compatible name
            ollama_name = map_hf_to_ollama(model_id, name)

            # Build model entry
            catalog.append({
                "name": name,
                "full_name": model_id,  # Use full HF model ID
                "ollama_name": ollama_name,  # Ollama-compatible name
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
                "is_hf_only": ollama_name is None  # True if not in Ollama library
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


def map_hf_to_ollama(hf_id, name):
    """
    Map Hugging Face model IDs to Ollama library names.
    Returns None if the model is not in Ollama's library.
    """
    # Common mappings from HF to Ollama
    hf_to_ollama = {
        # Llama models
        'meta-llama/Llama-3.2-1B': 'llama3.2:1b',
        'meta-llama/Llama-3.2-3B': 'llama3.2:latest',
        'meta-llama/Meta-Llama-3.1-8B': 'llama3.1:latest',
        'meta-llama/Meta-Llama-3.1-70B': 'llama3.1:70b',

        # Mistral
        'mistralai/Mistral-7B-Instruct-v0.3': 'mistral:latest',
        'mistralai/Mixtral-8x7B-Instruct': 'mixtral:latest',

        # Qwen
        'Qwen/Qwen2.5-7B': 'qwen2.5:latest',
        'Qwen/Qwen2.5-14B': 'qwen2.5:14b',
        'Qwen/Qwen2-7B': 'qwen:7b',

        # Phi
        'microsoft/Phi-3-mini-4k-instruct': 'phi3:latest',

        # Gemma
        'google/gemma-2-9b': 'gemma2:latest',

        # CodeLlama
        'codellama/CodeLlama-7b-Instruct': 'codellama:latest',
    }

    # Check exact match
    if hf_id in hf_to_ollama:
        return hf_to_ollama[hf_id]

    # Try to extract base model name from GGUF repos
    # Many GGUF models follow pattern: author/ModelName-GGUF
    if '-gguf' in hf_id.lower():
        # Extract base model name
        base_name = name.lower().replace('-gguf', '').replace('_gguf', '')

        # Common base model patterns
        if 'hermes' in base_name and '3' in base_name:
            if '405b' in base_name:
                 return 'hermes3:405b'
            elif '70b' in base_name:
                 return 'hermes3:70b'
            return 'hermes3:latest'
        elif 'dolphin' in base_name and 'llama3' in base_name:
            if '2.9' in base_name or '2_9' in base_name:
                 return 'dolphin-llama3:latest' # v2.9 is common
            return 'dolphin-llama3:latest'
        
        # Generic Llama detection
        elif 'llama' in base_name and '3.2' in base_name:
            if '1b' in base_name:
                return 'llama3.2:1b'
            return 'llama3.2:latest'
        elif 'llama' in base_name and '3.1' in base_name:
            if 'hermes' in base_name or 'dolphin' in base_name:
                # Avoid mapping fine-tunes to base model if we missed the specific check above
                return None
            if '70b' in base_name:
                return 'llama3.1:70b'
            return 'llama3.1:latest'
        elif 'mistral' in base_name:
            if 'hermes' in base_name:
                return 'hermes:latest' # Old hermes mistral
            return 'mistral:latest'
        elif 'qwen' in base_name:
            return 'qwen2.5:latest'
        elif 'phi' in base_name:
            return 'phi3:latest'
        elif 'gemma' in base_name:
            return 'gemma2:latest'
        elif 'codellama' in base_name or 'code-llama' in base_name:
            return 'codellama:latest'

    # Not found in Ollama library - this is HF-only
    return None


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

from app.tasks.processing import download_model_task
import uuid
import os
import json
from celery.result import AsyncResult

# KISS Persistence for Active Downloads
DOWNLOADS_FILE = os.path.join(os.getcwd(), 'active_downloads.json')

def load_downloads_file():
    if not os.path.exists(DOWNLOADS_FILE):
        return {}
    try:
        with open(DOWNLOADS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_downloads_file(data):
    try:
        with open(DOWNLOADS_FILE, 'w') as f:
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

@bp.route('/pull', methods=['POST'])
def pull_model():
    """Trigger a model pull in Ollama with Celery background task."""
    data = request.json
    model_name = data.get('model')
    display_name = data.get('display_name', model_name) # Capture display name
    if not model_name:
        return jsonify({"error": "Model name required"}), 400

    try:
        # Generate a task ID to track this download
        task_id = str(uuid.uuid4())

        # Start the download as a background task
        task = download_model_task.apply_async(
            args=[model_name],
            task_id=task_id
        )

        # Track this download peristently
        add_active_download(task_id, display_name)

        return jsonify({
            "task_id": task_id,
            "status": "started",
            "model": model_name
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
            
            # If it's done (SUCCESS or FAILURE), mark for removal (or keep for one last status check if needed)
            # Actually, let's keep them in the list so the UI can see they are done, 
            # but maybe we should rely on the UI polling to eventually remove them?
            # 
            # Better strategy for KISS: 
            # Return current status. If SUCCESS/FAILURE, the UI will see it and stop polling.
            # We can remove it from our file if it is SUCCESS/FAILURE to keep the file clean,
            # BUT if we remove it immediately, the UI might miss the final "Success" message on reload.
            #
            # However, the user asked for "active downloads always are displayed". 
            # If it's finished, it's not active.
            # So we can remove it if it is done.
            
            if status in ['SUCCESS', 'FAILURE', 'REVOKED']:
                # It's done. But if we remove it now, a user reloading the page won't see "Success".
                # They will just see nothing. which is probably fine for "Active downloads".
                # If they want to see "History", that's a different feature.
                ids_to_remove.append(task_id)
            else:
                # It is still running or pending
                active_list.append({
                    'task_id': task_id,
                    'model_name': info.get('model_name', 'Unknown'),
                    'status': status,
                    'started_at': info.get('started_at')
                })
        except Exception as e:
            # If we allow this to fail, we might lose track. 
            # Assume it's a zombie if we can't check it?
            logger.error(f"Error checking task {task_id}: {e}")
    
    # Clean up finished tasks
    if ids_to_remove:
        for tid in ids_to_remove:
             if tid in active_map:
                 del active_map[tid]
        save_downloads_file(active_map)

    return jsonify({"active_tasks": active_list})
import os
import psutil
import json

@bp.route('/hardware', methods=['GET'])
def get_hardware_info():
    """Get system hardware info (RAM)."""
    try:
        mem = psutil.virtual_memory()
        return jsonify({
            "ram_total": mem.total,
            "ram_available": mem.available,
            "ram_percent": mem.percent
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/import/scan', methods=['GET'])
def scan_imports():
    """Scan import directory for GGUF files."""
    try:
        # Path inside APP container
        import_dir = "/app/ollama_import" 
        if not os.path.exists(import_dir):
            return jsonify({"files": []})
            
        files = [f for f in os.listdir(import_dir) if f.endswith('.gguf')]
        return jsonify({"files": files})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/import', methods=['POST'])
def import_model():
    """Import a GGUF model."""
    data = request.json
    filename = data.get('filename')
    model_name = data.get('model_name') # User defined name
    
    if not filename or not model_name:
        return jsonify({"error": "Filename and Model Name required"}), 400
        
    try:
        base_url = settings.OLLAMA_BASE_URL.replace("/v1", "")
        
        # 1. We tell Ollama to create a model from this file.
        # The file is at /root/.ollama/import/{filename} inside OLLAMA container.
        # (Assuming we matched the volume mounts correctly)
        
        modelfile_content = f"FROM /root/.ollama/import/{filename}"
        
        payload = {
            "name": model_name,
            "modelfile": modelfile_content
        }
        
        # Stream the creation process
        def generate():
            with requests.post(f"{base_url}/api/create", json=payload, stream=True, timeout=300) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk

        return generate(), {"Content-Type": "application/json"}

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/current-model', methods=['GET'])
def get_current_model():
    """Get the currently selected LLM model."""
    current = model_manager.get_model()
    
    # Fallback to default if not set
    if not current:
         # Try global settings default
         if settings.LLM_PROVIDER == 'ollama':
             current = settings.LOCAL_LLM_MODEL
         elif settings.LLM_PROVIDER == 'openai':
             current = settings.OPENAI_MODEL
         elif settings.LLM_PROVIDER == 'anthropic':
             current = settings.ANTHROPIC_MODEL
             
    return jsonify({
        "model": current,
        "provider": settings.LLM_PROVIDER,
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
            "chunk_size": 512,
            "chunk_overlap": 50,
            "whisper_model": "base"
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
        "local_llm_base_url": prefs.local_llm_base_url or "http://host.docker.internal:1234/v1",
        "transcription_provider": getattr(prefs, 'transcription_provider', 'local'),
        "selected_llm_model": prefs.selected_llm_model or ""
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

    # LLM Config
    if 'llm_provider' in data:
        prefs.llm_provider = data['llm_provider']
    if 'openai_api_key' in data:
        prefs.openai_api_key = data['openai_api_key']
    if 'anthropic_api_key' in data:
        prefs.anthropic_api_key = data['anthropic_api_key']
    if 'local_llm_base_url' in data:
        prefs.local_llm_base_url = data['local_llm_base_url']
    if 'groq_api_key' in data:
        prefs.groq_api_key = data['groq_api_key']
    
    if 'selected_llm_model' in data:
        prefs.selected_llm_model = data['selected_llm_model']
        # Also update the ModelManager singleton to reflect immediate change
        from app.services.model_manager import model_manager
        model_manager.set_model(data['selected_llm_model'])

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
