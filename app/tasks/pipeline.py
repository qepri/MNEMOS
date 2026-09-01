"""Document processing pipeline, split into discrete resumable stages.

Each stage is a small function with one job, so `process_document_task` reads
as an ordered list of steps rather than one long branch. Stage outcomes are
recorded on `Document.metadata_['pipeline']`, which makes it possible to see
where a document stopped without reading the worker log.

Services are injected as optional arguments so a stage can be exercised with a
fake in future tests; the defaults preserve current behaviour.
"""
import logging
import os
import time

from sqlalchemy.orm.attributes import flag_modified

from app.extensions import db
from app.models.chunk import Chunk
from app.services.chunker import ChunkerService
from app.services.embedder import EmbedderService
from app.services.epub_processor import EpubProcessor
from app.services.pdf_processor import PDFProcessor
from app.services.transcription import TranscriptionService
from app.services.vision_service import VisionService
from app.services.youtube import YouTubeService
from app.utils.archive import archive_file
from config.settings import settings

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 100

# langdetect code -> PostgreSQL text search configuration. Must stay in sync
# with chunk_ts_config() in the a006 migration and RAGService._PG_LANG_MAP:
# if index-time and query-time configurations disagree, keyword search
# silently returns nothing.
PG_LANG_MAP = {
    'en': 'english', 'es': 'spanish', 'de': 'german', 'fr': 'french',
    'it': 'italian', 'ru': 'russian', 'pt': 'portuguese', 'nl': 'dutch',
    'sv': 'swedish', 'no': 'norwegian', 'da': 'danish', 'fi': 'finnish',
}


def record_stage(doc, stage: str, status: str, **extra) -> None:
    """Persist per-stage progress on the document.

    Uses the existing metadata_ JSONB column rather than adding a schema
    change. flag_modified is required because we mutate in place.
    """
    meta = dict(doc.metadata_ or {})
    pipeline = dict(meta.get('pipeline') or {})
    pipeline[stage] = {"status": status, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), **extra}
    meta['pipeline'] = pipeline
    doc.metadata_ = meta
    flag_modified(doc, "metadata_")
    db.session.commit()


def set_progress(doc, percent: int) -> None:
    doc.processing_progress = percent
    db.session.commit()


def _save_transcription(doc, segments, filename: str) -> None:
    """Write the transcript alongside the media. Non-blocking by design."""
    try:
        os.makedirs(settings.TRANSCRIPTION_FOLDER, exist_ok=True)
        path = os.path.join(settings.TRANSCRIPTION_FOLDER, filename)
        if TranscriptionService.save_to_txt(segments, path):
            logger.info(f"Saved transcription to {path}")
            db.session.refresh(doc)
            meta = dict(doc.metadata_ or {})
            meta["transcription_file"] = filename
            doc.metadata_ = meta
            flag_modified(doc, "metadata_")
            db.session.commit()
    except Exception as e:
        logger.error(f"Error saving transcription file: {e}")


def _transcribe_to_chunks(doc, full_path: str, transcript_name: str,
                          transcriber=None, chunker=None) -> list:
    transcriber = transcriber or TranscriptionService()
    chunker = chunker or ChunkerService()
    logger.info(f"Transcribing: {full_path}")
    segments = transcriber.transcribe(full_path)
    _save_transcription(doc, segments, transcript_name)
    return chunker.chunk_transcript_segments(segments)


def extract_youtube(doc, yt_service=None, **kw) -> list:
    yt_service = yt_service or YouTubeService()

    # Only download when this is a fresh record; a retry reuses the audio.
    if not doc.file_path or doc.file_path.startswith('youtube_'):
        logger.info(f"Downloading audio from YouTube: {doc.youtube_url}")
        info = yt_service.download_audio(doc.youtube_url)
        doc.file_path = info["filename"]
        doc.original_filename = info["title"]
        doc.metadata_ = {
            "duration": info["duration"],
            "author": info["author"],
            "description": (info["description"] or "")[:1000],
            "title": info["title"],
        }
        logger.info(f"YouTube download complete: {doc.file_path}")

        audio_path = os.path.join(settings.UPLOAD_FOLDER, doc.file_path)
        if archive_file(audio_path, doc.file_path, 'youtube'):
            logger.info(f"YouTube audio archived: {doc.file_path}")

    full_path = os.path.join(settings.UPLOAD_FOLDER, doc.file_path)
    return _transcribe_to_chunks(doc, full_path, f"{doc.id}_transcription.txt", **kw)


def extract_media(doc, **kw) -> list:
    full_path = os.path.join(settings.UPLOAD_FOLDER, doc.file_path)
    return _transcribe_to_chunks(
        doc, full_path, f"{doc.id}_{doc.filename}_transcription.txt", **kw
    )


