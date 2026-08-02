---

description: "Task list for Production Readiness — Local-Only, Single-User Deployment"
---

# Tasks: Production Readiness — Local-Only, Single-User Deployment

**Input**: Design documents from `/specs/003-production-readiness/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: No test tasks are generated. Unit/e2e suites are explicitly out of scope (HC-5). Verification is by measured checks — row counts, greps, complexity measurement, live endpoint polls — drawn from `quickstart.md`. Refactoring tasks still require dependency-injection-friendly structure so a future suite is cheap.

**Organization**: Tasks are grouped by user story. Phase 2 (User Story 0) is both a user story and the blocking foundational gate — **no migration work may begin until it completes**.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US0–US5)
- Exact file paths are included in every task

## Path Conventions

Brownfield repository, existing layout retained. Backend at `app/`, config at `config/`, frontend at `frontend_spa/src/app/`, orchestration at repo root (`docker-compose*.yml`, `Dockerfile`, `entrypoint.sh`, `start-dev.bat`).

## ⚠️ Hard Constraints (apply to EVERY task)

- **Never** run `docker-compose down -v`; never remove the `postgres_data` or `redis_data` volumes. Stop the stack with `docker-compose stop`.
- **Never** DROP or recreate the `chunks` table. Never re-embed. `EMBEDDING_DIMENSION` stays 1024; model stays `BAAI/bge-m3`.
- The only intended destructive schema operation in this entire feature is T063 (`DROP COLUMN user_preferences.ollama_num_ctx`). Any other proposed DROP means something is wrong — **stop and surface it**.
- Reference row counts to preserve: **documents=58, chunks=6150, collections=8, conversations=143**.

---

## Phase 1: Setup (Baseline Measurement)

**Purpose**: Capture the "before" state so success criteria are measurable at the end.

- [X] T001 Confirm the stack is running and healthy (`docker-compose ps`), and record image/tool versions to `specs/003-production-readiness/baseline-metrics.md`
- [X] T002 [P] Record baseline Python line counts to `specs/003-production-readiness/baseline-metrics.md` via `find app -name "*.py" -not -path "*__pycache__*" -exec wc -l {} + | sort -rn | head -20` (expect server.py 1783, settings.py 1278, rag.py 723, processing.py 500)
- [X] T003 [P] Install `radon` in the app container and record baseline cyclomatic complexity for `app/tasks/processing.py`, `app/api/settings.py`, `app/services/llm_client.py` into `specs/003-production-readiness/baseline-metrics.md` (verify the reported CC 44 for `process_document_task` and CC 45 for `save_chat_settings`)
- [X] T004 [P] Record baseline grep counts for `ollama` and `render_template` to `specs/003-production-readiness/baseline-metrics.md`

---

## Phase 2: User Story 0 - Data Safety Gate (Priority: P1) 🚧 BLOCKING FOUNDATION

**Goal**: A restorable snapshot exists and reference counts are recorded before anything can touch the schema.

**Independent Test**: A timestamped `pg_dump` exists in `backups/`, is non-empty, and restores into a scratch database with `chunks` = 6150.

**⚠️ CRITICAL**: T005–T010 MUST complete before Phase 6 (Alembic) begins. No task in any later phase may run a migration until this checkpoint passes.

- [X] T005 [US0] Verify `backups/` exists and is git-ignored (already present at `.gitignore:230` — confirm, do not duplicate the entry)
- [X] T006 [US0] Take a fresh timestamped dump: `docker-compose exec -T db pg_dump -U mnemos_user mnemos_db > backups/mnemos_db_$(date +%Y%m%d-%H%M%S).sql`, and confirm the file is non-empty (expect ~230 MB)
- [X] T007 [US0] Record reference row counts (documents, chunks, collections, conversations) into `specs/003-production-readiness/baseline-metrics.md` using the query in `quickstart.md` §0
- [X] T008 [US0] Record vector integrity (populated count, null count, `vector_dims`) into `specs/003-production-readiness/baseline-metrics.md` — expect 6150 / 0 / 1024
- [X] T009 [US0] Restore the dump into a scratch database `restore_test`, verify `chunks` = 6150, then `DROP DATABASE restore_test` (per `quickstart.md` §0)
- [X] T010 [US0] Record the confirmed-good backup filename in `specs/003-production-readiness/baseline-metrics.md` as the designated rollback point

**Checkpoint**: ✅ Data safety gate satisfied — migration work is now unblocked.

---

## Phase 3: User Story 1 - Legacy UI and Dead Code Removed (Priority: P2)

**Goal**: One frontend only. Every backend route is JSON-only; known-dead modules are gone.

**Independent Test**: Zero `render_template` hits in `app/`; SPA chat, documents, and conversations all still work.

**Why first**: No schema impact, and all removals are provably unreferenced by the SPA (branches are `HX-Request`-gated) or provably broken (the dead RAG method).

- [X] T011 [US1] Remove the `web_bp` import and `app.register_blueprint(web_bp)` call from `app/__init__.py` (lines ~45 and ~56)
- [X] T012 [US1] Delete `app/web.py`
- [X] T013 [US1] Delete the `app/templates/` directory
- [X] T014 [US1] Delete the `app/static/` directory
- [X] T015 [P] [US1] Remove the `HX-Request` branch at `app/api/chat.py:137` and drop `render_template` from its import on line 1 — route returns `jsonify` only
- [X] T016 [P] [US1] Remove the two `HX-Request` branches at `app/api/conversations.py:30` and `:59` and drop `render_template` from its import on line 1
- [X] T017 [P] [US1] Remove the three `HX-Request` branches at `app/api/documents.py:55`, `:110`, `:176` and drop `render_template` from its import on line 2
- [X] T018 [P] [US1] Delete `app/services/rag_method_dump.py` (unreferenced duplicate of `RAGService._build_hierarchical_context`)
- [X] T019 [US1] Delete the dead `RAGService.search_similar_documents` method (`app/services/rag.py:95-121`) — it queries `Document.summary_embedding` / `summary_search_vector`, columns dropped by `phase2_strip_embeddings.sql`, so it raises at runtime today
- [X] T020 [US1] Delete the `search_similar_documents` MCP tool (`app/mcp_server/server.py:519-545`) which called the method removed in T019
- [X] T021 [P] [US1] Delete `scripts/update_schema.py` and `scripts/run_migration.py` (superseded by Alembic in US3)
- [X] T022 [P] [US1] Remove the unused `import docker` from `app/tasks/processing.py:20` (verified: `docker` appears nowhere else in that file)
- [X] T023 [US1] Verify per `quickstart.md` §1: zero `render_template` hits in `app/`, deleted paths gone, and the SPA at `http://localhost:5200` still lists documents, opens conversations, and sends chat messages

