# Implementation Plan: Automated Test Suite

**Branch**: `004-test-suite` | **Date**: 2026-08-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-test-suite/spec.md`

## Summary

MNEMOS currently has zero automated tests; every change is verified by hand with curl, `docker exec`, and manual SQL. This feature adds a host-side pytest suite covering Flask API routes, backend services (RAG, LLM client, embedder), and the Celery pipeline stages, running against a throwaway `pgvector/pgvector:pg16` container started by testcontainers and migrated with the real Alembic chain. Only outbound LLM/embedding HTTP calls are faked; the database and all internal services run for real. A separate suite proves the migration chain upgrades and downgrades cleanly on a scratch database. The Angular SPA gets smoke-level component tests on Vitest via Angular 21's native `@angular/build:unit-test` builder. A GitHub Actions workflow runs all three on every pull request, with a coverage ratchet gating the RAG and document-processing pipelines against regression.

The persistent dev database is never touched: containers bind random host ports and are destroyed at session end.

## Technical Context

**Language/Version**: Python 3.11 (matches `python:3.11-slim` in the Dockerfile); TypeScript 5.9 for the SPA

**Primary Dependencies**: pytest, pytest-cov, testcontainers[postgres], respx/responses (HTTP-boundary fakes) — added to a new `requirements-dev.txt`, not the locked runtime deps. Frontend: vitest + jsdom via `@angular/build:unit-test`.

**Storage**: PostgreSQL 16 + pgvector, provisioned per test session as a disposable container from image `pgvector/pgvector:pg16`; Redis 7 (`redis:7-alpine`) for cache/broker paths. Schema built by running the real Alembic revisions, never `db.create_all()`.

**Testing**: pytest (backend, migrations) and Vitest (frontend). Celery stages tested as direct function calls plus `task_always_eager` for the orchestrator.

**Target Platform**: Linux CI runners (`ubuntu-latest`) and developer workstations (Windows 11 host in this case) — both need only a container runtime and a local Python 3.11 environment.

**Project Type**: Web application (Flask + Celery backend, Angular SPA frontend) with existing source layout; this feature adds a test layer, no production source restructuring.

**Performance Goals**: Full backend suite completes fast enough for pre-merge use — target under ~3 minutes on CI, dominated by one container start and one migration run per session (both session-scoped, amortized across all tests).

**Constraints**:
- Must never read or write the persistent dev database (58 documents, 6150 chunks) — enforced by random-port containers and a fixture guard, not by convention.
- Must not modify or slow `docker-compose up -d --build`: no changes to `Dockerfile`, `docker-compose.yml`, or `entrypoint.sh`; test deps stay out of the runtime lock file.
- No mocking of the DB, ORM, or internal services — fakes only at the outbound HTTP boundary.
- `config/settings.py` instantiates settings at import time, so container URLs must be in the environment before `app` is first imported.

**Scale/Scope**: ~13 API route modules, ~19 service modules, 5 pipeline stages, and the Alembic revision chain. Enforced coverage scope is narrowed to the two highest-risk pipelines; the rest is measured and reported but not gated.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` is unmodified boilerplate — every principle, section, and governance rule is still a `[PLACEHOLDER]` token with example comments. There are no ratified project principles to check against.

**Gate result: PASS (vacuous).** No constitutional constraints exist to violate, and therefore nothing requires justification in Complexity Tracking.

**Observation, not a gate**: the template's own example principle III is "Test-First (NON-NEGOTIABLE)". This feature is what would make such a principle enforceable. Worth running `/speckit-constitution` at some point to ratify real principles — but that is a separate effort and not a blocker here.

**Post-Phase 1 re-check**: unchanged — still vacuous PASS. The design adds no production-code changes at all (test-only files plus a CI workflow), so it cannot conflict with future principles about production architecture.

## Project Structure

### Documentation (this feature)

