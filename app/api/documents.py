import logging
from flask import Blueprint, request, render_template, jsonify, send_from_directory, Response
from werkzeug.utils import secure_filename
from app.models.document import Document
from app.tasks.processing import process_document_task
from app.extensions import db
from config.settings import settings
import os
from uuid import uuid4

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bp = Blueprint('documents', __name__, url_prefix='/api/documents')

def detect_file_type(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    if ext == 'pdf':
        return 'pdf'
    if ext == 'epub':
        return 'epub'
    if ext in ['mp3', 'wav', 'm4a', 'opus']:
        return 'audio'
    if ext in ['mp4', 'webm', 'mov']:
        return 'video'
    return 'audio' # Default / Fallback

@bp.route('/', methods=['GET'])
def list_documents():
    """Lista documentos - retorna partial HTML para HTMX o JSON."""
    logger.info("Listing documents")
    
    collection_id = request.args.get('collection_id')
    query = db.session.query(Document)
    
    if collection_id:
        if collection_id == 'null':
             query = query.filter(Document.collection_id.is_(None))
        else:
             query = query.filter(Document.collection_id == collection_id)
             
    documents = query.order_by(Document.created_at.desc()).all()
    
    if request.headers.get('HX-Request') and not request.headers.get('HX-History-Restore-Request'):
        return render_template('partials/document_list.html', documents=documents)
    
    return jsonify([d.to_dict() for d in documents])

@bp.route('/upload', methods=['POST'])
def upload_document():
    """Sube documento y encola procesamiento."""
    logger.info("Received upload request")
    file = request.files.get('file')
    youtube_url = request.form.get('youtube_url')
    
    doc = None
    
    if file and file.filename:
        logger.info(f"Processing file upload: {file.filename}")
        filename = secure_filename(file.filename)
        # Ensure unique filename to prevent overwrite
        saved_filename = f"{uuid4().hex}_{filename}"
        
        doc = Document(
            filename=saved_filename,
            original_filename=file.filename,
            file_type=detect_file_type(file.filename),
            status='pending'
        )
        file_path_disk = os.path.join(settings.UPLOAD_FOLDER, doc.filename)
        file.save(file_path_disk)
        logger.info(f"File saved to {file_path_disk}")
        doc.file_path = doc.filename
        
    elif youtube_url:
        logger.info(f"Processing YouTube URL: {youtube_url}")
        doc = Document(
            filename=f"youtube_{uuid4().hex[:8]}",
            original_filename=youtube_url, # Will be updated after download
            file_type='youtube',
            youtube_url=youtube_url,
            status='pending'
        )
    else:
        logger.error("No file or URL provided in upload request")
        return jsonify({"error": "No file or URL provided"}), 400
    
    db.session.add(doc)
    db.session.commit()
    logger.info(f"Document created with ID: {doc.id}")
    
    process_document_task.delay(str(doc.id))
    logger.info(f"Task enqueued for document {doc.id}")
    
    if request.headers.get('HX-Request'):
        return render_template('partials/document_item.html', document=doc)
    
    return jsonify(doc.to_dict()), 201

@bp.route('/<string:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """Elimina un documento y su archivo."""
    logger.info(f"Deleting document {doc_id}")
    doc = db.session.query(Document).get(doc_id)
    if not doc:
        logger.warning(f"Document {doc_id} not found for deletion")
        return "", 404
        
    # Delete file from disk if it exists
    if doc.file_path and not doc.file_path.startswith('youtube_'):
         # Note: file_path should be just basename in our model currently
         full_path = os.path.join(settings.UPLOAD_FOLDER, doc.file_path)
         if os.path.exists(full_path):
             try:
                 os.remove(full_path)
                 logger.info(f"Deleted file {full_path}")
             except Exception as e:
                 logger.error(f"Error deleting file {full_path}: {e}")
    
    db.session.delete(doc)
    db.session.commit()
    logger.info(f"Document {doc_id} deleted from DB")
    
    return "", 200

@bp.route('/<string:doc_id>/status', methods=['GET'])
def get_document_status(doc_id):
    """HTMX polling endpoint for status updates."""
    # Reduced logging here to avoid spamming
    doc = db.session.query(Document).get(doc_id)
    if not doc:
        return "", 404
        
    if request.headers.get('HX-Request'):
        return render_template('partials/document_item.html', document=doc)
        
    return jsonify({"status": doc.status, "error": doc.error_message})

@bp.route('/<string:doc_id>/content', methods=['GET'])
def get_document_content(doc_id):
    """Serve the document file content."""
    doc = db.session.query(Document).get(doc_id)
    if not doc or not doc.file_path:
        return "", 404
    
    # Ensure it's not a youtube "file" (which are URLs)
    if doc.file_type == 'youtube':
        return "", 400

    return send_from_directory(settings.UPLOAD_FOLDER, doc.file_path)

@bp.route('/<string:doc_id>', methods=['PUT'])
def update_document(doc_id):
    """Update document metadata."""
    data = request.get_json()
    doc = db.session.query(Document).get(doc_id)
    
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    try:
        if 'tag' in data:
            doc.tag = data['tag']
        if 'stars' in data:
            doc.stars = int(data['stars'])
        if 'comment' in data:
            doc.comment = data['comment']
        if 'collection_id' in data:
            col_id = data['collection_id']
            if col_id is None or col_id == "":
                doc.collection_id = None
            else:
                doc.collection_id = col_id
        
        db.session.commit()
        logger.info(f"Document updated: {doc_id}")
        return jsonify(doc.to_dict()), 200
    except Exception as e:
        logger.error(f"Error updating document: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/<string:doc_id>/transcribe', methods=['POST'])
def generate_transcription(doc_id):
    """Generates transcription for an existing audio/video document."""
    from app.services.transcription import TranscriptionService
    
    doc = db.session.query(Document).get(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
        
    # Check if we already have one
    if doc.metadata_ and doc.metadata_.get('transcription_file'):
         # If forced? For now, just return success
         return jsonify({'status': 'exists', 'file': doc.metadata_['transcription_file']}), 200

    if doc.file_type not in ['audio', 'video', 'youtube']:
        return jsonify({'error': 'Document type not supported for transcription'}), 400

    try:
        # Determine path
        full_path = os.path.join(settings.UPLOAD_FOLDER, doc.file_path)
        
        # Transcribe
        transcriber = TranscriptionService()
        segments = transcriber.transcribe(full_path)
        
        # Save
        os.makedirs(settings.TRANSCRIPTION_FOLDER, exist_ok=True)
        transcription_filename = f"{doc.id}_{doc.filename}_transcription.txt"
        transcription_path = os.path.join(settings.TRANSCRIPTION_FOLDER, transcription_filename)
        
        if TranscriptionService.save_to_txt(segments, transcription_path):
             current_meta = doc.metadata_ or {}
             current_meta["transcription_file"] = transcription_filename
             doc.metadata_ = current_meta
             db.session.commit()
             return jsonify({'status': 'completed', 'file': transcription_filename}), 200
        else:
             return jsonify({'error': 'Failed to save transcription file'}), 500
             
    except Exception as e:
        logger.error(f"Error generating transcription: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/<string:doc_id>/transcription', methods=['GET'])
def download_transcription(doc_id):
    """Download the transcription file."""
    doc = db.session.query(Document).get(doc_id)
    if not doc:
        return "", 404
        
    filename = None
    if doc.metadata_ and doc.metadata_.get('transcription_file'):
        filename = doc.metadata_['transcription_file']
    
    # Fallback check if file exists manually (e.g. migration)
    if not filename:
         potential_file = f"{doc.id}_transcription.txt"
         if os.path.exists(os.path.join(settings.TRANSCRIPTION_FOLDER, potential_file)):
             filename = potential_file

    if not filename:
        return "", 404
        
    return send_from_directory(settings.TRANSCRIPTION_FOLDER, filename, as_attachment=True)