**Checkpoint**: ✅ Backend is JSON-only; dead code removed.

---

## Phase 4: User Story 2 - Ollama Fully Purged (Priority: P2)

**Goal**: No Ollama code, config, UI, Docker service, or privileged socket mount remains; stored preferences degrade gracefully.

**Independent Test**: Case-insensitive grep for "ollama" returns zero hits outside build output, dated notes, backups, and migration history; the app boots and chats normally; the settings page loads with no console 404s.

**⚠️ ORDERING**: This phase must precede Phase 6, which carries the `ollama → llamacpp` data migration. T029 (runtime fallback) must land **before** any migration, because `RUN_MIGRATIONS` may be false.

### Backend code removal

- [X] T024 [US2] Remove the `ollama_manage_bp` import (`app/__init__.py:49`) and its registration at `url_prefix='/api/settings/ollama'` (line 60)
- [X] T025 [US2] Delete `app/api/ollama_manage.py`
- [X] T026 [US2] Remove `OLLAMA = "ollama"` from the `LLMProvider` enum in `config/settings.py:12`
- [X] T027 [P] [US2] Remove all Ollama provider branches from `app/services/llm_client.py`
- [X] T028 [P] [US2] Remove all Ollama provider branches from `app/services/embedder.py`
- [X] T029 [US2] Add a graceful provider fallback in `app/services/llm_client.py`: an unrecognized stored provider value (notably `ollama`) resolves to `llamacpp` with a warning log instead of raising — required because migrations may not have run yet (FR-022)
- [X] T030 [P] [US2] Remove Ollama references from `app/services/memory_service.py`
- [X] T031 [P] [US2] Remove Ollama references from `app/utils/hf_downloader.py`
- [X] T032 [P] [US2] Remove Ollama references from `app/mcp_server/server.py`
- [X] T033 [P] [US2] Remove Ollama references from `app/tasks/processing.py`
- [X] T034 [P] [US2] Remove Ollama references from `app/models/user_preferences.py` (leave the `ollama_num_ctx` **column** in place — it is dropped by migration T063, not by model edits alone)
- [X] T035 [US2] Remove `map_hf_to_ollama` and all Ollama pull/download logic from `app/api/settings.py`

