# Feature Specification: Production Readiness — Local-Only, Single-User Deployment

**Feature Branch**: `003-production-readiness`

**Created**: 2026-08-01

**Status**: Draft

**Input**: User description: "Prepare MNEMOS for production readiness as a LOCAL-ONLY, single-user deployment across five workstreams: data safety gate, removal of the deprecated HTMX/Jinja UI and dead code, complete removal of Ollama, adoption of Alembic as the single migration path, Docker/launcher hardening, and refactoring of complexity hotspots with dependency/observability hygiene."

## Overview

MNEMOS currently works, but its operational foundation has accumulated risk: the schema is mutated at app startup instead of by migrations, containers modify themselves at boot via network installs, a root-equivalent Docker socket is mounted with only a dead consumer, a retired LLM backend (Ollama) permeates code/config/UI, a deprecated server-rendered UI coexists with the Angular SPA, and several files/functions have grown beyond maintainable size. This feature brings the system to a production-ready state for its actual deployment model — one machine, one user, served on a trusted home network — **without ever putting existing data (documents, chunks, embeddings, collections, conversations) at risk**.

**Deployment model, precisely stated**: single user, self-hosted, reachable from the operator's own devices on the local network (the SPA is used from a phone). Not exposed to the public internet. Infrastructure surfaces (database, cache, admin UI) are restricted to the host machine; the application and web UI intentionally remain reachable across the LAN. See Accepted Risks.

### Hard Constraints (apply to every workstream)

- **HC-1**: A timestamped database backup MUST exist in `backups/` before any schema-touching or migration work executes; task ordering must enforce this.
- **HC-2**: Never run `docker-compose down -v`; never remove the `postgres_data` or `redis_data` volumes; never DROP or recreate the `chunks` table.
- **HC-3**: Embedding dimension stays 1024 and the embedding model stays BAAI/bge-m3. Existing chunk vectors MUST remain valid — no re-embedding.
- **HC-4**: If any proposed change would alter the vector dimension or drop a populated table, work stops and the issue is surfaced to the user before proceeding.
- **HC-5**: Authentication/authorization is out of scope — deferred to a dedicated future spec, not deemed unnecessary. The VideoMix feature (`app/api/videomix.py`, `app/services/videomix_script_generator.py`, `app/tasks/videomix_tasks.py`, `app/models/videomix.py`) is left untouched. Unit/e2e test suites are a separate follow-up, but refactored code must remain structured for testability (dependency injection over module-level singletons where cheap).

## Clarifications

### Session 2026-08-01

- Q: The `update_chunk_search_vector` trigger does not exist and never did — all 6,150 chunks have an empty `search_vector`, so the keyword arm of hybrid retrieval has always returned nothing. Repair it in this feature, or leave retrieval vector-only? → A: Include the full repair — create the trigger and backfill all existing chunks.
- Q: `user_preferences.ollama_num_ctx` is a live column (integer, one row, value 2048) that nothing reads after the Ollama purge. Drop it (a destructive operation on a populated table) or leave it as a harmless orphan? → A: Drop it, in its own isolated and independently revertible revision.
- Q: The app (5000) and web UI (5200) ports publish on all interfaces, so any device that can reach this machine gets unauthenticated access. Restrict them to 127.0.0.1? → A: No — leave both on all interfaces. Mobile access to the SPA is a wanted capability; authentication will be added in a separate future spec.

## User Scenarios & Testing *(mandatory)*

### User Story 0 - Data Safety Gate (Priority: P1)

Before anything else changes, the operator has a restorable snapshot of the live database, and every later step is provably unable to destroy existing knowledge-base content.

**Why this priority**: Every other workstream touches schema, config, or startup behavior. The knowledge base (documents, embeddings, conversations) is the product; losing it is the only unrecoverable failure.

**Independent Test**: Run the backup step alone; verify a timestamped `pg_dump` file exists in `backups/`, is non-empty, restores into a scratch database, and `backups/` is git-ignored.

**Acceptance Scenarios**:

1. **Given** the running stack, **When** the backup step executes, **Then** a timestamped dump of `mnemos_db` is written to `C:\Users\qepri\Documents\git_qepri\mnemos\dev\backups\` and `backups/` is listed in `.gitignore`.
2. **Given** row counts captured for documents, chunks, collections, and conversations before the work begins, **When** all workstreams complete, **Then** the same row counts are observed (no data loss).
3. **Given** any implementation task that touches schema or migrations, **When** task ordering is inspected, **Then** the backup task strictly precedes and blocks it.

---

### User Story 1 - Legacy UI and Dead Code Removed (Priority: P2)

The operator maintains one frontend (the Angular SPA). The obsolete server-rendered HTMX/Jinja UI and known-dead modules are gone, so every backend route has exactly one behavior: JSON in, JSON out.

**Why this priority**: Dual-response branches are dead weight that complicates every later refactor; removing them first shrinks the surface the remaining workstreams must touch.

**Independent Test**: Grep the backend for `render_template` and `templates/` — zero hits; exercise the SPA's chat, documents, and conversations features — all still work.

**Acceptance Scenarios**:

1. **Given** the codebase after removal, **When** searching the backend for `render_template` or a `templates/` directory, **Then** there are zero hits (`app/web.py`, `app/templates/`, `app/static/` deleted; dual-response branches in `app/api/chat.py`, `app/api/documents.py`, `app/api/conversations.py` removed).
2. **Given** the SPA, **When** the user chats, browses documents, and manages conversations, **Then** all flows behave exactly as before.
3. **Given** the dead module `app/services/rag_method_dump.py` and ad-hoc scripts `scripts/update_schema.py` / `scripts/run_migration.py`, **When** removal completes, **Then** they no longer exist and nothing references them.

---

### User Story 2 - Ollama Fully Purged (Priority: P2)

The operator, who now uses llama.cpp (with the generic "custom" connection covering other backends), finds no trace of Ollama anywhere — no code paths, no settings, no UI, no Docker service, no privileged Docker socket mount — and any stored preferences that referenced Ollama silently fall back to a working provider.

**Why this priority**: Dead provider branches inflate the exact files being refactored in Workstream 5, and the Docker socket mount that exists only for Ollama container management is a root-equivalent host exposure.

**Independent Test**: Case-insensitive grep for "ollama" across the repo returns zero hits outside migration history and `backups/`; the app boots and chats normally; a database row with an ollama preference resolves to llamacpp without error.

**Acceptance Scenarios**:

1. **Given** the purged codebase, **When** grepping case-insensitively for "ollama", **Then** the only hits are in migration history and `backups/`.
2. **Given** a `UserPreferences` or `LLMConnection` row referencing ollama, **When** the migration runs, **Then** the row is migrated to llamacpp (or custom) and the app never errors at runtime because of a stale ollama reference.
3. **Given** `app/utils/docker_helpers.py` has no remaining consumer after the purge, **When** cleanup completes, **Then** the module is deleted, the `/var/run/docker.sock` mounts are removed from app and worker in all compose files, and the `docker` package is dropped from requirements if unused.
4. **Given** `config/settings.py`, **When** inspected, **Then** the embedding provider default is `local` (matching the live compose environment) and no `OLLAMA_*` settings remain.
5. **Given** the Angular settings feature, **When** inspected, **Then** the Ollama pull/model-management UI (pollDownloads, GGUF/pull modals targeting Ollama) is gone and remaining settings screens function.

---

### User Story 3 - Single Migration Path via Alembic (Priority: P1)

The operator evolves the database schema exclusively through versioned, reviewable migrations. The app never mutates schema at startup; a fresh boot against the live database changes nothing.

**Why this priority**: This is the core production-readiness gap — schema drift from `db.create_all()` plus ad-hoc startup ALTERs is unreproducible and dangerous. It also carries the data migrations that Workstream 2 depends on.

**Independent Test**: On the live database, stamp the baseline, then run the migration upgrade command — it must be a no-op; boot the app — it must not execute any DDL.

**Acceptance Scenarios**:

1. **Given** that no real Alembic setup exists today (only a raw `phase2_strip_embeddings.sql`), **When** adoption completes, **Then** a baseline revision hand-written to reflect the CURRENT live schema exists and the live DB is stamped with it — not produced by applying a raw autogenerate diff.
2. **Given** the `chunks.search_vector` column and its GIN index exist while the `update_chunk_search_vector` trigger does **not** (verified against the live database — it was never created, leaving all 6,150 chunks with an empty `search_vector`), **When** the baseline is inspected, **Then** it records this true state: column and index present, no trigger. The trigger is created separately by the repair revision (FR-035), never assumed to pre-exist.
3. **Given** `phase2_strip_embeddings.sql`, **When** baselining, **Then** its applied/not-applied status is verified against the live DB and the baseline reflects true state.
4. **Given** the four startup ALTER TABLE blocks, the `collection_documents` data-migration INSERT, the missing `user_preferences.local_llm_model` column (and its `getattr` workaround), and the ollama→llamacpp preference fallback, **When** conversion completes, **Then** each exists as a proper reviewed Alembic revision and the corresponding startup code / workaround is removed.
5. **Given** the app after conversion, **When** it boots, **Then** it executes no `create_all` and no ad-hoc DDL; migrations run only via `flask db upgrade` in the entrypoint, gated by `RUN_MIGRATIONS=true`.
6. **Given** any autogenerated revision, **When** reviewed, **Then** every DROP TABLE / DROP COLUMN / DROP INDEX is removed unless explicitly intended and called out.
7. **Given** the embedder pre-warm currently in `create_app`, **When** refactoring completes, **Then** it no longer runs in every gunicorn/Celery worker process.

---

### User Story 4 - Reliable Containers and Launcher (Priority: P3)

The operator starts the stack and it comes up deterministically: no network access needed at container start, services wait on real health signals, everything restarts after a crash or reboot, admin/database ports are reachable only from the local machine, and containers don't run as root.

**Why this priority**: Operational quality-of-life and local attack-surface reduction; valuable but doesn't block the data-integrity workstreams.

**Independent Test**: Disconnect networking, start the stack — all containers start from the image alone; kill a container — it restarts; check listening ports — db/redis/adminer bound to 127.0.0.1 only; `start-dev.bat` proceeds as soon as the API reports healthy.

**Acceptance Scenarios**:

1. **Given** the entrypoint, **When** a container starts, **Then** no package installation runs (yt-dlp is pinned in requirements and updated via image rebuild) and start requires no network access.
2. **Given** the compose files, **When** inspected, **Then** redis has a healthcheck with dependents using `service_healthy`; app, worker, db, redis have `unless-stopped` restart policies; db (5433), redis (6380), and adminer (8080) bind to 127.0.0.1 only; adminer is opt-in behind a profile.
3. **Given** the image, **When** a container runs, **Then** the process runs as a non-root user, and the multi-stage build with the shared app/worker/mcp image is preserved.
4. **Given** the Celery worker, **When** configured via env, **Then** pool/concurrency are overridable with current `--pool=solo` behavior as default, and the compose file documents why solo is used (GPU contention).
5. **Given** `start-dev.bat`, **When** launching, **Then** it polls `http://localhost:5000/api/health` until healthy (with a cap) instead of a blind 15-second sleep, while keeping the smart-build, preflight, and prune logic.
6. **Given** the health endpoint, **When** queried, **Then** liveness remains as-is and a readiness distinction reports whether migrations are applied and llama.cpp is reachable.

