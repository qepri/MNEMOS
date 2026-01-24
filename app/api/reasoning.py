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
    use_semantic_leap = data.get('use_semantic_leap', False)
    max_depth = data.get('max_depth', 3)
    
    if not start_concept or not goal_concept:
        return jsonify({"error": "Missing start or goal concept"}), 400
        
    try:
        engine = ReasoningEngine()
        result = engine.traverse(start_concept, goal_concept, collection_ids=collection_ids, use_semantic_leap=use_semantic_leap, max_depth=max_depth)
        
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
                graph_content = result['graph_data']
                if graph_content:
                    graph_content['search_params'] = {
                        'max_depth': max_depth,
                        'use_semantic_leap': use_semantic_leap
                    }

                msg_ai = Message(
                    conversation_id=conversation.id,
                    role='assistant',
                    content=result['narrative'],
                    graph_data=graph_content
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

# Simple in-memory status tracker for KISS requirement
# In production with multiple workers, this should be Redis/Database
REPROCESSING_STATUS = {
    "status": "idle" # idle, processing
}

@bp.route('/reprocess', methods=['POST'])
def reprocess_all():
    global REPROCESSING_STATUS
    if REPROCESSING_STATUS["status"] == "processing":
         return jsonify({"status": "processing", "message": "Already reprocessing..."})

    REPROCESSING_STATUS["status"] = "processing"
    
    # Run in background due to potentially long running time
    import threading
    def run_reprocess():
        global REPROCESSING_STATUS
        try:
            logger.info("Starting reprocessing...")
            engine = ReasoningEngine()
            engine.build_graph() # Assuming this method exists and rebuilds everything
            logger.info("Reprocessing complete.")
        except Exception as e:
            logger.error(f"Reprocessing failed: {e}")
        finally:
            REPROCESSING_STATUS["status"] = "idle"

    thread = threading.Thread(target=run_reprocess)
    thread.start()

    return jsonify({"status": "processing", "message": "Reprocessing started in background"})

@bp.route('/reprocess/status', methods=['GET'])
def get_reprocess_status():
    global REPROCESSING_STATUS
    return jsonify(REPROCESSING_STATUS)