### Configuration

- [X] T036 [US2] Remove `OLLAMA_SERVICE_NAME`, `OLLAMA_BASE_URL`, and `OLLAMA_NUM_CTX` from `config/settings.py:57-61`
- [X] T037 [US2] Fix the diverged embedding defaults in `config/settings.py:64-65`: `EMBEDDING_PROVIDER = "local"` and `EMBEDDING_MODEL = "BAAI/bge-m3"` (both currently contradict the live compose environment that produced the existing vectors). Leave `EMBEDDING_DIMENSION = 1024` untouched
- [X] T038 [P] [US2] Remove `OLLAMA_*` entries from `.env.example` and `.env`
- [X] T039 [P] [US2] Remove Ollama entries from `.dockerignore` and `.gitignore`

### Frontend (must land WITH the backend blueprint removal — T024/T025 — or the settings page 404s)

- [X] T040 [P] [US2] Remove Ollama endpoint constants from `frontend_spa/src/app/core/constants/api-endpoints.ts`
- [X] T041 [P] [US2] Remove Ollama fields from `frontend_spa/src/app/core/models/settings.model.ts`
- [X] T042 [US2] Remove Ollama API calls (pull, download polling) from `frontend_spa/src/app/services/settings.service.ts`
- [X] T043 [US2] Remove the Ollama pull/GGUF modals and `pollDownloads` logic from `frontend_spa/src/app/features/settings/components/settings-discover-tab/settings-discover-tab.component.ts` and `.html`
- [X] T044 [P] [US2] Remove Ollama options from `frontend_spa/src/app/components/modals/llm-selection-modal/llm-selection-modal.component.ts` and `.html`
- [X] T045 [P] [US2] Remove Ollama options from `frontend_spa/src/app/shared/components/llm-selector/llm-selector.component.ts`
- [X] T046 [P] [US2] Remove Ollama references from `frontend_spa/src/app/features/chat/components/chat-input/chat-input.component.ts`
- [X] T047 [P] [US2] Remove Ollama references from `frontend_spa/src/app/features/chat/pages/chat-page/chat-page.component.ts`

### Infrastructure — remove the root-equivalent socket mount

- [X] T048 [US2] Delete `app/utils/docker_helpers.py` (verified: its only consumer was `app/api/ollama_manage.py`, deleted in T025; the only other `import docker` was the stray one removed in T022)
- [X] T049 [US2] Remove the `/var/run/docker.sock:/var/run/docker.sock` mounts from the `app` (line 41) and `worker` (line 79) services in `docker-compose.yml`, and any equivalent in `docker-compose.dev.yml` and `docker-compose.cpu.yml`
- [X] T050 [US2] Remove `docker>=7.0.0` from `requirements.txt`
- [X] T051 [US2] Remove the `ollama` service definition from `docker-compose.cpu.yml:20` (the main and dev compose files do not declare it)

### Documentation

- [X] T052 [P] [US2] Remove Ollama references from `CLAUDE.md` and `README.md`
- [X] T053 [P] [US2] Remove Ollama references from `presets/`
- [X] T054 [P] [US2] Remove Ollama references from `installer/install.ps1`, `installer/build-installer.ps1`, `installer/mnemos-installer.nsi`, `installer/docker-compose.podman.yml`, `installer/docker-compose.podman.test.yml`

### Verification

- [X] T055 [US2] Rebuild the frontend and run the grep gate from `quickstart.md` §2 — zero hits excluding `frontend_spa/dist/`, `.agent/`, `backups/`, `migrations/`. Confirm no `docker.sock` in any compose file, the app boots, chat works, and the settings page has no console 404s

**Checkpoint**: ✅ Ollama fully purged; privileged socket mount gone.

---

