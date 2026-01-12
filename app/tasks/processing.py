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
import json
import docker
from app.utils.hf_downloader import HFDownloader

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
    """
    try:
        base_url = settings.OLLAMA_BASE_URL.replace("/v1", "")
        logger.info(f"Initiating background model download for: {model_name}")

        # Track download progress
        last_progress = None
        
        # Use simple json parsing to check for errors
        import json

        with requests.post(
            f"{base_url}/api/pull",
            json={"name": model_name},
            stream=True,
            timeout=1800  # 30 minutes timeout for the download
        ) as r:
            if r.status_code != 200:
                logger.error(f"Ollama API returned non-200 status: {r.status_code} - {r.text}")
                r.raise_for_status()

            # Process the response and send updates as the download progresses
            for line in r.iter_lines():
                if line:
                    try:
                        progress_str = line.decode('utf-8')
                        progress_data = json.loads(progress_str)
                        
                        # VERBOSE LOGGING:
                        # Log specific milestones or errors to server console
                        if 'error' in progress_data:
                            error_msg = progress_data['error']
                            logger.error(f"Ollama reported error during pull for {model_name}: {error_msg}")
                            raise Exception(f"Ollama API Error: {error_msg}")
                            
                        status = progress_data.get('status', '')
                        
                        # Log unique statuses to show progress in server logs
                        # Avoid logging every single percentage tick to keep logs readable but informative
                        if 'completed' in status or 'pulling manifest' in status or 'verifying' in status:
                             logger.info(f"[Pull {model_name}] {status}")
                             
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
                    except json.JSONDecodeError:
                        logger.warning(f"Could not parse progress line as JSON: {line}")
                    except Exception as e:
                        # Re-raise explicit API errors
                        if "Ollama API Error" in str(e):
                            raise e
                        logger.error(f"Error processing progress line: {e}")

        logger.info(f"Model download completed successfully for {model_name}")
        return {'status': 'success', 'model_name': model_name, 'last_progress': last_progress}

    except Exception as e:
        logger.error(f"TASK FAILED: Error downloading model {model_name}: {e}")
        return {'status': 'error', 'model_name': model_name, 'error': str(e)}

@celery_app.task(bind=True)
def download_gguf_task(self, repo_id, filename, model_name):
    """
    Download a GGUF file from HF and import it into Ollama.
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

        # 1. Download
        dest_path = HFDownloader.download_file(repo_id, filename, progress_callback)
        logger.info(f"Download complete: {dest_path}")

        # 2. Import to Ollama
        self.update_state(state='PROGRESS', meta={'status': 'importing', 'model_name': model_name})
        
        # Use Docker SDK to run CLI command directly in the Ollama container
        try:
            client = docker.from_env()
            container = client.containers.get('mnemos-ollama')
        except Exception as docker_e:
             raise Exception(f"Docker connection failed: {docker_e}")

        ollama_path = f"/root/.ollama/import/{filename}"
        # Sanitize model name for filename
        modelfile_name = f"Modelfile_{model_name.replace(':', '_').replace('/', '_')}"
        modelfile_path = f"/root/.ollama/{modelfile_name}"
        
        logger.info(f"Creating Modelfile inside container: {modelfile_path}")
        # Create Modelfile
        exit_code, output = container.exec_run(f'sh -c "echo \'FROM {ollama_path}\' > {modelfile_path}"')
        if exit_code != 0:
            raise Exception(f"Failed to create Modelfile: {output.decode()}")

        logger.info(f"Running ollama create {model_name}...")
        
        # Stream the CLI output
        exec_stream = container.exec_run(f"ollama create {model_name} -f {modelfile_path}", stream=True)
        
        for chunk in exec_stream.output:
            line = chunk.decode().strip()
            if line:
                logger.info(f"Ollama Import: {line}")
                self.update_state(state='PROGRESS', meta={'status': f"importing: {line[:50]}", 'model_name': model_name})
                
        # Cleanup Modelfile
        container.exec_run(f"rm {modelfile_path}")

        logger.info(f"Successfully imported {model_name}")
        return {'status': 'success', 'model_name': model_name}

    except Exception as e:
        logger.error(f"GGUF Task failed: {e}")
        return {'status': 'failure', 'error': str(e)}
