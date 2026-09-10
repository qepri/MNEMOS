# Phase 1 Data Model

This feature introduces **no database entities and no schema changes**. The "entities" here are in-memory/structural artifacts that shape the implementation and its tests. No Alembic migration is created.

## 1. PromptBundle (internal, Item 1)

The value passed from `_build_prompt` → `_fit_to_budget` → `_generate`. It exists only to make the extracted helpers testable; it is not serialized or persisted.

| Field | Type | Meaning |
|---|---|---|
| `system_prompt` | `str` | Fully assembled system prompt (default/RAG/vanilla + injected user memories). |
| `user_prompt` | `str` | Assembled user prompt (conversation context + doc/web context + question + scaffold). |
| `rag_context` | `str` | The Document→Section→Chunk context block (+ web results), pre-question. Needed so the budget step can rebuild after trimming. |
| `sources` | `list[dict]` | Citation sources (document + web). Rebuilt alongside `rag_context` when chunks are trimmed. |
| `search_queries` | `list[str]` | Web-search queries generated (empty when `web_search=False`). |
| `context_warning` | `str \| None` | Long-history warning; unchanged semantics. |
| `chunks` | `list[Chunk]` | Retrieved chunks, ranked; the mutable set the budget step trims (lowest-rank-first). |
| `graph_sections` | `list` | Graph-retrieved sections; passed through to context rebuilds, not trimmed. |
| `proceed` | `bool` | Whether generation should proceed (False → the existing "no relevant documents" early return). Encodes the current vanilla/vision/no-context decision. |

**Validation / invariants**:
- The returned dict from `query()` still exposes exactly `{answer, sources, context_warning, search_queries}` (unchanged keys).
- `chunks` is always a prefix-preserving subset after trimming (never reordered).
- `graph_sections` and non-chunk context are never removed by trimming (FR-011).

**Note**: `PromptBundle` may be realized as a small dataclass or a tuple; the exact shape is an implementation detail as long as the helper boundaries and `query()`'s external contract hold.

## 2. BudgetFit inputs/outputs (internal, Item 1)

Pure function surface for the unit-testable trim logic:

| Field | Type | Meaning |
|---|---|---|
| `ranked_chunks` | `list[Chunk]` | Input, highest-rank first. |
| `fixed_overhead_tokens` | `int` | Tokens for system prompt + history + question + scaffold (non-chunk). |
| `budget` | `int` | `ctx_size - reserve_tokens - sys_tokens` (same formula as today). |
| `keep_count` | `int` (output) | Number of leading chunks retained. |

**Invariant (FR-010 / SC-005)**: `keep_count` equals the number the legacy pop-until-under-budget loop would have retained for the same inputs.

## 3. RouteClassification (audit artifact, Item 2)

One record per backend route in the audit report (`contracts/route-audit-report.md`). Not code — a documentation table.

| Field | Type | Meaning |
|---|---|---|
| `method` | `str` | HTTP method(s). |
| `path` | `str` | Full route path. |
| `blueprint_file` | `str` | `app/api/*.py` it is defined in. |
| `classification` | `enum{used, unused, ambiguous}` | Result. |
| `evidence` | `str` | Frontend/MCP/test reference, or reason for ambiguity/retention. |
| `action` | `enum{keep, remove, keep-documented}` | Disposition. |
| `mirrors_updated` | `list{mcp, swagger, readme}` | Which mirrors changed (only for `remove`). |

**Invariants**:
- `classification=unused` ⇒ `action` may be `remove`; any other classification ⇒ `action ∈ {keep, keep-documented}` (FR-014/FR-017).
- Every `remove` lists the mirrors updated (FR-016).

## 4. SearchOutcome (UI state, Item 3)

The Search page's mutually-exclusive display state, derived from component signals.

| Outcome | Signals | Rendered |
|---|---|---|
| `loading` | `loading()==true` | "Searching…" |
| `results` | `!loading && searched && results().length>0 && !error()` | results list + count header |
| `empty` | `!loading && searched && results().length==0 && !error()` | "No matching passages found." |
| `error` | `!loading && error()!=null` | distinct error message (e.g. "Search failed — please try again.") |

**Invariants**:
- `error` supersedes `empty` and `results` (checked first in template).
- Submitting a new search clears `error` before the request resolves (FR-003).
- Exactly one outcome is visible at a time.
