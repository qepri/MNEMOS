# Contract: Health & Readiness Endpoints

**Feature**: `003-production-readiness` | Satisfies FR-045, FR-044, SC-011

Two distinct concerns, two distinct endpoints. The existing endpoint is preserved unchanged so the launcher poll and any external checks keep working; readiness is added alongside it.

## `GET /api/health` — liveness (UNCHANGED)

Existing behavior at `app/__init__.py:84` is preserved exactly. Documented here to lock it against accidental change during refactoring.

**Semantics**: can this process serve requests at all? Checks its own dependencies (database, Redis) and nothing else.

**Response 200** — all checks pass:
```json
{ "status": "ok", "db": true, "redis": true }
```

**Response 503** — any check fails:
```json
{ "status": "degraded", "db": true, "redis": false }
```

**Caching**: results cached 5 seconds behind a lock. Polling faster than ~3s intervals gains nothing.

**Consumer**: `start-dev.bat` polls this until 200 (bounded, ~90s cap at 3s intervals), then aborts loudly on timeout instead of proceeding silently. Replaces the blind `timeout /t 15`.

## `GET /api/ready` — readiness (NEW)

**Semantics**: is the system fully ready to do useful work? Adds the two conditions in FR-045 on top of liveness.

**Response 200** — ready:
```json
{
  "status": "ready",
  "db": true,
  "redis": true,
  "migrations": { "ok": true, "current": "<revision>", "head": "<revision>" },
  "llamacpp": { "ok": true }
}
```

**Response 503** — not ready. Same shape, with the failing component false and a `detail` string:
```json
{
  "status": "not_ready",
  "db": true,
  "redis": true,
  "migrations": { "ok": false, "current": "003_ollama_fallback", "head": "005_chunks_fts", "detail": "pending revisions" },
  "llamacpp": { "ok": false, "detail": "connection refused" }
}
```

### Check definitions

| Check | Method | Failure meaning |
|---|---|---|
| `db` / `redis` | same as liveness | infrastructure down |
| `migrations` | compare Alembic current revision against script head | schema behind code — the condition that used to be masked by `db.create_all()` |
| `llamacpp` | short-timeout GET to the llama.cpp `/health` endpoint | local inference unavailable; RAG generation will fail |

### Requirements

- **Must not block**: llama.cpp check uses a short timeout (≤2s) and must never hang the endpoint. A cold llama.cpp start can take minutes (compose allows `start_period: 300s`), so an unreachable backend is a normal transient state, not an error to retry internally.
- **Must be cached** like liveness (5s) so polling cannot amplify into load on the inference server.
- **Must not mutate anything** — no migration is triggered by observing that migrations are pending.
- **Liveness stays green when readiness is red**: if llama.cpp is down the process is still alive and `/api/health` must still return 200. This is the distinction the spec asks for and the edge case it names.

## Migration execution contract

**Where**: `entrypoint.sh`, before `exec "$@"`.

**Gate**: runs only when `RUN_MIGRATIONS=true`. The variable already exists in `docker-compose.yml:21` but currently does nothing.

```sh
if [ "$RUN_MIGRATIONS" = "true" ]; then
  flask db upgrade
fi
exec "$@"
```

**Rules**:
- Default when unset: **do not run**. Only the `app` service sets it true; `worker` and `mcp` must not run migrations, or concurrent starts race on the same schema.
- Failure is fatal — `set -e` is already in effect, so a failed upgrade must stop the container rather than starting an app against a mismatched schema.
- No package installation happens in the entrypoint (FR-040): the `pip install --upgrade yt-dlp` line is removed and `yt-dlp` is pinned in requirements. After this change the entrypoint requires no network access.

## Celery pool contract

Env-configurable with today's behavior as default (FR-043):

| Variable | Default | Meaning |
|---|---|---|
| `CELERY_POOL` | `solo` | preserves current `--pool=solo` |
| `CELERY_CONCURRENCY` | unset | passed through only when set |

The compose file must carry a comment explaining *why* solo is the default: the worker loads embedding models onto the same GPU that llama.cpp occupies, so concurrent tasks contend for VRAM.
