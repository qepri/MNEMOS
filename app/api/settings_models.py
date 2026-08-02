"""Settings endpoints for local model management.

GGUF discovery, HuggingFace library search, downloads/imports and hardware
info. Registers on the same blueprint as app/api/settings.py, which owns it.
"""

import json
import logging
import os
import uuid
from datetime import datetime

import requests
from flask import jsonify, request
from celery.result import AsyncResult

from app.extensions import db, celery_app
from app.models.user_preferences import UserPreferences
from app.services.model_manager import model_manager
from config.settings import settings

from app.api.settings import bp

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
