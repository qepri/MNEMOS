# Research: Fix MCP Uploads Volume Mount

**Feature**: 002-fix-mcp-uploads-volume | **Date**: 2026-08-01

No open questions — the root cause was confirmed directly from the repository. This document records what was verified and why the chosen fix is the right one.

## Root cause (confirmed)

1. `docker-compose.yml:144-146` — the `mcp` service mounts only `.\app:/app/app` and `.\config:/app/config`.
2. `docker-compose.yml:37` (`app`) and `:74` (`worker`) both mount `./data/uploads:/app/uploads`.
3. `app/mcp_server/server.py:999-1002` — `upload_document` copies the source file to `os.path.join(settings.UPLOAD_FOLDER, unique_name)` and stores only the bare filename in `Document.file_path`.
4. `config/settings.py:100` — `UPLOAD_FOLDER` is `/app/uploads` inside Linux containers.

So the MCP container writes into its own writable container layer at `/app/uploads`. The worker later resolves the same relative filename against the *shared* `/app/uploads`, finds nothing, and the document ends in `status: error` with `no such file: /app/uploads/...`.

## Decision: add the missing bind mount to the `mcp` service

- **Decision**: Add `- ./data/uploads:/app/uploads` to the `mcp` service's `volumes` list, matching `app` and `worker`.
- **Rationale**: The MCP code is already correct — it uses the same `UPLOAD_FOLDER` setting as the rest of the stack. The only broken assumption is that the directory is shared. One line restores the invariant that every service resolving a `Document.file_path` sees the same bytes.
- **Alternatives considered**:
  - *Named Docker volume shared across services* — would work, but the stack already uses a host bind mount for uploads; introducing a second mechanism for one service creates an inconsistency and makes host-side inspection of uploads harder.
  - *Have MCP call the HTTP upload endpoint instead of writing files directly* — larger change, adds a network hop and an auth surface, and would leave the underlying inconsistency in place for any future direct-write code.
  - *Change `UPLOAD_FOLDER` for the MCP container* — does not help; the problem is the directory is not shared, not that the path is wrong.

## Decision: recreate rather than restart the container

- **Decision**: Apply with `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d mcp`.
- **Rationale**: Volume mounts are fixed at container creation. `docker restart dev-mcp-1` reuses the existing container and would silently leave the bug in place — a realistic way to "apply" the fix and still see failures.
- **Alternatives considered**: `docker compose restart mcp` (rejected — does not re-read volume config); full stack `up -d` (unnecessary churn on `db`, `redis`, `app`, `worker`).

## Non-issues checked

- **Celery broker**: `mcp` sets no `REDIS_URL`, but `config/settings.py:24` defaults to `redis://redis:6379/0`, which resolves inside the compose network. `process_document_task.delay(...)` at `server.py:1016` already reaches the worker today — which is exactly why documents get created and *then* fail on file access, rather than never being queued.
- **`.env` not mounted in `mcp`**: acceptable — the defaults for `UPLOAD_FOLDER` and `REDIS_URL` are already the correct in-container values. Out of scope for this fix.
- **Pre-existing failed documents**: none. Verified after the fix — all 58 rows in `documents` are `status='completed'` and every `file_path` resolves on disk. The previously failed MCP uploads had already been cleaned up and re-uploaded through the web app before this work started, so no remediation was needed.
