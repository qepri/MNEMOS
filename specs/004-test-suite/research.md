# Phase 0 Research: Automated Test Suite

**Feature**: 004-test-suite | **Date**: 2026-08-02

All Technical Context unknowns are resolved below. No NEEDS CLARIFICATION markers remain.

---

## D1. Test database provisioning

**Decision**: `testcontainers[postgres]` starting `pgvector/pgvector:pg16`, one container per test session, plus `redis:7-alpine` for the Celery/cache paths.

**Rationale**: FR-013 requires the developer to run tests from their own environment with the disposable database supplied automatically — testcontainers does exactly that with no extra compose file to maintain and no port fixed in advance (it binds a random host port, so it cannot collide with a running dev stack on 5432). It uses the same image tag the dev stack uses, so pgvector, the extension version, and the FTS configuration match production behavior. The container is torn down at session end, satisfying "fully disposable, fresh per run" (FR-002).

**Alternatives considered**:
- *Dedicated `docker-compose.test.yml` service* — workable, but requires the developer to remember a second up/down lifecycle, pins a host port (collision risk with the dev stack, violating the "never touch the dev database" constraint in spirit), and needs separate wiring in CI. Rejected as more moving parts for the same outcome.
- *Reusing the dev database with a separate schema or transaction rollback* — rejected outright: FR-002 forbids any run touching the persistent dev data, and a bug in cleanup would destroy the 58 documents / 6150 chunks the user explicitly protected.
- *SQLite* — impossible; pgvector, `TSVECTOR`, JSONB, and the DB trigger have no SQLite equivalent, and FR-003 forbids mocking the database.

**Note on CI**: GitHub Actions `services:` can supply Postgres/Redis directly, but using testcontainers in *both* places keeps one code path (SC-001: same documented command works locally and in CI). Docker is available on `ubuntu-latest` runners, so testcontainers works there unchanged.

---

## D2. Schema setup per test run

