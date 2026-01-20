import logging
from flask import Blueprint, request, jsonify
from app.models.collection import Collection
from app.extensions import db
from sqlalchemy.exc import IntegrityError
from uuid import UUID

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bp = Blueprint('collections', __name__, url_prefix='/api/collections')

@bp.route('/', methods=['GET'])
def list_collections():
    """List all collections."""
    logger.info("Listing collections")
    collections = db.session.query(Collection).order_by(Collection.name.asc()).all()
    return jsonify([c.to_dict() for c in collections])

@bp.route('/', methods=['POST'])
def create_collection():
    """Create a new collection."""
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'Name is required'}), 400

    try:
        collection = Collection(
            name=data['name'],
            description=data.get('description')
        )
        db.session.add(collection)
        db.session.commit()
        logger.info(f"Collection created: {collection.id}")
        return jsonify(collection.to_dict()), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Collection with this name already exists'}), 409
    except Exception as e:
        logger.error(f"Error creating collection: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/<string:collection_id>', methods=['PUT'])
def update_collection(collection_id):
    """Update a collection."""
    data = request.get_json()
    collection = db.session.query(Collection).get(collection_id)
    
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404

    try:
        if 'name' in data:
            collection.name = data['name']
        if 'description' in data:
            collection.description = data['description']
        
        db.session.commit()
        logger.info(f"Collection updated: {collection_id}")
        return jsonify(collection.to_dict()), 200
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Collection name conflict'}), 409
    except Exception as e:
        logger.error(f"Error updating collection: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/<string:collection_id>', methods=['DELETE'])
def delete_collection(collection_id):
    """Delete a collection."""
    collection = db.session.query(Collection).get(collection_id)
    
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404

    try:
        # Note: Documents related to this collection will have collection_id set to NULL
        # (or cascade delete if configured, currently manual handling might be safer or rely on DB constraint)
        # Using default SQLAlchemy behavior which defaults to setting null if not cascade delete-orphan, 
        # but documents backref didn't specify cascade. Let's assume we just unlink them or DB SET NULL.
        # Actually our migration didn't specify ON DELETE CASCADE, so it will fail if we don't handle documents.
        # Let's unlink documents first for safety if not configured at DB level.
        
        documents = collection.documents
        for doc in documents:
            doc.collection_id = None
        
        db.session.delete(collection)
        db.session.commit()
        logger.info(f"Collection deleted: {collection_id}")
        return "", 204
    except Exception as e:
        logger.error(f"Error deleting collection: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500
