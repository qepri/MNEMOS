from app.extensions import celery_app, db
from app.models.document import Document
from app.models.chunk import Chunk
from app.services.transcription import TranscriptionService
from app.services.pdf_processor import PDFProcessor
from app.services.chunker import ChunkerService
from app.services.epub_processor import EpubProcessor
from app.services.embedder import EmbedderService
from app.services.youtube import YouTubeService
from config.settings import settings
import os
import logging
import time
from uuid import UUID
import requests

# Configure Logger for Worker
logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
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
                
                # Now treat as audio
                full_path = os.path.join(settings.UPLOAD_FOLDER, doc.file_path)
                transcriber = TranscriptionService()
                logger.info(f"Transcribing audio: {full_path}")
                segments = transcriber.transcribe(full_path)
                
                # Merge small segments into meaningful chunks
                chunker = ChunkerService()
                text_chunks = chunker.chunk_transcript_segments(segments)
                
            elif doc.file_type in ['audio', 'video']:
                full_path = os.path.join(settings.UPLOAD_FOLDER, doc.file_path)
                transcriber = TranscriptionService()
                logger.info(f"Transcribing file: {full_path}")
                segments = transcriber.transcribe(full_path)
                
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

            texts_to_embed = [c["text"] for c in text_chunks]
            if texts_to_embed:
                logger.info(f"Generating embeddings for {len(texts_to_embed)} chunks...")
                doc.processing_progress = 50  # Starting embeddings
                db.session.commit()

                start_time = time.time()
                embeddings = embedder.embed(texts_to_embed)

                elapsed = time.time() - start_time
                logger.info(f"Embeddings generated in {elapsed:.2f}s ({len(texts_to_embed)/elapsed:.1f} chunks/sec)")
                doc.processing_progress = 80  # Embeddings done
                db.session.commit()

                # Save chunks to database
                logger.info("Saving chunks to database...")
                for i, chunk_data in enumerate(text_chunks):
                    new_chunk = Chunk(
                        document_id=doc.id,
                        content=chunk_data["text"],
                        chunk_index=i,
                        start_time=chunk_data.get("start"),
                        end_time=chunk_data.get("end"),
                        page_number=chunk_data.get("page"),
                        embedding=embeddings[i]
                    )
                    db.session.add(new_chunk)
                logger.info(f"Saved {len(text_chunks)} chunks to database")
                doc.processing_progress = 95  # Saving done
                db.session.commit()

            doc.status = 'completed'
            doc.processing_progress = 100
            db.session.commit()
            logger.info(f"Processing successfully completed for document {document_id}")

        except Exception as e:
            logger.exception(f"Error processing document {document_id}")
            db.session.rollback()
            if 'doc' in locals() and doc:
                 doc.status = 'error'
                 doc.error_message = str(e)
                 db.session.commit()
            raise e

@celery_app.task(bind=True)
def download_model_task(self, model_name):
    """
    Celery task for downloading a model in the background.
    This allows the API to return immediately while the download runs in the background.
    """
    try:
        base_url = settings.OLLAMA_BASE_URL.replace("/v1", "")

        # Track download progress
        last_progress = None

        with requests.post(
            f"{base_url}/api/pull",
            json={"name": model_name},
            stream=True,
            timeout=1800  # 30 minutes timeout for the download
        ) as r:
            r.raise_for_status()

            # Process the response and send updates as the download progresses
            for line in r.iter_lines():
                if line:
                    try:
                        progress_str = line.decode('utf-8')
                        # Update the task state with progress
                        self.update_state(
                            state='PROGRESS',
                            meta={
                                'status': 'downloading',
                                'progress_line': progress_str,
                                'model_name': model_name
                            }
                        )
                        last_progress = progress_str
                    except Exception as e:
                        logger.error(f"Error processing progress line: {e}")

        logger.info(f"Model download completed for {model_name}")
        return {'status': 'success', 'model_name': model_name, 'last_progress': last_progress}

    except Exception as e:
        logger.error(f"Error downloading model {model_name}: {e}")
        return {'status': 'error', 'model_name': model_name, 'error': str(e)}