**Decision**: Run the real Alembic chain (`flask db upgrade` equivalent via Alembic's Python API) against the fresh container once per session. Never `db.create_all()`.

**Rationale**: CLAUDE.md states Alembic is the only migration path and the app performs zero DDL at startup. Using `create_all()` in tests would build a schema that diverges from the migrated one — notably the `update_chunk_search_vector` trigger, which exists only in the `a005_chunks_fts`/`a006_fix_ts_config` revisions. Without the trigger, `search_vector` is NULL and every keyword-search test would silently pass against a broken schema, reproducing exactly the historical bug the migrations fixed. Migrating also means US2's migration tests and the main suite exercise the same code path.

**Alternatives considered**: `db.create_all()` (faster, but produces a schema the app never actually runs on — rejected per above).

---

## D3. Test isolation between tests

**Decision**: One migrated database per session; each test runs inside a transaction rolled back at teardown (nested-transaction / `SAVEPOINT` binding on the SQLAlchemy session).

**Rationale**: Migrating per test would cost seconds per test and make the suite unusable. Rollback-per-test gives full isolation at near-zero cost while still hitting real Postgres. Tests that must commit (e.g. verifying trigger behavior that fires on commit) can opt out via a dedicated fixture that truncates instead.

**Alternatives considered**: truncate-all-tables between tests (slower, and resets sequences awkwardly); fresh database per test (far too slow).

---

## D4. Configuration override

**Decision**: `tests/conftest.py` sets `DATABASE_URL` / `REDIS_URL` environment variables to the container's URLs **before** `app` or `config.settings` is imported, then calls `create_app()`.

**Rationale**: `create_app()` takes no arguments and reads a module-level `settings` object instantiated at import time (`config/settings.py`), so configuration must be in the environment before first import. This is the constraint that most shapes conftest ordering — container startup must therefore happen in a session-scoped fixture that runs before any app import, and test modules must not import `app` at module scope. Documented explicitly so the pattern is not accidentally broken later.

**Alternatives considered**: Adding a `create_app(config=...)` parameter to the application factory — cleaner long-term, but it changes production code to suit tests and is not required by any functional requirement. Deferred; revisit only if env-ordering proves fragile.

---

## D5. Boundary for external-service fakes

**Decision**: Fake at the HTTP transport layer using `respx` (for the `httpx`-based Anthropic SDK) and `responses`/monkeypatched transport for the OpenAI SDK path — not by replacing `LLMClient`, `EmbedderService`, or any internal service object.

**Rationale**: FR-003 requires internal services to run for real; only outbound network calls may be faked. Patching at the transport layer means `LLMClient`'s provider dispatch (`PROVIDER_SPECS`), its fallback-to-llamacpp behavior on unknown providers, retry handling, and response parsing are all genuinely exercised — which is the point, since those are the parts that break. Patching `LLMClient.chat` instead would leave the interesting logic untested.

**Additional guard (edge case in spec)**: the suite configures an autouse fixture that fails any test attempting a real outbound connection to a non-container host, so a missing stub fails loudly instead of hanging on a live network call.

**Embeddings**: `EmbedderService` in local mode loads `sentence-transformers` (a real model download, ~2GB, GPU-adjacent). Tests configure the remote/OpenAI-compatible embedding provider and fake it at the HTTP layer, returning deterministic fixed-dimension vectors matching `EMBEDDING_DIMENSION` (1024). This keeps the vector-search path real (pgvector does the actual similarity math) while avoiding a model download in CI.

---

## D6. Celery execution mode

**Decision**: `task_always_eager=True` for pipeline-stage tests; stages are additionally tested as plain functions where possible.

**Rationale**: `app/tasks/pipeline.py` already exposes each stage as a discrete function (`stage_extract`, `stage_detect_language`, `stage_embed_and_save`, `stage_summarize`, `stage_hypergraph`) with `process_document_task` as a thin orchestrator — so most coverage comes from calling those functions directly against a real database, no broker involved. Eager mode covers the orchestrator itself. A live worker process is unnecessary and would make the suite slow and flaky.

---

## D7. Frontend test runner

**Decision**: **Vitest**, via Angular's built-in `@angular/build:unit-test` builder.

**Rationale**: Verified against the installed toolchain — `frontend_spa/node_modules/@angular/build/src/builders/` contains a `unit-test` builder whose schema declares `"runner"` with `"default": "vitest"` and enum `["karma", "vitest"]`. Vitest is therefore the framework-native default on Angular 21, requires no third-party builder, and reuses the Vite pipeline the project already builds with. Karma remains available but is the legacy path. Note that `npm test` (`ng test`) currently fails outright — `package.json` declares the script but no test dependencies are installed at all, so this is a from-zero setup either way.

**Alternatives considered**: Karma/Jasmine (legacy, heavier, launches a real browser); Playwright/Cypress component testing (out of proportion to the smoke-level scope in FR-005).

**Dependencies to add**: `vitest`, `jsdom`, `@angular/build` test peer deps as required by the builder.

---

## D8. Coverage measurement and the ratchet

**Decision**: `pytest-cov` measuring the whole backend, with the enforced gate scoped to two path groups — the RAG pipeline (`app/services/rag.py`, `app/services/rag_context.py`) and the document processing pipeline (`app/tasks/pipeline.py`, `app/tasks/processing.py`, `app/services/chunker.py`). Baseline percentages are committed to a small tracked file; CI fails if either group falls below its recorded value.

**Rationale**: Implements the Session 2026-08-02 clarification (FR-012, SC-007) — report everything, gate only on regression in the two highest-risk areas, no arbitrary global target that would block unrelated PRs. Storing the baseline in-repo makes the ratchet explicit and reviewable in the diff when it moves up.

**Alternatives considered**: `--cov-fail-under` global threshold (blunt; punishes PRs touching untested-but-unrelated modules); third-party coverage services (external dependency and account for a single-maintainer project — rejected as overkill).

---

## D9. CI platform

**Decision**: GitHub Actions, one workflow triggered on `pull_request`, with three jobs — `backend` (pytest + coverage gate), `migrations`, `frontend` (vitest).

**Rationale**: The repository is already on GitHub (`gh` tooling available, `main` as default branch), and Actions runners provide Docker for testcontainers at no setup cost. Separate jobs give FR-009's "which layer failed" signal directly in the PR checks UI without parsing logs.

**Note**: No `services:` block is used — testcontainers manages its own containers (per D1), keeping the local and CI paths identical.

---

## D10. Keeping the dev workflow untouched

**Decision**: Test dependencies live in a separate `requirements-dev.txt`; no changes to `Dockerfile`, `docker-compose.yml`, or `entrypoint.sh`; no test service in the default compose stack.

**Rationale**: FR-008 and SC-005 require `docker-compose up -d --build` to be unaffected. Keeping test deps out of the locked runtime requirements means the app image does not grow and the build does not slow. The suite is a host-side concern (D1/FR-013), so it needs nothing from the compose stack at all.

---

## Findings from implementation

Discovered while getting the suite to actually pass, not anticipated in the original design:

**`requirements.lock.txt` is CUDA-locked, not host-installable.** It pins `torch==2.13.0` alongside standalone `nvidia-cufile`/`nvidia-cublas`/etc. lines built for the GPU container image. `pip install -r requirements.lock.txt` fails outright on Windows (no matching wheel) and would likely also fail or pull multi-GB CUDA packages needlessly on a CPU-only CI runner. Fixed by installing from the unpinned `requirements.in` with PyTorch's CPU wheel index added (`--extra-index-url https://download.pytorch.org/whl/cpu`) — both in `quickstart.md` and the CI workflow's install step. This is now the documented, verified install path for host-side testing; D1/D10 are otherwise unaffected.

**`flask_migrate.current()` prints, it doesn't return.** It's a Click-command wrapper meant for `flask db current` at a terminal — calling it as a Python function returns `None` even after a successful upgrade, which broke the `migrated_schema`/`assert_not_dev_database`-adjacent head-revision check. Fixed by reading the revision the same way `app/__init__.py`'s own `_migration_status()` already does: `MigrationContext.configure(conn).get_current_revision()` after `flask_migrate.upgrade()`. Applied in both `tests/conftest.py` and `tests/migrations/test_migrations.py`.

**The baseline migration's `downgrade()` never dropped its Postgres ENUM types.** `594d02684e1e_baseline_live_schema.py` was Alembic-autogenerated and, per its own `# please adjust!` comment, was never fully adjusted: `op.drop_table(...)` doesn't implicitly drop the `sa.Enum(...)` types those tables' columns used (`videomixstatusenum`, `renderjobstatusenum`, `file_type_enum`, `status_enum`), so a downgrade-to-base followed by a re-upgrade failed with `type "videomixstatusenum" already exists`. This path was never exercised before (no test suite, and CLAUDE.md's Database section notes the baseline was hand-verified against the live *upgrade* state, not downgrade). US2's round-trip test (`tests/migrations/test_migrations.py::test_downgrade_round_trip_does_not_error`) caught it; fixed by appending explicit `sa.Enum(name=...).drop(bind, checkfirst=True)` calls at the end of `downgrade()`, after all four owning tables are already dropped. No change to `upgrade()` or the live schema.