```text
specs/004-test-suite/
├── plan.md              # This file
├── spec.md              # Feature specification (with clarifications)
├── research.md          # Phase 0 output — 10 resolved decisions
├── data-model.md        # Phase 1 output — fixture/entity model
├── quickstart.md        # Phase 1 output — how to run the suite
├── contracts/           # Phase 1 output — fixture and CI contracts
│   ├── fixtures.md
│   └── ci-workflow.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
tests/                              # NEW — host-side pytest suite
├── conftest.py                     # session container, migrated schema, app fixture,
│                                   #   per-test transaction rollback, no-network guard
├── factories.py                    # Document/Chunk/Concept builders
├── fakes/
│   ├── llm.py                      # HTTP-boundary fakes for OpenAI/Anthropic/llamacpp
│   └── embeddings.py               # deterministic 1024-dim vectors
├── api/                            # Flask route tests (app/api/*)
│   ├── test_documents.py           #   incl. upload validation: 400 / 413 per type
│   ├── test_chat.py
│   ├── test_health.py              #   /api/health vs /api/ready divergence
│   ├── test_collections.py
│   └── test_settings.py
├── services/
│   ├── test_rag.py                 # RRF, MMR, adjacent-chunk expansion, token budget,
│   │                               #   no-document_ids => no sources (intended behavior)
│   ├── test_llm_client.py          # provider dispatch, unknown-provider => llamacpp fallback
│   ├── test_embedder.py
│   └── test_chunker.py
├── pipeline/
│   ├── test_stages.py              # stage_extract / detect_language / embed_and_save /
│   │                               #   summarize / hypergraph, each against real DB
│   ├── test_processing.py          # orchestrator + resume logic + metadata_['pipeline']
│   └── test_search_vector.py       # DB trigger populates search_vector; lang config
│                                   #   matches RAGService._detect_query_language
└── migrations/
    └── test_migrations.py          # baseline->head in order; downgrade round-trip

pytest.ini                          # NEW — testpaths, markers, coverage config
requirements-dev.txt                # NEW — test deps, separate from the runtime lock

frontend_spa/
├── angular.json                    # MODIFIED — add "test" target: @angular/build:unit-test
├── package.json                    # MODIFIED — add vitest + jsdom devDependencies
├── vitest.config.ts                # NEW (if advanced config needed)
└── src/app/**/                     # NEW *.spec.ts smoke tests:
                                    #   chat, document upload, settings

.github/workflows/tests.yml         # NEW — PR-triggered: backend | migrations | frontend

coverage-baseline.json              # NEW — recorded per-group baselines for the ratchet
```

**Structure Decision**: A single top-level `tests/` package mirroring the existing `app/` layout (`api/`, `services/`, `pipeline/`), plus frontend specs colocated with their components under `frontend_spa/src/app/` per Angular convention. This is the standard layout for a Flask + Angular repo and requires zero changes to production source directories — which is what keeps FR-008 (dev workflow untouched) trivially true. `tests/migrations/` is separated because those tests manage their own database lifecycle rather than using the shared migrated-session fixture.

## Key Design Decisions

Full rationale in [research.md](./research.md); the load-bearing ones:

| # | Decision | Why it matters here |
|---|---|---|
| D1 | testcontainers, not a compose test service | Random host port makes dev-DB collision structurally impossible (FR-002) |
| D2 | Real Alembic chain, never `create_all()` | `create_all()` omits the `update_chunk_search_vector` trigger — keyword-search tests would pass against a broken schema, re-creating the exact historical bug |
| D3 | Session-scoped DB, per-test transaction rollback | Isolation without paying migration cost per test |
| D4 | Env vars set before first `app` import | `config/settings.py` builds settings at import time; conftest ordering is load-bearing |
| D5 | Fake at HTTP transport, plus a fail-loud no-network guard | Keeps `LLMClient` dispatch/fallback/parsing real (FR-003); missing stubs fail instead of hanging |
| D7 | Vitest via `@angular/build:unit-test` | Verified as the builder's own default runner on the installed Angular 21 toolchain |
| D8 | Coverage ratchet on two path groups | Implements FR-012/SC-007 — regression-gated, no arbitrary global target |

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Accidental connection to the dev database | Containers bind random ports; autouse fixture asserts the configured DB host/port is the container's, and fails the run otherwise |
| Test writes real files into `uploads/` | `tmp_path`-backed upload directory override per test |
| `sentence-transformers` model download in CI (~2GB) | Tests configure the remote embedding provider and fake it at HTTP level (D5); local model path is never loaded |
| Docker unavailable on a dev machine | Suite fails fast with an explicit message (spec edge case); documented as a prerequisite in quickstart |
| Coverage baseline set too high on first run, blocking later PRs | Baseline is whatever the initial suite measures, recorded in-repo and reviewable; ratchet only moves up by explicit commit |
| Angular 21 `unit-test` builder is relatively new | Scope is smoke-level only (3 screens); Karma remains an escape hatch via the same builder's `runner` option |

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified.

Not applicable — Constitution Check passed vacuously (boilerplate constitution, no ratified principles). No violations to justify.
