# Phase 0 Research: RAG Refactor, Dead-Route Audit & Search Error State

This feature has no unknown technologies — everything runs on the existing stack. The "research" here resolves the design decisions and risks that determine how the three items are implemented safely.

---

## Item 1 — Decomposing `RAGService.query`

### Decision: Extract four cohesive private helpers behind an unchanged `query()` orchestrator

`query()` (rag.py:267–472) currently inlines nine responsibilities. Extract:

- `_retrieve(question, document_ids, top_k, use_graph_rag) -> (chunks, graph_sections)` — standard hybrid retrieval + optional graph retrieval + the "no docs selected" logging.
- `_build_prompt(question, chunks, graph_sections, conversation_history, system_prompt, web_search, images) -> PromptBundle` — hierarchical context build, web-search augmentation, conversation-history formatting, system-prompt selection, user-memory injection, final user-prompt assembly, and the "no context / vanilla / vision" abort decision. Returns the assembled `system_prompt`, `user_prompt`, `sources`, `search_queries`, `context_warning`, plus the mutable `chunks`/`graph_sections` needed by the budget step.
- `_fit_to_budget(bundle, chunks, graph_sections, ...) -> bundle` — the token-budget trim (see next decision).
- `_generate(system_prompt, user_prompt, images) -> answer` — the single `self.llm.chat(...)` call plus timing logs.

`query()` becomes: `retrieve → build_prompt → (abort?) → fit_to_budget → generate → return dict`.

**Rationale**: These four seams match the natural data-flow boundaries and each is independently testable. The public signature and the returned dict keys (`answer`, `sources`, `context_warning`, `search_queries`) stay identical (FR-008).

**Alternatives considered**:
- *Split into a separate `RagPipeline` class* — rejected: larger blast radius, more churn, no test benefit for a behavior-preserving change.
- *Leave `query()` monolithic, only fix the loop* — rejected: the spec explicitly asks for decomposition (FR-006) and the loop fix is hard to unit-test without a seam.

### Decision: Replace the O(n²) trim loop with a single-pass budget fit

Current loop (rag.py:427–441) pops one chunk, then **rebuilds the entire prompt string and re-tokenizes** every iteration. For `d` dropped chunks that is `d` full re-assemblies + `d` tokenizations.

New approach — **estimate per-chunk cost once, compute the keep-count, assemble once more**:
1. Compute the fixed overhead: `system_tokens + conversation_tokens + question/scaffold tokens` (everything that is *not* retrieved-chunk context).
2. Measure each retained chunk's token contribution to `rag_context`. Since `_build_hierarchical_context` groups chunks under Document→Section headers, per-chunk token counts are derived by tokenizing the built context once and attributing the delta, or by tokenizing each chunk's rendered text. To stay **exactly** behavior-equivalent to the old "pop lowest until under budget" semantics, the fit computes the largest prefix of the (already-ranked) chunk list whose cumulative cost keeps `prompt_tokens <= budget`, then rebuilds context **once** from that prefix and re-tokenizes **once** to confirm.
3. If the confirmation check is still over budget (possible because header/grouping tokens are non-linear), drop one more chunk and rebuild — this fallback runs at most a small constant number of times in practice, not once per chunk.

**Equivalence requirement (FR-010)**: the retained set must equal what the old loop retained. The old loop drops strictly lowest-ranked-first until under budget, so the kept set is always a **prefix** of the ranked list. The new fit therefore only needs to find the same prefix boundary. A characterization test (below) locks this.

**Rationale**: reduces full-prompt assembly from `O(d)` to `O(1)` amortized while provably keeping the same prefix-of-ranked-chunks semantics.

**Alternatives considered**:
- *Binary search on keep-count* — correct and `O(log n)` rebuilds, kept as a fallback option if per-chunk attribution proves unreliable; single-pass prefix-sum is simpler and preferred.
- *Drop in fixed batches (e.g. halves)* — rejected: risks dropping more chunks than the old loop would have, violating FR-010.

### Decision: Guard the refactor with a characterization ("golden") test written FIRST

Before touching `query()`, add a test that drives it with faked LLM/embedding (existing `tests/fakes/`) across representative inputs — docs selected, vanilla (no docs), web-search on, over-budget context, images present — and snapshots the **exact** `system_prompt`, `user_prompt`, `sources`, and returned dict. Run green on the current code, then refactor until it stays green. This is the oracle for FR-007.

**Rationale**: a pure refactor needs a behavioral lock, not just "tests still pass." The spec's SC-003 (byte-for-byte identical) demands snapshot-level assertions.

### Risk / Decision: `stream_query` is a near-duplicate — share helpers WITHOUT changing its behavior