**Test-order pollution via `UserPreferences.llm_provider`'s DB-level default.** Two related traps, both from the same root cause: `UserPreferences.llm_provider` has `default='lm_studio'` at the SQLAlchemy column level, which only applies on flush/INSERT, not at Python object construction.
- A `committing_db`-based pipeline test that incidentally created a default `UserPreferences` row (e.g. via `stage_summarize`) left it committed in the shared container's database for the rest of the session, since `committing_db`'s truncate list is opt-in per test. Later, an unrelated `db_session`-based test's `UserPreferences.query().first()` could nondeterministically return that leftover row instead of the one it just added in its own (uncommitted) transaction. Fixed by including `"user_preferences"` in the truncate set of every `committing_db` test that could plausibly create one, and by making the affected test delete-first for defense in depth.
- Separately, `app/api/chat.py`'s get-or-create path means POSTing to `/api/chat/` seeds a real `UserPreferences` row whose `llm_provider` resolves to `'lm_studio'` (the column default) even when `settings.LLM_PROVIDER` was monkeypatched to `openai` — because DB preference outranks settings in `LLMClient`'s resolution order. A chat-route test faking the `openai` provider must seed `UserPreferences(llm_provider="openai", ...)` itself beforehand, or the route resolves to `lm_studio` and the fake never gets hit (surfacing as a 502, not an obviously-related failure).

**`tiktoken` downloads its BPE file over the network on first use.** `RAGService.query()`'s token-budget guard calls `tiktoken.get_encoding("cl100k_base")`, which fetches `cl100k_base.tiktoken` from OpenAI's public blob storage the first time it runs in a given environment — unrelated to anything a RAG test is meant to exercise, and correctly caught by the `no_external_network` guard. Fixed with a session-wide autouse fixture (`tests/conftest.py::no_tiktoken_download`) stubbing `tiktoken.get_encoding`/`encoding_for_model` with the same `len(text) // 4` approximation `_count_tokens` itself falls back to when tiktoken is unavailable.
