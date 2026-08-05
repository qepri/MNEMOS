# Contract: LLM Availability

## `GET /api/settings/llm-availability`

Reports whether LLM-dependent features can currently be used. Read-only, cheap,
safe to call on every view load.

### Why this endpoint exists

The SPA cannot compute this itself. Reachability must be evaluated from inside
the container — `LOCAL_LLM_BASE_URL` defaults to `host.docker.internal`
(`config/settings.py:49`), and `_normalize_local_url` (`llm_client.py:28-29`)
rewrites any `localhost`/`127.0.0.1` the user enters into that form. Those
addresses are meaningless in the browser.

### Response — 200

```json
{
  "state": "available",
  "provider": "lm_studio",
  "endpoint": "http://host.docker.internal:11434/v1",
  "detail": null,
  "checked_at": "2026-08-04T10:15:30Z"
}
```

| Field | Type | Notes |
|---|---|---|
| `state` | `"unconfigured"` \| `"unreachable"` \| `"available"` | See table below |
| `provider` | string \| null | Resolved provider name; `null` when `unconfigured` |
| `endpoint` | string \| null | Resolved base URL. Omitted for hosted providers where it carries no useful information. **Must never include an API key.** |
| `detail` | string \| null | Human-readable cause when not `available` |
| `checked_at` | ISO-8601 UTC | When the underlying probe ran — may be older than the request, since results are cached |

Always `200`. A `503` would conflate "the LLM is down" with "MNEMOS is down",
and MNEMOS is explicitly *up* and useful without an LLM. Non-200 is reserved for
the endpoint itself failing.

### States

| `state` | Condition | `detail` example | What the UI offers |
|---|---|---|---|
| `unconfigured` | No provider resolvable, or no credentials/endpoint for the resolved one | `"No LLM provider is configured."` | Route to provider settings |
| `unreachable` | Configured, but the probe failed | `"Connection refused at http://host.docker.internal:11434/v1"` | Tell the user to start their server; show the endpoint being tried |
| `available` | Probe succeeded | `null` | Nothing — features render normally |

The `unconfigured` / `unreachable` split is required by FR-006: telling someone
to install Ollama when Ollama is installed but not running is a wrong
instruction, and `settings.LLM_PROVIDER` alone cannot tell the two apart (slim
mode ships a provider value pointing at a possibly-absent endpoint).

### Probe behaviour

- **Target**: `GET {base_url}/models` — the OpenAI-compatible listing endpoint,
  supported by Ollama, LM Studio, vLLM, and llama-server alike.
- **Timeout**: explicit and short. Mandatory, not optional: no LLM client in the
  codebase sets `timeout=` (`llm_client.py:56`, `:132`, `:165`), so the inherited
  SDK default is 600 seconds. A probe that can block for ten minutes is not a
  probe.
- **Cache**: short TTL (order of 30s), plus explicit invalidation on settings
  change via the existing `reset_client()` seam (`connections.py:134`). One
  invalidation point, not two.
- **Anthropic and other hosted providers**: presence of a usable API key is
  sufficient for `available`. Do not spend a live request on every page load to
  prove a hosted API is up.

### Guarantees

- Never mutates state. Safe to poll.
- Never raises to the caller. A probe failure is a `state`, not an HTTP error.
- Never returns an API key, in any field, in any state.

### Contract tests

| Test | Assertion |
|---|---|
| No provider configured | `200`, `state == "unconfigured"` |
| Configured, endpoint refuses connection | `200`, `state == "unreachable"`, `detail` names the endpoint |
| Configured, endpoint responds | `200`, `state == "available"`, `detail is None` |
| Endpoint stalls | Returns within the configured timeout, `state == "unreachable"` |
| Any state | Response body contains no configured API key |
| Repeated calls within TTL | Underlying probe invoked once |
| Call after `reset_client()` | Probe invoked again |

---

## Modified: `GET /api/documents/<doc_id>/status`

Existing endpoint (`app/api/documents.py:202-214`). Currently returns:

```json
{"status": "completed", "progress": 100, "error": null}
```

**Change**: include the per-stage record so the SPA can distinguish "no summary
because no LLM" from "summary generated", without a second request.

```json
{
  "status": "completed",
  "progress": 100,
  "error": null,
  "pipeline": {
    "extract":   {"status": "completed", "at": "...", "chunks": 412},
    "embed":     {"status": "completed", "at": "...", "chunks": 412},
    "summarize": {"status": "failed",    "at": "...", "error": "Connection refused"},
    "hypergraph":{"status": "failed",    "at": "...", "error": "Connection refused"}
  }
}
```

Additive — `status`, `progress`, and `error` keep their meaning, so existing
consumers are unaffected. `pipeline` is read from `Document.metadata_['pipeline']`
and may be absent for documents processed before the stage record existed;
consumers must treat it as optional.

**Depends on** the Step 2 fix in `plan.md`. Until `stage_summarize` stops
recording `completed` unconditionally (`pipeline.py:297`), this field would
report a failed summary as a success and be actively misleading. Do not expose it
before that fix lands.

---

## Contract note: SPA document status

Not an HTTP contract, but a cross-boundary agreement this feature must repair.

The backend emits `'error'` (`app/models/document.py:17`, a PostgreSQL ENUM). The
SPA declares `'failed'` (`frontend_spa/src/app/core/models/document.model.ts:6`)
and branches on it (`sidebar.component.html:139`,
`document-item.component.ts:32,48`).

TypeScript cannot catch this — the union is an unchecked assertion over JSON — so
the error badge has never rendered. FR-012 ("documents indexed without an LLM
must not display as errors") currently passes for the wrong reason: *nothing*
displays as an error.

**Required**: align the SPA on `'error'` and add a test pinning the SPA union
against the backend enum, so the two cannot drift again silently.