---

### User Story 5 - Maintainable Hotspots, Pinned Builds, Observable Runtime (Priority: P3)

The operator (and future contributors) can read, modify, and diagnose the system: no monster files or functions, dependencies resolve identically on every build, uploads are bounded and validated, and logs are structured with request correlation across web and worker.

**Why this priority**: Long-term maintainability; safe to do last because it is behavior-preserving refactoring on top of an already-cleaned codebase.

**Independent Test**: Line/complexity measurement of the named hotspots meets thresholds; two clean builds resolve identical dependency sets; an oversized or wrong-type upload is rejected at the boundary; a request can be traced across app and worker logs by ID.

**Acceptance Scenarios**:

1. **Given** `process_document_task` (cyclomatic 44), **When** decomposed, **Then** the pipeline runs as discrete resumable stages (extract, chunk, embed, save, summarize, hypergraph) with per-stage status persisted on the Document, and resume-if-chunks-exist behavior is preserved.
2. **Given** `app/api/settings.py` (1,278 lines) and `app/mcp_server/server.py` (1,783 lines), **When** split, **Then** no Python file in `app/` exceeds ~600 lines, `save_chat_settings` (cyclomatic 45) is decomposed, model management lives in a service, and MCP tools are grouped by domain with shared helpers.
3. **Given** the LLM client, **When** dispatch is simplified to a provider-config table, **Then** public `chat()` behavior and the constructor > DB > settings priority are unchanged.
4. **Given** upload handling, **When** a file exceeds realistic per-file-type limits (replacing the 50GB cap) or has an invalid type, **Then** it is rejected at the boundary with a clear error.
5. **Given** the dependency setup, **When** built twice from clean, **Then** Python and frontend dependencies resolve identically (lockfile-pinned).
6. **Given** any request or background task, **When** it logs, **Then** output is structured JSON with a request/task ID usable to correlate across Flask and Celery, and production serving uses a gunicorn config file instead of inline CMD flags.