## Phase 5: User Story 3 - Single Migration Path via Alembic (Priority: P1)

**Goal**: Schema evolves only through reviewed migrations. The app never mutates schema at startup, and `flask db upgrade` on the live database applies exactly the intended revisions.

**Independent Test**: After stamping the baseline, `flask db migrate` produces an **empty** revision; the app boots with zero DDL; row counts are unchanged.

**⚠️ GATED**: Requires Phase 2 checkpoint (T005–T010). Requires T029 from Phase 4 for safe pre-migration runtime behavior.

### Baseline (the critical part — get this right before writing any revision)

- [X] T056 [US3] Run `flask db init` in the app container to create `migrations/env.py`, `alembic.ini`, and `versions/` (Flask-Migrate is already wired in `app/extensions.py`; no new dependencies needed)
- [X] T057 [US3] Hand-write the baseline revision in `migrations/versions/` reflecting the **verified live schema** per `data-model.md`: all 17 tables including the three VideoMix tables, the `vector` extension, and the `file_type_enum` / `status_enum` types. Do **not** paste a raw `--autogenerate` diff
- [X] T058 [US3] In the baseline, declare `chunks` exactly as live: `embedding vector(1024)`, `search_vector tsvector` (no trigger — it has never existed), plus indexes `chunks_pkey`, `ix_chunks_embedding` as **hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)**, and `ix_chunks_search_vector` as gin. Exact HNSW parameters matter or a later autogenerate will propose an expensive rebuild
- [X] T059 [US3] In the baseline, encode the already-applied state: `document_sections.embedding`, `documents.summary_embedding`, `documents.summary_search_vector`, `hyper_edges.embedding` **absent** (phase2 was applied); `user_preferences.retrieval_top_k` / `hypergraph_llm_provider` / `hypergraph_llm_model` and `documents.embedding_model_used` **present** (startup ALTERs already applied)
- [X] T060 [US3] Stamp the live database with the baseline (`flask db stamp <baseline_rev>`) — never execute the baseline against the live DB
- [X] T061 [US3] **Baseline faithfulness gate**: run `flask db migrate -m "baseline-verification-DISCARD-ME"` and confirm the generated revision's `upgrade()` and `downgrade()` are both empty. Any operation means the baseline is wrong — fix T057–T059 and repeat. Delete the generated file either way. **Do not proceed until this passes.**

### Revisions

- [X] T062 [US3] Revision 001 in `migrations/versions/`: `ALTER TABLE user_preferences ADD COLUMN local_llm_model VARCHAR(255)` (nullable, no default, no backfill) — verified absent from the live table
- [X] T063 [US3] Revision 002: the `collection_documents` backfill INSERT moved from `app/__init__.py:175-180`, written idempotently with `ON CONFLICT DO NOTHING` (a no-op against current data — it has run on every boot)
- [X] T064 [US3] Revision 003: ollama preference fallback data migration — `UPDATE user_preferences SET memory_provider='llamacpp' WHERE memory_provider='ollama'` (1 live row), plus the same for `llm_provider`, plus `UPDATE llm_connections SET provider_type='custom' WHERE provider_type='ollama'` (0 live rows, written for correctness against any DB state). `downgrade()` is a documented no-op, not a fake inverse
- [X] T065 [US3] Revision 004 ⚠ **THE ONE DESTRUCTIVE OPERATION**: `ALTER TABLE user_preferences DROP COLUMN ollama_num_ctx`, in its own revision containing no other change. `downgrade()` must be the exact restore: `ADD COLUMN ollama_num_ctx INTEGER NOT NULL DEFAULT 2048` (FR-024)
- [X] T066 [US3] Revision 005: create the `update_chunk_search_vector()` function building `to_tsvector(<config>, NEW.content)`, choosing the config from `NEW.language` with a `'simple'` fallback for unsupported languages. The config choice MUST match query-time selection in `app/services/rag.py::_detect_query_language` or matches will silently be empty (FR-035)
- [X] T067 [US3] Revision 005 (same file): create `TRIGGER update_chunk_search_vector BEFORE INSERT OR UPDATE OF content, language ON chunks FOR EACH ROW`, then backfill `UPDATE chunks SET search_vector = to_tsvector(...)` for all 6,150 rows. Writes **only** `search_vector` — must not read, alter, or invalidate `embedding`. `downgrade()` drops trigger + function and sets `search_vector = NULL`
- [X] T068 [US3] Review every revision for unintended `DROP TABLE` / `DROP COLUMN` / `DROP INDEX`; remove any that is not T065 (FR-033)

