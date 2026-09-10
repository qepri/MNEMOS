# Dead-Route Audit Report (Item 2 / US3) — RESULTS

Audit performed 2026-09-10 against `app/api/*.py` (all Flask blueprints), cross-referenced with the Angular frontend (`frontend_spa/src`, including dynamically built URLs via `ApiEndpoints` and template strings), the MCP tools (`app/mcp_server/*.py`), and the backend tests (`tests/**`).

## Method

1. Enumerated every route from the blueprint decorators and resolved each blueprint's `url_prefix`.
2. Cross-referenced each route path fragment against the three reference sets.
3. Classified **used** / **ambiguous** / **unused**. Only `unused` is eligible for removal; anything reached via a runtime-built URL or plausibly invoked manually is **ambiguous → retained** (FR-014, FR-017).

## Blueprints & prefixes

| Blueprint | Prefix | Routes |
|---|---|---|
| documents | `/api/documents` | 17 |
| collections | `/api/collections` | 7 |
| chat | `/api/chat` | 2 |
| conversations | `/api/conversations` | 4 |
| settings (+ settings_downloads, settings_models attach to it) | `/api/settings` | 26 |
| connections | `/api/settings/connections` | 5 |
| memory | `/api/memory` | 2 |
| voice | `/api/voice` | 3 |
| reasoning | `/api/reasoning` | 3 |
| wiki | `/api/wiki` | 3 |
| videomix | `/api/videomix` | 11 |
| docs | `/api/docs` | 1 (`swagger.json`) |

## Classification summary

- **Used** — the large majority. Wired to the frontend directly through `ApiEndpoints` (documents CRUD/search/status/content, chat + stream, conversations, collections, settings chat/models/prompts/downloads/pull/hardware/library-search/connections, memory, wiki concepts/article/search, videomix projects/scripts/render-jobs, reasoning traverse/reprocess) or reached via built URLs (`/api/documents/{id}/chunks`, `/{id}/sections`, `/{id}/transcribe`, `/{id}/transcription`, `/{id}/summary`, `/{id}/collections`, `/api/settings/reembed`, `/api/settings/llamacpp/models`, `/api/settings/import/*`, `/api/settings/current-model`, `/api/settings/models/lookup`, `/api/settings/pull_gguf`, voice `/transcribe` `/synthesize` `/message/{id}/audio`).
- **Ambiguous → retained** — see findings below.
- **Unused → removed** — **none**. No route was provably dead.

## Findings (retained, documented)

| # | Route / symbol | Evidence | Disposition |
|---|---|---|---|
| 1 | `POST /api/documents/backfill-concepts` | No frontend / MCP / test reference. Self-described **one-shot maintenance** endpoint ("Use this after upgrading… idempotent"). Plausibly curl-invoked during upgrades. | **keep-documented.** Not deleted (manual-ops endpoint, hard-to-reverse if someone relies on it). **Mirror gap fixed:** it was missing from `swagger.json`; a path entry was added so the mirrors now agree. |
| 2 | `POST /api/documents/reprocess-hypergraph` | Not wired to the frontend, but present in `swagger.json`; its underlying `reprocess_hypergraph_task` is used by the MCP tool in `tools_settings.py` and by `tests/api/test_llm_backfill.py`. Manual admin trigger. | **keep-documented.** Retained; already documented in swagger. |
| 3 | `ollama` provider fallback (`app/services/llm_client.py:97`) | Only reference to the retired provider is a defensive fallback mapping a stale stored `ollama` value → `llamacpp`. Still reachable via a stale `UserPreferences` row in an existing DB. | **keep-documented.** Removing it would raise on old preferences (FR-015/FR-017). No live `/api/settings/ollama` backend route exists — the graph node was a frontend-side URL artifact, not a Flask route. |

## Mirror consistency actions taken

- Added the missing `POST /api/documents/backfill-concepts` entry to `swagger.json` (validated: file parses; both admin paths present).
- No routes removed → no MCP-tool or README changes required.
- `swagger.json` validated with `node -e "JSON.parse(...)"` → OK.

## Conclusion

Zero routes removed. Per the spec this is a valid outcome — the classified inventory is the deliverable, and the conservative rule (flag, don't delete) governed the two UI-unwired admin endpoints. The single genuine mirror discrepancy (backfill-concepts absent from swagger) was corrected, so the API-surface mirrors now agree for the audited routes.

### Follow-ups (out of scope, noted for later)

- The audit surfaced no dead routes but the API surface is large; a future pass could add MCP tools for the two admin maintenance endpoints if agent-driven maintenance is desired.
