# Tasks: Fix MCP Uploads Volume Mount

**Feature**: 002-fix-mcp-uploads-volume | **Plan**: [plan.md](./plan.md)

One-line configuration fix; no code changes, no new tests (repo has no test suite). Verification is the end-to-end upload.

## Phase 1: Core

- [X] **T001** Add `- ./data/uploads:/app/uploads` to the `mcp` service `volumes` in `docker-compose.yml` (matching `app` and `worker`). — `docker-compose.yml:147`

## Phase 2: Apply

- [X] **T002** Recreate the MCP container: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d mcp` (restart is insufficient — mounts are fixed at creation).
- [X] **T002b** *(unplanned, blocker)* Fix two pre-existing parse errors in `docker-compose.dev.yml` that made the documented command fail under Compose v5.0.2: empty `frontend:` key (rejected as "must be a mapping") and unquoted `app:create_app()` in `app.command` (rejected as "invalid command line string").

## Phase 3: Verify

- [X] **T003** Confirm mount: `docker exec dev-mcp-1 ls /app/uploads` → 60 entries, matching host `data/uploads` (59 files + 1 dir).
- [X] **T004** End-to-end: uploaded a small PDF via the MCP `upload_document` code path inside `dev-mcp-1`; document `f05228c9…` reached `completed` in ~60s with 1 chunk and a 1037-char summary. No `no such file` error. Test document and source file removed afterwards.