### Remove startup schema mutation

- [X] T069 [US3] Remove `db.create_all()` and the surrounding block from `app/__init__.py:164-186`, keeping the `from app import models` import so SQLAlchemy still registers models
- [X] T070 [US3] Remove the four ad-hoc `ALTER TABLE` blocks from `app/__init__.py:122-150` (their columns are captured by the baseline — these are deleted, not converted)
- [X] T071 [US3] Remove the `collection_documents` backfill INSERT from `app/__init__.py:173-182` (now revision 002)
- [X] T072 [US3] Keep the `CREATE EXTENSION IF NOT EXISTS vector` guard decision explicit: move it into the baseline revision and remove it from `app/__init__.py:115-120` so startup performs no DDL at all
- [X] T073 [US3] Replace the `getattr(db_prefs, 'local_llm_model', None)` workaround with normal attribute access everywhere it appears (now that revision 001 creates the column), and remove the note from `CLAUDE.md`
- [X] T074 [US3] Move the embedder pre-warm out of `create_app()` (`app/__init__.py:152-162`) so it no longer runs in all 4 gunicorn workers plus the Celery worker; make it explicit/opt-in via env, defaulting off, relying on the existing lazy-load path
- [X] T075 [US3] Add the gated migration run to `entrypoint.sh` before `exec "$@"`: `if [ "$RUN_MIGRATIONS" = "true" ]; then flask db upgrade; fi`. Default when unset is **do not run**; failure must be fatal (`set -e` already active)
- [X] T076 [US3] Ensure `RUN_MIGRATIONS=true` is set **only** on the `app` service in all compose files — the `worker` and `mcp` services must not race on schema

### Verification

- [X] T077 [US3] Run `quickstart.md` §3: `flask db upgrade` reaches head, re-running is a no-op, `docker-compose restart app` logs show no `create_all` / `ALTER TABLE`, and `\d chunks` still shows `vector(1024)` + hnsw
- [X] T078 [US3] Run `quickstart.md` §4: trigger exists, zero NULL `search_vector`, and — the check that actually matters — a keyword search through the SPA using a distinctive term now returns results where it previously returned none. Then process a small document and confirm its new chunks have non-NULL `search_vector`
- [X] T079 [US3] Re-verify row counts against T007: documents=58, chunks=6150, collections=8, conversations=143

**Checkpoint**: ✅ Alembic is the single migration path; full-text search works for the first time.

---

## Phase 6: User Story 4 - Reliable Containers and Launcher (Priority: P3)

**Goal**: Deterministic startup with no network dependency, real health gating, restart policies, reduced local attack surface, and non-root containers.

**Independent Test**: Stack starts with networking disabled; a killed container restarts; db/redis/adminer bind to 127.0.0.1 while 5000/5200 stay LAN-reachable; the launcher proceeds as soon as the API is healthy.

