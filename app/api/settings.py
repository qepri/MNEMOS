from flask import Blueprint, jsonify, request
from celery.result import AsyncResult
import requests
import logging
from config.settings import settings
from app.services.model_manager import model_manager
from app.extensions import db, celery_app
from app.models.user_preferences import UserPreferences, SystemPrompt
from app.models.llm_connection import LLMConnection
from app.utils.hf_downloader import HFDownloader
from datetime import datetime

bp = Blueprint('settings', __name__, url_prefix='/api/settings')

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

def _clamp_int(lo, hi):
    return lambda v: max(lo, min(hi, int(v)))


def _nullable(v):
    """Empty string / falsy -> None (used for optional FK columns)."""
    return v if v else None


def _or_empty(v):
    return v or ""


WHISPER_MODELS = frozenset({
    'tiny', 'base', 'small', 'medium', 'large', 'large-v3',
    'whisper-large-v3', 'whisper-large-v3-turbo',
})

# field name -> coercion applied when the key is present in the payload.
# Declarative so adding a setting is one line, not another if-block.
PREFERENCE_FIELDS = {
    'use_conversation_context': bool,
    'max_context_messages': _clamp_int(0, 20),
    'selected_system_prompt_id': _nullable,
    'chunk_size': _clamp_int(100, 2000),
    'chunk_overlap': _clamp_int(0, 500),
    'transcription_provider': str,
    'memory_enabled': bool,
    'memory_provider': str,
    'max_memories': int,
    'openai_api_key': str,
    'anthropic_api_key': str,
    'local_llm_base_url': str,
    'groq_api_key': str,
    'custom_api_key': str,
    'active_connection_id': _nullable,
    'web_search_provider': str,
    'tavily_api_key': str,
    'brave_search_api_key': str,
    'deepgram_api_key': str,
    'tts_provider': str,
    'stt_provider': str,
    'tts_voice': str,
    'tts_enabled': bool,
    'openai_tts_model': str,
    'openai_stt_model': str,
    'llm_max_tokens': int,
    'llm_temperature': float,
    'llm_top_p': float,
    'llm_frequency_penalty': float,
    'llm_presence_penalty': float,
    'retrieval_top_k': _clamp_int(1, 50),
    'hypergraph_llm_provider': _or_empty,
    'hypergraph_llm_model': _or_empty,
    'archive_enabled': bool,
}

# Present-but-empty values are ignored for these: the UI hides the field for
# some providers and posts "", which must not wipe a configured value.
IGNORE_IF_EMPTY = frozenset({'memory_llm_model', 'llm_provider'})


def _apply_selected_llm_model(prefs, data):
    """selected_llm_model also drives the ModelManager singleton."""
    new_model = data['selected_llm_model']

    # Do not clear a configured model when the frontend hides the input for
    # local providers and posts an empty string.
    provider = data.get('llm_provider', prefs.llm_provider)
    if provider == 'llamacpp' and not new_model:
        return

    prefs.selected_llm_model = new_model
    from app.services.model_manager import model_manager
    model_manager.set_model(new_model)


@bp.route('/chat', methods=['POST'])
def save_chat_settings():
    """Save chat behavior settings."""
    data = request.json or {}

    prefs = db.session.query(UserPreferences).first()
    if not prefs:
        prefs = UserPreferences()
        db.session.add(prefs)

    for field, coerce in PREFERENCE_FIELDS.items():
        if field in data:
            setattr(prefs, field, coerce(data[field]))

    for field in IGNORE_IF_EMPTY:
        if data.get(field):
            setattr(prefs, field, data[field])

    if 'whisper_model' in data and data['whisper_model'] in WHISPER_MODELS:
        prefs.whisper_model = data['whisper_model']

    if 'selected_llm_model' in data:
        _apply_selected_llm_model(prefs, data)

    prefs.updated_at = datetime.utcnow()
    db.session.commit()

    # Reload LLM Client so the new settings take effect immediately.
    reset_client()

    return jsonify({"success": True})



# ============= LLM Availability =============

@bp.route('/llm-availability', methods=['GET'])
def get_llm_availability():
    """Report whether LLM-dependent features can be used right now.

    Always 200, never 503: a 503 would say "MNEMOS is down" when MNEMOS is up
    and perfectly usable for upload and search - having no language model is a
    supported state, not an outage.
    """
    from app.services.llm_availability import get_availability

    return jsonify(get_availability(force=request.args.get('force') == 'true'))


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
    # Imported here rather than at module scope: app.tasks.processing pulls in
    # the whole processing stack (and app.api.settings_downloads imports from
    # the API layer), so a top-level import risks an import cycle at startup.
    from app.tasks.processing import download_gguf_task
    from app.api.settings_downloads import add_active_download

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
