# Implementation Plan: Production Readiness — Local-Only, Single-User Deployment

**Branch**: `003-production-readiness` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-production-readiness/spec.md`

## Summary

Bring MNEMOS to a production-ready operational baseline for its actual deployment model (one machine, one user, self-hosted on a trusted home network with the SPA reachable from mobile, no public internet exposure) without risking the live knowledge base: 58 documents, 6,150 chunks with valid 1024-dim vectors, 8 collections, 143 conversations.

Six sequenced workstreams: take a data-safety backup, delete the dead HTMX/Jinja UI, purge Ollama entirely, adopt Alembic by **baselining against the verified live schema**, harden Docker and the launcher, then refactor the complexity hotspots with pinned dependencies and structured logging.

**Approach**: every claim in the spec was verified against the running database before planning. Three turned out to be wrong (see Key Discoveries) and the plan is built on the measured reality, not the documentation.

## Key Discoveries (change the plan vs. the spec)

Full detail in [research.md](./research.md). Summary of what differs from what the spec assumed:

1. **The FTS trigger does not exist and full-text search has never worked.** The live DB has zero triggers; all 6,150 `search_vector` values are NULL. The documented hybrid RRF retrieval has been running as pure vector search, silently. The spec asked to *preserve* this trigger; instead the baseline records reality and an explicit revision *creates* the trigger and backfills (confirmed in scope by clarification). (research F2)

2. **`phase2_strip_embeddings.sql` was already applied, and code still references the dropped columns.** `RAGService.search_similar_documents` queries `Document.summary_embedding` / `summary_search_vector`, which no longer exist — so the MCP tool `search_similar_documents` raises whenever called. It gets removed as dead code rather than preserved. (research F3)

3. **The four startup `ALTER TABLE` blocks are already applied.** Their columns exist in the live schema, so they are captured *by the baseline* and the startup code is simply deleted — not "converted into revisions" as FR-031 assumed. Same for the `collection_documents` backfill, which is idempotent and already done. (data-model)

Two smaller corrections: `EMBEDDING_MODEL`'s code default (`bge-m3`) also diverges from the live value (`BAAI/bge-m3`), not just `EMBEDDING_PROVIDER`; and the Ollama footprint spans 40+ files including the installer and six frontend components, well beyond the spec's enumeration.

## Technical Context

**Language/Version**: Python 3.11 (backend, `python:3.11-slim`); TypeScript / Angular 21 (frontend)

**Primary Dependencies**: Flask 3, SQLAlchemy 2, Flask-Migrate + Alembic (installed, unconfigured), Celery + Redis, pgvector, sentence-transformers (BAAI/bge-m3), llama.cpp server, gunicorn

**Storage**: PostgreSQL 16 + pgvector (`pgvector/pgvector:pg16`), volume `postgres_data`; Redis 7 with AOF, volume `redis_data`

**Testing**: No suite exists and none is added (out of scope per HC-5). Verification is by measured checks: row counts, greps, complexity measurement (`radon cc`), live endpoint polls, and a real document-processing run. Refactors favor dependency injection so a future suite is cheap.

**Target Platform**: Windows 11 host, Docker Desktop, NVIDIA GPU; launched via `start-dev.bat`

**Project Type**: Containerized web application — Flask API + Celery worker + Angular SPA + MCP server, all orchestrated by docker-compose

**Performance Goals**: No regression. Specifically: container start must not require network (currently blocked on a `pip install`), and redundant GPU model loads (4× embedder pre-warm under `gunicorn -w 4`) are eliminated.

**Constraints**: HC-1..HC-5 from the spec. Operationally: never `docker-compose down -v`, never drop `postgres_data`/`redis_data`, never drop or recreate `chunks`, `EMBEDDING_DIMENSION` stays 1024, model stays BAAI/bge-m3, no re-embedding.

**Scale/Scope**: Single user, ~12.4k lines of Python across `app/`, 58 documents / 6,150 chunks live, 17 tables.

## Constitution Check

`.specify/memory/constitution.md` is an **unfilled template** — every principle is still a `[PRINCIPLE_N_NAME]` placeholder and the version/ratification fields are unpopulated. There are no ratified project principles to gate against.

**Result: PASS (vacuous).** No violations are possible because no constraints are defined.

The spec's own hard constraints (HC-1..HC-5) serve as this feature's gates and are enforced throughout the plan:

| Gate | Enforcement |
|---|---|
| HC-1 backup precedes migrations | Phase 1 is a blocking prerequisite for Phase 4 |
| HC-2 no volume/table destruction | No task uses `down -v`; no revision drops a populated table; the one DROP COLUMN is called out in data-model C3 with an exact downgrade |
| HC-3 vectors stay valid | No revision touches `chunks.embedding`; no re-embed anywhere; dimension pinned at 1024 |
| HC-4 surface violations | Two surfaced already (FTS trigger absent, phase2 applied); the destructive `ollama_num_ctx` drop is surfaced as a reviewable decision |
| HC-5 scope | VideoMix untouched (but its tables **are** in the baseline, so autogenerate never proposes dropping them); no test suites written |

**Recommendation**: filling in the constitution is worth doing separately — it would give future features real gates. Out of scope here.

## Project Structure

### Documentation (this feature)

```text
specs/003-production-readiness/
├── plan.md                        # This file
├── spec.md                        # Feature specification
├── research.md                    # Phase 0 — live-DB findings F1-F12
├── data-model.md                  # Phase 1 — baseline inventory + revisions C1-C4
├── contracts/
│   ├── health-readiness.md        # /api/health (unchanged) + /api/ready (new), migration gate
│   └── api-surface-changes.md     # JSON-only routes, removed endpoints/tools, upload limits, logging
├── quickstart.md                  # Phase 1 — verification runbook
└── tasks.md                       # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
app/
├── __init__.py                    # STRIP: create_all, 4 ALTER blocks, backfill INSERT, embedder pre-warm
├── web.py                         # DELETE
├── templates/  static/            # DELETE
├── api/
│   ├── ollama_manage.py           # DELETE
│   ├── settings.py                # SPLIT (1,278 lines) → focused blueprints + services
│   ├── chat.py  documents.py  conversations.py   # strip HX-Request render_template branches
│   └── ...
├── services/
│   ├── rag_method_dump.py         # DELETE
│   ├── rag.py                     # 723 lines — remove dead search_similar_documents, light split
│   ├── llm_client.py              # provider-config table replaces if/elif dispatch
│   └── embedder.py                # remove Ollama branch
├── tasks/processing.py            # decompose process_document_task into resumable stages
├── mcp_server/server.py           # SPLIT (1,783 lines) → per-domain tool modules
├── utils/docker_helpers.py        # DELETE (only consumer was ollama_manage)
└── models/                        # unchanged except user_preferences.local_llm_model