def _merge_metadata(doc, metadata: dict) -> None:
    if not metadata:
        return
    logger.info(f"Found metadata: {metadata}")
    meta = dict(doc.metadata_ or {})
    meta.update(metadata)
    doc.metadata_ = meta
    flag_modified(doc, "metadata_")


def _pages_to_chunks(pages, chunker) -> list:
    chunks = []
    for page in pages:
        for i, sub in enumerate(chunker.chunk_text(page["text"])):
            chunks.append({
                # Postgres rejects null bytes in text columns.
                "text": sub.replace('\x00', ''),
                "page": page["page"],
                "chunk_index": i,
            })
    return chunks


def _extract_diagrams(doc, processor, full_path: str, start_index: int) -> list:
    """Describe embedded images via the vision model. Opt-in, non-blocking."""
    chunks = []
    try:
        diagrams_dir = os.path.join(settings.UPLOAD_FOLDER, 'diagrams', str(doc.id))
        images = processor.extract_images(full_path, diagrams_dir)[:settings.DIAGRAMS_MAX_PER_DOC]
        logger.info(f"Found {len(images)} diagram(s) in PDF")

        vision = VisionService()
        for img in images:
            description = vision.describe_image(img["image_path"], page_number=img["page"])
            if not description:
                continue
            chunks.append({
                "text": f"[Diagram on page {img['page']}] {description}".replace('\x00', ''),
                "page": img["page"],
                "chunk_index": start_index + len(chunks),
                "chunk_type": "diagram",
                "image_path": os.path.relpath(img["image_path"], settings.UPLOAD_FOLDER),
            })
    except Exception as e:
        logger.error(f"Diagram extraction failed: {e}")
    return chunks


def extract_pdf(doc, processor=None, chunker=None) -> list:
    processor = processor or PDFProcessor()
    chunker = chunker or ChunkerService()
    full_path = os.path.join(settings.UPLOAD_FOLDER, doc.file_path)

    logger.info(f"Extracting text from PDF: {full_path}")
    pages, metadata = processor.extract_text(full_path)
    _merge_metadata(doc, metadata)

    logger.info(f"Chunking {len(pages)} pages of text")
    chunks = _pages_to_chunks(pages, chunker)

    if settings.VISION_ENABLED:
        chunks.extend(_extract_diagrams(doc, processor, full_path, len(chunks)))
    return chunks


def extract_epub(doc, processor=None, chunker=None) -> list:
    processor = processor or EpubProcessor()
    chunker = chunker or ChunkerService()
    full_path = os.path.join(settings.UPLOAD_FOLDER, doc.file_path)

    logger.info(f"Extracting text from EPUB: {full_path}")
    pages, metadata = processor.process(full_path)
    _merge_metadata(doc, metadata)

    logger.info(f"Chunking {len(pages)} chapters/sections of text")
    return _pages_to_chunks(pages, chunker)


def extract_text_file(doc, chunker=None) -> list:
    """Read a plain-text file and chunk it.

    No parsing step: the file already IS the text. Encoding is decoded as UTF-8
    and falls back to latin-1, which never raises — a legal or archival document
    that arrives in cp1252 should be indexed with a couple of odd characters
    rather than rejected outright.

    Everything ends up on page 1 because a .txt has no pages. That keeps the
    page column honest instead of inventing pagination that does not exist.
    """
    chunker = chunker or ChunkerService()
    full_path = os.path.join(settings.UPLOAD_FOLDER, doc.file_path)

    logger.info(f"Reading text file: {full_path}")
    raw = open(full_path, 'rb').read()
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        logger.info("Not valid UTF-8, falling back to latin-1")
        text = raw.decode('latin-1')

    if not text.strip():
        raise ValueError("Text file is empty")

    return _pages_to_chunks([{"text": text.strip(), "page": 1}], chunker)


EXTRACTORS = {
    'youtube': extract_youtube,
    'audio': extract_media,
    'video': extract_media,
    'pdf': extract_pdf,
    'epub': extract_epub,
    'text': extract_text_file,
}


def stage_extract(doc) -> list:
    """Route to the extractor for this file type and return raw chunk dicts."""
    logger.info(f"Extracting content for type: {doc.file_type}")
    extractor = EXTRACTORS.get(doc.file_type)
    if extractor is None:
        raise ValueError(f"Unsupported file type: {doc.file_type}")

    text_chunks = extractor(doc)
    logger.info(f"Extraction complete. Total chunks: {len(text_chunks)}")
    record_stage(doc, 'extract', 'completed', chunks=len(text_chunks))
    set_progress(doc, 30)
    return text_chunks


