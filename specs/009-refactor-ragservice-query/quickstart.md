# Quickstart: Implementing & Verifying Feature 009

Three independent workstreams. Land them separately; suggested order by risk: **Item 3 → Item 1 → Item 2**.

## Prerequisites

```bash
# Backend tests need Docker running (disposable Postgres/Redis via testcontainers)
python -m pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.in -r requirements-dev.txt

# Frontend
cd frontend_spa && npm install
```

---

## Item 3 — Search error state (smallest, user-visible)

**Edit**: `frontend_spa/src/app/features/search/search.component.ts`
- Add `error = signal<string | null>(null)`.
- `onSubmit`: `error.set(null)` before dispatch; on `error` callback set the message + `searched=true` + `loading=false`.
- Template: add `@if (error())` branch before the empty-state `@if`, and gate the empty state on `!error()`.

**New test**: `frontend_spa/src/app/features/search/search.component.spec.ts` — stub `searchChunks` for results / empty / error.

**Verify**:
```bash
cd frontend_spa && npm test        # new spec passes; results/empty/error all covered
```
Manual: run the app, stop the backend, submit a search → distinct error (not "No matching passages found.").

---

## Item 1 — Decompose `RAGService.query` (guarded refactor)

**Step 1 — lock behavior FIRST** (`tests/services/test_rag.py`): add a characterization test snapshotting `query()`'s `system_prompt`, `user_prompt`, `sources`, and returned dict across: docs-selected, vanilla (no docs), web-search on, over-budget context, images present. Use the existing `tests/fakes/` LLM + embedding fakes. Confirm green on **current** code.

```bash
pytest tests/services/test_rag.py -q      # golden test green before refactor
```

**Step 2 — extract helpers** in `app/services/rag.py`: `_retrieve`, `_build_prompt`, `_fit_to_budget`, `_generate`; rewrite `query()` as the orchestrator. Keep signature + return keys identical (see `contracts/rag-helpers.md`).

**Step 3 — replace the O(n²) trim loop** with the single-pass prefix fit (`_fit_to_budget`). Add a unit test asserting the retained `keep_count` equals the legacy pop-loop result and that full-prompt assembly happens a bounded number of times.

**Step 4 — (optional)** share `_retrieve`/`_build_prompt` into `stream_query` only if a `stream_query` event-sequence characterization test stays green; otherwise leave `stream_query` as-is.

**Verify**:
```bash
pytest tests/services/test_rag.py tests/services/test_rag_no_llm.py -q   # all green, golden unchanged
pytest -q                                                               # full suite green
```

---

## Item 2 — Dead-route audit (most judgment)

**Produce** `contracts/route-audit-report.md` filled in: enumerate `app/api/*.py` routes, classify used/unused/ambiguous with evidence (frontend incl. built URLs, MCP, tests).

**Remove** only confirmed-dead routes. For each removal, update the three mirrors together (MCP tool + `swagger.json` + both README halves) and re-validate swagger JSON.

**Retain & document** the `ollama` fallback in `llm_client.py:97` (do not delete).

**Verify**:
```bash
node -e "JSON.parse(require('fs').readFileSync('swagger.json','utf8'))"   # swagger still valid
pytest -q                                                                # backend green
cd frontend_spa && npm test                                              # frontend green
```

---

## Definition of done (all items)

- `pytest -q` and `cd frontend_spa && npm test` both green.
- `query()` public contract unchanged; golden test proves identical output (SC-003).
- Over-budget trim assembles the full prompt a bounded number of times (SC-004) and retains the same chunk set as before (SC-005).
- Search shows distinct results/empty/error states, all three tested (SC-002).
- Route audit inventory complete; any removals reflected in MCP + swagger + bilingual README; swagger parses (SC-006/SC-007).
- No new endpoints, no schema changes, no auth work.