---

### Edge Cases

- Backup runs while the worker is mid-task: dump is still consistent (pg_dump snapshot semantics); acceptable for single-user.
- The live DB already has some of the startup-ALTER columns and possibly `phase2_strip_embeddings.sql` applied: baseline must reflect discovered state, not assumed state — verified column-by-column against the live schema.
- A stored preference references ollama but the migration hasn't run yet (e.g., `RUN_MIGRATIONS=false`): runtime code must still not crash — provider resolution falls back rather than raising.
- `RUN_MIGRATIONS` unset or false: app boots against the existing schema without attempting any DDL.
- Health poll cap reached in `start-dev.bat`: launcher reports failure clearly instead of proceeding.
- Non-root container user must still be able to write `uploads/` and other mounted paths.
- Readiness check when llama.cpp is down: readiness reports not-ready; liveness stays healthy (app process is fine).
- An upload arrives at exactly the type-specific limit boundary: accepted at the limit, rejected just above it.

## Requirements *(mandatory)*

### Functional Requirements

**Data Safety (gates everything)**

- **FR-001**: A timestamped backup of the live database MUST be created in `backups/` (folder created, git-ignored) before any schema-touching or migration task executes; ordering MUST make the backup a blocking prerequisite.
- **FR-002**: All existing documents, chunks (including vectors), collections, and conversations MUST survive every workstream unchanged, verified by before/after row counts.
- **FR-003**: No task may drop or recreate the `chunks` table, remove data volumes, change the embedding dimension (1024), or change the embedding model (BAAI/bge-m3); any change implying these MUST halt and be surfaced.

**Legacy UI / Dead Code**

- **FR-010**: The server-rendered UI (`app/web.py`, `app/templates/`, `app/static/`) and all dual-response `render_template` branches in chat, documents, and conversations routes MUST be removed; affected routes MUST return JSON only.
- **FR-011**: `app/services/rag_method_dump.py`, `scripts/update_schema.py`, and `scripts/run_migration.py` MUST be removed with no dangling references.

**Ollama Removal**

- **FR-020**: All Ollama-specific code MUST be removed: the management API (`app/api/ollama_manage.py` + blueprint registration), the OLLAMA enum member and provider branches in the LLM client and embedder, `map_hf_to_ollama` and pull/download logic in settings, and the Ollama model-management UI in the Angular settings feature.
- **FR-021**: All Ollama configuration MUST be removed (`OLLAMA_*` settings, compose service/profile, doc references in CLAUDE.md/README/.env.example/presets), and the embedding provider code default MUST become `local`.
- **FR-022**: Stored preferences/connections referencing ollama MUST be migrated to llamacpp (or custom) by data migration; runtime resolution MUST fall back gracefully, never error, if such a row is encountered pre-migration.
- **FR-023**: If `docker_helpers.py` has no consumer after the purge, it MUST be deleted, the Docker socket mounts removed from app/worker in all compose files, and the `docker` dependency dropped if unused; any surviving socket mount MUST have a justified, documented consumer.

- **FR-024**: The dead `user_preferences.ollama_num_ctx` column MUST be dropped by a dedicated migration revision containing no other change, with an exact downgrade that restores both the column and its `2048` default. This is the feature's only destructive schema operation and is deliberate, reviewed, and independently revertible.

**Migrations**

