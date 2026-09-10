# Contract: RAG query helpers (Item 1)

Internal contract for the extracted helpers. These are private to `RAGService`; the only **external** contract is that `query()` is unchanged.

## Public (unchanged) contract — MUST hold

```
RAGService.query(
    question: str,
    document_ids: list[str] | None = None,
    top_k: int = 10,
    conversation_history: list | None = None,
    system_prompt: str | None = None,
    web_search: bool = False,
    use_graph_rag: bool = False,
    images: list[str] | None = None,
) -> dict   # keys: {"answer", "sources", "context_warning", "search_queries"}
```

- Signature, defaults, and returned dict keys are **identical** to the current implementation.
- For any fixed input, `answer`, `sources`, `context_warning`, and `search_queries` are byte-for-byte identical to pre-refactor output (SC-003).

## Extracted helpers (internal)

### `_retrieve(question, document_ids, top_k, use_graph_rag) -> (chunks, graph_sections)`
- When `document_ids` is falsy/empty → `chunks == []` (no retrieval), matching current behavior.
- When `use_graph_rag` → `graph_sections` from `_retrieve_via_graph(..., top_k=3)`; else `[]`.
- Pure w.r.t. logging aside; no prompt assembly.

### `_build_prompt(question, chunks, graph_sections, conversation_history, system_prompt, web_search, images) -> PromptBundle`
- Produces `system_prompt`, `user_prompt`, `rag_context`, `sources`, `search_queries`, `context_warning`, and `proceed`.
- Encodes the current decisions exactly:
  - web-search augmentation appends `=== WEB SEARCH RESULTS ===` block and extends `sources`;
  - default system prompt selection (RAG vs vanilla) identical to current strings;
  - user-memory injection identical (guarded by `prefs.memory_enabled`);
  - `context_warning` set when `conversation_history` length ≥ 8;
  - `proceed == False` reproduces the current early-return `{"answer": "No relevant documents or web results found for this query.", "sources": [], "context_warning": None}` path (no context, not vanilla, no images).

### `_fit_to_budget(bundle) -> PromptBundle`
- Budget formula unchanged: `budget = _model_ctx_size(model, provider) - reserve_tokens - _count_tokens(system_prompt)`, `reserve_tokens` from `UserPreferences.llm_max_tokens` (default 4096).
- Retains a **prefix** of `bundle.chunks` (lowest-ranked dropped first), equal to the legacy loop's kept set (FR-010).
- Rebuilds `rag_context`/`sources`/`user_prompt` **a constant number of times**, not once per dropped chunk (SC-004).
- No-op when already under budget or when `chunks` is empty.
- Never removes conversation history, system prompt, or web context (FR-011).

### `_generate(system_prompt, user_prompt, images) -> str`
- Single `self.llm.chat(system=..., messages=[{"role":"user","content":user_prompt}], images=images)` call; returns the answer string. Timing logs preserved.

## Test obligations
- **Golden/characterization test** on `query()` (written first, green on current code) across: docs-selected, vanilla, web-search, over-budget, images-present.
- **Unit test** on the budget fit: for a battery of (ranked chunks, overhead, budget) cases, `keep_count` equals the legacy pop-loop result; assert full-prompt assembly count is bounded by a small constant.
- **Unit test** on `_build_prompt`: system-prompt selection, memory injection on/off, web-search block presence, `proceed` decision matrix.
- Optional: characterization test on `stream_query` event sequence if helpers are shared into it.