def stage_detect_language(doc, text_chunks: list) -> str:
    """Pick the Postgres text search configuration for this document.

    'simple' is the deliberate fallback for unsupported languages - it indexes
    without stemming rather than mis-stemming with the wrong dictionary.
    """
    try:
        from langdetect import detect
        sample = " ".join(c["text"] for c in text_chunks[:5])[:2000]
        code = detect(sample)
        # Chinese needs pg_jieba, which is not installed.
        language = 'simple' if code.lower().startswith('zh') else PG_LANG_MAP.get(code, 'simple')
        logger.info(f"Detected language: {code} -> {language}")
    except Exception as e:
        logger.error(f"Language detection failed: {e}. Falling back to 'simple'.")
        language = 'simple'

    doc.language = language
    db.session.commit()
    record_stage(doc, 'detect_language', 'completed', language=language)
    return language


def stage_embed_and_save(doc, text_chunks: list, language: str, embedder=None) -> int:
    """Embed in batches and persist Chunk rows. Returns rows written."""
    if not text_chunks:
        record_stage(doc, 'embed', 'skipped', reason='no content extracted')
        return 0

    embedder = embedder or EmbedderService()
    total = len(text_chunks)
    logger.info(f"Generating embeddings for {total} chunks...")
    set_progress(doc, 50)

    started = time.time()
    for batch_start in range(0, total, EMBED_BATCH_SIZE):
        batch = text_chunks[batch_start:batch_start + EMBED_BATCH_SIZE]
        embeddings = embedder.embed([c["text"] for c in batch])

        db.session.add_all([
            Chunk(
                document_id=doc.id,
                content=data["text"],
                chunk_index=batch_start + j,
                start_time=data.get("start"),
                end_time=data.get("end"),
                page_number=data.get("page"),
                embedding=embeddings[j],
                language=language,
                metadata_={
                    k: data[k] for k in ("chunk_type", "image_path") if data.get(k)
                } or None,
            )
            for j, data in enumerate(batch)
        ])
        db.session.flush()
        logger.info(f"Saved chunks {batch_start + 1}-{batch_start + len(batch)}/{total}")

    db.session.commit()
    elapsed = time.time() - started
    logger.info(f"Embeddings + save complete in {elapsed:.2f}s ({total / elapsed:.1f} chunks/sec)")

    set_progress(doc, 70)
    record_stage(doc, 'embed', 'completed', chunks=total)
    return total


def stage_summarize(doc, summary_fn) -> None:
    """Generate the document summary. Non-blocking, like stage_hypergraph.

    A document whose chunks and embeddings are already committed (see the
    commit at the end of stage_embed_and_save) is fully searchable without a
    summary, so an unreachable LLM records a failed stage rather than failing
    the document.

    The recorded outcome is what the UI reads to tell "no summary because no
    LLM" from "summary generated" - so it must reflect what actually happened.
    """
    if doc.summary:
        logger.info("Summary already exists, skipping.")
        record_stage(doc, 'summarize', 'skipped', reason='already present')
        return
    try:
        summary_fn(doc.id)
    except Exception as e:
        logger.error(f"Summary generation failed (non-blocking): {e}")
        record_stage(doc, 'summarize', 'failed', error=str(e))
        return

    # SummaryService swallows per-batch LLM errors internally (a failed map
    # batch is dropped and logged, and the reduce step tolerates an empty set),
    # so returning without raising does not mean a summary was produced. The
    # honest signal is whether one actually landed on the document.
    if doc.summary:
        record_stage(doc, 'summarize', 'completed')
    else:
        record_stage(doc, 'summarize', 'failed',
                     error='no summary produced (LLM unreachable?)')


def stage_hypergraph(doc) -> None:
    """Extract concepts/edges. Non-blocking: failure must not fail the task."""
    set_progress(doc, 90)
    try:
        from app.services.hypergraph_extractor import HypergraphExtractor
        HypergraphExtractor.process_document(doc.id)
    except Exception as e:
        logger.error(f"Hypergraph extraction failed (non-blocking): {e}")
        record_stage(doc, 'hypergraph', 'failed', error=str(e))
        return

    # Same caveat as stage_summarize: the extractor drops failed batches and
    # returns normally when none produced usable output, so "did not raise" is
    # not "worked". Count the edges it was supposed to create instead.
    from app.models.knowledge_graph import HyperEdge
    if db.session.query(HyperEdge).filter_by(source_document_id=doc.id).count():
        record_stage(doc, 'hypergraph', 'completed')
    else:
        record_stage(doc, 'hypergraph', 'failed',
                     error='no concepts extracted (LLM unreachable?)')
