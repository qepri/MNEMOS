# Tasks: Automated Test Suite

**Input**: Design documents from `/specs/004-test-suite/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: This feature's deliverable *is* the test suite — there is no separate "write tests first, then implement" split. Each task below directly produces test code, fixtures, or CI config against the real application code that already exists.

**Organization**: Tasks are grouped by user story from spec.md (US1–US4), in priority order.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps to spec.md user stories (US1–US4)

## Path Conventions

Per plan.md's Project Structure: `tests/` and `requirements-dev.txt` at repo root; `frontend_spa/src/app/**/*.spec.ts` and `frontend_spa/vitest.config.ts` for the SPA; `.github/workflows/tests.yml` for CI; `coverage-baseline.json` at repo root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Get a runnable, empty test harness in place before any real test is written.

- [x] T001 Create `requirements-dev.txt` at repo root with pytest, pytest-cov, testcontainers[postgres], respx, responses, factory_boy (or plain builder functions per data-model.md) — kept separate from `requirements.lock.txt` per plan.md constraint (never slow `docker-compose up`)
- [x] T002 Create `pytest.ini` at repo root: `testpaths = tests`, register markers `api`, `service`, `pipeline`, `migration`, `slow` (per contracts/fixtures.md § Markers), and coverage config pointing at `app/`
- [x] T003 [P] Create `tests/__init__.py`, `tests/api/__init__.py`, `tests/services/__init__.py`, `tests/pipeline/__init__.py`, `tests/migrations/__init__.py` (empty package markers)
- [x] T004 [P] Create `tests/fakes/__init__.py`

**Checkpoint**: `pytest --collect-only` runs cleanly with zero tests collected.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared fixture layer every user story's tests depend on. Implements research.md D1–D6 and contracts/fixtures.md in full.

**⚠️ CRITICAL**: No test file in Phases 3–6 can be written until this phase passes its own smoke check.

- [x] T005 Implement session-scoped `postgres_url` fixture in `tests/conftest.py`: start a `pgvector/pgvector:pg16` testcontainer on a random host port (research D1)
- [x] T006 [P] Implement session-scoped `redis_url` fixture in `tests/conftest.py`: start a `redis:7-alpine` testcontainer on a random host port (research D1)
- [x] T007 Implement `migrated_schema` fixture in `tests/conftest.py`: export `DATABASE_URL`/`REDIS_URL` env vars from T005/T006 **before** any `app`/`config.settings` import, then run the real Alembic chain to head via Alembic's Python API (`alembic.command.upgrade`) — never `db.create_all()` (research D2, D4); assert non-empty head revision; on failure, surface the offending revision in the error message (FR-009)
- [x] T008 Implement session-scoped `app` fixture in `tests/conftest.py`: call `create_app()` only after T007 has set the environment (research D4)
- [x] T009 Implement `assert_not_dev_database` autouse session fixture in `tests/conftest.py`: assert the configured DB host/port matches the container's from T005, abort the entire run otherwise (FR-002, contracts/fixtures.md)
- [x] T010 Implement `db_session` function-scoped fixture in `tests/conftest.py`: open a nested transaction/savepoint on the app's engine, roll back at teardown (research D3)
- [x] T011 [P] Implement `committing_db` function-scoped fixture in `tests/conftest.py`: commits for real, truncates affected tables at teardown — for trigger-behavior tests only (research D3)
- [x] T012 [P] Implement `client` fixture in `tests/conftest.py`: Flask test client bound to `app`, sharing `db_session`'s transaction
- [x] T013 [P] Implement `tmp_uploads` fixture in `tests/conftest.py`: override `UPLOAD_FOLDER` to a `tmp_path`-backed directory so no test writes into the real `uploads/`
- [x] T014 [P] Implement `no_external_network` autouse fixture in `tests/conftest.py`: fail any test whose HTTP call reaches a host that is neither a test container nor a registered fake (research D5, spec edge case)
- [x] T015 [P] Implement `fake_llm` fixture in `tests/fakes/llm.py`: intercept outbound HTTP at the transport layer for the OpenAI-SDK-compatible providers (respx for httpx/Anthropic, responses for OpenAI SDK transport) with `.completion(...)` to queue responses and `.calls` to assert requests (research D5, contracts/fixtures.md)
- [x] T016 [P] Implement `fake_embeddings` fixture in `tests/fakes/embeddings.py`: deterministic vectors of exactly `EMBEDDING_DIMENSION` (1024) floats, same content ⇒ same vector (research D5)
- [x] T017 [P] Implement `document_factory` and `chunk_factory` in `tests/factories.py` per data-model.md's DocumentFixture/ChunkFixture: chunk factory never sets `search_vector` directly — left to the DB trigger
- [x] T018 Write a foundational smoke test `tests/test_harness_smoke.py`: insert a document+chunk via the factories through `db_session`, assert the row round-trips and `search_vector` is populated by the trigger (proves T005–T017 all wire together correctly)

**Checkpoint**: `pytest tests/test_harness_smoke.py` passes against a real, migrated, disposable database. Foundation ready for all user stories.

---

## Phase 3: User Story 1 - Maintainer verifies a change before merging (Priority: P1) 🎯 MVP

**Goal**: A single documented command exercises Flask API routes, backend services, and Celery pipeline stages against the real database, faking only external LLM/embedding network calls.

**Independent Test**: Run `pytest` from a clean checkout per quickstart.md; observe real DB reads/writes and a clear pass/fail result, with the dev database untouched.

### Implementation for User Story 1

- [x] T019 [P] [US1] API tests for document upload/validation in `tests/api/test_documents.py`: valid upload persists via `app/api/documents.py`; unsupported extension → 400; oversize per `MAX_UPLOAD_BY_TYPE` → 413 (per CLAUDE.md Uploads section)
- [x] T020 [P] [US1] API tests for health/readiness divergence in `tests/api/test_health.py`: `/api/health` liveness-only 200; `/api/ready` 503 when llama.cpp probe fails while `/api/health` stays 200 (per CLAUDE.md)
- [x] T021 [P] [US1] API tests for chat in `tests/api/test_chat.py` using `fake_llm`: request/response flow, citations present when `document_ids` supplied
- [x] T022 [P] [US1] API tests for collections in `tests/api/test_collections.py`
- [x] T023 [P] [US1] API tests for settings/provider selection in `tests/api/test_settings.py`, including the stale `ollama` → `llamacpp` fallback-with-warning behavior (per CLAUDE.md LLM Client section)
- [x] T024 [P] [US1] Service tests for `LLMClient` in `tests/services/test_llm_client.py` using `fake_llm`: provider-priority resolution (constructor arg > DB `UserPreferences` > settings.py), table-driven `PROVIDER_SPECS` dispatch, unknown-provider fallback to llamacpp with a warning
- [x] T025 [P] [US1] Service tests for `EmbedderService` in `tests/services/test_embedder.py` using `fake_embeddings`: batch size (100 chunks/batch), dimension enforcement against `EMBEDDING_DIMENSION`
- [x] T026 [P] [US1] Service tests for `ChunkerService` in `tests/services/test_chunker.py`: `CHUNK_SIZE`/`CHUNK_OVERLAP` defaults and per-user `UserPreferences` overrides
- [x] T027 [US1] Service tests for the RAG pipeline in `tests/services/test_rag.py` (depends on T017, T025): cosine vector search, PostgreSQL FTS via `plainto_tsquery`, RRF merge (k=60), MMR re-rank (λ=0.7), adjacent-chunk expansion (chunk_index ±1), token budget drop-lowest-chunks behavior, and the intended no-`document_ids` ⇒ no-sources behavior (per CLAUDE.md RAG section)
- [x] T028 [P] [US1] Pipeline stage tests in `tests/pipeline/test_stages.py` (depends on T017): `stage_extract`, `stage_detect_language`, `stage_embed_and_save`, `stage_summarize` (using `fake_llm`), `stage_hypergraph` (using `fake_llm`) — each called directly against `db_session`, asserting `Document.metadata_['pipeline']` records each stage's outcome
- [x] T029 [US1] Orchestrator/resume-logic tests in `tests/pipeline/test_processing.py` (depends on T028): `process_document_task` with `task_always_eager=True`; resume behavior skips extraction/embedding when chunks already exist and jumps to summary/hypergraph
- [x] T030 [US1] Trigger/FTS-config test in `tests/pipeline/test_search_vector.py` using `committing_db` (T011): inserting a chunk populates `search_vector` via the DB trigger; the trigger's language config matches `RAGService._detect_query_language` and the `lang_map` in `app/tasks/pipeline.py` for at least two languages (regression guard for the historical NULL-`search_vector` bug per CLAUDE.md Database section)
- [x] T031 [US1] Non-blocking-error tests: hypergraph extraction and transcription-file-save failures are caught and logged without failing the parent task (per CLAUDE.md Common Patterns), added to `tests/pipeline/test_stages.py`

**Checkpoint**: User Story 1 fully functional — `pytest -m "api or service or pipeline"` passes independently of migration/frontend suites.

---

## Phase 4: User Story 2 - Maintainer verifies a schema change is safe (Priority: P2)

**Goal**: Automated proof that the full Alembic chain applies cleanly from empty to head and reverses without breaking the schema.

**Independent Test**: Point `tests/migrations/test_migrations.py` at its own scratch database; confirm full upgrade then downgrade with no manual DB involved.

### Implementation for User Story 2

- [x] T032 [US2] Scratch-database fixture in `tests/migrations/conftest.py`: a dedicated testcontainer (independent of the shared `migrated_schema` session fixture in T007, per plan.md's isolation note) so a downgrade test cannot corrupt Phase 3's schema
- [x] T033 [US2] Migration upgrade test in `tests/migrations/test_migrations.py` (depends on T032): applies every revision in order from empty schema to `heads`; on failure, the assertion names the specific revision that broke (FR-009)
- [x] T034 [US2] Migration downgrade test in `tests/migrations/test_migrations.py` (depends on T032): downgrades from head to base (or to `-1` per revision, whichever matches the existing revision chain), asserting no error and a clean resulting schema state
- [x] T035 [US2] Baseline-revision regression test in `tests/migrations/test_migrations.py`: confirms `594d02684e1e_baseline_live_schema.py` alone produces the `update_chunk_search_vector` trigger once `a005_chunks_fts`/`a006_fix_ts_config` are applied on top (per CLAUDE.md Database section)

**Checkpoint**: `pytest -m migration` passes independently, using its own database, never touching the Phase 2/3 schema.

---

## Phase 5: User Story 3 - Maintainer verifies the frontend still works (Priority: P3)

**Goal**: Fast automated smoke checks for the chat, document upload, and settings screens using Angular 21's native Vitest runner.

**Independent Test**: Run `npm test` in `frontend_spa/` per quickstart.md; confirm it exercises all three screens without the full Docker stack running.

### Implementation for User Story 3

- [x] T036 [US3] Add `vitest` and `jsdom` to `frontend_spa/package.json` devDependencies; add a `"test"` target using `@angular/build:unit-test` with `"runner": "vitest"` in `frontend_spa/angular.json` (research D7 — verified as the builder's own default)
- [x] T037 [P] [US3] Create `frontend_spa/vitest.config.ts` only if the default builder config proves insufficient for jsdom/environment needs (research D7)
- [x] T038 [P] [US3] Smoke test for the chat screen: component renders, basic message-send interaction, in the relevant `*.component.spec.ts` under `frontend_spa/src/app/`
- [x] T039 [P] [US3] Smoke test for the document upload screen: component renders, file-select interaction, in the relevant `*.component.spec.ts` under `frontend_spa/src/app/`
- [x] T040 [P] [US3] Smoke test for the settings screen: component renders, provider/model selection interaction, in the relevant `*.component.spec.ts` under `frontend_spa/src/app/`

**Checkpoint**: `npm test` in `frontend_spa/` passes independently of the backend suite, no Docker required.

---

## Phase 6: User Story 4 - Pull request is automatically checked (Priority: P2)

**Goal**: Every PR gets an automated pass/fail signal from freshly provisioned, disposable services, with the failing layer identifiable without local reruns.

**Independent Test**: Open a PR and confirm the workflow provisions its own containers, runs all three suites, and reports a single visible status per job.

### Implementation for User Story 4

- [x] T041 [US4] Create `.github/workflows/tests.yml` with `backend`, `migrations`, `frontend` jobs on `pull_request` and `push: main` triggers, `ubuntu-latest` runners, Python 3.11 + Node LTS setup, no `services:` block (containers come from testcontainers per research D1, contracts/ci-workflow.md)
- [x] T042 [US4] Wire the `backend` job in `.github/workflows/tests.yml`: `pip install -r requirements.lock.txt -r requirements-dev.txt`, `pytest -m "not migration" --cov`
- [x] T043 [P] [US4] Wire the `migrations` job in `.github/workflows/tests.yml`: `pytest -m migration`
- [x] T044 [P] [US4] Wire the `frontend` job in `.github/workflows/tests.yml`: `cd frontend_spa && npm ci && npm test`

**Checkpoint**: A test PR against the branch shows three separate check statuses in the GitHub UI, each provisioning and discarding its own containers.

---

## Phase 7: Coverage Ratchet (cross-cutting, FR-012/SC-007)

**Purpose**: Implements the Session 2026-08-02 clarification — report coverage everywhere, gate only the two highest-risk pipelines against regression.

- [x] T045 Configure `pytest-cov` scope groups in `pytest.ini`/`pyproject.toml`: `rag_pipeline` = `app/services/rag.py` + `app/services/rag_context.py`; `processing_pipeline` = `app/tasks/pipeline.py` + `app/tasks/processing.py` + `app/services/chunker.py` (research D8, data-model.md CoverageBaseline)
- [x] T046 Run the full suite once to measure initial coverage for both groups, then create `coverage-baseline.json` at repo root recording those percentages and the date (data-model.md CoverageBaseline)
- [x] T047 Add a coverage-gate step to the `backend` job in `.github/workflows/tests.yml` (depends on T042, T045, T046): compare measured coverage against `coverage-baseline.json`; fail with group name + baseline + measured value if either drops below its recorded baseline; never auto-raise the baseline

**Checkpoint**: A deliberately under-tested change to `app/services/rag.py` fails the `backend` job; an unrelated change with untouched RAG/pipeline coverage does not.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final documentation and validation pass across all stories.

- [x] T048 [P] Update `CLAUDE.md` line "No test suite exists in the repo currently." to describe the new `pytest` / `npm test` commands, replacing the now-inaccurate statement
- [x] T049 [P] Add a "Testing" section to `CLAUDE.md`'s Development Commands referencing `quickstart.md`'s commands (pytest subsets, coverage, frontend test)
- [x] T050 Run every command in `specs/004-test-suite/quickstart.md` from a clean checkout end-to-end (backend install → `pytest`, `frontend_spa` → `npm ci && npm test`) and fix any drift between the doc and reality
- [ ] T051 Verify SC-002 directly: run the full suite twice in a row and confirm the pre-existing dev database's `documents`/`chunks` row counts are unchanged (manual one-time verification, not an automated test)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1. **BLOCKS all of Phases 3–7.**
- **User Story 1 (Phase 3)**: Depends on Phase 2 only.
- **User Story 2 (Phase 4)**: Depends on Phase 1 only (uses its own scratch DB, not the Phase 2 fixtures) — can run in parallel with Phase 3.
- **User Story 3 (Phase 5)**: No backend dependency at all — can start immediately after Phase 1, in parallel with Phases 3–4.
- **User Story 4 (Phase 6)**: Depends on Phases 3, 4, and 5 existing (it wires them into CI) — must come after at least one real test exists in each suite.
- **Coverage Ratchet (Phase 7)**: Depends on Phase 3 (needs RAG/pipeline tests to measure) and Phase 6's `backend` job (T042).
- **Polish (Phase 8)**: Depends on all prior phases.

### Parallel Opportunities

- T003–T004 in parallel (different empty files).
- T006, T011–T017 in parallel within Phase 2 (independent fixture files).
- Nearly all of Phase 3's tasks (T019–T026, T028) are `[P]` — different test files, only T027/T029/T030/T031 have same-file or fixture-order dependencies noted inline.
- Phase 4 (US2) and Phase 5 (US3) can run entirely in parallel with Phase 3 (US1) and with each other, since none share files.
- T043–T044 in parallel within Phase 6 (different CI job blocks, though same file — coordinate via sequential edits to `tests.yml` if literally simultaneous).

---

## Parallel Example: User Story 1

```bash
# Once Phase 2 (Foundational) checkpoint passes, launch these together:
Task: "API tests for document upload/validation in tests/api/test_documents.py"
Task: "API tests for health/readiness divergence in tests/api/test_health.py"
Task: "API tests for chat in tests/api/test_chat.py"
Task: "Service tests for LLMClient in tests/services/test_llm_client.py"
Task: "Service tests for EmbedderService in tests/services/test_embedder.py"
Task: "Pipeline stage tests in tests/pipeline/test_stages.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational) — the fixture harness.
2. Complete Phase 3 (US1) — API/service/pipeline coverage against the real DB.
3. **STOP and VALIDATE**: `pytest -m "api or service or pipeline"` passes from a clean checkout; dev database untouched.
4. This alone already satisfies most of SC-001, SC-002, SC-004.

### Incremental Delivery

1. Setup + Foundational → harness ready.
2. US1 → maintainers get real pre-merge verification (MVP).
3. US2 → migration safety net (parallelizable with US1).
4. US3 → frontend smoke coverage (parallelizable with US1/US2).
5. US4 → CI wiring ties US1–US3 into a PR gate.
6. Coverage Ratchet → makes FR-012/SC-007 enforceable.
7. Polish → docs catch up to reality.

---

## Notes

- No task modifies application source code in `app/` or `frontend_spa/src/app/`'s component logic — this feature is additive (tests, fixtures, CI, docs) per the Constitution Check's PASS in plan.md.
- Tasks intentionally avoid a generic "write tests" phrasing — each names the exact behavior under test, drawn from CLAUDE.md and the spec's Acceptance Scenarios, so no task requires guessing what "correct" looks like.
- Commit after each checkpoint, not after every single task — checkpoints are the meaningful, independently-testable units per spec.md.
