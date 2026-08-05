# Implementation Plan: LLM-Optional Mode

**Branch**: `006-llm-optional-mode` | **Date**: 2026-08-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-llm-optional-mode/spec.md`

## Summary

Make MNEMOS fully usable with no LLM configured: upload, index, and search work
out of the box; summaries, chat, and the concept graph become opt-in once a
provider is connected.

Phase 0 research materially reduced this feature's scope. The ingestion pipeline
is already LLM-tolerant — `_generate_summary_logic` (`processing.py:102-105`)
swallows summary failures and `stage_hypergraph` is independently wrapped — so
the backend work is not "add guards" but "stop recording a failed summary as
completed", plus one new availability endpoint. The bulk of the remaining work is
frontend presentation and a bulk-backfill enqueue loop over two Celery tasks that
already exist.

No new database entities. No schema migration (deliberately — see R-001).

## Technical Context

**Language/Version**: Python 3.11 (Flask backend, Celery worker); TypeScript /
Angular 21 (SPA)

**Primary Dependencies**: Flask, SQLAlchemy, Alembic, Celery, Redis, pgvector,
OpenAI SDK (used for all non-Anthropic providers), Angular 21, TailwindCSS,
Cytoscape.js

**Storage**: PostgreSQL 16 + pgvector. No schema change in this feature —
per-stage outcomes use the existing `Document.metadata_` JSONB column.

**Testing**: pytest with testcontainers-provisioned Postgres/Redis (host-side,
disposable, random port); Vitest via `@angular/build:unit-test` for the SPA

**Target Platform**: Docker Compose on Windows/Linux, single-user local-first
deployment. Explicit target for this feature: a machine with **no GPU and no LLM
server installed**.

**Project Type**: Web application — Flask API + Celery worker + Angular SPA

**Performance Goals**: Availability probe must not add perceptible latency to
document list rendering — cached, short TTL (R-002). Search latency must be
unchanged from current behaviour (SC-003).

**Constraints**: No new persisted entities. No `status_enum` change (R-001).
Embedding remains unconditional (FR-016). Availability probe requires an explicit
short timeout because the LLM clients configure none (R-006).

**Scale/Scope**: Single user, single machine. Backfill is expected to run over
libraries in the tens-to-hundreds of documents, sequentially through a
`--pool=solo` Celery worker.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` is an **unfilled template** — every principle is
still a `[PRINCIPLE_N_NAME]` placeholder. There are no ratified gates to evaluate
against, so this check is vacuous rather than passing.

In its absence, the binding constraints applied are those in `CLAUDE.md`, which
this plan is checked against explicitly:

| CLAUDE.md constraint | Compliance |
|---|---|
| Alembic is the only migration path; no DDL at startup | PASS — no schema change at all (R-001) |
| `EMBEDDING_DIMENSION` must match the pgvector column | PASS — untouched; FR-016 forbids making embedding optional |
| Never run tests against the live/dev database | PASS — existing testcontainers fixtures reused |
| Non-root container user, cache paths under `/home/mnemos` | PASS — no container or volume changes |
| `RUN_MIGRATIONS=true` only on the `app` service | PASS — unaffected |

**Post-Phase-1 re-check**: still passing. The Phase 1 design adds one read-only
API endpoint, one Celery enqueue loop over existing tasks, and SPA presentation
changes. None touch schema, migrations, embedding configuration, or container
layout.

## Project Structure

### Documentation (this feature)

