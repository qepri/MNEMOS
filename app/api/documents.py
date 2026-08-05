import logging
from flask import Blueprint, request, jsonify, send_from_directory, Response
from werkzeug.utils import secure_filename
from app.models.document import Document
from app.models.section import DocumentSection
from app.tasks.processing import process_document_task
from app.extensions import db
from config.settings import settings
from app.utils.archive import archive_file
import os
from uuid import uuid4

logger = logging.getLogger(__name__)

bp = Blueprint('documents', __name__, url_prefix='/api/documents')

# Accepted extensions -> internal file_type. Anything not listed is rejected
# at the boundary rather than being guessed at.
ALLOWED_EXTENSIONS = {
    'pdf': 'pdf',
    'epub': 'epub',
    'mp3': 'audio', 'wav': 'audio', 'm4a': 'audio', 'opus': 'audio',
    'flac': 'audio', 'ogg': 'audio', 'aac': 'audio',
    'mp4': 'video', 'webm': 'video', 'mov': 'video',
    'mkv': 'video', 'avi': 'video',
}

MAX_UPLOAD_BY_TYPE = {
    'pdf': settings.MAX_UPLOAD_DOCUMENT,
    'epub': settings.MAX_UPLOAD_DOCUMENT,
    'audio': settings.MAX_UPLOAD_AUDIO,
    'video': settings.MAX_UPLOAD_VIDEO,
}


def detect_file_type(filename):
    """Map a filename to its internal file_type, or None if unsupported."""
    _, _, ext = filename.rpartition('.')
    return ALLOWED_EXTENSIONS.get(ext.lower()) if ext else None


def _uploaded_size(file_storage) -> int:
    """Size of an uploaded file without reading it into memory."""
    stream = file_storage.stream
    pos = stream.tell()
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(pos)
    return size

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
            from app.models.collection_document import collection_documents
            query = query.outerjoin(
                collection_documents,
                Document.id == collection_documents.c.document_id
            ).filter(
                db.or_(
                    Document.collection_id == collection_id,
                    collection_documents.c.collection_id == collection_id
                )
            ).distinct()
             
    documents = query.order_by(Document.created_at.desc()).all()
    
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

        # Validate before anything is persisted or queued.
        file_type = detect_file_type(file.filename)
        if file_type is None:
            accepted = ', '.join(sorted(ALLOWED_EXTENSIONS))
            return jsonify({
                "error": f"Unsupported file type. Accepted extensions: {accepted}"
            }), 400

        limit = MAX_UPLOAD_BY_TYPE[file_type]
        size = _uploaded_size(file)
        if size > limit:
            return jsonify({
                "error": (
                    f"File too large: {size / (1024**2):.1f} MB exceeds the "
                    f"{limit / (1024**2):.0f} MB limit for {file_type} uploads."
                )
            }), 413

        filename = secure_filename(file.filename)
        # Ensure unique filename to prevent overwrite
        saved_filename = f"{uuid4().hex}_{filename}"

        doc = Document(
            filename=saved_filename,
            original_filename=file.filename,
            file_type=file_type,
            status='pending'
        )
        file_path_disk = os.path.join(settings.UPLOAD_FOLDER, doc.filename)
        file.save(file_path_disk)
        logger.info(f"File saved to {file_path_disk}")
        doc.file_path = doc.filename

        # Archive file if enabled
        if archive_file(file_path_disk, saved_filename, doc.file_type):
            logger.info(f"File archived: {saved_filename}")
        
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
    
    return jsonify(doc.to_dict()), 201

