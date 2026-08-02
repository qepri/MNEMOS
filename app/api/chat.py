from flask import Blueprint, request, jsonify, Response, stream_with_context
from app.services.rag import RAGService
from app.services.embedder import EmbedderService
from app.services.llm_client import LLMError
from app.extensions import db, limiter
from app.models.conversation import Conversation, Message
from app.models.user_preferences import UserPreferences, SystemPrompt
import logging
import json

logger = logging.getLogger(__name__)

bp = Blueprint('chat', __name__, url_prefix='/api/chat')

@bp.route('/', methods=['POST'])
@limiter.limit("30 per minute")
def chat():
    """Chat endpoint with RAG and conversation context support."""
    # Handle both multipart/form-data (HTMX) and JSON
    if request.is_json:
        data = request.json
        question = data.get('question')
        doc_ids = data.get('document_ids', [])
        conversation_id = data.get('conversation_id')
        images = data.get('images', []) # List of base64 strings
    else:
        question = request.form.get('question')
        doc_ids_str = request.form.get('document_ids', '')
        doc_ids = [d.strip() for d in doc_ids_str.split(',') if d.strip()]
        conversation_id = request.form.get('conversation_id')
        images = [] # Form data support for images could be added via file keys, but for now assuming JSON mostly or empty

    if not question:
        return jsonify({"error": "Question required"}), 400

    # Load user preferences
    prefs = db.session.query(UserPreferences).first()
    if not prefs:
        prefs = UserPreferences(
            use_conversation_context=True,
            max_context_messages=10
        )
        db.session.add(prefs)
        db.session.commit()

    # Conversation handling
    conversation = None
    if conversation_id:
        conversation = db.session.query(Conversation).get(conversation_id)
        if not conversation:
            return jsonify({"error": "Conversation not found"}), 404
    else:
        title = question[:80] + "..." if len(question) > 80 else question
        conversation = Conversation(title=title)
        db.session.add(conversation)
        db.session.commit()

    user_msg = Message(
        conversation_id=conversation.id,
        role='user',
        content=question,
        images=images # Save images to simple DB column (JSONB)
    )
    db.session.add(user_msg)
    db.session.commit()

    # Load conversation history if enabled
    conversation_history = []
    if prefs.use_conversation_context and conversation_id:
        # Get previous messages (excluding the one we just added)
        history_msgs = db.session.query(Message).filter(
            Message.conversation_id == conversation.id,
            Message.id != user_msg.id
        ).order_by(Message.created_at.desc()).limit(prefs.max_context_messages).all()

        conversation_history = list(reversed(history_msgs))

        logger.info(f"Loaded {len(conversation_history)} messages for conversation context")

    # Load selected system prompt
    system_prompt = None
    if prefs.selected_system_prompt_id:
        prompt_obj = db.session.query(SystemPrompt).get(prefs.selected_system_prompt_id)
        if prompt_obj:
            system_prompt = prompt_obj.content

    web_search = data.get('web_search', False) if request.is_json else False
    use_graph_rag = data.get('use_graph_rag', False) if request.is_json else False

    # Perform RAG with conversation context
    top_k = max(1, min(50, getattr(prefs, 'retrieval_top_k', 10)))
    rag = RAGService(db.session)
    try:
        result = rag.query(
            question=question,
            document_ids=doc_ids,
            top_k=top_k,
            conversation_history=conversation_history,
            system_prompt=system_prompt,
            web_search=web_search,
            use_graph_rag=use_graph_rag,
            images=images
        )
    except LLMError as e:
        logger.error(f"LLM provider error: {e}")
        return jsonify({"error": str(e)}), 502

    assistant_msg = Message(
        conversation_id=conversation.id,
        role='assistant',
        content=result["answer"],
        sources=result["sources"],
        search_queries=result.get("search_queries", [])
    )
    db.session.add(assistant_msg)

    conversation.updated_at = db.func.now()
    db.session.commit()

    # Trigger Memory Extraction (Async)
    if prefs.memory_enabled:
        try:
            from app.tasks.memory_tasks import extract_memories_task
            
            # Prepare context: history + new exchange
            # Note: conversation_history was reversed earlier to be chronological logic, but let's verify.
            # Line 76: conversation_history = list(reversed(history_msgs)) -> So it IS chronological (oldest to newest).
            
            all_msgs = conversation_history + [user_msg, assistant_msg]
            msgs_dicts = [{'role': m.role, 'content': m.content} for m in all_msgs]
            
            extract_memories_task.delay(msgs_dicts)
        except Exception as e:
            logger.error(f"Failed to trigger memory task: {e}")

    response = result
    response['conversation_id'] = str(conversation.id)
    return jsonify(response)


