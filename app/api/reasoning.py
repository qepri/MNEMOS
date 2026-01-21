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
    
    if not start_concept or not goal_concept:
        return jsonify({"error": "Missing start or goal concept"}), 400
        
    try:
        engine = ReasoningEngine()
        result = engine.traverse(start_concept, goal_concept)
        
        # Result is now a dict { "narrative": str, "graph_data": dict }
        if isinstance(result, str):
             # Handle error strings returned by traverse
             return jsonify({"narrative": result, "graph_data": None})
             
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Traversal error: {e}")
        return jsonify({"error": str(e)}), 500