config/settings.py                 # remove OLLAMA_*, fix EMBEDDING_PROVIDER/MODEL defaults, upload limits
migrations/                        # NEW: env.py, alembic.ini, versions/ (baseline + 5 revisions)
scripts/update_schema.py           # DELETE
scripts/run_migration.py           # DELETE
requirements.in / requirements.txt # NEW .in + compiled pins
Dockerfile                         # non-root user, relocated caches, gunicorn.conf.py
gunicorn.conf.py                   # NEW
entrypoint.sh                      # remove pip install; add gated flask db upgrade
docker-compose{,.dev,.cpu}.yml     # healthchecks, restart policies, 127.0.0.1 binds, drop docker.sock, drop ollama
start-dev.bat                      # poll /api/health instead of timeout /t 15
frontend_spa/src/app/              # remove Ollama UI across 6+ components
backups/                           # exists, git-ignored — pre-migration dump lands here
```

**Structure Decision**: Existing layout is kept. This feature deletes and reorganizes within `app/`; it does not introduce a new top-level structure. The only new directories are `migrations/versions/` and the contracts/docs under `specs/`.

## Implementation Phases

Ordering is driven by dependency, not by the spec's numbering. The critical constraint: **backup blocks migrations**, and **Ollama purge precedes the Alembic revisions** that carry its data migration.

### Phase 1 — Data safety gate (blocks Phases 4+)

Take a fresh timestamped `pg_dump` into `backups/`, record the four baseline row counts (58 / 6,150 / 8 / 143), and verify the dump restores into a scratch database. `backups/` already exists and is already git-ignored at `.gitignore:230`; a 232 MB dump from 2026-08-01 18:58 is present but a fresh one is taken regardless.

**Exit**: restorable dump exists, counts recorded. No later phase may begin migration work until this passes.

### Phase 2 — Dead code removal (no schema impact, safe to parallelize)

Delete `app/web.py`, `templates/`, `static/`, `rag_method_dump.py`, the six `HX-Request` branches, the dead `RAGService.search_similar_documents` plus its MCP tool, and the ad-hoc `scripts/`. Remove the unused `import docker` from `processing.py`.

**Why first**: shrinks the surface every later phase touches, and all of it is provably unreferenced by the SPA (branches are header-gated) or provably broken (the dead RAG method).

**Exit**: zero `render_template` hits in `app/`; SPA chat/documents/conversations still work.

### Phase 3 — Ollama purge (must precede Phase 4's fallback revision)

Backend: delete `ollama_manage.py` + its blueprint registration, remove `OLLAMA` from `LLMProvider`, strip Ollama branches from `llm_client.py` / `embedder.py` / `memory_service.py` / `hf_downloader.py` / `mcp_server`, remove `map_hf_to_ollama` and pull logic from `settings.py`, remove `OLLAMA_*` from `config/settings.py` and `.env.example`.

Config defaults corrected: `EMBEDDING_PROVIDER = "local"`, `EMBEDDING_MODEL = "BAAI/bge-m3"` (both diverge from live today).

Frontend: remove Ollama UI from the settings discover tab, `llm-selection-modal`, `llm-selector`, `chat-input`, `chat-page`, `api-endpoints.ts`, `settings.model.ts`, `settings.service.ts` — **together with the backend blueprint removal**, or the settings page 404s.

Infrastructure: delete `docker_helpers.py`, remove both `/var/run/docker.sock` mounts, drop `docker>=7.0.0` from requirements, remove the `ollama` service from `docker-compose.cpu.yml:20`, purge docs (CLAUDE.md, README, presets, installer).

Runtime safety: provider resolution must fall back to `llamacpp` on an unrecognized stored value **before** the data migration runs, since `RUN_MIGRATIONS` may be false.

**Exit**: grep for "ollama" is clean outside `frontend_spa/dist/` (build artifacts), `.agent/` (dated design notes), `backups/`, and migration history.

### Phase 4 — Alembic adoption (gated on Phase 1; carries Phase 3's data migration)

1. `flask db init` — creates `migrations/env.py`, `alembic.ini`, `versions/`.
2. **Hand-write the baseline** reflecting the verified live schema: all 17 tables (VideoMix included), the `vector` extension, both enums, and the HNSW index with its exact operator class and build parameters (`m=16, ef_construction=64`). Columns dropped by phase2 stay absent; columns added by the startup ALTERs are present.
3. `flask db stamp <baseline>` — never execute it against the live DB.
4. **Prove the baseline is faithful**: run `flask db migrate` and confirm the generated revision is **empty**. Discard it. A non-empty diff means the baseline is wrong — fix it before continuing. This check is the real validation, more than any review.
5. Write revisions 001-005 per [data-model.md](./data-model.md): add `local_llm_model`, `collection_documents` backfill, ollama fallback, drop `ollama_num_ctx` (destructive — reviewed, exact downgrade), FTS trigger + backfill.
6. Strip `create_app()`: remove `db.create_all()`, the four ALTER blocks, the backfill INSERT, and the embedder pre-warm. Remove the `getattr(db_prefs, 'local_llm_model', None)` workaround.
7. Wire `flask db upgrade` into `entrypoint.sh` gated on `RUN_MIGRATIONS=true`, for the `app` service only — the worker and mcp services must not race on schema.

**Exit**: app boots with zero DDL; `flask db upgrade` reaches head; row counts unchanged.

### Phase 5 — Docker & launcher hardening

Entrypoint: remove `pip install --upgrade yt-dlp`, pin `yt-dlp` in requirements.

Compose (all three files): redis healthcheck + `service_healthy`; `unless-stopped` on app/worker/db/redis; bind `5433`/`6380`/`8080` to `127.0.0.1`; adminer behind a `tools` profile; `CELERY_POOL`/`CELERY_CONCURRENCY` env with `solo` default and a comment explaining GPU contention.

**Resolved (clarification 2026-08-01)**: ports `5000` and `5200` **stay published on all interfaces**. Mobile access to the SPA over the LAN is a required capability, and authentication is deferred to its own future spec. This is recorded as accepted risk AR-001 in the spec. Compose changes must not silently "harden" these two ports — only `5433`, `6380`, and `8080` move to `127.0.0.1`.

Dockerfile — **the riskiest task in the feature**: adding a non-root user requires relocating the Whisper and HuggingFace caches off `/root/.cache`, coordinated across the Dockerfile `COPY --from=builder` target and the mount targets in all three compose files, plus write access to `uploads/`, `archive/`, and `models/`. Verified by an actual document-processing run, not merely by "the container started". Add `gunicorn.conf.py` replacing inline CMD flags.

Launcher: replace `start-dev.bat:77`'s `timeout /t 15` with a bounded poll of `/api/health` (~90s cap, 3s interval — the endpoint self-caches for 5s so faster polling is wasted), aborting loudly on timeout. Keep smart-build, preflight, and prune logic untouched.

Add `GET /api/ready` per [contracts/health-readiness.md](./contracts/health-readiness.md) — separate from `/api/health`, which stays byte-for-byte as-is.

**Exit**: stack starts with networking disabled; killed containers restart; db/redis/adminer local-only.

### Phase 6 — Refactors, pinning, observability

`process_document_task` → resumable stages (extract, chunk, embed, save, summarize, hypergraph) with per-stage status in `documents.metadata_` (jsonb, no schema change needed; remember `flag_modified`), preserving resume-if-chunks-exist.

Split `mcp_server/server.py` (1,783) by domain and `api/settings.py` (1,278) into blueprints + services; decompose `save_chat_settings`. **Also split `services/rag.py`** — at 723 lines it exceeds SC-008's ~600 threshold despite not being named in the spec; this is the one place the plan adds scope, and it does so to satisfy the spec's own success criterion.

`LLMClient` dispatch → provider-config table, preserving `chat()` behavior and constructor > DB > settings priority exactly.

Upload limits per file type with boundary validation (see contracts). Pin backend deps via `pip-tools` (`requirements.in` → compiled `requirements.txt`), compiled from inside `python:3.11-slim` so wheels match the image; ensure the frontend build uses `npm ci` against the existing `package-lock.json`. Structured JSON logging with `request_id` propagated from Flask into Celery task headers.

**Exit**: no `app/` Python file over ~600 lines; `radon cc` shows no refactored function above 20; two clean builds resolve identically; a request ID correlates app and worker logs.

## Risks

| Risk | Mitigation |
|---|---|
| Baseline doesn't match live schema → later autogenerate proposes destructive diffs | The empty-diff check in Phase 4 step 4 is a hard gate before any revision is written |
| Non-root user breaks model caches / bind-mount writes | Relocate caches and verify with a real processing run; single coordinated task across Dockerfile + 3 compose files |
| Frontend and backend Ollama removal land separately → settings page 404s | Treated as one atomic change in Phase 3 |
| FTS backfill uses a text-search config that doesn't match query-time | Verify by running an actual keyword search that previously returned nothing; row-count check alone is insufficient |
| Refactoring the 1,783-line MCP server silently changes tool behavior | Reorganization only — tool names and signatures fixed by contract; verify by listing tools from Claude Desktop before/after |
| `RUN_MIGRATIONS=true` on worker + app races on schema | Gate set only on `app` |

## Complexity Tracking

No constitution gates exist to violate, so this table records the two places the plan **deliberately exceeds the spec**, for reviewer visibility:

| Deviation | Why Needed | Alternative Rejected Because |
|---|---|---|
| Split `services/rag.py` (723 lines), not named in the spec's hotspot list | SC-008 requires no `app/` file over ~600 lines; `rag.py` violates it | Leaving it would fail the spec's own success criterion; raising the threshold would weaken a stated goal |
| Add FTS trigger + backfill (spec said "preserve" an existing trigger) | The trigger never existed; keyword retrieval returns nothing for all 6,150 chunks | Baselining the broken state as "correct" would permanently enshrine a silently degraded retrieval pipeline; the fix is additive and cheap |

## Out of Scope (restated)

Authentication/authorization; the VideoMix feature (code untouched — but its tables **are** in the migration baseline); unit/e2e test suites; re-embedding or any change to vector dimension or embedding model; restoring summary-level document search (would require re-adding dropped vector columns).

## Observation not addressed

`llm_connections` stores a provider API key in plaintext, visible in the table. For a single-user local deployment this is consistent with the threat model (the operator owns the machine), and secrets management is not in this feature's scope — noted so it is a recorded decision rather than an oversight.
