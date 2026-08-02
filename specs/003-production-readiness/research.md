# Phase 0 Research: Production Readiness

**Feature**: `003-production-readiness` | **Date**: 2026-08-01

All findings below were verified against the **running stack and live database** (`dev-db-1`, `mnemos_db`), not inferred from documentation. Three findings contradict CLAUDE.md and/or the spec and change the plan; they are marked **⚠ CONTRADICTS SPEC**.

## Baseline measurements (recorded before any change)

| Table | Rows |
|---|---|
| documents | 58 |
| chunks | 6,150 |
| collections | 8 |
| conversations | 143 |

These are the reference counts for SC-002. Re-measure after every workstream.

Additional verified facts: `chunks.embedding` is `vector(1024)`, zero NULL embeddings, HNSW index `ix_chunks_embedding` (cosine, m=16, ef_construction=64) present. Live table list contains 17 tables including the three VideoMix tables.

---

## F1. Alembic is genuinely absent — confirmed

**Finding**: `alembic_version` table does not exist. `migrations/` contains only `phase2_strip_embeddings.sql` — no `env.py`, no `alembic.ini`, no `versions/`. `docker exec dev-app-1 flask db current` fails with `ImportError: Can't find Python file migrations/env.py`.

However, **Flask-Migrate is already wired**: `app/extensions.py` defines `migrate = Migrate()` and `create_app()` calls `migrate.init_app(app, db)`. `alembic` and `flask-migrate` are already in `requirements.txt`.

**Decision**: Adoption is purely a matter of running `flask db init` and hand-writing the baseline. No new dependencies, no wiring changes.

**Rationale**: The plumbing exists; only the migration environment and revision history are missing.

**Alternatives considered**: Adding a separate standalone Alembic config outside Flask-Migrate — rejected, it would duplicate the DB URL and app context handling that `Migrate` already provides.

---

## F2. ⚠ CONTRADICTS SPEC — the `update_chunk_search_vector` trigger does not exist, and full-text search is dead

**Finding**: The live database has **zero** non-internal triggers (`select tgname from pg_trigger where not tgisinternal` returns 0 rows). No `update_chunk_search_vector` function exists.

Consequently: **all 6,150 chunks have `search_vector IS NULL`** (verified: `null_sv=6150, filled_sv=0`).

`app/models/chunk.py:27` carries the comment `# Managed by DB Trigger: update_chunk_search_vector` and the GIN index `ix_chunks_search_vector` exists, but nothing ever populated the column. CLAUDE.md's claim that "`Chunk.search_vector` is maintained by a DB trigger" is false, and spec acceptance scenario US3-2 (which asks to "preserve" the trigger) describes something that was never there.

**Impact**: `app/services/rag.py:221-225` filters on `Chunk.search_vector @@ kw_query`. With every value NULL, the keyword arm of the hybrid retrieval **always returns zero rows**. The documented RRF hybrid search has been running as pure vector search this entire time — silently, with no error.

**Decision**: The baseline revision reflects **reality**: `search_vector` column and GIN index exist, no trigger. Creating the trigger and backfilling becomes a **separate, explicitly-called-out fix revision**, not part of the baseline.

The backfill is `UPDATE chunks SET search_vector = to_tsvector(<lang>, content)` — it writes only the `search_vector` column. It does not touch `embedding`, does not drop or recreate the table, and does not re-embed. It is therefore compatible with HC-2/HC-3.

**Open decision for the user** (surfaced per HC-4-style caution, though it is additive rather than destructive): whether to include the FTS fix in this feature or defer it. Recommendation: **include it**, because (a) it is the difference between the retrieval pipeline the docs describe and the one that actually runs, (b) the backfill is cheap at 6,150 rows, and (c) doing it inside the migration story is far safer than as an ad-hoc script later. The plan schedules it as an opt-in revision that can be skipped without blocking anything else.