@bp.route('/stream', methods=['POST'])
@limiter.limit("30 per minute")
def chat_stream():
    """SSE streaming chat endpoint. Same interface as POST /, returns text/event-stream."""
    data = request.json or {}
    question = data.get('question')
    doc_ids = data.get('document_ids', [])
    conversation_id = data.get('conversation_id')
    web_search = data.get('web_search', False)
    use_graph_rag = data.get('use_graph_rag', False)

    if not question:
        return jsonify({"error": "Question required"}), 400

    prefs = db.session.query(UserPreferences).first()
    if not prefs:
        prefs = UserPreferences(use_conversation_context=True, max_context_messages=10)
        db.session.add(prefs)
        db.session.commit()

    conversation = None
    if conversation_id:
        conversation = db.session.query(Conversation).get(conversation_id)
        if not conversation:
            return jsonify({"error": "Conversation not found"}), 404
    else:
        title = question[:80] + "..." if len(question) > 80 else question
        conversation = Conversation(title=title)
        db.session.add(conversation)
        db.session.commit()

    user_msg = Message(conversation_id=conversation.id, role='user', content=question)
    db.session.add(user_msg)
    db.session.commit()

    conversation_history = []
    if prefs.use_conversation_context and conversation_id:
        history_msgs = db.session.query(Message).filter(
            Message.conversation_id == conversation.id,
            Message.id != user_msg.id
        ).order_by(Message.created_at.desc()).limit(prefs.max_context_messages).all()
        conversation_history = list(reversed(history_msgs))

    system_prompt = None
    if prefs.selected_system_prompt_id:
        prompt_obj = db.session.query(SystemPrompt).get(prefs.selected_system_prompt_id)
        if prompt_obj:
            system_prompt = prompt_obj.content

    conv_id = str(conversation.id)

    top_k_stream = max(1, min(50, getattr(prefs, 'retrieval_top_k', 10)))

    @stream_with_context
    def generate():
        rag = RAGService(db.session)
        accumulated = ""
        sources = []
        try:
            for event in rag.stream_query(
                question=question,
                document_ids=doc_ids,
                top_k=top_k_stream,
                conversation_history=conversation_history,
                system_prompt=system_prompt,
                web_search=web_search,
                use_graph_rag=use_graph_rag,
            ):
                if event["type"] == "metadata":
                    sources = event.get("sources", [])
                    payload = {
                        "type": "metadata",
                        "sources": sources,
                        "search_queries": event.get("search_queries", []),
                        "conversation_id": conv_id,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                elif event["type"] == "token":
                    accumulated += event["delta"]
                    yield f"data: {json.dumps({'type': 'token', 'delta': event['delta']})}\n\n"
                elif event["type"] == "done":
                    accumulated = event.get("answer", accumulated)

            # Persist assistant message after stream completes
            assistant_msg = Message(
                conversation_id=conversation.id,
                role='assistant',
                content=accumulated,
                sources=sources,
                search_queries=[],
            )
            db.session.add(assistant_msg)
            conversation.updated_at = db.func.now()
            db.session.commit()

            yield f"data: {json.dumps({'type': 'done', 'done': True, 'message_id': str(assistant_msg.id)})}\n\n"

        except LLMError as e:
            logger.error(f"LLM stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream')
