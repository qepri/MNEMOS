from flask import Blueprint, request, jsonify
from app.services.reasoning_engine import ReasoningEngine
import logging

logger = logging.getLogger(__name__)
bp = Blueprint('reasoning', __name__, url_prefix='/api/reasoning')

@bp.route('/traverse', methods=['POST'])
def traverse_graph():
    """
    Find a path between two concepts.
    Body: { "start": "ConceptA", "goal": "ConceptB" }
    """
    data = request.json
    start_concept = data.get('start')
    goal_concept = data.get('goal')
    collection_ids = data.get('collection_ids', [])
    save_to_chat = data.get('save_to_chat', False)
    
    if not start_concept or not goal_concept:
        return jsonify({"error": "Missing start or goal concept"}), 400
        
    try:
        engine = ReasoningEngine()
        result = engine.traverse(start_concept, goal_concept, collection_ids=collection_ids)
        
        # Result is now a dict { "narrative": str, "graph_data": dict }
        if isinstance(result, str):
             # Handle error strings returned by traverse
             return jsonify({"narrative": result, "graph_data": None})
        
        # Auto-Save to Chat if requested
        conversation_id = None
        if save_to_chat:
            try:
                from app.models.conversation import Conversation, Message
                from app.extensions import db
                
                # Title: Reasoning: Start -> Goal
                title = f"Reasoning: {start_concept} -> {goal_concept}"
                conversation = Conversation(title=title)
                db.session.add(conversation)
                db.session.flush()
                
                # User Prompt
                msg_user = Message(
                    conversation_id=conversation.id,
                    role='user',
                    content=f"Find logical path from '{start_concept}' to '{goal_concept}'"
                )
                db.session.add(msg_user)
                
                # AI Response
                msg_ai = Message(
                    conversation_id=conversation.id,
                    role='assistant',
                    content=result['narrative'],
                    graph_data=result['graph_data']
                )
                db.session.add(msg_ai)
                db.session.commit()
                conversation_id = str(conversation.id)
            except Exception as e:
                logger.error(f"Failed to save reasoning to chat: {e}")
                # Don't fail the request, just log it? Or maybe notify user.
                # We'll return the ID handling in the response so UI knows.

        response = result.copy()
        if conversation_id:
            response['conversation_id'] = conversation_id
            
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Traversal error: {e}")
        return jsonify({"error": str(e)}), 500
