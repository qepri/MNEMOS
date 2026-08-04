# Contract: `GET /api/ready`

**Branch**: `005-slim-deployment-mode` | **Status**: modified by this feature

The only externally-observable interface this feature changes. `GET /api/health` is **unchanged**.

## Consumers

- `start-dev.bat` and installer startup scripts (poll until ready)
- Container orchestrators / operators
- Anyone following the README quickstart

## Behaviour

Readiness = liveness + migrations applied + (llama.cpp reachable **only when the deployment uses it**).

Mode is derived from `settings.LLM_PROVIDER`:
- `llamacpp` → **full mode**, llama.cpp health is probed and required
- anything else → **slim mode**, llama.cpp is not probed at all

Response is cached for 5 seconds (unchanged).

## Response schema

```jsonc
{
  "db": true,                    // bool — SELECT 1 succeeded
  "redis": true,                 // bool — celery backend ping succeeded
  "migrations": {                // object — alembic current == head
    "ok": true,
    "current": "<revision>",     // present on success
    "head": "<revision>",        // present on success
    "detail": "<error string>"   // present instead, on failure
  },
  "llamacpp": {                  // OMITTED ENTIRELY in slim mode
    "ok": true,
    "detail": "<ExceptionName>"  // present only when ok is false
  },
  "status": "ready"              // "ready" | "not_ready"
}
```

## Status codes

| Condition | Code | `status` |
|---|---|---|
| All required checks pass | 200 | `ready` |
| Any required check fails | 503 | `not_ready` |

## Verdict rule

```
ok = db AND redis AND migrations.ok AND (slim_mode OR llamacpp.ok)
```

## Contract changes introduced

| # | Change | Compatibility |
|---|---|---|
| 1 | The `llamacpp` key is **absent** from the payload in slim mode | **Breaking for payload consumers** that assume the key exists. No known consumer reads it — existing scripts check only the HTTP status code. Chose omission over `{"ok": true, "skipped": true}` because a fabricated `ok: true` for an unprobed service is a lie that would mislead an operator reading the JSON. |
| 2 | In slim mode, readiness can be 200 while no inference server is reachable | **Intentional.** Readiness reports on services this deployment owns. A user's external Ollama instance is not owned by MNEMOS, and probing it would make MNEMOS report itself unhealthy because of a process it does not manage. Failures there surface as clear errors at query time. |
| 3 | Full-mode behaviour | **Unchanged** — byte-identical payload and status semantics. This is the SC-004 guard. |

## Examples

**Slim mode, healthy** → `200`

```json
{
  "db": true,
  "redis": true,
  "migrations": { "ok": true, "current": "a006_fix_ts_config", "head": "a006_fix_ts_config" },
  "status": "ready"
}
```

**Full mode, llama.cpp cold-starting** → `503` (normal transient state)

```json
{
  "db": true,
  "redis": true,
  "migrations": { "ok": true, "current": "a006_fix_ts_config", "head": "a006_fix_ts_config" },
  "llamacpp": { "ok": false, "detail": "ConnectionError" },
  "status": "not_ready"
}
```

**Slim mode, migrations pending** → `503`

```json
{
  "db": true,
  "redis": true,
  "migrations": { "ok": false, "current": "a005_chunks_fts", "head": "a006_fix_ts_config" },
  "status": "not_ready"
}
```
