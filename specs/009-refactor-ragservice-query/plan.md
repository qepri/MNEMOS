# Implementation Plan: RAG Refactor, Dead-Route Audit & Search Error State

**Branch**: `009-refactor-ragservice-query` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/009-refactor-ragservice-query/spec.md`

## Summary

Three independent, low-risk maintainability/correctness changes, each shippable on its own:

1. **RAG decomposition (P2)** — split the 206-line `RAGService.query` into an orchestrator plus cohesive private helpers (`_retrieve`, `_build_prompt`, `_fit_to_budget`, `_generate`), and replace the O(n²) token-budget `while` loop with a single-pass fit that assembles the full prompt a constant number of times. Behavior-preserving; `query()`'s signature and return shape are unchanged.
2. **Search error state (P1)** — give the Search page a distinct error state so a failed request no longer renders identically to a genuine empty result. Add frontend specs for results / empty / error.
3. **Dead-route audit (P3)** — inventory every `app/api/` route, classify used/unused/ambiguous with evidence, remove only confirmed-dead routes/retired-provider remnants, and keep the MCP-tool / `swagger.json` / bilingual `README.md` mirrors in sync.

Technical approach and the one real risk (a `stream_query` near-duplicate that must keep its current no-trim behavior) are resolved in [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.11 (backend), TypeScript / Angular 21 (frontend)

**Primary Dependencies**: Flask, SQLAlchemy, pgvector, tiktoken (token counting), Celery; Angular signals, RxJS, Vitest (`@angular/build:unit-test`)

**Storage**: PostgreSQL 16 + pgvector (unchanged; no schema/migration in this feature)

**Testing**: `pytest` with disposable testcontainers Postgres/Redis + faked LLM/embedding HTTP (`tests/fakes/`); Vitest for the SPA

**Target Platform**: Linux server (Docker) backend; browser SPA served by Nginx

**Project Type**: Web application (Flask API + Angular SPA + Celery worker + MCP server, one image)

**Performance Goals**: Item 1 removes a per-dropped-chunk full-prompt re-assembly; over-budget trimming becomes O(n) in chunk count with a constant number of full-prompt builds. No other perf targets.

**Constraints**: Behavior preservation is the hard constraint for Item 1 (identical retrieval set, prompt, sources, answer). No new endpoints, no schema changes, no new dependencies, no auth work (explicitly deferred).

**Scale/Scope**: Single-user self-hosted app. Touch surface: `app/services/rag.py`, `frontend_spa/.../search.component.ts` (+ new spec), and whatever `app/api/*.py` routes the audit confirms dead (plus their `swagger.json` / MCP / README mirrors).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project constitution (`.specify/memory/constitution.md`) is an **unfilled template** — it contains only placeholder principle names, so there are no ratified project-specific gates to evaluate. In their absence, this plan self-imposes the gates that the spec and `CLAUDE.md` already imply:

| Gate | Source | Status |
|---|---|---|
| Behavior preservation for Item 1 (identical prompt/sources/answer) | spec FR-007/FR-008/FR-010 | PASS — enforced by a golden/characterization test written **before** the refactor |
| No new endpoints, features, or schema changes | spec Out of Scope | PASS — plan touches only existing code paths |
| API-surface mirrors stay in sync on any route change | `CLAUDE.md` "Keeping the API surface in sync" | PASS — Item 2 tasks update MCP + swagger + bilingual README together |
| LLM-optional invariant preserved (search works with no provider) | `CLAUDE.md` Health/Uploads/Workers | PASS — Items unchanged w.r.t. dormant-LLM behavior |
| Conservative deletion (flag-don't-delete when unsure) | spec FR-014/FR-017 | PASS — audit records evidence; ambiguous routes retained |

No violations. **Complexity Tracking table intentionally omitted** (nothing to justify).

## Project Structure

### Documentation (this feature)

```text
specs/009-refactor-ragservice-query/
├── plan.md              # This file
├── spec.md              # Feature spec (already written)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── rag-helpers.md            # Internal contracts of the extracted RAG helpers
│   ├── search-ui-states.md       # Search page state contract (results/empty/error)
│   └── route-audit-report.md     # Template for the dead-route classification report
├── checklists/
│   └── requirements.md  # Spec quality checklist (already written)
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
app/
├── services/
│   └── rag.py                     # Item 1: decompose query(); extract shared helpers
│                                  #         (also reused by stream_query — see research.md)
└── api/
    ├── documents.py               # search route lives here (unchanged by Item 3 unless audited dead)
    ├── settings*.py, connections.py, wiki.py, voice.py,
    │   videomix.py, reasoning.py, memory.py, collections.py …  # Item 2: audit targets
    └── docs.py                    # serves swagger.json

app/mcp_server/                    # Item 2: MCP-tool mirror (per-domain modules)
swagger.json                       # Item 2: OpenAPI mirror (hand-maintained)
README.md                          # Item 2: bilingual endpoint/tool tables (two halves)

frontend_spa/src/app/features/search/
├── search.component.ts            # Item 3: add distinct error state
└── search.component.spec.ts       # Item 3: NEW — results/empty/error coverage

tests/
├── services/
│   ├── test_rag.py                # Item 1: extend — golden query() + helper unit tests
│   └── test_rag_no_llm.py         # unchanged; must still pass
```

**Structure Decision**: Existing web-app layout is kept as-is. No new modules or directories in `app/` — Item 1 adds private methods inside the existing `RAGService` class; Item 3 adds one sibling `.spec.ts`; Item 2 only removes/annotates existing routes and their mirrors. All three are edits to established files, which is why no restructuring is proposed.

## Complexity Tracking

No constitution violations to justify; table omitted.