**Language handling**: `Chunk.language` is populated per-chunk. The trigger should map the language to a Postgres text-search config with a safe fallback to `'simple'` for unsupported languages, matching how `rag.py::_detect_query_language` picks the query-side config. A mismatch between index-time and query-time configs would silently return no matches, so this pairing must be verified by an actual search after backfill.

**Alternatives considered**: Maintaining `search_vector` in application code on insert — rejected, it would need to be duplicated across the processing pipeline and any future writer, which is exactly the drift the trigger avoids. Dropping the column and the FTS arm entirely — rejected, it would silently downgrade documented functionality.

---

## F3. ⚠ CONTRADICTS SPEC — `phase2_strip_embeddings.sql` WAS applied, and code still references the dropped columns

**Finding**: All four columns the script drops are absent from the live schema (`document_sections.embedding`, `documents.summary_embedding`, `documents.summary_search_vector`, `hyper_edges.embedding` — the reconciliation query returned zero rows). The script has been applied.

But `app/services/rag.py::search_similar_documents` (lines 95-121) still builds queries against `Document.summary_embedding` (line 109) and `Document.summary_search_vector` (line 113). That method is reachable: `app/mcp_server/server.py:519` exposes an MCP tool `search_similar_documents` that calls it at line 540.

**Impact**: That MCP tool is **broken at runtime** — it will raise as soon as it is invoked, because the ORM references columns that no longer exist in the database.

**Decision**: The baseline reflects the post-phase2 schema (columns absent). The dead `RAGService.search_similar_documents` method and its MCP tool wrapper are removed as part of Workstream 1 (dead code), since the feature they implement no longer has a schema to run against. Reinstating summary-level search would mean re-adding vector columns and re-embedding summaries — out of scope under HC-3.

**Rationale**: Leaving a known-broken tool exposed to Claude Desktop is worse than removing it; restoring it is a feature decision, not a readiness one.

**Alternatives considered**: Rewriting the method to use chunk-level search instead — rejected as scope creep; it changes retrieval semantics rather than removing dead weight. Flagged in the plan as a possible follow-up.

---

## F4. Docker socket mount has no surviving consumer

**Finding**: `app/utils/docker_helpers.py` is imported only by `app/api/ollama_manage.py`. The only other `import docker` is `app/tasks/processing.py:20`, which is an **unused import** — `docker` appears on that line and nowhere else in the file.

**Decision**: After the Ollama purge, delete `docker_helpers.py`, remove the stray import from `processing.py`, drop `docker>=7.0.0` from requirements, and remove both `/var/run/docker.sock` mounts (app and worker, `docker-compose.yml:41` and `:79`).

**Rationale**: Confirms spec FR-023's conditional. Root-equivalent host access with zero consumers is pure liability.

---

## F5. Non-root migration is the riskiest Docker change — cache paths are the blocker

**Finding**: The Dockerfile pre-downloads the Whisper model to `/root/.cache/whisper` and copies it into the runtime stage. Compose mounts host directories onto **`/root/.cache/whisper`** and **`/root/.cache/huggingface`** for both app and worker. Bind-mounted volumes on Windows/Docker Desktop arrive owned by root.

**Decision**: Introduce a non-root user with an explicit `HOME` and relocate caches to that home (e.g. `/home/mnemos/.cache/...`), updating the Dockerfile `COPY --from=builder` target and the compose mount targets together. `uploads/`, `archive/`, and `models/` mounts must also be writable by the new UID.

**Rationale**: Changing `USER` without moving the cache paths would break Whisper (re-download at runtime, violating the no-network-at-start goal) and break HF model loading. This is a coordinated Dockerfile + all-three-compose-files change, which is why the plan sequences it as one task, verified by an actual document-processing run rather than just "container starts".

**Alternatives considered**: `chown`ing `/root` and keeping paths — rejected, `/root` with a non-root user is confusing and the bind mounts would still be root-owned. Running non-root only for the `mcp` service — rejected as half a fix.