```text
specs/006-llm-optional-mode/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output — R-000..R-007
├── data-model.md        # Phase 1 output — state transitions, no new entities
├── quickstart.md        # Phase 1 output — verification walkthrough
├── contracts/
│   └── api-llm-availability.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
app/
├── api/
│   ├── settings.py            # MODIFY — add GET /api/settings/llm-availability
│   └── documents.py           # MODIFY — expose pipeline stage record on status
├── services/
│   └── llm_availability.py    # NEW — cached probe; the only new module
├── tasks/
│   ├── pipeline.py            # MODIFY — stage_summarize records truthfully
│   └── processing.py          # MODIFY — _generate_summary_logic reports outcome
└── models/                    # UNCHANGED — no new entities, no schema change

frontend_spa/src/app/
├── core/models/document.model.ts        # MODIFY — 'failed' → 'error' (R-005)
├── services/
│   └── llm-availability.service.ts      # NEW — polls/caches the endpoint
├── components/
│   ├── documents/document-item.component.ts    # MODIFY — status cases
│   └── sidebar/sidebar.component.html          # MODIFY — badge string
└── features/                            # MODIFY — dormant states for chat,
                                         #   graph, wiki, summary panel

tests/
├── api/
│   ├── test_llm_availability.py         # NEW — contract tests
│   └── test_documents.py                # MODIFY — status serialization
└── tasks/
    └── test_pipeline_no_llm.py          # NEW — the R-000 verification test

presets/ + docker-compose*.yml + start-lite.bat   # MODIFY — R-007 prerequisite
```

**Structure Decision**: The existing web-application layout is used unchanged —
Flask blueprints under `app/api/`, services under `app/services/`, Celery stages
under `app/tasks/`, and the Angular SPA under `frontend_spa/src/app/`. Exactly
one new backend module (`llm_availability.py`) and one new SPA service are
introduced; everything else is a modification to an existing file. No new
services, containers, or database objects.

## Implementation Approach

Ordered so that the cheapest disconfirming test comes first.

**Step 0 — Unblock (R-007, prerequisite).** Fix the two suspected 005 defects and
verify slim mode starts on a machine with no NVIDIA runtime. Until this passes,
SC-001 and SC-006 cannot be evaluated on target hardware.

**Step 1 — Verify, don't build (R-000).** Write an integration test that runs a
document through the pipeline with an unreachable LLM and asserts it reaches
`status='completed'` with chunks persisted. If it passes, FR-001 is already met
and the remaining backend work is small. If it fails, the assumption in R-000 is
wrong and the plan is revised before any UI work starts.

**Step 2 — Truthful stage records (FR-002).** `_generate_summary_logic` currently
swallows silently; make it report its outcome so `stage_summarize` can record
`completed` / `failed` accurately instead of always `completed`. This is what
makes "no summary because no LLM" machine-distinguishable from "summary
generated" — every downstream UI decision depends on it.

**Step 3 — Availability endpoint (FR-004, FR-006).** New `llm_availability.py`
with a cached probe returning the three-state result from R-002, invalidated via
the existing `reset_client()` seam. Explicit short timeout (R-006).

**Step 4 — SPA status correctness (R-005, FR-012).** Fix `'failed'` → `'error'`
and pin the union type against the backend enum with a test, so FR-012 becomes a
meaningful assertion rather than one that passes vacuously.

**Step 5 — Dormant states (FR-010, FR-011).** Chat, graph, wiki, and summary
panel consume the availability service and render explanatory states with a route
to settings.

**Step 6 — Backfill (FR-007, FR-008, FR-009).** Eligibility query plus an enqueue
loop over the existing `generate_summary_task` and `reprocess_hypergraph_task`.
Manual trigger only.

Steps 1-2 are backend-only and independently shippable. Step 5 is the largest
surface and depends on Steps 3-4. Step 6 is genuinely optional for a first cut —
User Story 3 is P3 and the per-document retry path already exists.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

No violations to justify — the constitution is an unfilled template (see
Constitution Check), and the plan adds no new entities, no schema changes, and
exactly one new backend module.

One deliberate scope inclusion worth recording, since it is not derivable from
the spec:

| Item | Why included | Simpler alternative rejected because |
|---|---|---|
| R-007 fixes to feature 005 | 006's acceptance criteria (SC-001, SC-006) cannot be evaluated if slim mode does not start on GPU-less hardware | Deferring them means shipping 006 unverified on its only target platform |
| R-005 SPA status string fix | FR-012 would otherwise pass vacuously — nothing currently renders as an error | Leaving it means the feature's headline requirement is untestable |
