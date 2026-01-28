from flask import Blueprint, jsonify, request
from app.extensions import db
from app.models.llm_connection import LLMConnection
from app.models.user_preferences import UserPreferences
from datetime import datetime

bp = Blueprint('connections', __name__, url_prefix='/api/settings/connections')

@bp.route('/', methods=['GET'])
def list_connections():
    """List all custom LLM connections."""
    try:
        connections = LLMConnection.query.order_by(LLMConnection.created_at.desc()).all()
        return jsonify({
            "connections": [c.to_dict() for c in connections]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/', methods=['POST'])
def create_connection():
    """Create a new LLM connection."""
    data = request.json
    name = data.get('name')
    base_url = data.get('base_url')
    api_key = data.get('api_key')
    
    if not name or not base_url:
        return jsonify({"error": "Name and base_url are required"}), 400
        
    try:
        # Check uniqueness
        if LLMConnection.query.filter_by(name=name).first():
            return jsonify({"error": "A connection with this name already exists"}), 400
            
        conn = LLMConnection(
            name=name,
            provider_type=data.get('provider_type', 'openai'),
            base_url=base_url,
            api_key=api_key,
            default_model=data.get('default_model'),
            models=data.get('models', [])
        )
        db.session.add(conn)
        db.session.commit()
        return jsonify(conn.to_dict()), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/<uuid:conn_id>', methods=['PUT'])
def update_connection(conn_id):
    """Update an existing connection."""
    try:
        conn = LLMConnection.query.get(conn_id)
        if not conn:
            return jsonify({"error": "Connection not found"}), 404
            
        data = request.json
        
        if 'name' in data:
            name = data['name']
            # Check unique if changed
            if name != conn.name and LLMConnection.query.filter_by(name=name).first():
                 return jsonify({"error": "Name already exists"}), 400
            conn.name = name
            
        if 'base_url' in data:
            conn.base_url = data['base_url']
            
        if 'api_key' in data:
             # Only update if provided and not empty mask
             if data['api_key'] != '***':
                 conn.api_key = data['api_key']
                 
        if 'default_model' in data:
            conn.default_model = data['default_model']
            
        if 'models' in data:
            conn.models = data['models']
            
        conn.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify(conn.to_dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/<uuid:conn_id>', methods=['DELETE'])
def delete_connection(conn_id):
    """Delete a connection."""
    try:
        conn = LLMConnection.query.get(conn_id)
        if not conn:
            return jsonify({"error": "Connection not found"}), 404
            
        # Check if active, if so, unset it?
        # Ideally we should handle referential integrity
        prefs = db.session.query(UserPreferences).first()
        if prefs and prefs.active_connection_id == conn.id:
            prefs.active_connection_id = None
            
        db.session.delete(conn)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/active', methods=['POST'])
def set_active_connection():
    """Set the active custom connection."""
    data = request.json
    conn_id = data.get('connection_id')
    
    try:
        prefs = db.session.query(UserPreferences).first()
        if not prefs:
            prefs = UserPreferences()
            db.session.add(prefs)
            
        if conn_id:
            # Verify existence
            conn = LLMConnection.query.get(conn_id)
            if not conn:
                return jsonify({"error": "Connection not found"}), 404
            prefs.active_connection_id = conn.id
            prefs.llm_provider = 'custom' # Force switch to custom provider mode
        else:
            prefs.active_connection_id = None
            
        db.session.commit()
        
        # Reset LLM client to pick up changes immediately
        from app.services.llm_client import reset_client
        reset_client()
        
        return jsonify({"success": True, "active_connection_id": conn_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
