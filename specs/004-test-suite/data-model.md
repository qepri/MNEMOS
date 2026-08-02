# Phase 1 Data Model: Automated Test Suite

**Feature**: 004-test-suite | **Date**: 2026-08-02

This feature adds no production database entities. The "data model" here is the fixture and artifact model of the test harness itself, mapped from the Key Entities in [spec.md](./spec.md).

---

## Harness entities

### TestSession

The outermost scope. One per `pytest` invocation.

| Field | Type | Notes |
|---|---|---|
| `postgres_container` | testcontainers container | image `pgvector/pgvector:pg16`, random host port |
| `redis_container` | testcontainers container | image `redis:7-alpine`, random host port |
| `database_url` | str | container URL, exported to env **before** first `app` import |
| `redis_url` | str | same |
| `schema_revision` | str | Alembic head after upgrade; asserted non-empty |

**Lifecycle**: created (session start) → containers ready → env exported → Alembic upgraded to head → *tests run* → containers destroyed. Destruction is unconditional, including on test failure or interrupt.

**Validation rules**:
- `database_url` host/port MUST match the container's, never `db:5432` or `localhost:5432` (dev-stack guard, FR-002).
- Schema MUST be built by the Alembic chain; `db.create_all()` MUST NOT be called (D2 — otherwise the `search_vector` trigger is silently absent).

---

### TestTransaction

Per-test isolation unit.

| Field | Type | Notes |
|---|---|---|
| `connection` | SQLAlchemy Connection | bound to the session engine |
| `savepoint` | nested transaction | rolled back at teardown |

**Lifecycle**: begin → test body → rollback (always; never commit).

**State transitions**: `open → rolled_back`. There is no `committed` state for the default fixture. Tests needing real commit semantics (e.g. verifying the `update_chunk_search_vector` trigger fires) use a distinct `committing_db` fixture that truncates affected tables on teardown instead.

---

### DocumentFixture

Builder for the domain objects the pipeline and RAG tests operate on. Mirrors the real models rather than substituting for them.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | generated |
| `filename` | str | |
| `file_type` | enum | `pdf` / `epub` / `audio` / `video` / `youtube` |
| `language` | str | drives FTS config selection |
| `metadata_` | JSONB | includes `pipeline` stage outcomes |
| `chunks` | list[ChunkFixture] | |

**Validation rules**:
- `metadata_` mutations in tests MUST use `flag_modified` or full reassignment, matching the production pattern in CLAUDE.md.
- A document under test MUST NOT reference any file outside the per-test temporary upload directory.

---

### ChunkFixture

| Field | Type | Notes |
|---|---|---|
| `document_id` | UUID FK | |
| `chunk_index` | int | adjacency tests depend on contiguous values (RAG step 5) |
| `content` | str | |
| `embedding` | Vector(1024) | MUST match `EMBEDDING_DIMENSION`; deterministic, not random |
| `search_vector` | TSVECTOR | populated by DB trigger, never set directly by the fixture |
| `metadata_` | JSONB | `chunk_type: "diagram"` for vision-path chunks |

**Validation rules**:
- Embedding dimension mismatch MUST fail loudly at insert (pgvector enforces this) — treated as a feature, it catches `EMBEDDING_DIMENSION` drift.
- `search_vector` MUST be left to the trigger; a fixture that sets it manually would mask trigger breakage.

---

### ExternalProviderFake

Stand-in for an outbound LLM/embedding HTTP call. Not a replacement for `LLMClient` or `EmbedderService` (FR-003).

| Field | Type | Notes |
|---|---|---|
| `provider` | enum | `openai` / `anthropic` / `groq` / `cerebras` / `deepseek` / `llamacpp` / `lm_studio` / `custom` |
| `route` | URL pattern | intercepted at transport level |
| `response` | dict | canned completion or embedding payload |
| `call_log` | list | recorded requests, assertable (e.g. "was the vision model used?") |

**Validation rules**:
- Any outbound request to a host that is neither a test container nor a registered fake MUST fail the test immediately (spec edge case: no silent pass, no hang on a live network call).
- Embedding fakes MUST return exactly `EMBEDDING_DIMENSION` floats.

---

### CoverageBaseline

Persisted artifact backing the FR-012 ratchet.

| Field | Type | Notes |
|---|---|---|
| `rag_pipeline` | float | `app/services/rag.py`, `rag_context.py` |
| `processing_pipeline` | float | `app/tasks/pipeline.py`, `processing.py`, `app/services/chunker.py` |
| `recorded_at` | date | |

**Stored as**: `coverage-baseline.json`, tracked in git.

**State transitions**: `measured → recorded` (first run) → `compared` on each subsequent run. A measured value **below** the recorded value fails the PR check (SC-007). A measured value **above** it does not auto-update — raising the baseline is an explicit, reviewable commit, so the ratchet never moves silently.

---

### TestRunResult

| Field | Type | Notes |
|---|---|---|
| `layer` | enum | `api` / `service` / `pipeline` / `migration` / `frontend` |
| `outcome` | enum | `passed` / `failed` / `error` |
| `coverage` | CoverageBaseline | backend runs only |

`layer` exists so failures identify which layer broke without log spelunking (FR-009); in CI it maps to separate jobs, and locally to the `tests/` subdirectory and pytest markers.

---

## Relationships

```text
TestSession 1──* TestTransaction 1──* DocumentFixture 1──* ChunkFixture
TestSession 1──* ExternalProviderFake
TestSession 1──1 CoverageBaseline (backend runs)
TestSession 1──* TestRunResult
```

## Notes

No Alembic revision is added by this feature. `tests/migrations/` exercises the existing chain against its own scratch database, independent of the shared `TestSession` schema, so a downgrade test cannot corrupt the schema other tests rely on.