@bp.route('/<string:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """Elimina un documento y su archivo."""
    from sqlalchemy import text
    logger.info(f"Deleting document {doc_id}")

    # Get file path before deletion
    doc = db.session.query(Document).get(doc_id)
    if not doc:
        logger.warning(f"Document {doc_id} not found for deletion")
        return "", 404

    file_path = doc.file_path
    file_type = doc.file_type

    # Delete file from disk if it exists
    if file_path and not file_path.startswith('youtube_'):
         full_path = os.path.join(settings.UPLOAD_FOLDER, file_path)
         if os.path.exists(full_path):
             try:
                 os.remove(full_path)
                 logger.info(f"Deleted file {full_path}")
             except Exception as e:
                 logger.error(f"Error deleting file {full_path}: {e}")

    # Also remove archive copy if present (best-effort — archive may not exist)
    if file_path and file_type:
        from app.utils.archive import get_archive_folder_for_type
        try:
            archive_path = os.path.join(get_archive_folder_for_type(file_type), file_path)
            if os.path.exists(archive_path):
                os.remove(archive_path)
                logger.info(f"Deleted archive copy {archive_path}")
        except Exception as e:
            logger.error(f"Error deleting archive copy for {file_path}: {e}")

    # Use raw SQL to avoid SQLAlchemy relationship tracking issues
    db.session.execute(text("DELETE FROM documents WHERE id = :id"), {"id": doc_id})
    db.session.commit()
    logger.info(f"Document {doc_id} deleted from DB")

    # Clean up orphan concepts
    try:
        result = db.session.execute(text("DELETE FROM concepts WHERE id NOT IN (SELECT concept_id FROM hyper_edge_members)"))
        db.session.commit()
        if result.rowcount > 0:
             logger.info(f"Cleanup: Removed {result.rowcount} orphan concepts.")
    except Exception as e:
        logger.warning(f"Orphan cleanup failed: {e}")
        db.session.rollback()

    return "", 200

@bp.route('/<string:doc_id>/status', methods=['GET'])
def get_document_status(doc_id):
    """Polling endpoint for status updates."""
    # Reduced logging here to avoid spamming
    doc = db.session.query(Document).get(doc_id)
    if not doc:
        return "", 404

    # `pipeline` is additive - existing consumers keep reading status/progress/
    # error unchanged. It lets the UI tell "no summary because no LLM" from
    # "summary generated" without a second request. Absent for documents
    # processed before per-stage records existed, so treat it as optional.
    return jsonify({
        "status": doc.status,
        "progress": doc.processing_progress,
        "error": doc.error_message,
        "pipeline": (doc.metadata_ or {}).get("pipeline"),
    })

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

@bp.route('/<string:doc_id>/sections', methods=['GET'])
def get_document_sections(doc_id):
    """Get all sections for a document with full details."""
    logger.info(f"Fetching sections for document {doc_id}")

    doc = db.session.query(Document).get(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    sections = db.session.query(DocumentSection).filter(
        DocumentSection.document_id == doc_id
    ).order_by(DocumentSection.start_page).all()

    sections_data = []
    for section in sections:
        section_dict = {
            "id": str(section.id),
            "title": section.title,
            "content": section.content,
            "start_page": section.start_page,
            "end_page": section.end_page,
            "metadata": section.metadata_
        }
        sections_data.append(section_dict)

    return jsonify(sections_data)

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
                # Also sync M2M: ensure doc is in this collection
                from app.models.collection import Collection
                coll = db.session.query(Collection).get(col_id)
                if coll and doc not in coll.documents:
                    coll.documents.append(doc)
        
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

@bp.route('/<string:doc_id>/summary', methods=['POST'])
def generate_summary(doc_id):
    """Manually trigger summary generation."""
    from app.tasks.processing import generate_summary_task
    
    doc = db.session.query(Document).get(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
        
    generate_summary_task.delay(doc_id)
    logger.info(f"Manual summary generation triggered for {doc_id}")
    
    return jsonify({'status': 'queued'}), 202

def _llm_backfill_candidates():
    """Documents that finished indexing but never got their LLM-dependent parts.

    Eligibility is a query, not a stored flag - a `needs_backfill` column would
    be a denormalization that goes stale against the data it describes.
    """
    from app.models.knowledge_graph import HyperEdge

    completed = db.session.query(Document).filter(Document.status == 'completed').all()
    with_edges = {
        row[0] for row in db.session.query(HyperEdge.source_document_id)
        .filter(HyperEdge.source_document_id.isnot(None)).distinct().all()
    }

    needs_summary = [d for d in completed if not d.summary]
    needs_concepts = [d for d in completed if d.id not in with_edges]
    return needs_summary, needs_concepts


@bp.route('/llm-backfill', methods=['GET'])
def llm_backfill_status():
    """How much work a backfill would be, so the UI can say '20 documents'
    before the user commits to it.
    """
    needs_summary, needs_concepts = _llm_backfill_candidates()
    return jsonify({
        'needs_summary': len(needs_summary),
        'needs_concepts': len(needs_concepts),
        'total': len({d.id for d in needs_summary} | {d.id for d in needs_concepts}),
    })


@bp.route('/llm-backfill', methods=['POST'])
def llm_backfill():
    """Generate summaries and concepts for already-indexed documents.

    Enqueues the existing per-document tasks rather than adding new ones -
    neither re-runs extraction or embedding, so a backfill never re-does the
    expensive part.

    Never triggered automatically. SummaryService fans out to five threads per
    document, so auto-backfilling a library the moment a provider is connected
    would saturate a local GPU for a long time without the user asking.
    """
    from app.tasks.processing import generate_summary_task, reprocess_hypergraph_task

    needs_summary, needs_concepts = _llm_backfill_candidates()

    for doc in needs_summary:
        generate_summary_task.delay(str(doc.id))
    for doc in needs_concepts:
        reprocess_hypergraph_task.delay(str(doc.id))

    queued = len({d.id for d in needs_summary} | {d.id for d in needs_concepts})
    logger.info(f"LLM backfill queued for {queued} document(s)")

    return jsonify({
        'status': 'queued',
        'summaries_queued': len(needs_summary),
        'concepts_queued': len(needs_concepts),
        'documents': queued,
    }), 202


@bp.route('/backfill-concepts', methods=['POST'])
def backfill_concepts():
    """
    One-shot: reads key_concepts from each document's metadata_ and upserts
    them into the Concept table. Safe to run multiple times (skips existing).
    Use this after upgrading to the version that writes concepts during summary.
    """
    from app.models.knowledge_graph import Concept
    from app.services.embedder import EmbedderService

    docs = db.session.query(Document).filter(Document.metadata_.isnot(None)).all()
    added = 0
    embedder = EmbedderService()

    for doc in docs:
        concepts_list = (doc.metadata_ or {}).get('key_concepts', [])
        for name in concepts_list:
            norm = name.lower().strip()
            if not norm:
                continue
            if db.session.query(Concept).filter_by(name=norm).first():
                continue
            concept = Concept(name=norm)
            concept.embedding = embedder.embed([norm])[0]
            db.session.add(concept)
            added += 1

    db.session.commit()
    logger.info(f"Backfill concepts: added {added} concepts from document metadata.")
    return jsonify({'status': 'done', 'added': added}), 200


@bp.route('/reprocess-hypergraph', methods=['POST'])
def reprocess_hypergraph():
    """
    Triggers background tasks to re-extract hypergraph data from documents.
    Supports 'missing_only' flag to avoid reprocessing existing graphs.
    """
    from app.tasks.processing import reprocess_hypergraph_task
    from app.models.knowledge_graph import HyperEdge
    
    data = request.get_json() or {}
    missing_only = data.get('missing_only', False)

    docs = db.session.query(Document).all()
    
    if missing_only:
        # Find documents that already have edges
        existing_doc_ids = db.session.query(HyperEdge.source_document_id).distinct().all()
        # Flatten list of tuples
        existing_ids = {str(row[0]) for row in existing_doc_ids if row[0]}
        
        # Filter docs
        docs = [d for d in docs if str(d.id) not in existing_ids]
        logger.info(f"Missing Only Mode: Found {len(docs)} documents needing processing out of {len(existing_ids)} existing.")

    count = 0
    
    for doc in docs:
        # Optional: Check if we have enough content/summary to extract from?
        # For now, just queue it, the task handles validation.
        reprocess_hypergraph_task.delay(str(doc.id))
        count += 1
        
    logger.info(f"Queued hypergraph reprocessing for {count} documents.")
    return jsonify({'status': 'queued', 'count': count, 'message': f'Started reprocessing {count} documents'}), 202

@bp.route('/<string:document_id>/collections', methods=['GET'])
def get_document_collections(document_id):
    """List all collections for a document."""
    from app.models.collection import Collection
    doc = db.session.query(Document).get(document_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    return jsonify([c.to_dict() for c in doc.collections])