---

## F6. Embedder pre-warm currently loads the model in every process

**Finding**: `create_app()` (lines 152-162) spawns a background thread that calls `EmbedderService.get_instance()`. The Dockerfile CMD runs `gunicorn -w 4 --threads 2`, so `create_app()` executes in **4 worker processes**, each loading BAAI/bge-m3 onto CUDA. The Celery worker also builds the app.

**Decision**: Remove the pre-warm from `create_app()`. Make it explicit and opt-in via env (default off for web processes), or trigger it lazily on first use as the fallback path already supports. Pair with the gunicorn config file (FR-055) where `preload_app` and worker count can be set deliberately.

**Rationale**: 4× redundant GPU model loads compete with llama.cpp for VRAM — which is the same GPU-contention reason the Celery worker runs `--pool=solo`.

---

## F7. Config defaults diverge from the live environment in two places

**Finding**: `config/settings.py:64` sets `EMBEDDING_PROVIDER = "ollama"` while compose sets `local`. Additionally `settings.py:65` sets `EMBEDDING_MODEL = "bge-m3"` while compose sets `BAAI/bge-m3` — a second, unreported divergence (the bare name is not a valid sentence-transformers identifier).

`MAX_CONTENT_LENGTH` is `50 * 1024**3` (50GB) at line 103.

**Decision**: Code defaults become `EMBEDDING_PROVIDER = "local"` and `EMBEDDING_MODEL = "BAAI/bge-m3"`, matching the environment that produced the live vectors. `EMBEDDING_DIMENSION` stays 1024 (already correct).

**Rationale**: Under HC-3 the defaults must describe the vectors that actually exist, or a future run without compose env would produce incompatible embeddings.

---

## F8. Ollama footprint is wider than the spec enumerates

**Finding**: Case-insensitive grep hits 40+ files. Beyond the spec's list, Ollama references also exist in:

- `app/services/memory_service.py`, `app/tasks/processing.py`, `app/utils/hf_downloader.py`, `app/mcp_server/server.py`, `app/models/user_preferences.py`
- Frontend beyond the settings feature: `llm-selection-modal`, `llm-selector`, `chat-input`, `chat-page`, `api-endpoints.ts`, `settings.model.ts`, `settings.service.ts`
- `installer/` (install.ps1, NSIS script, podman compose files), `presets/`, `.env`, `.env.example`, `.dockerignore`, `.gitignore`
- Only `docker-compose.cpu.yml` declares an `ollama` service (line 20); the main and dev compose files do not.
- Build artifacts under `frontend_spa/dist/` (regenerated on build — not source, exclude from the grep gate)

**Decision**: The purge task list is driven by a live grep sweep, not the spec's enumeration. SC-003's "zero hits" gate must exclude `frontend_spa/dist/`, `.agent/` historical notes, `backups/`, and migration history. `.agent/` files are dated design notes — historical record, left alone.

---

## F9. Dependency pinning: backend unpinned, frontend already locked

**Finding**: `requirements.txt` has **zero** version pins except `docker>=7.0.0`, `flask>=3.0`, `sqlalchemy>=2.0`. This includes `torch`, `transformers`, `sentence-transformers`, and `openai-whisper` — the packages most likely to break on a float. `frontend_spa/package-lock.json` exists, so the frontend is already reproducible provided the build uses `npm ci` rather than `npm install`.

**Decision**: Adopt `pip-tools`: keep the human-edited list as `requirements.in`, compile to a fully-pinned hashed `requirements.txt`, and have the Dockerfile install from the compiled file. Verify the frontend Dockerfile uses `npm ci`.

**Rationale**: `pip-tools` keeps the existing single-file layout and needs no new runtime tooling in the image, unlike switching to `uv` or Poetry.

**Alternatives considered**: `uv` — faster and increasingly standard, but changes the build toolchain for a single-user local deployment where build speed is not the pain point. Reasonable future swap; recorded, not adopted.