`stream_query` (rag.py:479–565) repeats retrieval, context build, web search, history formatting, system-prompt selection, memory injection, and prompt assembly — but has **no token-budget trim** and no `images`. The extracted `_retrieve` and `_build_prompt` helpers **should** be reused by `stream_query` to kill the duplication, but:

- `stream_query` must **not** gain trimming (that would change its current behavior — out of scope and unverified for streaming).
- `stream_query` emits a `metadata` event with `sources`/`search_queries` at a specific point; helper extraction must preserve that ordering and its current (no-`context_warning`, no-abort) semantics.

**Decision**: reuse `_retrieve` and `_build_prompt` in `stream_query` **only if** a second characterization test for `stream_query` (snapshotting the yielded event sequence) stays green. If sharing proves risky within the time box, leave `stream_query` untouched and only refactor `query()` — the spec scopes Item 1 to `query`. This is recorded as an explicit, optional sub-step, not a requirement.

---

## Item 2 — Dead-route audit

### Decision: Evidence-based classification, three-way (used / unused / ambiguous), delete only "used=no + ambiguous=no"

Build the route inventory from `app/api/*.py` (Flask blueprints) and cross-reference three reference sets:
- **Frontend**: string search across `frontend_spa/src` for the path, including dynamically built URLs (`ApiEndpoints`, template strings like `/api/documents/${id}/...`). A statically-unreferenced route reached via a built URL is **ambiguous**, never "unused" (FR-014).
- **MCP tools**: `app/mcp_server/*.py` wrappers that call the same service/route.
- **Tests**: `tests/**` that exercise the route.

**Rationale**: the static import graph shows several routes with `in_degree=0` that are actually reached via runtime-constructed URLs — deleting on graph-degree alone would break live features. FR-014 forbids it.

### Decision: The `ollama` remnant is a retained defensive fallback, NOT a dead route

Investigation confirms the only `ollama` reference in backend code is a **comment + fallback** in `app/services/llm_client.py:97` — a stored preference naming the retired `ollama` provider is mapped to `llamacpp` at runtime. This path is still reachable (a user's old DB row can still say `ollama`), so per FR-015/FR-017 it is **kept and documented**, not removed. The audit report will list it explicitly under "retained with reason." (No live `/api/settings/ollama` route exists in the backend; the graph node was a frontend-side URL artifact.)

**Rationale**: removing the fallback would raise on stale DB values — exactly the regression `CLAUDE.md` warns about.

### Decision: Any route removal updates all three mirrors in the same change

Per `CLAUDE.md`, for each deleted route: remove/adjust the matching `@mcp.tool()`, delete the `swagger.json` path entry (and validate the file parses), and update **both** language halves of the README endpoint/tool tables (FR-016). The audit report (`contracts/route-audit-report.md`) is the deliverable that records classification + evidence even when nothing is deleted.

---

## Item 3 — Search error state

### Decision: Add an explicit `error` signal; render it as a distinct branch that supersedes the empty state

`search.component.ts` currently models outcome implicitly via `searched`, `loading`, and `results().length`. The `error` callback (line 120) sets `results=[]; searched=true`, which collapses into the "No matching passages found." branch.

Add `error = signal<string | null>(null)`. In `onSubmit`:
- on submit start: `error.set(null)` (clears any prior error — edge case in spec);
- `next`: set results, `error.set(null)`, `searched.set(true)`;
- `error`: `error.set('Search failed — please try again.')`, `searched.set(true)`, leave/blank results, `loading.set(false)`.

Template: add an `@if (error())` branch **before** the empty-state `@if`, and gate the empty-state on `!error()`. Loading and results branches unchanged (FR-004).

**Rationale**: minimal, signal-idiomatic, and keeps the three outcomes mutually exclusive (results / genuine-empty / error) as required by FR-001–FR-003.

**Alternatives considered**:
- *Reuse a global toast/notification service* — rejected: heavier, and the spec wants an in-page distinct state that a test can assert on the component.

### Decision: New `search.component.spec.ts` following the existing Vitest pattern

Model it on the existing specs (`chat-page.component.spec.ts`, `pdf-viewer.component.spec.ts`) using a stubbed `DocumentsService.searchChunks` returning (a) results, (b) empty `results: []`, (c) a throwing/erroring `Observable`. Assert the rendered branch for each (FR-005 / SC-002).

---

## Cross-cutting

- **No new dependencies, no schema/migrations, no new endpoints.** All three items edit existing files.
- **Test infra reused**: backend testcontainers + `tests/fakes/`; frontend Vitest via `npm test`. No new runners.
- **Ordering**: items are independent and can land in any order / separate PRs (spec Assumptions). Suggested landing order by risk: Item 3 (smallest, user-visible) → Item 1 (guarded by golden test) → Item 2 (most judgment).