- [X] T080 [US4] Remove `pip install --no-cache-dir --upgrade yt-dlp` from `entrypoint.sh:8` and pin `yt-dlp` to a specific version in `requirements.txt` (updates now come via image rebuild)
- [X] T081 [P] [US4] Add a redis healthcheck (`redis-cli ping`) in `docker-compose.yml` and switch the `app` and `worker` `depends_on` for redis from `service_started` to `service_healthy` (lines 46, 84); mirror in `docker-compose.dev.yml` and `docker-compose.cpu.yml`
- [X] T082 [P] [US4] Add `restart: unless-stopped` to `app`, `worker`, `db`, and `redis` in all three compose files
- [X] T083 [US4] Bind infrastructure ports to localhost in all three compose files: db `127.0.0.1:5433:5432`, redis `127.0.0.1:6380:6379`, adminer `127.0.0.1:8080:8080`. ⚠ **Leave `5000` and `5200` on all interfaces** — LAN/mobile access to the SPA is a required capability (FR-041a, accepted risk AR-001). Binding them to localhost is a bug, not a hardening win
- [X] T084 [US4] Move `adminer` behind a `tools` compose profile so it is opt-in (`docker-compose --profile tools up -d adminer`)
- [X] T085 [US4] Make the Celery pool configurable in all three compose files: `--pool=${CELERY_POOL:-solo}` with optional `CELERY_CONCURRENCY`, preserving today's solo default, and add a comment explaining why (the worker loads embedding models onto the same GPU llama.cpp occupies, so concurrent tasks contend for VRAM)
- [X] T086 [US4] Add a non-root user to `Dockerfile` with an explicit `HOME`, and relocate the Whisper cache off `/root/.cache/whisper` — update the `COPY --from=builder` target (line 41) to the new home. ⚠ Highest-risk task in the feature
- [X] T087 [US4] Update the cache mount targets in all three compose files to match T086's new home (currently `/root/.cache/whisper` and `/root/.cache/huggingface` at `docker-compose.yml:39-40` and `:76-77`), and ensure the non-root UID can write `data/uploads`, `data/archive`, and `models/`
- [X] T088 [US4] Create `gunicorn.conf.py` at repo root covering bind, workers, threads, timeout, access logging, and logging class; replace the inline flags in the `Dockerfile` CMD (line 57) with `-c gunicorn.conf.py`
- [X] T089 [US4] Add `GET /api/ready` per `contracts/health-readiness.md`: liveness checks plus Alembic current-vs-head comparison and a llama.cpp `/health` probe with a ≤2s timeout, 5s cached, mutating nothing. **Leave `GET /api/health` byte-for-byte unchanged** (`app/__init__.py:84-109`)
- [X] T090 [US4] Replace the blind `timeout /t 15 /nobreak` at `start-dev.bat:77` with a bounded poll of `http://localhost:5000/api/health` (~90s cap at 3s intervals — the endpoint self-caches 5s so faster polling is wasted) that aborts with a clear message on timeout. Keep the smart-build, preflight, and prune logic untouched
- [X] T091 [US4] Verify per `quickstart.md` §5–§6: no-network start succeeds, killed container restarts, port bindings are correct (including 5000/5200 still on 0.0.0.0), `id` shows non-root, liveness stays 200 while readiness returns 503 with llama.cpp stopped
- [X] T092 [US4] Non-root regression check: upload and fully process a document end-to-end, confirming model caches, `uploads/`, and `archive/` remain writable
- [X] T093 [US4] LAN check: load the SPA from a phone at `http://<host-lan-ip>:5200` and send a chat message, confirming mobile access survived the hardening

**Checkpoint**: ✅ Containers are deterministic, restartable, non-root, and network-independent at start.

---

## Phase 7: User Story 5 - Maintainable Hotspots, Pinned Builds, Observable Runtime (Priority: P3)

**Goal**: No monster files or functions; reproducible builds; bounded validated uploads; structured correlated logs.

**Independent Test**: No `app/` Python file over ~600 lines; no refactored function above cyclomatic 20; two clean builds resolve identically; an oversized/wrong-type upload is rejected; a request ID correlates app and worker logs.

**Note**: All refactors are behavior-preserving. Prefer dependency injection over module-level singletons where cheap (HC-5) so a future test suite is inexpensive.

