# Implementation Plan: Fix MCP Uploads Volume Mount

**Branch**: `002-fix-mcp-uploads-volume` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-fix-mcp-uploads-volume/spec.md`

## Summary

The `mcp` service in `docker-compose.yml` mounts only `./app` and `./config`, unlike `app` and `worker` which also mount `./data/uploads:/app/uploads`. `upload_document` copies the source file to `settings.UPLOAD_FOLDER` (`/app/uploads`), which for the MCP container is a container-local directory the worker cannot see — so processing fails with `no such file: /app/uploads/...` and the document ends in `status: error`.

Fix: add the single missing volume line to the `mcp` service, recreate the container, and verify end-to-end with a real MCP upload reaching `completed`.

## Technical Context

**Language/Version**: Python 3.11 (backend image `mnemos-backend:latest`)

**Primary Dependencies**: Docker Compose, Flask, Celery, FastMCP (`app/mcp_server/server.py`)

**Storage**: Host bind mount `./data/uploads` → `/app/uploads`; PostgreSQL for document records

**Testing**: No test suite in repo — verification is a manual end-to-end MCP upload plus a directory listing inside the container

**Target Platform**: Docker Compose stack on Windows host (dev)

**Project Type**: Infrastructure/configuration fix to an existing web service stack

**Performance Goals**: N/A — no runtime performance impact

**Constraints**: Minimal diff (one line in `docker-compose.yml`); must not disrupt `app`, `worker`, `db`, or `redis` while recreating `mcp`

**Scale/Scope**: One service definition, one line

### Verified facts (from source)

| Fact | Evidence |
|---|---|
| `mcp` mounts only app + config | `docker-compose.yml:144-146` |
| `app` and `worker` mount `./data/uploads:/app/uploads` | `docker-compose.yml:37`, `docker-compose.yml:74` |
| MCP upload writes to `settings.UPLOAD_FOLDER` | `app/mcp_server/server.py:999-1002` |
| `UPLOAD_FOLDER` defaults to `/app/uploads` in Linux containers | `config/settings.py:100` |
| MCP enqueues to Celery with default broker `redis://redis:6379/0` | `app/mcp_server/server.py:1016`, `config/settings.py:24` |

The Celery broker default already resolves inside the compose network, so no environment changes are needed — the missing volume is the only defect.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` is an unfilled template (all placeholders), so no project-specific gates apply. Generic gate — "is this the simplest change that works?" — passes: one line of configuration, no code changes, no new dependencies.

**Post-design re-check**: PASS. Design phase produced no new components, schemas, or interfaces.

## Project Structure

### Documentation (this feature)

```text
specs/002-fix-mcp-uploads-volume/
├── plan.md              # This file
├── research.md          # Phase 0: root cause + why this fix
├── quickstart.md        # Phase 1: apply + verify steps
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

No `data-model.md` — the change touches no schema or entity. No `contracts/` — no interface changes; the MCP `upload_document` signature and `GET /api/documents/{id}/status` response are unchanged.

### Source Code (repository root)

```text
docker-compose.yml       # ONLY file modified: add uploads volume to `mcp` service
data/uploads/            # Shared host directory (already exists, used by app + worker)
app/mcp_server/server.py # Read-only reference — upload_document, unchanged
```

**Structure Decision**: Single-file configuration change. No source code is modified; the MCP server code is already correct and works once the shared storage is attached.

## Phase 0: Research

See [research.md](./research.md). No NEEDS CLARIFICATION items — the root cause was verifiable directly from the compose file and the MCP source.

## Phase 1: Design

No new entities, contracts, or interfaces. Design output is the operational procedure in [quickstart.md](./quickstart.md): edit, recreate, verify listing, verify end-to-end upload.

## Complexity Tracking

No constitution violations; no complexity to justify.

## Implementation notes (post-execution)

The planned one-line fix worked as designed. Two **pre-existing, unrelated** defects in `docker-compose.dev.yml` blocked the documented apply command under Compose v5.0.2 and had to be fixed to proceed:

1. An empty `frontend:` key (a no-op that never disabled anything) — Compose v5 rejects it with "services.frontend must be a mapping". Removed.
2. `command: gunicorn … app:create_app()` — Compose v5 rejects the unquoted parentheses with "invalid command line string". Quoted as `"app:create_app()"`.

Both are behaviour-preserving. Verification result: document processed to `completed` with 1 chunk and a generated summary.
