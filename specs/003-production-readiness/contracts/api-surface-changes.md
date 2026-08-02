# Contract: API Surface Changes

**Feature**: `003-production-readiness` | Satisfies FR-010, FR-011, FR-020, FR-053, FR-055

What consumers (the Angular SPA and the MCP server) can rely on before and after this feature.

## 1. JSON-only responses — no behavior change for the SPA

Every dual-response branch is gated on the `HX-Request` header, verified at:

- `app/api/documents.py:55, 110, 176`
- `app/api/chat.py:137`
- `app/api/conversations.py:30, 59`

Pattern in every case:

```python
if request.headers.get('HX-Request'):
    return render_template('partials/....html', ...)
return jsonify(...)          # ← the SPA always lands here
```

**Guarantee**: the Angular SPA never sends `HX-Request`, so it already receives the JSON branch exclusively. Deleting the template branches changes the response for **zero** current consumers. The JSON payloads themselves are untouched.

**Removed**: `app/web.py` blueprint (`GET /` → `index.html`, `GET /settings` → `settings.html`), `app/templates/`, `app/static/`. The SPA is served by Nginx on `:5200` and does not use these routes.

## 2. Removed endpoints

| Endpoint | Reason | Consumer impact |
|---|---|---|
| `/api/settings/ollama/*` (whole blueprint) | Ollama purged (FR-020) | Angular settings "discover" tab calls these; the corresponding UI is removed in the same change |
| `GET /` , `GET /settings` (from `app/web.py`) | server-rendered UI removed | none — SPA serves its own routes |

**Frontend coordination required**: `frontend_spa/src/app/core/constants/api-endpoints.ts` declares the Ollama endpoints and `settings.service.ts` calls them. Backend and frontend removal must land together, or the settings page issues 404s. The affected frontend surfaces are the settings discover tab (`pollDownloads`, GGUF/pull modals), `llm-selection-modal`, `llm-selector`, `chat-input`, and `chat-page`.

## 3. Removed MCP tool

`search_similar_documents` (`app/mcp_server/server.py:519`) is removed.

**Justification**: it calls `RAGService.search_similar_documents`, which queries `Document.summary_embedding` and `Document.summary_search_vector` — columns dropped from the database by `phase2_strip_embeddings.sql` (verified applied). **The tool raises at runtime today.** Removing a broken tool is not a capability regression; it is the removal of a trap.

Restoring summary-level search would require re-adding vector columns and embedding all 58 document summaries, which HC-3 places out of scope. Recorded as a possible follow-up feature.

Remaining MCP tools keep their names and signatures. The server is split into per-domain modules (documents, search, wiki, graph, settings) with shared `_validate_uuid` / `_version_footer` helpers — a **file reorganization only**, with no change to the tool surface Claude Desktop sees.

## 4. Upload limits and validation (FR-053)

Current: single global `MAX_CONTENT_LENGTH = 50 * 1024**3` (50 GB) at `config/settings.py:103`, with no type validation at the boundary.

After: per-type ceilings enforced at the upload boundary, with `MAX_CONTENT_LENGTH` set to the largest of them as a backstop.

| Category | Extensions | Suggested ceiling |
|---|---|---|
| Documents | `.pdf`, `.epub` | 512 MB |
| Audio | `.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg` | 2 GB |
| Video | `.mp4`, `.mkv`, `.mov`, `.webm`, `.avi` | 8 GB |

**Contract**:
- Unknown or disallowed extension → `400` with a clear message naming the accepted types. Rejection happens before the file is persisted or a Celery task is queued.
- Over the category ceiling → `413` with the limit stated in the message.
- YouTube ingestion is URL-based and unaffected by size limits.
- Exact ceilings are tunable; the requirement is that they are realistic and per-type, not that they match this table.

**Note**: validation is by extension plus declared content type. This is a trust-boundary check appropriate to a single-user local deployment — it is not a defense against a malicious local operator, who by definition already controls the machine.

## 5. Structured logging (FR-055)

**Format**: one JSON object per line, on stdout, from both Flask and Celery.

Required fields:

| Field | Notes |
|---|---|
| `timestamp` | ISO 8601 |
| `level` | standard log level |
| `logger` | module name |
| `message` | the log text |
| `request_id` | correlation ID — see below |

**Correlation rule**: Flask generates a `request_id` per request (accepting an inbound `X-Request-ID` if present). When a request enqueues a Celery task, the ID is propagated into the task's headers so worker log lines carry the *same* `request_id`. This is what makes SC-010 verifiable: take an ID from an app log line, find the worker lines for the same operation.

Tasks started without an originating request (scheduled or manual) generate their own ID; the field is never empty.

**Gunicorn**: inline CMD flags are replaced by a config file (`gunicorn.conf.py`) covering bind, workers, threads, timeout, access logging, and the logging class. This also gives a single deliberate place to set worker count, which matters because `create_app()` currently runs once per worker (see research F6 on the embedder pre-warm).

## 6. Explicitly unchanged

- All JSON request/response payload shapes for existing endpoints
- `GET /api/health` (see `health-readiness.md`)
- Every VideoMix endpoint (`app/api/videomix.py`) — out of scope per HC-5
- Authentication — there is none, and none is added (local-only by design)