**Pinning must not float torch.** Compilation should happen from inside the same `python:3.11-slim` platform to avoid resolving wheels the image cannot use.

---

## F10. Compose hardening details

**Finding**: `redis` has no healthcheck and both app and worker use `condition: service_started` for it. No `restart:` policy on app, worker, db, or redis (only `llamacpp` has `unless-stopped`, and `adminer` has `restart: always`). Ports `5433`, `6380`, `8080`, `5000`, `5200` all publish on `0.0.0.0`.

**Decision**: Add `redis-cli ping` healthcheck + `service_healthy`; `unless-stopped` on app/worker/db/redis; bind `5433`, `6380`, `8080` to `127.0.0.1`. Move adminer behind a `tools` profile.

**Note on `5000`/`5200`**: The spec (SC-012) only requires db/redis/adminer be local-only. Leaving the app and frontend ports on all interfaces is a deliberate choice so the SPA stays reachable from other devices on the LAN if desired — but for a local-only single-user deployment with no auth, binding these to `127.0.0.1` too is the safer default. Flagged as a decision point in the plan; recommendation is to bind them locally as well, since "local-only by design" is the stated deployment model and there is no authentication.

---

## F11. Launcher health poll

**Finding**: `start-dev.bat:77` is a blind `timeout /t 15`. The `/api/health` endpoint already exists (`app/__init__.py:84`), returns 200/503 with a 5-second internal cache, and checks db + redis.

**Decision**: Replace with a bounded `curl`/PowerShell poll of `http://localhost:5000/api/health` (recommend ~90s cap at 3s intervals, comfortably above cold start), aborting loudly on timeout. The existing 5s health cache means polling faster than 3s gains nothing.

Readiness (FR-045) adds a separate concern — migrations applied and llama.cpp reachable — which should be a **distinct endpoint** (`/api/ready`) rather than a change to `/api/health`, so the launcher's liveness poll and the readiness gate can't be confused. `/api/health` stays exactly as-is per spec ("keep the existing endpoint").

---

## F12. Complexity hotspots — measured

| File | Lines | In scope |
|---|---|---|
| `app/mcp_server/server.py` | 1,783 | yes — split by domain |
| `app/api/settings.py` | 1,278 | yes — split into blueprints/services |
| `app/services/rag.py` | 723 | **over threshold, not named in spec** |
| `app/tasks/processing.py` | 500 | yes — decompose the task function |
| `app/services/videomix_script_generator.py` | 422 | no — VideoMix excluded (HC-5) |
| `app/api/videomix.py` | 418 | no — VideoMix excluded (HC-5) |

**Decision**: `rag.py` at 723 lines exceeds the ~600 line criterion in SC-008 but is not one of the spec's named hotspots. It shrinks somewhat when dead `search_similar_documents` is removed (F3). The plan includes a light split of `rag.py` to satisfy SC-008, sequenced last and kept behavior-preserving — this is the only place the plan adds scope beyond the spec's explicit list, and it is required to meet the spec's own success criterion.

Cyclomatic complexity for `process_document_task` (44) and `save_chat_settings` (45) is taken from the user's report; the plan verifies with a measurement tool (`radon cc`) before and after rather than trusting the numbers.

---

## Resolved unknowns summary

| Unknown | Resolution |
|---|---|
| Does the FTS trigger exist? | No — never existed; FTS silently dead (F2) |
| Was phase2 SQL applied? | Yes — and code still references dropped columns (F3) |
| Any non-Ollama consumer of docker.sock? | No — stray unused import only (F4) |
| Is a backup needed before starting? | A 232MB dump from 2026-08-01 18:58 already exists; plan still takes a fresh pre-migration dump (F-baseline) |
| Frontend reproducibility | `package-lock.json` present; needs `npm ci` in build (F9) |
| Ollama fallback target | `llamacpp`, per spec Assumptions; verified `LLMProvider.LLAMACPP` exists |
