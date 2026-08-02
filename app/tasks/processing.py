from app.extensions import celery_app, db
from app.models.document import Document
from app.models.chunk import Chunk
from app.services.transcription import TranscriptionService
from app.services.pdf_processor import PDFProcessor
from app.services.vision_service import VisionService
from app.services.chunker import ChunkerService
from app.services.epub_processor import EpubProcessor
from app.services.embedder import EmbedderService
from app.services.youtube import YouTubeService
from app.services.llm_client import get_llm_client
from config.settings import settings
from app.utils.archive import archive_file
import os
import logging
import time
from uuid import UUID
import requests
import json
from app.utils.hf_downloader import HFDownloader

# Configure Logger for Worker
logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=2, soft_time_limit=3300, time_limit=3600)
def process_document_task(self, document_id: str):
    """Process an uploaded document through the ingestion pipeline.

    Orchestration only - each stage lives in app/tasks/pipeline.py and records
    its own outcome on Document.metadata_['pipeline'].
    """
    from app import create_app
    from app.tasks import pipeline

    app = create_app()
    with app.app_context():
        try:
            logger.info(f"Starting processing for document {document_id}")

            doc = db.session.get(Document, UUID(document_id))
            if not doc:
                logger.error(f"Document {document_id} not found")
                return "Document not found"

            doc.status = 'processing'
            doc.processing_progress = 10
            db.session.commit()

            # Resume gate: the DB is the checkpoint. If chunks already exist,
            # extraction and embedding are skipped so an interrupted upload
            # does not re-burn local GPU time.
            existing_chunks = db.session.query(Chunk).filter_by(document_id=doc.id).count()
            if existing_chunks > 0:
                logger.info(
                    f"Resume: {existing_chunks} chunks already exist for doc {document_id}. "
                    f"Skipping extraction + embedding."
                )
                pipeline.record_stage(doc, 'extract', 'skipped', reason='chunks already exist')
                pipeline.set_progress(doc, 70)
            else:
                text_chunks = pipeline.stage_extract(doc)
                language = pipeline.stage_detect_language(doc, text_chunks)
                pipeline.stage_embed_and_save(doc, text_chunks, language)

            pipeline.stage_summarize(doc, _generate_summary_logic)
            pipeline.stage_hypergraph(doc)

            # Re-fetch: the user may have deleted the document mid-process.
            doc = db.session.get(Document, UUID(document_id))
            if not doc:
                logger.warning(
                    f"Document {document_id} was deleted during processing; nothing to finalize."
                )
                return "Deleted during processing"

            doc.status = 'completed'
            doc.processing_progress = 100
            db.session.commit()
            logger.info(f"Processing successfully completed for document {document_id}")
            return "Resumed and completed" if existing_chunks else "Processed"

        except Exception as e:
            logger.exception(f"Error processing document {document_id}")
            db.session.rollback()
            try:
                fresh = db.session.get(Document, UUID(document_id))
                if fresh:
                    fresh.status = 'error'
                    fresh.error_message = str(e)
                    db.session.commit()
            except Exception as inner:
                logger.error(f"Failed to mark doc as error (likely deleted): {inner}")
            raise


def _generate_summary_logic(document_id):
    """
    Helper function to generate summary for a document.
    Can be called from main processing task or independent summary task.
    """
    from app.services.summary_service import SummaryService
    try:
        SummaryService.generate_summary(document_id)
    except Exception as e:
        logger.error(f"Failed to generate summary (wrapper): {e}")

@celery_app.task(bind=True, max_retries=2, soft_time_limit=1800, time_limit=2000)
def generate_summary_task(self, document_id: str):
    """
    Standalone task to generate summary (e.g. retry).
    """
    from app import create_app
    app = create_app()
    with app.app_context():
        try:
             # Set status to processing so UI shows bar
             doc = db.session.get(Document, UUID(document_id))
             if doc:
                 doc.status = 'processing'
                 doc.processing_progress = 50 
                 db.session.commit()
                 
             _generate_summary_logic(document_id)
             
             # Mark done
             if doc:
                 doc.status = 'completed'
                 doc.processing_progress = 100
                 db.session.commit()
                 
             return "Summary generated"
        except Exception as e:
            logger.error(f"Error in generate_summary_task: {e}")
            # Ensure we don't leave it stuck if we can help it
            try:
                doc = db.session.get(Document, UUID(document_id))
                if doc:
                    doc.status = 'error'
                    doc.error_message = str(e)
                    db.session.commit()
            except:
                pass
            raise e

@celery_app.task(bind=True, max_retries=2, soft_time_limit=1800, time_limit=2000)
def reprocess_hypergraph_task(self, document_id: str):
    """
    Task to specifically re-run hypergraph extraction for a document.
    """
    from app import create_app
    app = create_app()
    with app.app_context():
        try:
            logger.info(f"Starting generic hypergraph reprocessing for {document_id}")
            from app.services.hypergraph_extractor import HypergraphExtractor
            
            # Simple wrapper
            HypergraphExtractor.process_document(document_id)
            return f"Hypergraph processed for {document_id}"
            
        except Exception as e:
            logger.error(f"Error in reprocess_hypergraph_task: {e}")
            raise e


@celery_app.task(bind=True)
def download_gguf_task(self, repo_id, filename, model_name):
    """
    Download a GGUF file from HF for llama.cpp.
    llama.cpp reads GGUF files directly from /models.
    """
    logger.info(f"Starting GGUF download: {repo_id}/{filename} as {model_name}")
    try:
        def progress_callback(current, total):
            if total > 0:
                percent = (current / total) * 100
                # Throttle updates slightly to avoid spamming Redis
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'status': 'downloading',
                        'progress': percent,
                        'current': current,
                        'total': total,
                        'model_name': model_name
                    }
                )

        # Download GGUF file to models directory
        dest_path = HFDownloader.download_file(repo_id, filename, progress_callback)
        logger.info(f"Download complete: {dest_path}")

        # For llama.cpp: No import step needed. The server loads GGUF files directly from /models.
        # Just verify the file exists and is readable
        if not os.path.exists(dest_path):
            raise Exception(f"Downloaded file not found at {dest_path}")

        file_size = os.path.getsize(dest_path)
        logger.info(f"Successfully downloaded {filename} ({file_size / (1024**3):.2f} GB)")
        logger.info(f"Model ready for llama.cpp at: {dest_path}")

        return {
            'status': 'success',
            'model_name': model_name,
            'path': dest_path,
            'filename': filename,
            'size_gb': round(file_size / (1024**3), 2)
        }

    except Exception as e:
        logger.error(f"GGUF Task failed: {e}")
        return {'status': 'failure', 'error': str(e)}
