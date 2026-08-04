# Tasks: Slim Deployment Mode

**Branch**: `005-slim-deployment-mode` | **Plan**: [plan.md](./plan.md)

Lean task list generated directly from the plan's ordered change list. The
implementation is ~15 lines across 5 files; a full `/speckit-tasks` breakdown
would have been longer than the diff.

## Phase 1: Tests

- [X] **T001** Pin `LLM_PROVIDER=llamacpp` in the three existing full-mode readiness tests
  (`tests/api/test_health.py`). Required: `.env` sets `LLM_PROVIDER=lm_studio` and
  pydantic reads it (`config/settings.py:113-115`), so without pinning these tests
  would silently take the slim path once T004 lands. Discovered during implementation.
- [X] **T002** Add slim-mode readiness tests (`tests/api/test_health.py`): returns 200
  with no `llamacpp` key, and `_llamacpp_status` is never called.

## Phase 2: Core

- [X] **T003** Add `profiles: ["local-llm"]` to the `llamacpp` service (`docker-compose.yml`). FR-001, FR-002, FR-005
- [X] **T004** Guard the llama.cpp probe on `settings.LLM_PROVIDER` in `ready()` (`app/__init__.py`). FR-006, FR-007
- [X] **T005** Add `presets/slim.env` — provider, base URL, embedding device only. FR-003, FR-004

## Phase 3: Docs

- [X] **T006** Add "Bring your own LLM server" section to `README.md`. FR-008

## Phase 4: Validation

- [X] **T007** `pytest tests/api/test_health.py` passes
- [X] **T008** `docker compose config --services` omits `llamacpp`; `--profile local-llm` includes it
