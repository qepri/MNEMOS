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
docker-compose exec -T db pg_dump -U mnemos_user mnemos_db > backups/mnemos_db_$(date +%Y%m%d-%H%M%S).sql
cat backup.sql | docker-compose exec -T db psql -U mnemos_user mnemos_db

# Migrations (Alembic — see Database section below)
docker exec dev-app-1 flask db upgrade      # apply pending revisions
docker exec dev-app-1 flask db current      # show current revision
docker exec dev-app-1 flask db history      # list all revisions

# Frontend dev (Angular SPA)
cd frontend_spa
npm install
npm run dev     # Vite dev server
npm run build   # Production build

# Rebuild llamacpp model only
docker-compose pull llamacpp

# Backend tests (host-side, disposable Postgres+Redis via testcontainers — needs Docker running)
python -m pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.in -r requirements-dev.txt
pytest                    # API/service/pipeline suite (real DB, faked LLM/embedding HTTP calls)
pytest -m migration       # Alembic upgrade/downgrade round-trip (separate process — see tests/migrations/conftest.py)
pytest --cov              # coverage report; RAG/processing-pipeline groups are gated against coverage-baseline.json

# Frontend tests (Vitest via Angular's native @angular/build:unit-test)
cd frontend_spa && npm test
```

Never run tests against the live/dev database — `pytest`'s fixtures always provision a disposable container on a random port and refuse to start if pointed at the compose stack's database. See `specs/004-test-suite/quickstart.md` for full details and troubleshooting.

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
4. **Embed** — `EmbedderService` (local sentence-transformers or remote OpenAI/LM Studio), 100 chunks/batch
5. **Save** — `Chunk` rows with `embedding` (Vector), `search_vector` (TSVECTOR via DB trigger)
6. **Summarize** — `SummaryService` parallel Map-Reduce via LLM
7. **Hypergraph** — `HypergraphExtractor` two-pass LLM extraction → `Concept`, `HyperEdge`, `HyperEdgeMember`

Resume logic: if chunks already exist for a doc, skip extraction/embedding entirely and jump to summary/hypergraph.

Each stage is a discrete function in `app/tasks/pipeline.py` (`stage_extract`, `stage_detect_language`, `stage_embed_and_save`, `stage_summarize`, `stage_hypergraph`); `process_document_task` in `processing.py` is a thin orchestrator over them. Every stage's outcome is recorded on `Document.metadata_['pipeline']`.

## RAG Query Pipeline (`app/services/rag.py`)

1. Embed query → cosine vector search (pgvector HNSW)
2. PostgreSQL FTS with `plainto_tsquery`
3. Merge via Reciprocal Rank Fusion (RRF, k=60)
4. Re-rank with MMR (λ=0.7)
5. Expand with adjacent chunks (chunk_index ±1)
6. Optionally traverse `HyperEdge` graph for graph-RAG
7. Build hierarchical context: Document → Section → Chunk (`app/services/rag_context.py`)
8. Token budget check — drop lowest chunks if over limit
9. LLM generation with citations

Chunks only participate in retrieval when `document_ids` is passed to `RAGService.query()`; with none selected, the model answers from its own knowledge and returns no sources — this is intended, not a bug.

## LLM Client (`app/services/llm_client.py`)

`LLMClient` is the unified abstraction. Provider priority: **constructor arg > DB (UserPreferences) > settings.py**. Dispatch is table-driven (`PROVIDER_SPECS` in `llm_client.py`) rather than if/elif; `LM_STUDIO` and `CUSTOM` (connection-driven) are handled separately since they need extra logic.

Supported providers (`LLMProvider` enum in `config/settings.py`): `openai`, `anthropic`, `groq`, `cerebras`, `deepseek`, `llamacpp`, `lm_studio`, `custom`. An unrecognized stored provider value (e.g. a stale `ollama` from before the migration) falls back to `llamacpp` with a warning instead of raising.

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

- **Alembic is the only migration path.** `app/__init__.py` performs zero DDL at startup — no `db.create_all()`, no ad-hoc `ALTER TABLE`. (Earlier versions of this file claimed otherwise; that was never actually true — `migrations/` held a single raw `.sql` script with no Alembic scaffolding until the schema was baselined.)
- Migrations run from `entrypoint.sh` via `flask db upgrade`, gated on `RUN_MIGRATIONS=true`. Only the `app` service sets that env var — `worker` and `mcp` must not, or concurrent starts race on the same schema.
- To add a schema change: edit models, then `docker exec dev-app-1 flask db migrate -m "description"`, review the generated revision by hand (destructive ops — DROP TABLE/COLUMN/INDEX — must be intentional and called out), then `flask db upgrade`.
- The baseline revision (`594d02684e1e_baseline_live_schema.py`) was hand-verified against the live database, not generated as a raw diff. Superseded raw SQL lives in `migrations_archive/` for history only.
- `chunks.search_vector` **is** maintained by a DB trigger (`update_chunk_search_vector`, created in the `a005_chunks_fts` / `a006_fix_ts_config` revisions) — but this was not always true. The trigger did not exist before this migration adoption; every chunk's `search_vector` was `NULL` and keyword search silently returned nothing. The trigger's language config must stay in sync with `RAGService._detect_query_language` and the `lang_map` in `app/tasks/pipeline.py` — a mismatch between index-time and query-time configs silently breaks matches again.
- `EMBEDDING_DIMENSION` in settings must match the pgvector column size (currently 1024, model `BAAI/bge-m3`). Changing it requires dropping and recreating the `chunks` table and re-embedding everything — do not do this casually.

## Health, Uploads, Workers

- `GET /api/health` — liveness only (db + redis reachable). Unchanged by this feature; the launcher polls it.
- `GET /api/settings/llm-availability` — three-state (`unconfigured` / `unreachable` / `available`), cached ~30s, invalidated through `reset_client()`. Always `200`: no LLM is a supported state, not an outage. **MNEMOS indexes and searches without an LLM** — extraction, chunking, embedding and the whole retrieval stack are LLM-free. Summaries, chat, and the concept graph/wiki are opt-in and render a dormant state (`app-llm-dormant`) until a provider is connected. `stage_summarize` and `stage_hypergraph` are both non-blocking and record `failed` on `Document.metadata_['pipeline']`; neither may ever set `status='error'`, because a document with chunks is still fully searchable.
- Both `SummaryService` and `HypergraphExtractor` swallow LLM errors internally, so "did not raise" does not mean "worked" — the stages check the actual outcome (`doc.summary`, and a `HyperEdge` count) instead. If you add another LLM-dependent stage, check its output, not its exceptions.
- `GET /api/ready` — readiness: liveness plus `flask db current == flask db heads` and a short-timeout probe of llama.cpp's `/health`. Can be `503` while `/api/health` is `200` — e.g. llama.cpp cold-starting is normal and does not mean the app is down.
- Uploads are validated at the boundary in `app/api/documents.py` (`detect_file_type`, `MAX_UPLOAD_BY_TYPE`): unsupported extensions get `400`, oversize gets `413`. Limits are per type in `config/settings.py` (`MAX_UPLOAD_DOCUMENT` 512MB, `MAX_UPLOAD_AUDIO` 2GB, `MAX_UPLOAD_VIDEO` 8GB) — there is no more single 50GB cap.
- Celery worker pool is env-configurable: `CELERY_POOL` (default `solo`) and optional `CELERY_CONCURRENCY`. Solo is the default on purpose — the worker loads embedding models onto the same GPU llama.cpp occupies, so concurrent tasks would contend for VRAM.
- `adminer` is opt-in behind a compose profile: `docker-compose --profile tools up -d adminer`. It is not started by `start-dev.bat` or the default `docker-compose up`.
- Ports 5000 (API) and 5200 (SPA) are intentionally reachable from the LAN, not just localhost — mobile access to the SPA is a supported use case and there is currently no authentication layer. `db`, `redis`, and `adminer` are bound to `127.0.0.1` only.

## Frontend (`frontend_spa/`)

Angular 21 SPA. Served by Nginx in Docker. The dev server proxies `/api` to `:5000`. Key libraries: TailwindCSS, RxJS, Cytoscape.js (graph viz), marked (markdown rendering).

## MCP Server

Runs as a long-lived idle container (`tail -f /dev/null`). Claude Desktop calls it via `docker exec -i dev-mcp-1 python -m app.mcp_server.server`.

Tools are split into per-domain modules under `app/mcp_server/`: `tools_graph.py`, `tools_search.py`, `tools_collections.py`, `tools_documents.py`, `tools_conversations.py`, `tools_settings.py`, `tools_legacy.py`. They share one `FastMCP`/`MCPServer` instance and helpers (`_validate_uuid`, `_version_footer`, `_format_document`) from `_shared.py`. `server.py` is just the entry point that imports every module for its registration side effects — add a new tool to the module matching its domain, not to `server.py`.

`_shared.py` imports `MCPServer` from `mcp.server.mcpserver` if available, falling back to `FastMCP` from `mcp.server.fastmcp` for `mcp` SDK 1.x — the `mcp` package renamed the class in 2.0. If tool registration ever breaks after a dependency bump, check this shim first.

## Keeping the API surface in sync (do this whenever you add/change a route)

The REST API is exposed three ways, and they drift silently — nothing fails a build when they disagree. When you add, remove, or change the contract of a route under `app/api/`, update **all** of these in the same change:

1. **MCP tool** — if the capability is useful to an agent, add/adjust the matching `@mcp.tool()` in the domain module under `app/mcp_server/` (`tools_search.py`, `tools_documents.py`, …). MCP tools do **not** auto-derive from Flask routes; they are hand-written wrappers, usually calling the same service the route calls (e.g. `search_passages` mirrors `POST /api/documents/search`, both calling `RAGService.search_similar_chunks`). Not every route needs a tool (health probes, file streaming) — use judgement, but a new user-facing capability normally does.
2. **`swagger.json`** (project root) — add/edit the path entry. This is a hand-maintained OpenAPI file served at `/api/docs`, not generated from the code, so it only stays correct if you edit it. Validate it parses (`node -e "JSON.parse(require('fs').readFileSync('swagger.json','utf8'))"`).
3. **`README.md`** — it is bilingual (Spanish then English); the "API — Endpoints / Endpoints Principales" table and, for MCP changes, the "Herramientas MCP / MCP Tools" list appear **twice**. Update both language halves, or they contradict each other.

A route that ships without its MCP tool and swagger entry is considered incomplete.

### Claude Desktop Integration

Copy `claude_desktop_config.json` to the Claude Desktop config directory:

- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

The config connects via `docker exec` so the MCP server runs inside the existing `dev-mcp-1` container. All 30+ MNEMOS tools become available in Claude Desktop conversations.

## Common Patterns

- **Non-blocking errors**: hypergraph extraction, diagram extraction, and transcription file saves are wrapped in try/except and logged without failing the task.
- **Thread-local LLM clients**: `get_llm_client()` returns a thread-local singleton to avoid shared state in parallel Celery/ThreadPoolExecutor contexts.
- **JSONB metadata**: `Document.metadata_` and `Chunk.metadata_` are JSONB. Use `flag_modified(obj, "metadata_")` after mutating them in-place, or reassign the dict entirely.
- **Either Docker or Podman**: `runtime-detect.bat` picks one and both launchers call it — never re-implement detection. Docker is preferred when both are present **because named volumes are runtime-bound**: `postgres_data` under Docker does not exist under Podman, so defaulting to Podman on a dual-runtime machine boots an empty database and the user's library appears to vanish. `MNEMOS_RUNTIME=docker|podman` overrides and must fail loudly rather than fall back. The same `docker-compose` binary drives both; only `DOCKER_HOST` differs. To run the test suite under Podman: `DOCKER_HOST=npipe:////./pipe/podman-machine-default` (add `TESTCONTAINERS_RYUK_DISABLED=true` if Ryuk misbehaves).
- **Releases are tag-locked**: pushing a `v*` tag triggers `.github/workflows/release-images.yml`, which builds CPU-torch images, pushes them to GHCR as `:vX.Y.Z` + `:sha-<commit>`, and creates the GitHub Release that `install.ps1` resolves. `MNEMOS_VERSION` in `.env` is the only switch onto the pulled-image path (`docker-compose.release.yml` + `--no-build`); dev machines never have it. The CPU image is produced by installing `requirements.lock.txt` with the PyTorch CPU index in front **and the 16 `nvidia-*`/`triton` lines filtered out** — that lock was compiled in a CUDA environment, so CPU torch alone would still pull the whole CUDA runtime in behind it. It must stay a single pip invocation: `--prefix` installs are invisible to a later pip run, so an earlier "install torch first" step gets silently overwritten by the lock (this shipped a `+cu130` image on the first release attempt). The workflow's smoke check — `torch.__version__` must end `+cpu` — is the real guard. Runbook: `specs/008-prebuilt-images/quickstart.md`.
- **Compose override files must use `!reset null`, not `[]`**, to clear a list inherited from `docker-compose.yml`. Compose *merges* sequences like `deploy.resources.reservations.devices` rather than replacing them, so `devices: []` is a silent no-op — `docker-compose.cpu.yml` carried that bug unnoticed for a long time and it would have kept the `driver: nvidia` reservation on GPU-less machines. Verify any override with `docker-compose -f a.yml -f b.yml config` before trusting it.
- **Container images run as a non-root user** (`mnemos`, uid 1000). Model caches (Whisper, HuggingFace) live under `/home/mnemos/.cache/...`, not `/root/.cache/...` — if you add a new cache path, mount and `chown` it accordingly in the Dockerfile and compose files together, or the non-root process won't be able to write it.
- **Structured JSON logs**: `app/logging_config.py` installs one JSON-per-line formatter for both Flask and Celery. A `request_id` is generated per HTTP request (or taken from an inbound `X-Request-ID` header), echoed back in the response, and propagated into Celery task headers — so a request and the background task it triggers share one id across both logs.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
`specs/009-refactor-ragservice-query/plan.md`
<!-- SPECKIT END -->
