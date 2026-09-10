---
description: "Task list for feature 009 — RAG refactor, dead-route audit, search error state"
---

# Tasks: RAG Refactor, Dead-Route Audit & Search Error State

**Input**: Design documents from `specs/009-refactor-ragservice-query/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: INCLUDED — the spec explicitly requires them (FR-005, FR-012). Golden/characterization test for `query()`, unit tests for the extracted helpers, and a new frontend spec.

**Organization**: Tasks grouped by user story. The three stories are **fully independent** — US1 is frontend-only (`search.component.ts`), US2 touches only `app/services/rag.py`, US3 touches only `app/api/*` + mirrors. Any order; any can be a standalone PR.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3

## Path Conventions

Web app: backend at repo root (`app/`, `tests/`), frontend at `frontend_spa/src/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Ensure both test stacks run. No project scaffolding needed — all three items edit existing files.

- [X] T001 [P] Verify backend test env per [quickstart.md](./quickstart.md): Docker running, `pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.in -r requirements-dev.txt`, then `pytest -q` (baseline green) at repo root
- [X] T002 [P] Verify frontend test env: `cd frontend_spa && npm install && npm test` (baseline green)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: None. This feature adds no shared schema, entities, endpoints, or infrastructure — there is intentionally no blocking foundational work. All three user stories may begin immediately after Setup.

**Checkpoint**: Foundation ready (trivially) — all user stories can start in parallel.

---

## Phase 3: User Story 1 - Failed search visibly distinct from empty library (Priority: P1) 🎯 MVP

**Goal**: A failed search request shows a distinct error state instead of "No matching passages found.", so a broken search is never mistaken for an empty library.

**Independent Test**: Force `searchChunks` to error → error message renders; return `[]` → empty state renders; return results → list renders. Frontend-only; no backend change.

### Tests for User Story 1 ⚠️ (write first — the error case FAILS on current code)

- [X] T003 [P] [US1] Create `frontend_spa/src/app/features/search/search.component.spec.ts` covering all three outcomes: (a) results returned, (b) genuine empty (`results: []`), (c) request error (throwing Observable). Stub `DocumentsService.searchChunks` per [contracts/search-ui-states.md](./contracts/search-ui-states.md). Confirm (c) FAILS against current component.

### Implementation for User Story 1

- [X] T004 [US1] In `frontend_spa/src/app/features/search/search.component.ts` add `error = signal<string | null>(null)`; in `onSubmit` set `error.set(null)` before dispatch, and in the `error` callback set `error.set('Search failed — please try again.')`, `searched.set(true)`, `loading.set(false)`; in `next` set `error.set(null)`
- [X] T005 [US1] In the same component's template add an `@if (error())` branch (before the empty-state block) and gate the empty-state `@if` on `!error()`; leave loading/results branches unchanged
- [X] T006 [US1] Run `cd frontend_spa && npm test` — all three outcomes in `search.component.spec.ts` pass (SC-002)

**Checkpoint**: Search page distinguishes results / empty / error, fully tested. MVP shippable.

---

## Phase 4: User Story 2 - Maintainable RAG path, no quadratic budget trim (Priority: P2)

**Goal**: `RAGService.query` becomes a readable orchestrator over `_retrieve` / `_build_prompt` / `_fit_to_budget` / `_generate`, and the O(n²) token-budget loop becomes a single-pass prefix fit — with byte-for-byte identical output.

**Independent Test**: A golden test snapshots `query()`'s prompt/sources/answer and stays green across the refactor; a unit test proves the trim keeps the same chunk set as the old loop with bounded prompt re-assembly. Backend-only; touches only `app/services/rag.py` and `tests/services/test_rag.py`.

### Tests for User Story 2 ⚠️ (characterization test written FIRST, green on current code)

- [X] T007 [US2] Add characterization/golden test to `tests/services/test_rag.py` snapshotting `RAGService.query()`'s `system_prompt`, `user_prompt`, returned `sources`, and full return dict across: docs-selected, vanilla (no docs), web-search on, over-budget context, images present. Use `tests/fakes/` LLM+embedding fakes. Confirm GREEN on current (pre-refactor) code — this is the behavior oracle (SC-003)

### Implementation for User Story 2

- [X] T008 [US2] In `app/services/rag.py` extract `_retrieve`, `_build_prompt`, `_generate` and rewrite `query()` as the orchestrator per [contracts/rag-helpers.md](./contracts/rag-helpers.md); keep signature + return keys identical; T007 golden test stays green
- [X] T009 [US2] In `app/services/rag.py` replace the `while chunks and prompt_tokens > budget` loop with `_fit_to_budget` — single-pass prefix fit that rebuilds the full prompt a bounded (constant) number of times, retaining the same prefix of ranked chunks (FR-010); T007 golden test stays green
- [X] T010 [US2] Add unit tests to `tests/services/test_rag.py`: (a) budget-fit `keep_count` equals the legacy pop-until-under-budget result across a battery of (ranked chunks, overhead, budget) cases (SC-005); (b) full-prompt assembly count is bounded by a small constant for a large over-budget input (SC-004); (c) `_build_prompt` decision matrix — RAG vs vanilla system prompt, memory injection on/off, web-search block presence, `proceed` early-return path
- [~] T011 [US2] (Optional — DEFERRED: stream_query left untouched to avoid changing streaming behavior) Share `_retrieve`/`_build_prompt` into `stream_query` in `app/services/rag.py` ONLY behind a new characterization test snapshotting its yielded event sequence; if risky, leave `stream_query` untouched (do NOT add trimming to it — would change behavior)
- [X] T012 [US2] Run `pytest tests/services/test_rag.py tests/services/test_rag_no_llm.py -q` then `pytest -q` — full suite green, golden unchanged

**Checkpoint**: RAG path decomposed, trim is single-pass, behavior provably identical.

---

## Phase 5: User Story 3 - No confirmed dead routes; mirrors agree (Priority: P3)

**Goal**: Every `app/api/*` route is classified with evidence; confirmed-dead routes/retired-provider remnants removed; MCP + `swagger.json` + bilingual README kept in sync. Conservative — flag, don't guess.

**Independent Test**: The filled audit report classifies 100% of routes; any removal leaves swagger valid and all tests green; ambiguous routes retained with reason. Touches only `app/api/*`, `app/mcp_server/*`, `swagger.json`, `README.md`.

### Implementation for User Story 3

- [X] T013 [US3] Enumerate every route in `app/api/*.py` and populate the classification table in [contracts/route-audit-report.md](./contracts/route-audit-report.md) (method, path, file)
- [X] T014 [US3] For each route, gather evidence from `frontend_spa/src` (including dynamically built URLs / `ApiEndpoints`), `app/mcp_server/*.py`, and `tests/**`; set classification used/unused/ambiguous — a route reached only via a built URL is **ambiguous**, never unused (FR-014)
- [X] T015 [US3] Remove ONLY `classification=unused` routes from `app/api/*.py`; record the `ollama` fallback in `app/services/llm_client.py` as **keep-documented** (still reachable via stale DB rows — do not delete) per [research.md](./research.md)
- [X] T016 [US3] For each removed route, sync all three mirrors in the same change: the matching `@mcp.tool()` in `app/mcp_server/*.py`, the `swagger.json` path entry, and BOTH language halves of the endpoint/tool tables in `README.md` (FR-016)
- [X] T017 [US3] Validate `node -e "JSON.parse(require('fs').readFileSync('swagger.json','utf8'))"`; run `pytest -q` and `cd frontend_spa && npm test` — all green (SC-006/SC-007/SC-008)

**Checkpoint**: API surface audited and internally consistent.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T018 [P] If any route changed in US3, reconcile the "Keeping the API surface in sync" / Health-Uploads-Workers notes in `CLAUDE.md` so docs match the live route set
- [X] T019 Run the full [quickstart.md](./quickstart.md) Definition-of-Done: `pytest -q` + `cd frontend_spa && npm test` green, swagger parses, and confirm no new endpoints/schema/auth were introduced

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: empty — does not block anything.
- **User Stories (Phase 3–5)**: each depends only on Setup. They are mutually independent (different files) and may run fully in parallel.
- **Polish (Phase 6)**: after the stories you choose to ship (T018 only relevant if US3 ran).

### User Story Dependencies

- **US1 (P1)**: independent (frontend only).
- **US2 (P2)**: independent (`rag.py` + `test_rag.py` only).
- **US3 (P3)**: independent (`api/*`, `mcp_server/*`, `swagger.json`, `README.md`).

### Within Each Story

- US1: T003 (failing test) → T004 → T005 → T006.
- US2: T007 (golden, green first) → T008 → T009 → T010 → (T011 optional) → T012. Sequential — all touch `rag.py`/`test_rag.py` (no intra-story [P]).
- US3: T013 → T014 → T015 → T016 → T017. Sequential — audit is inherently ordered.

### Parallel Opportunities

- T001 ‖ T002 (Setup, different stacks).
- **Across stories**: US1, US2, US3 can each be worked by a different developer at the same time — no shared files.
- Within a story there is little parallelism (each story is a small, mostly single-file edit chain); intra-story tasks are deliberately not marked [P] because they share a file.

---

## Parallel Example: whole-team

```bash
# After Setup, three developers pick up one story each — zero file overlap:
Dev A (US1, MVP): frontend_spa/src/app/features/search/search.component.ts (+ .spec.ts)
Dev B (US2):      app/services/rag.py (+ tests/services/test_rag.py)
Dev C (US3):      app/api/*, app/mcp_server/*, swagger.json, README.md
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. US1 (T003–T006) → 3. **STOP and VALIDATE**: broken search now shows a distinct error → 4. Ship. Smallest, user-visible fix.

### Incremental Delivery

1. Ship US1 (MVP) — user-visible correctness.
2. Ship US2 — behavior-preserving refactor + perf, gated by golden test.
3. Ship US3 — conservative cleanup; may remove zero routes and still be valuable (the classified inventory is the deliverable).

Each ships as its own PR; no ordering requirement.

---

## Notes

- Tests are required here (FR-005, FR-012) — US2's golden test MUST be green on current code before any refactor, and US1's error test MUST fail before T004.
- US2 hard rule: `query()`'s signature and return keys are frozen; the golden test is the oracle for "identical output."
- US3 hard rule: never delete on static in_degree=0 alone; when unsure, `keep-documented`. The audit is valid even if nothing is deleted.
- Out of scope (do not do): authentication/LAN-exposure work, new endpoints, new features, schema/migrations, broad coverage expansion beyond these paths.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