- **FR-030**: A migration baseline MUST be hand-written to match the verified current live schema (including the `chunks.search_vector` column and its trigger, and the reconciled status of `phase2_strip_embeddings.sql`) and stamped — never applied as a raw autogenerate diff.
- **FR-031**: The four startup ALTER blocks, the `collection_documents` backfill INSERT, the `user_preferences.local_llm_model` column (retiring the `getattr` workaround), and the ollama fallback (FR-022) MUST each become reviewed migration revisions.
- **FR-032**: App startup MUST NOT mutate schema: no `create_all`, no ad-hoc DDL in `create_app()`. Migrations run only via the entrypoint, gated by `RUN_MIGRATIONS=true`.
- **FR-033**: Every autogenerated revision MUST be manually reviewed; destructive operations (DROP TABLE/COLUMN/INDEX) are removed unless explicitly intended and called out.
- **FR-034**: The embedder pre-warm MUST move out of `create_app` so it does not execute in every web/worker process.
- **FR-035**: A migration revision MUST repair full-text search: create the `update_chunk_search_vector` function and trigger on `chunks`, and backfill `search_vector` for all existing chunks. The index-time text-search configuration MUST match the query-time configuration chosen by the retrieval layer (falling back to `simple` for unsupported languages), and the revision MUST write only `search_vector` — never reading, altering, or invalidating `embedding`.

**Docker & Launcher**

- **FR-040**: Container start MUST NOT install packages or require network access; yt-dlp is version-pinned and updated by image rebuild.
- **FR-041**: Compose MUST provide: redis healthcheck with `service_healthy` dependencies, `unless-stopped` restart policies on app/worker/db/redis, 127.0.0.1-only bindings for db/redis/adminer, and adminer behind an opt-in profile.
- **FR-041a**: The app (5000) and frontend (5200) ports MUST remain published on all interfaces. LAN access to the SPA from mobile devices is a required capability. Because the system has no authentication, this is a knowingly accepted exposure — see the Accepted Risks section — and MUST NOT be silently "hardened" to 127.0.0.1 during compose changes.
- **FR-042**: The container image MUST run as a non-root user while preserving the existing multi-stage build and shared image; the non-root user MUST retain write access to required mounted paths.
- **FR-043**: Celery pool/concurrency MUST be env-configurable with the current solo behavior as default, and the reason (GPU contention) documented in the compose file.
- **FR-044**: The dev launcher MUST wait on the API health endpoint (bounded retries) instead of a fixed sleep, preserving its existing smart-build/preflight/prune behavior, and MUST fail loudly if the cap is reached.
- **FR-045**: The health surface MUST distinguish liveness (process up, current behavior) from readiness (migrations applied AND llama.cpp reachable).

**Refactoring & Hygiene**

- **FR-050**: The document processing task MUST be decomposed into discrete, resumable stages with per-stage status persisted on the Document, preserving resume-if-chunks-exist.
- **FR-051**: The settings API and MCP server modules MUST be split so no Python file in `app/` exceeds ~600 lines and no refactored function exceeds cyclomatic complexity 20; model management moves into a service; MCP tools are organized by domain with shared helpers.
- **FR-052**: LLM provider dispatch MUST be table-driven with no change to public `chat()` behavior or the constructor > DB > settings priority.
- **FR-053**: Upload size limits MUST be realistic per file type (replacing the global 50GB cap) and file types MUST be validated at the upload boundary.
- **FR-054**: All Python and frontend dependencies MUST be pinned via lockfiles producing reproducible builds.
- **FR-055**: Logging MUST be structured JSON with request/task IDs correlating Flask and Celery; production serving MUST use a gunicorn config file rather than inline command flags.
- **FR-056**: Refactored code MUST prefer dependency injection over module-level singletons where the cost is low, to remain testable (test suites themselves are out of scope).

### Key Entities

