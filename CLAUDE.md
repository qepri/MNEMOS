# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is MNEMOS

MNEMOS is a **GraphRAG + Wiki** system that processes documents (PDF, EPUB, audio, video, YouTube) into an interconnected knowledge hypergraph stored in PostgreSQL with pgvector. Users interact via an Angular 21 SPA or MCP tools.

## Development Commands

```bash
# Start all services (normal — GPU required for llamacpp)
docker-compose up -d --build

# Start without GPU (llamacpp will fail, everything else works)
docker-compose -f docker-compose.cpu.yml up -d

# Dev mode — auto-reload Flask on file change (app/ and config/ are bind-mounted)
docker-compose -f docker-compose.dev.yml up -d

# Watch logs
docker-compose logs -f app
docker-compose logs -f worker

# Run a single Flask route locally (needs local PostgreSQL + Redis)
docker-compose up -d db redis
flask run --debug

# Database backup / restore
docker-compose exec db pg_dump -U mnemos_user mnemos_db > backup.sql
cat backup.sql | docker-compose exec -T db psql -U mnemos_user mnemos_db

# Frontend dev (Angular SPA)
cd frontend_spa
npm install
npm run dev     # Vite dev server
npm run build   # Production build

# Rebuild llamacpp model only
docker-compose pull llamacpp
```

No test suite exists in the repo currently.

## Architecture

```
Angular SPA (:5200)
      │ REST
Flask app (:5000)  ──── Celery worker (same image, different command)
      │                        │
      └────────────────────────┤
                               ▼
                     PostgreSQL 16 + pgvector
                     Redis (task queue + cache)
                     llama.cpp server (:8082)
```

The **Flask app** and **Celery worker** run from the same Docker image. `app/` and `config/` are bind-mounted, so edits take effect without rebuilding.

## Document Processing Pipeline

All processing is async via Celery. Flow in `app/tasks/processing.py`:

1. **Extract** — routes by `file_type`:
   - `pdf` → `PDFProcessor.extract_text()` (PyMuPDF), optionally `extract_images()` + `VisionService` if `VISION_ENABLED=True`
   - `epub` → `EpubProcessor.process()` (ebooklib + BeautifulSoup)
   - `audio`/`video`/`youtube` → `TranscriptionService.transcribe()` (Whisper)
2. **Chunk** — `ChunkerService` (LangChain `RecursiveCharacterTextSplitter`)
3. **Language detect** — `langdetect` → stored on `Document.language` for FTS
4. **Embed** — `EmbedderService` (local sentence-transformers or remote OpenAI/Ollama/LM Studio), 100 chunks/batch
5. **Save** — `Chunk` rows with `embedding` (Vector), `search_vector` (TSVECTOR via DB trigger)
6. **Summarize** — `SummaryService` parallel Map-Reduce via LLM
7. **Hypergraph** — `HypergraphExtractor` two-pass LLM extraction → `Concept`, `HyperEdge`, `HyperEdgeMember`

Resume logic: if chunks already exist for a doc, skip extraction/embedding entirely and jump to summary/hypergraph.

## RAG Query Pipeline (`app/services/rag.py`)

1. Embed query → cosine vector search (pgvector HNSW)
2. PostgreSQL FTS with `plainto_tsquery`
3. Merge via Reciprocal Rank Fusion (RRF, k=60)
4. Re-rank with MMR (λ=0.7)
5. Expand with adjacent chunks (chunk_index ±1)
6. Optionally traverse `HyperEdge` graph for graph-RAG
7. Build hierarchical context: Document → Section → Chunk
8. Token budget check — drop lowest chunks if over limit
9. LLM generation with citations

## LLM Client (`app/services/llm_client.py`)

`LLMClient` is the unified abstraction. Provider priority: **constructor arg > DB (UserPreferences) > settings.py**.

Supported providers (`LLMProvider` enum in `config/settings.py`): `openai`, `anthropic`, `groq`, `cerebras`, `llamacpp`, `ollama`, `lm_studio`, `custom`.

All non-Anthropic providers use the OpenAI SDK with a custom `base_url`. Images are passed as base64 in `chat(images=[...])`.

`ModelManager` (singleton) holds the active model in memory and persists it to `UserPreferences.selected_llm_model`.

## Key Config (`config/settings.py` + `.env`)

All settings are `pydantic_settings.BaseSettings` — env vars override defaults.

| Setting | Purpose |
|---|---|
| `LLM_PROVIDER` | Active LLM backend |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` / `EMBEDDING_DIMENSION` | Must match — changing dimension requires a full re-embed |
| `LLAMACPP_BASE_URL` / `LLAMACPP_NUM_CTX` | Local inference server |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | Affects retrieval quality; per-user overrides in `UserPreferences` |
| `VISION_ENABLED` / `VISION_MODEL` | Enable diagram extraction from PDFs (opt-in) |
| `DIAGRAMS_MAX_PER_DOC` | Safety cap on images extracted per document (default 50) |

## Diagram / Vision Extraction (new)

When `VISION_ENABLED=True`, PDF processing also runs `PDFProcessor.extract_images()` (PyMuPDF) and sends each image to `VisionService.describe_image()`. Descriptions become chunks with `metadata_={"chunk_type": "diagram", "image_path": "<rel_path>"}`. Images are saved to `uploads/diagrams/{doc_id}/`. Set `VISION_MODEL` to use a different model than the main LLM (e.g. `deepseek-vl2`).

## Database

- Uses `db.create_all()` on startup — no migration runner needed for new tables during dev.
- Alembic (`flask db migrate / upgrade`) is used for production schema changes in `migrations/`.
- Ad-hoc schema fixes (e.g. `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`) run at startup in `app/__init__.py` for backwards-compat.
- `Chunk.search_vector` is maintained by a DB trigger (`update_chunk_search_vector`), not the application.
- `EMBEDDING_DIMENSION` in settings must match the pgvector column size. Changing it requires dropping and recreating the `chunks` table.

## Frontend (`frontend_spa/`)

Angular 21 SPA. Served by Nginx in Docker. The dev server proxies `/api` to `:5000`. Key libraries: TailwindCSS, RxJS, Cytoscape.js (graph viz), marked (markdown rendering).

## MCP Server

Runs as a long-lived idle container (`tail -f /dev/null`). Claude Desktop calls it via `docker exec -i dev-mcp-1 python -m app.mcp_server.server`.

### Claude Desktop Integration

Copy `claude_desktop_config.json` to the Claude Desktop config directory:

- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

The config connects via `docker exec` so the MCP server runs inside the existing `dev-mcp-1` container. All 30+ MNEMOS tools become available in Claude Desktop conversations.

## Common Patterns

- **Non-blocking errors**: hypergraph extraction, diagram extraction, and transcription file saves are wrapped in try/except and logged without failing the task.
- **Thread-local LLM clients**: `get_llm_client()` returns a thread-local singleton to avoid shared state in parallel Celery/ThreadPoolExecutor contexts.
- **JSONB metadata**: `Document.metadata_` and `Chunk.metadata_` are JSONB. Use `flag_modified(obj, "metadata_")` after mutating them in-place, or reassign the dict entirely.
- **`local_llm_model` in UserPreferences**: the DB column does not exist yet — access via `getattr(db_prefs, 'local_llm_model', None)` to avoid AttributeError.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
`specs/002-fix-mcp-uploads-volume/plan.md`
<!-- SPECKIT END -->