- [X] T094 [US5] Decompose `process_document_task` in `app/tasks/processing.py` into discrete stage functions (extract, chunk, embed, save, summarize, hypergraph), preserving the existing resume-if-chunks-exist behavior exactly
- [X] T095 [US5] Persist per-stage status on the Document using the existing `documents.metadata_` JSONB column (no schema change needed) — remember `flag_modified(obj, "metadata_")` after in-place mutation, per project convention
- [X] T096 [US5] Split `app/api/settings.py` (1,278 lines) into focused blueprints plus a model-management service, keeping all existing routes and payload shapes
- [X] T097 [US5] Decompose `save_chat_settings` (cyclomatic 45) in the settings blueprint into helpers, each under cyclomatic 20
- [X] T098 [US5] Split `app/mcp_server/server.py` (1,783 lines) into per-domain tool modules (documents, search, wiki, graph, settings) with shared `_validate_uuid` and `_version_footer` helpers. **Tool names and signatures must not change** — reorganization only
- [X] T099 [US5] Split `app/services/rag.py` (723 lines, ~700 after T019) so no file exceeds ~600 lines — required by SC-008 though not named in the original spec's hotspot list
- [X] T100 [US5] Replace the if/elif provider dispatch in `app/services/llm_client.py` with a provider-config table, preserving public `chat()` behavior and the constructor > DB > settings priority exactly
- [X] T101 [US5] Replace the 50GB `MAX_CONTENT_LENGTH` in `config/settings.py:103` with per-file-type ceilings per `contracts/api-surface-changes.md` (documents 512MB, audio 2GB, video 8GB), setting the global value to the largest as a backstop
- [X] T102 [US5] Enforce upload validation at the boundary in `app/api/documents.py`: reject unknown/disallowed extensions with `400` naming accepted types, and over-limit files with `413` stating the limit — both **before** the file is persisted or a Celery task is queued
- [X] T103 [US5] Create `requirements.in` from the current `requirements.txt` dependency list, compile a fully-pinned `requirements.txt` with `pip-tools` **from inside `python:3.11-slim`** so resolved wheels match the image, and update the `Dockerfile` to install from the compiled file
- [X] T104 [P] [US5] Verify the frontend build uses `npm ci` (not `npm install`) against the existing `frontend_spa/package-lock.json` in `frontend_spa/Dockerfile`
- [X] T105 [US5] Add structured JSON logging to Flask in `app/__init__.py` (replacing the `logging.basicConfig` format on lines 10-13) with `timestamp`, `level`, `logger`, `message`, `request_id`; generate a `request_id` per request, honoring an inbound `X-Request-ID`
- [X] T106 [US5] Propagate `request_id` into Celery task headers when tasks are enqueued, and emit it in worker logs; tasks started without an originating request generate their own so the field is never empty
- [X] T107 [US5] Verify per `quickstart.md` §7: line counts under ~600, `radon cc` shows no refactored function above 20, two clean builds produce identical `pip freeze`, and a request ID from an app log line locates the corresponding worker lines

**Checkpoint**: ✅ Hotspots maintainable, builds reproducible, runtime observable.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T108 [P] Correct the two false claims in `CLAUDE.md`: it states Alembic is already in use (it was not — `migrations/` held only a raw SQL file) and that `Chunk.search_vector` is maintained by a DB trigger (the trigger did not exist until T066/T067)
- [X] T109 [P] Update `CLAUDE.md` architecture and commands sections: `flask db upgrade` / `RUN_MIGRATIONS` workflow, the new `/api/ready` endpoint, per-type upload limits, `CELERY_POOL` env, and the `tools` compose profile for adminer
- [X] T110 [P] Update `README.md` for the changed startup flow (no network needed at container start, non-root containers, adminer opt-in)
- [X] T111 [P] Remove the stale trigger comment at `app/models/chunk.py:27` or update it to reference the migration that now creates the trigger
- [X] T112 Reconcile `migrations/phase2_strip_embeddings.sql`: it was verified applied, so either delete it or move it to an archive path with a note that revision history now supersedes it
- [X] T113 Full `quickstart.md` pass — run every section end-to-end against the live system
- [X] T114 **Final data integrity gate**: re-run T007/T008 queries and confirm exact match with the recorded baseline (58 / 6150 / 8 / 143, and 6150 non-null 1024-dim embeddings). Then ask the SPA a question answerable from a pre-existing document and confirm cited results still return

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (US0 Data Safety)**: 🚧 **BLOCKS Phase 5 entirely**. Must complete before any migration task
- **Phase 3 (US1 Dead Code)**: Independent — can run any time after Phase 1
- **Phase 4 (US2 Ollama)**: Must precede Phase 5 (which carries the ollama data migration). T022 (Phase 3) should land before T048
- **Phase 5 (US3 Alembic)**: Requires Phase 2 checkpoint **and** T029 from Phase 4
- **Phase 6 (US4 Docker)**: Requires T075/T076 from Phase 5 for the migration gate; otherwise independent
- **Phase 7 (US5 Refactors)**: Best last — refactors a codebase already stripped of dead code and Ollama branches
- **Phase 8 (Polish)**: Requires all desired phases complete

### Critical Path

