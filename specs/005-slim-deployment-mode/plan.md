# Implementation Plan: Slim Deployment Mode

**Branch**: `005-slim-deployment-mode` | **Date**: 2026-08-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-slim-deployment-mode/spec.md`

## Summary

Make MNEMOS start without the bundled `llamacpp` container by default, pointed at an LLM server the user already runs (Ollama / LM Studio), with readiness reporting that stays accurate when that container is absent.

Technical approach: one `profiles:` key on the existing compose service, one new `presets/slim.env`, and a provider-conditional guard around the existing llama.cpp readiness probe. No new services, no new settings, no new abstractions — every mechanism this feature needs already exists in the codebase (`LM_STUDIO` provider, `LOCAL_LLM_BASE_URL`, `_normalize_local_url`, `_llamacpp_status`).

Research corrected two assumptions in the original request: the provider must be `lm_studio` rather than `custom` (which hard-fails without a DB connection row), and the preset must not touch `EMBEDDING_MODEL`/`EMBEDDING_DIMENSION` (which would break existing corpora). See [research.md](./research.md) R-001 and R-002.

## Technical Context

**Language/Version**: Python 3.11 (Flask backend), YAML (Compose), PowerShell (preset script)

**Primary Dependencies**: Flask, Docker Compose v2 (profiles support), OpenAI SDK (used for all OpenAI-compatible endpoints), `requests` (readiness probe)

**Storage**: PostgreSQL 16 + pgvector — **unchanged by this feature**; no schema change, no migration

**Testing**: pytest (`tests/api/test_health.py` already covers `/api/ready`); manual compose verification for the profile behaviour

**Target Platform**: Linux containers via Docker Desktop (Windows/macOS) or native Docker (Linux)

**Project Type**: Web service (Flask API + Celery worker + Angular SPA), deployed via Docker Compose

**Performance Goals**: Slim startup pulls one fewer image and skips llama.cpp model load; readiness reaches ready without the 2s-timeout probe blocking the verdict

**Constraints**: No GPU/CUDA requirement in slim mode; zero behaviour change for existing full-mode deployments (SC-004); no DDL at startup (project rule)

**Scale/Scope**: 3 files changed, 1 file added, ~2 tests added. Single-user local deployment.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` is an **unfilled template** — all principles are placeholders (`[PRINCIPLE_1_NAME]`, etc.) with no ratified content. There are therefore no project-specific gates to evaluate.

Falling back to the constraints that *are* documented and binding (CLAUDE.md):

| Rule | Status |
|------|--------|
| Alembic is the only migration path; zero DDL at startup | PASS — no schema change |
| `RUN_MIGRATIONS=true` only on `app` service | PASS — untouched |
| `EMBEDDING_DIMENSION` must match the pgvector column | PASS — preset deliberately does not set it (R-002) |
| Never run tests against the live database | PASS — pytest fixtures provision disposable containers |
| Container images run as non-root `mnemos` | PASS — no image change |

**Post-Phase 1 re-check**: PASS. The design added no new services, settings, or persistence, so no gate status changed.

## Project Structure

### Documentation (this feature)

```text
specs/005-slim-deployment-mode/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output — R-001..R-004
├── data-model.md        # Phase 1 output — no entities (documented why)
├── quickstart.md        # Phase 1 output — the r/LocalLLaMA-facing instructions
├── contracts/
│   └── api-ready.md     # /api/ready response contract
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
docker-compose.yml           # MODIFIED — add `profiles: ["local-llm"]` to llamacpp service
presets/
├── slim.env                 # NEW — LLM_PROVIDER, LOCAL_LLM_BASE_URL, EMBEDDING_DEVICE
├── low.env                  # unchanged
├── medium.env               # unchanged
├── high.env                 # unchanged
└── apply.ps1                # unchanged — already generic over preset name
app/
└── __init__.py              # MODIFIED — provider guard around _llamacpp_status() call
tests/api/
└── test_health.py           # MODIFIED — add slim-mode readiness cases
README.md                    # MODIFIED — BYO-LLM quickstart section (FR-008)
```

**Structure Decision**: No new directories or modules. This feature is configuration and one conditional; it deliberately does not introduce a deployment-mode abstraction, a mode registry, or a slim-specific compose file. The existing preset mechanism (`presets/*.env` + `apply.ps1`) is already generic over preset names and needs no changes to accept a new one.

