from flask import Blueprint, request, render_template, jsonify
from app.services.rag import RAGService
from app.services.embedder import EmbedderService
from app.extensions import db
from app.models.conversation import Conversation, Message
from app.models.user_preferences import UserPreferences, SystemPrompt
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('chat', __name__, url_prefix='/api/chat')

@bp.route('/', methods=['POST'])
def chat():
    """Chat endpoint with RAG and conversation context support."""
    # Handle both multipart/form-data (HTMX) and JSON
    if request.is_json:
        data = request.json
        question = data.get('question')
        doc_ids = data.get('document_ids', [])
        conversation_id = data.get('conversation_id')
    else:
        question = request.form.get('question')
        doc_ids_str = request.form.get('document_ids', '')
        doc_ids = [d.strip() for d in doc_ids_str.split(',') if d.strip()]
        conversation_id = request.form.get('conversation_id')

    if not question:
        return jsonify({"error": "Question required"}), 400

    # Load user preferences
    prefs = db.session.query(UserPreferences).first()
    if not prefs:
        # Create default preferences if none exist
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
        # Create new conversation
        title = question[:40] + "..." if len(question) > 40 else question
        conversation = Conversation(title=title)
        db.session.add(conversation)
        db.session.commit()

    # Save User Message
    user_msg = Message(
        conversation_id=conversation.id,
        role='user',
        content=question
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

    # Perform RAG with conversation context
    rag = RAGService(db.session)
    result = rag.query(
        question=question,
        document_ids=doc_ids,
        top_k=5,
        conversation_history=conversation_history,
        system_prompt=system_prompt
    )

    # Save Assistant Message
    assistant_msg = Message(
        conversation_id=conversation.id,
        role='assistant',
        content=result["answer"],
        sources=result["sources"]
    )
    db.session.add(assistant_msg)

    # Update conversation timestamp
    conversation.updated_at = db.func.now()
    db.session.commit()

    if request.headers.get('HX-Request'):
        return render_template(
            'partials/chat_messages.html',
            question=question,
            answer=result["answer"],
            sources=result["sources"],
            conversation_id=conversation.id,
            message_id=assistant_msg.id,
            context_warning=result.get("context_warning")
        )

    response = result
    response['conversation_id'] = str(conversation.id)
    return jsonify(response)
