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
    """
    Background task to process uploaded documents (PDF, Audio, Video, YouTube).
    """
    from app import create_app
    app = create_app()
    with app.app_context():
        try:
            logger.info(f"Starting processing for document {document_id}")
            
            doc = db.session.get(Document, UUID(document_id))
            if not doc:
                logger.error(f"Document {document_id} not found")
                return "Document not found"
            
            doc.status = 'processing'
            doc.processing_progress = 10  # Started
            db.session.commit()

            # Resume gate: if chunks already exist for this document, skip
            # extraction + embedding entirely and jump straight to summary/hypergraph.
            # The DB is our checkpoint — interrupted uploads don't re-burn local GPU time.
            existing_chunk_count = db.session.query(Chunk).filter_by(document_id=doc.id).count()
            if existing_chunk_count > 0:
                logger.info(f"Resume: {existing_chunk_count} chunks already exist for doc {document_id}. "
                            f"Skipping extraction + embedding.")
                doc.processing_progress = 70
                db.session.commit()

                if not doc.summary:
                    _generate_summary_logic(doc.id)
                else:
                    logger.info("Resume: summary already exists, skipping.")

                try:
                    from app.services.hypergraph_extractor import HypergraphExtractor
                    doc.processing_progress = 90
                    db.session.commit()
                    HypergraphExtractor.process_document(doc.id)
                except Exception as hg_e:
                    logger.error(f"Hypergraph extraction failed (non-blocking): {hg_e}")

                doc.status = 'completed'
                doc.processing_progress = 100
                db.session.commit()
                logger.info(f"Resume complete for document {document_id}")
                return "Resumed and completed"

            text_chunks = [] # List of {"text": str, "start": float, "end": float, "page": int}

            # 1. Extract Content
            logger.info(f"Extracting content for type: {doc.file_type}")
            if doc.file_type == 'youtube':
                yt_service = YouTubeService()
                # If it is a new download
                if not doc.file_path or doc.file_path.startswith('youtube_'):
                     logger.info(f"Downloading audio from YouTube: {doc.youtube_url}")
                     info = yt_service.download_audio(doc.youtube_url)
                     doc.file_path = info["filename"] # Update with actual filename on disk
                     doc.original_filename = info["title"]
                     doc.metadata_ = {
                         "duration": info["duration"],
                         "author": info["author"],
                         "description": info["description"][:1000] if info["description"] else "", # Truncate description
                         "title": info["title"]  # Redundant but useful for RAG context standardized keys
                     }
                     logger.info(f"YouTube download complete: {doc.file_path}")

                     # Archive downloaded YouTube audio if enabled
                     youtube_audio_path = os.path.join(settings.UPLOAD_FOLDER, doc.file_path)
                     if archive_file(youtube_audio_path, doc.file_path, 'youtube'):
                         logger.info(f"YouTube audio archived: {doc.file_path}")
                
                # Now treat as audio
                full_path = os.path.join(settings.UPLOAD_FOLDER, doc.file_path)
                transcriber = TranscriptionService()
                logger.info(f"Transcribing audio: {full_path}")
                segments = transcriber.transcribe(full_path)
                
                # Save transcription to file (Auto-save)
                try:
                    from sqlalchemy.orm.attributes import flag_modified
                    
                    os.makedirs(settings.TRANSCRIPTION_FOLDER, exist_ok=True)
                    transcription_filename = f"{doc.id}_transcription.txt"
                    transcription_path = os.path.join(settings.TRANSCRIPTION_FOLDER, transcription_filename)
                    if TranscriptionService.save_to_txt(segments, transcription_path):
                        logger.info(f"Saved transcription to {transcription_path}")
                        
                        # Force refresh metadata
                        db.session.refresh(doc)
                        current_meta = dict(doc.metadata_ or {})
                        current_meta["transcription_file"] = transcription_filename
                        doc.metadata_ = current_meta
                        flag_modified(doc, "metadata_")
                        
                        db.session.commit()
                except Exception as e:
                    logger.error(f"Error saving transcription file: {e}")

                # Merge small segments into meaningful chunks
                chunker = ChunkerService()
                text_chunks = chunker.chunk_transcript_segments(segments)
                
            elif doc.file_type in ['audio', 'video']:
                full_path = os.path.join(settings.UPLOAD_FOLDER, doc.file_path)
                transcriber = TranscriptionService()
                logger.info(f"Transcribing file: {full_path}")
                segments = transcriber.transcribe(full_path)
                
                # Save transcription to file (Auto-save)
                try:
                    from sqlalchemy.orm.attributes import flag_modified
                    os.makedirs(settings.TRANSCRIPTION_FOLDER, exist_ok=True)
                    transcription_filename = f"{doc.id}_{doc.filename}_transcription.txt"
                    transcription_path = os.path.join(settings.TRANSCRIPTION_FOLDER, transcription_filename)
                    
                    if TranscriptionService.save_to_txt(segments, transcription_path):
                        logger.info(f"Saved transcription to {transcription_path}")
                        current_meta = dict(doc.metadata_ or {})
                        current_meta["transcription_file"] = transcription_filename
                        doc.metadata_ = current_meta
                        flag_modified(doc, "metadata_")
                        db.session.commit()
                except Exception as e:
                    logger.error(f"Error saving transcription file: {e}")

                # Merge small segments into meaningful chunks
                chunker = ChunkerService()
                text_chunks = chunker.chunk_transcript_segments(segments)
                
            elif doc.file_type == 'pdf':
                full_path = os.path.join(settings.UPLOAD_FOLDER, doc.file_path)
                processor = PDFProcessor()
                logger.info(f"Extracting text from PDF: {full_path}")
                pages, metadata = processor.extract_text(full_path)

                # Update Metadata
                if metadata:
                    logger.info(f"Found metadata: {metadata}")
                    current_meta = doc.metadata_ or {}
                    current_meta.update(metadata)
                    doc.metadata_ = current_meta

                chunker = ChunkerService()
                logger.info(f"Chunking {len(pages)} pages of text")

                for page in pages:
                    sub_chunks = chunker.chunk_text(page["text"])
                    for i, sub in enumerate(sub_chunks):
                        # Sanitize text for Postgres (no null bytes)
                        clean_text = sub.replace('\x00', '')
                        text_chunks.append({
                            "text": clean_text,
                            "page": page["page"],
                            "chunk_index": i
                        })

                # Diagram extraction (opt-in via VISION_ENABLED)
                if settings.VISION_ENABLED:
                    try:
                        diagrams_dir = os.path.join(settings.UPLOAD_FOLDER, 'diagrams', str(doc.id))
                        images = processor.extract_images(full_path, diagrams_dir)[:settings.DIAGRAMS_MAX_PER_DOC]
                        logger.info(f"Found {len(images)} diagram(s) in PDF")

                        vision = VisionService()
                        for img in images:
                            description = vision.describe_image(img["image_path"], page_number=img["page"])
                            if description:
                                rel_path = os.path.relpath(img["image_path"], settings.UPLOAD_FOLDER)
                                text_chunks.append({
                                    "text": f"[Diagram on page {img['page']}] {description}".replace('\x00', ''),
                                    "page": img["page"],
                                    "chunk_index": len(text_chunks),
                                    "chunk_type": "diagram",
                                    "image_path": rel_path,
                                })
                    except Exception as diag_e:
                        logger.error(f"Diagram extraction failed: {diag_e}")

            elif doc.file_type == 'epub':
                full_path = os.path.join(settings.UPLOAD_FOLDER, doc.file_path)
                processor = EpubProcessor()
                logger.info(f"Extracting text from EPUB: {full_path}")
                pages, metadata = processor.process(full_path)
                
                # Update Metadata
                if metadata:
                    logger.info(f"Found metadata: {metadata}")
                    current_meta = doc.metadata_ or {}
                    current_meta.update(metadata)
                    doc.metadata_ = current_meta
                
                chunker = ChunkerService()
                logger.info(f"Chunking {len(pages)} chapters/sections of text")
                
                for page in pages:
                    sub_chunks = chunker.chunk_text(page["text"])
                    for i, sub in enumerate(sub_chunks):
                        clean_text = sub.replace('\x00', '')
                        text_chunks.append({
                            "text": clean_text,
                            "page": page["page"],
                            "chunk_index": i
                        })
            
            logger.info(f"Extraction complete. Total chunks: {len(text_chunks)}")
            doc.processing_progress = 30  # Extraction done
            db.session.commit()



            # 2. Vectorize and Save Chunks
            embedder = EmbedderService()

            # --- DETECT LANGUAGE (New Step) ---
            try:
                from langdetect import detect
                # Sample first 2000 chars for detection
                sample_text = " ".join([c["text"] for c in text_chunks[:5]])[:2000]
                detected_code = detect(sample_text)
                
                # Map to Postgres Dictionaries
                # Postgres supports: english, spanish, german, french, italian, etc.
                # We map codes to standard names. Fallback handled by Trigger ('simple').
                lang_map = {
                    'en': 'english',
                    'es': 'spanish',
                    'de': 'german',
                    'fr': 'french',
                    'it': 'italian',
                    'ru': 'russian',
                    'pt': 'portuguese',
                    'nl': 'dutch',
                    'sv': 'swedish',
                    'no': 'norwegian',
                    'da': 'danish',
                    'fi': 'finnish'
                }
                
                # Check for Chinese variants
                if detected_code.lower().startswith('zh'):
                    # To support Chinese, we typically need pg_jieba. 
                    # If not installed, our trigger maps unknown strings to 'simple'
                    # so we pass 'chinese' (or 'simple') as the value.
                    doc_language = 'simple' 
                else:
                    doc_language = lang_map.get(detected_code, 'simple')

                logger.info(f"Detected language: {detected_code} -> {doc_language}")
                
                doc.language = doc_language
                # Chunks will inherit this language in the loop below
                
                db.session.commit()
            except Exception as e:
                logger.error(f"Language detection failed: {e}. Defaulting to 'english'.")
                # Default is typically english or simple
                doc.language = 'simple'
                doc_language = 'simple'


            texts_to_embed = [c["text"] for c in text_chunks]
            if texts_to_embed:
                logger.info(f"Generating embeddings for {len(texts_to_embed)} chunks...")
                doc.processing_progress = 50
                db.session.commit()

                BATCH_SIZE = 100
                total = len(texts_to_embed)
                start_time = time.time()

                for batch_start in range(0, total, BATCH_SIZE):
                    batch_texts = texts_to_embed[batch_start:batch_start + BATCH_SIZE]
                    batch_data = text_chunks[batch_start:batch_start + BATCH_SIZE]
                    batch_embeddings = embedder.embed(batch_texts)

                    chunk_rows = []
                    for j, chunk_data in enumerate(batch_data):
                        chunk_meta = {k: chunk_data[k] for k in ("chunk_type", "image_path") if chunk_data.get(k)} or None
                        chunk_rows.append(Chunk(
                            document_id=doc.id,
                            content=chunk_data["text"],
                            chunk_index=batch_start + j,
                            start_time=chunk_data.get("start"),
                            end_time=chunk_data.get("end"),
                            page_number=chunk_data.get("page"),
                            embedding=batch_embeddings[j],
                            language=doc_language,
                            metadata_=chunk_meta
                        ))
                    db.session.add_all(chunk_rows)
                    db.session.flush()
                    logger.info(f"Saved chunks {batch_start + 1}–{batch_start + len(batch_texts)}/{total}")

                elapsed = time.time() - start_time
                logger.info(f"Embeddings + save complete in {elapsed:.2f}s ({total/elapsed:.1f} chunks/sec)")
                db.session.commit()
                doc.processing_progress = 70
                db.session.commit()
                logger.info(f"Saved {total} chunks to database")
                
                # --- Generate Document Summary (Summary Indexing) ---
                if not doc.summary:
                    _generate_summary_logic(doc.id)
                else:
                    logger.info("Summary already exists, skipping.")

                # --- Hypergraph Extraction (New Step) ---
                try:
                    from app.services.hypergraph_extractor import HypergraphExtractor
                    doc.processing_progress = 90
                    db.session.commit()
                    HypergraphExtractor.process_document(doc.id)
                except Exception as hg_e:
                    logger.error(f"Hypergraph extraction failed (non-blocking): {hg_e}")

                
            # Re-fetch in case the doc was deleted mid-process by the user
            doc = db.session.get(Document, UUID(document_id))
            if not doc:
                logger.warning(f"Document {document_id} was deleted during processing; nothing to finalize.")
                return "Deleted during processing"

            doc.status = 'completed'
            doc.processing_progress = 100
            db.session.commit()
            logger.info(f"Processing successfully completed for document {document_id}")

        except Exception as e:
            logger.exception(f"Error processing document {document_id}")
            db.session.rollback()
            # Re-fetch fresh — original `doc` may be stale or deleted
            try:
                fresh_doc = db.session.get(Document, UUID(document_id))
                if fresh_doc:
                    fresh_doc.status = 'error'
                    fresh_doc.error_message = str(e)
                    db.session.commit()
            except Exception as inner:
                logger.error(f"Failed to mark doc as error (likely deleted): {inner}")
            raise e

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
def download_model_task(self, model_name):
    """
    DEPRECATED: Celery task for downloading Ollama models.
    This is no longer used as the system now uses llama.cpp instead of Ollama.
    Use download_gguf_task for GGUF model downloads instead.
    """
    logger.error(f"download_model_task called but Ollama is deprecated. Use download_gguf_task instead.")
    return {
        'status': 'error',
        'model_name': model_name,
        'error': 'Ollama model downloads are deprecated. Please use GGUF downloads for llama.cpp instead.'
    }

@celery_app.task(bind=True)
def download_gguf_task(self, repo_id, filename, model_name):
    """
    Download a GGUF file from HF for llama.cpp.
    Note: Ollama import functionality is deprecated. llama.cpp reads GGUF files directly from /models.
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