## Phase 1 Design

### Change 1 — Compose profile (FR-001, FR-002, FR-005)

Add to the `llamacpp` service in `docker-compose.yml` (~line 103):

```yaml
  llamacpp:
    profiles: ["local-llm"]
```

Verified safe: no service declares `depends_on: llamacpp`, so excluding it cannot block another service's startup.

Resulting commands:
- `docker compose up -d` → app, worker, db, redis, mcp, frontend (slim, default)
- `docker compose --profile local-llm up -d` → adds llamacpp (full, today's behaviour)

`start-dev.bat` names services explicitly (`... app worker llamacpp mcp db redis`). Naming a profiled service directly still starts it, so the developer flow is unaffected — but the llamacpp preflight/healthcheck steps in that script assume the container exists. Task list keeps `start-dev.bat` on the full path to preserve the maintainer's own workflow.

### Change 2 — `presets/slim.env` (FR-003, FR-004)

```env
# Slim — no bundled llama.cpp. Bring your own OpenAI-compatible LLM server.
# Ollama: http://host.docker.internal:11434/v1  |  LM Studio: http://host.docker.internal:1234/v1
LLM_PROVIDER=lm_studio
LOCAL_LLM_BASE_URL=http://host.docker.internal:11434/v1
EMBEDDING_DEVICE=cpu
```

Deliberately omits `EMBEDDING_MODEL` and `EMBEDDING_DIMENSION` (R-002) — slim mode must never invalidate existing vectors. `LLM_PROVIDER=lm_studio` despite targeting Ollama by default: that provider path is a generic OpenAI-compatible client, and `custom` hard-fails without a DB connection row (R-001).

### Change 3 — Readiness guard (FR-006, FR-007)

In `app/__init__.py`, replace the unconditional probe (line 178) and verdict (lines 180-185):

```python
payload["migrations"] = _migration_status()

# ponytail: slim deployments don't start llamacpp; probing it would pin
# readiness at 503 forever. Keyed on settings (deploy-time) not UserPreferences,
# which a user can flip at runtime without changing which containers run.
uses_llamacpp = settings.LLM_PROVIDER == LLMProvider.LLAMACPP
if uses_llamacpp:
    payload["llamacpp"] = _llamacpp_status()

ok = (
    payload["db"]
    and payload["redis"]
    and payload["migrations"]["ok"]
    and (not uses_llamacpp or payload["llamacpp"]["ok"])
)
```

`_llamacpp_status` stays a module-level function so the three existing tests that monkeypatch `app._llamacpp_status` keep working.

Requires importing `LLMProvider` alongside the existing `settings` import in `app/__init__.py`.

### Change 4 — README (FR-008)

A "Bring your own LLM server" section: apply the slim preset, point `LOCAL_LLM_BASE_URL` at Ollama or LM Studio, `docker compose up -d`. Content drafted in [quickstart.md](./quickstart.md).

### Testing strategy

Add to `tests/api/test_health.py`:
1. Slim mode (`LLM_PROVIDER != llamacpp`) → `/api/ready` returns 200 with db/redis/migrations healthy, and `_llamacpp_status` is **never called** (assert via a probe that raises or a call counter).
2. Slim mode → response payload omits the `llamacpp` key.
3. Existing full-mode tests must continue to pass unmodified — that is the SC-004 regression guard.

Compose profile behaviour is verified manually (`docker compose config --services` with and without `--profile local-llm`); it is not worth a test harness.

## Complexity Tracking

> No constitution violations to justify — the constitution is an unfilled template and the change introduces no new abstractions.

| Consideration | Resolution |
|---|---|
| Second compose file | Rejected in favour of a profile (R-004) — avoids drift |
| New `SLIM_MODE` setting | Rejected — derivable from `LLM_PROVIDER`, cannot contradict it (R-003) |
| New `ollama` provider enum | Rejected — `lm_studio` is already a generic OpenAI-compatible path (R-001) |

## Honest scope note

This plan documents a change of roughly 15 lines across 4 files. The planning artifacts are substantially longer than the implementation. The research phase earned its keep — it caught the `custom` provider failure and the embedding-dimension trap, both of which would have shipped as bugs — but `/speckit-tasks` is likely unnecessary here. Recommend going straight to implementation.