```
T005–T010 (backup) ──┐
                     ├──► T056–T079 (Alembic) ──► T080–T093 (Docker) ──► T094–T107 (Refactors) ──► T108–T114
T024–T055 (Ollama) ──┘
```

### Priority vs. Ordering Note

US3 is **P1** but is scheduled after US2 (**P2**) because the Ollama fallback data migration lives inside the Alembic revision chain, and the runtime fallback (T029) must exist before any migration runs. This is a genuine dependency, not a priority downgrade.

### Within Each Story

- Deletions before verification
- Baseline before revisions (T061 is a hard gate — do not write revisions against an unverified baseline)
- Backend and frontend Ollama removal are **atomic together** (T024/T025 with T040–T047)
- Refactors are behavior-preserving: measure before (T002/T003), measure after (T107)

### Parallel Opportunities

- Phase 1: T002, T003, T004 all parallel
- Phase 3: T015, T016, T017 (three different API files) parallel; T018, T021, T022 parallel
- Phase 4: T027/T028 parallel; T030–T034 parallel; T040/T041/T044–T047 parallel; T052–T054 parallel
- Phase 6: T081, T082 parallel
- Phase 8: T108–T111 parallel

---

## Parallel Example: Phase 3 (Dead Code Removal)

```bash
# Three independent API files — no shared state
Task: "Remove HX-Request branch in app/api/chat.py:137"
Task: "Remove HX-Request branches in app/api/conversations.py:30,59"
Task: "Remove HX-Request branches in app/api/documents.py:55,110,176"

# Independent deletions
Task: "Delete app/services/rag_method_dump.py"
Task: "Delete scripts/update_schema.py and scripts/run_migration.py"
Task: "Remove unused import docker from app/tasks/processing.py:20"
```

## Parallel Example: Phase 4 (Ollama — backend service files)

```bash
Task: "Remove Ollama branches from app/services/llm_client.py"
Task: "Remove Ollama branches from app/services/embedder.py"
Task: "Remove Ollama references from app/services/memory_service.py"
Task: "Remove Ollama references from app/utils/hf_downloader.py"
```

---

## Implementation Strategy

### Recommended increment order

1. **Phase 1 + Phase 2** — measurement and the safety net. Nothing else is safe without T005–T010.
2. **Phase 3 (US1)** — smallest, lowest-risk win; shrinks the surface every later phase touches.
3. **Phase 4 (US2)** — removes the privileged socket mount and the dead provider. Stop and validate: app boots, chat works, settings page clean.
4. **Phase 5 (US3)** — the core production-readiness gap. **Stop and validate hard**: T061 empty-diff, T077 no-op upgrade, T079 row counts, T078 keyword search now working.
5. **Phase 6 (US4)** — operational reliability. T086/T087 (non-root) is the riskiest pair; validate with T092 before moving on.
6. **Phase 7 (US5)** — behavior-preserving cleanup, safe to defer or split across sessions.
7. **Phase 8** — docs and the final integrity gate.

### Suggested MVP scope

**Phases 1, 2, 3, 4, and 5** (T001–T079). That delivers the actual production-readiness thesis: a safety net, a clean codebase, no privileged host access, schema under version control, an app that no longer mutates its own database at boot — plus working full-text search as a bonus. Phases 6–7 are quality-of-life and maintainability improvements that can land incrementally afterward.

### Stop-and-surface conditions

Halt and report rather than proceeding if any of these occur:

- T061's verification revision is **not** empty after two correction attempts — the baseline does not match reality
- Any autogenerated revision proposes a DROP that is not T065
- Row counts diverge from 58 / 6150 / 8 / 143 at any checkpoint
- Any change would alter `EMBEDDING_DIMENSION` or the embedding model
- The non-root change (T086/T087) breaks document processing and the cause is not obviously a path or permission fix

---

## Notes

- `[P]` = different files, no dependencies on incomplete tasks
- Commit after each task or logical group; the branch is `003-production-readiness`
- No test-writing tasks by design (HC-5) — verification is measurement-based via `quickstart.md`
- VideoMix files (`app/api/videomix.py`, `app/services/videomix_script_generator.py`, `app/tasks/videomix_tasks.py`, `app/models/videomix.py`) are **untouched** by every task — but their three tables ARE in the migration baseline (T057), or autogenerate would propose dropping them
