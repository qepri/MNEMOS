from flask import Blueprint, request, jsonify, render_template
from app.models.conversation import Conversation, Message
from app.extensions import db
from sqlalchemy import or_

bp = Blueprint('conversations', __name__, url_prefix='/api/conversations')

@bp.route('/', methods=['POST'])
def create_conversation():
    data = request.json or {}
    title = data.get('title', "New Conversation")
    
    conversation = Conversation(title=title)
    db.session.add(conversation)
    db.session.commit()
    
    return jsonify(conversation.to_dict()), 201

@bp.route('/', methods=['GET'])
def list_conversations():
    search = request.args.get('search', '').strip()
    query = db.session.query(Conversation).order_by(Conversation.updated_at.desc())
    
    if search:
        query = query.filter(Conversation.title.ilike(f'%{search}%'))
        
    conversations = query.all()
    
    if request.headers.get('HX-Request'):
        return render_template('partials/conversation_list.html', conversations=conversations)
        
    return jsonify([c.to_dict() for c in conversations])

@bp.route('/<string:conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    conversation = db.session.query(Conversation).get(conversation_id)
    if not conversation:
        return jsonify({"error": "Conversation not found"}), 404
        
    messages = conversation.messages
    
    # Extract related documents from message sources
    related_doc_ids = set()
    source_filenames = set()
    
    for msg in messages:
        if msg.sources:
            for source in msg.sources:
                if 'document' in source:
                    source_filenames.add(source['document'])
                    
    if source_filenames:
        from app.models.document import Document
        docs = db.session.query(Document.id).filter(Document.original_filename.in_(source_filenames)).all()
        related_doc_ids = {str(d.id) for d in docs}
    
    if request.headers.get('HX-Request'):
        # Pass messages to the chat interface to be rendered
        return render_template(
            'partials/chat_history.html', 
            messages=messages, 
            conversation=conversation,
            related_document_ids=list(related_doc_ids)
        )
        
    return jsonify({
        "conversation": conversation.to_dict(),
        "messages": [m.to_dict() for m in messages],
        "related_document_ids": list(related_doc_ids)
    })

@bp.route('/<string:conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    conversation = db.session.query(Conversation).get(conversation_id)
    if not conversation:
        return jsonify({"error": "Conversation not found"}), 404
        
    db.session.delete(conversation)
    db.session.commit()
    
    return "", 200
