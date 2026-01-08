from flask import Blueprint, jsonify, request
from app.services.memory_service import MemoryService
from uuid import UUID

bp = Blueprint('memory', __name__)
service = MemoryService()

@bp.route('/', methods=['GET'])
def get_memories():
    memories = service.get_memories()
    prefs = service.get_preferences()
    return jsonify({
        'memories': [m.to_dict() for m in memories],
        'usage': {
            'current': len(memories),
            'max': prefs.max_memories if prefs else 50
        }
    })

@bp.route('/<uuid:memory_id>', methods=['DELETE'])
def delete_memory(memory_id):
    success = service.delete_memory(memory_id)
    if success:
        return jsonify({'status': 'success'})
    return jsonify({'error': 'Memory not found'}), 404