- **Document**: A processed source (PDF/EPUB/audio/video/YouTube); gains per-stage processing status; counts must be identical before/after.
- **Chunk**: Text segment with a 1024-dim embedding vector and DB-trigger-maintained search vector; the most protected entity — no drops, no re-embeds.
- **Collection / Conversation**: User-facing groupings and chat history; preserved bit-for-bit through migrations.
- **UserPreferences / LLMConnection**: Stored provider choices; rows referencing ollama are migrated to a working provider; `local_llm_model` becomes a real column.
- **Migration Revision**: Versioned, reviewed schema/data change; the baseline reflects verified live state; the only mechanism allowed to alter schema.
- **Backup Artifact**: Timestamped database dump in `backups/`; precondition for all schema work; excluded from version control.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A timestamped database dump exists in `backups/` with a creation time earlier than the first migration-related change.
- **SC-002**: Row counts for documents, chunks, collections, and conversations are identical before and after all workstreams; existing search and chat over prior documents return results as before (embeddings still valid).
- **SC-003**: Case-insensitive search for "ollama" across the repository yields zero hits outside migration history and `backups/`.
- **SC-004**: Search for `render_template` in the backend yields zero hits and no `templates/` directory exists under `app/`.
- **SC-005**: No Docker socket is mounted into any service without a documented consumer (expected: none remain).
- **SC-006**: Booting the app performs zero schema changes, and running the migration upgrade against the stamped live database is a no-op.
- **SC-007**: Starting all containers with networking disabled succeeds using only the built images.
- **SC-008**: No Python file under `app/` exceeds ~600 lines; the four named hotspot functions each measure at or below cyclomatic complexity 20.
- **SC-009**: Two consecutive clean builds resolve byte-identical dependency sets (backend and frontend).
- **SC-010**: A single request/task ID retrieved from an app log line locates the corresponding worker log lines; both streams are structured JSON.
- **SC-011**: The dev launcher proceeds within seconds of the API becoming healthy and aborts with a clear message if health is never reached within its cap.
- **SC-012**: Database, cache, and admin UI ports are reachable from the local machine only; the admin UI is absent unless explicitly enabled. The app (5000) and frontend (5200) ports remain reachable across the local network, verified by loading the SPA from a phone on the same network.
- **SC-013**: Keyword search returns results where it previously returned none: zero chunks have an empty `search_vector`, a search for a distinctive term known to appear in an existing document surfaces that document, and a newly processed document's chunks are keyword-searchable without manual intervention.

## Accepted Risks

Knowingly accepted for this feature, recorded so they read as decisions rather than oversights.

- **AR-001 — Unauthenticated LAN exposure of the application and web UI.** Ports 5000 and 5200 stay published on all interfaces so the SPA can be used from the operator's phone. Any device that can route to this machine can therefore read and modify the entire knowledge base without credentials. Accepted because the deployment sits on a trusted home network and mobile access is a wanted capability. **Mitigation is a dedicated future authentication spec**, which is the point at which this risk closes. Until then, the system should not be used on untrusted networks (public wifi, shared office LANs), and it must not be port-forwarded to the internet.
- **AR-002 — Provider API keys stored in plaintext.** `llm_connections.api_key` holds credentials in clear text in the database. Consistent with the single-operator threat model (the operator owns the machine), but note that AR-001 widens who can read them: anyone with LAN access to the settings API can retrieve stored keys. Secrets management is out of scope here and is a natural companion to the future authentication work.

## Assumptions

- The live compose environment is the source of truth for embedding config: vectors were produced by local sentence-transformers with BAAI/bge-m3 at dimension 1024; the settings-code default saying "ollama" is simply wrong and will be corrected to `local`.
- CLAUDE.md's claim that Alembic is in use is incorrect; `migrations/` holds only a raw SQL file, so adoption starts from a hand-written baseline against the live schema (verified, not assumed).
- "Production" means the operator's self-hosted deployment: single user, no public internet exposure, reachable from the operator's own devices on a trusted local network. Auth/authz, TLS, and rate limiting are deferred to a follow-up authentication spec rather than judged unnecessary (see AR-001).
- Ollama fallback target: rows referencing ollama as the LLM provider fall back to `llamacpp`; anything that only the generic custom connection can represent falls back to `custom`.
- The `RUN_MIGRATIONS` env var already exists but is inert; giving it effect (gating `flask db upgrade` in the entrypoint) is the intended behavior, defaulting to not running migrations when unset.
- Realistic upload limits will be set per file type at sane defaults (e.g., documents far smaller than media) rather than one global cap; exact numbers are an implementation-time decision within the "realistic" requirement.
- ~600 lines and cyclomatic 20 are working thresholds ("no monster files/functions"), not hard style law for pre-existing files outside the named hotspots.
- VideoMix modules are excluded from all workstreams, including refactoring thresholds and the ollama grep only insofar as they contain no ollama references (if they do, that will be surfaced rather than silently edited).
- Windows is the host platform; backup and launcher behavior target the existing `docker-compose` + `start-dev.bat` workflow.
