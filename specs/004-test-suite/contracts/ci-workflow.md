# Contract: Pull Request Check

**Feature**: 004-test-suite | **File**: `.github/workflows/tests.yml`

---

## Trigger

`pull_request` against any branch, plus `push` to `main`. Every PR gets a status without anyone asking for it (SC-003).

## Jobs

Three independent jobs so the PR checks UI names the failing layer directly (FR-009) — no log parsing required.

| Job | Runs | Fails when |
|---|---|---|
| `backend` | `pytest -m "not migration"` with coverage | any API/service/pipeline test fails, **or** coverage for either gated group drops below its recorded baseline |
| `migrations` | `pytest -m migration` | any revision fails to apply in order, or the downgrade round-trip fails |
| `frontend` | `npm ci && npm test` (Vitest, headless) | any smoke test for chat / document upload / settings fails |

`backend` and `migrations` are split because migration tests manage their own database lifecycle and would otherwise serialize behind the shared session schema.

## Environment

- Runner: `ubuntu-latest` (provides Docker, which testcontainers needs).
- Python 3.11, matching the Dockerfile base image.
- Node: version per `frontend_spa` engines / LTS.
- **No `services:` block.** Containers come from testcontainers so the local and CI code paths are identical (research D1) — one path to keep working, and SC-001's "same documented command" holds literally.

## Guarantees

- **Isolation**: every run provisions its own throwaway containers. No shared or persistent environment is read or written (FR-006, SC-002). No secrets are needed, since all external providers are faked at the HTTP boundary.
- **No production impact**: the workflow builds no images and touches no compose file, so `docker-compose up -d --build` is unaffected (FR-008, SC-005).
- **Determinism**: no live LLM/embedding calls, so runs cannot fail on provider outages, rate limits, or cost.

## Coverage gate

`backend` compares measured coverage against `coverage-baseline.json`:

- Below baseline for `rag_pipeline` or `processing_pipeline` → **fail**, reporting group, baseline, and measured value.
- At or above → pass. Raising the baseline is a deliberate, reviewable commit; the ratchet never moves on its own (FR-012, SC-007).

Coverage for the rest of the backend is reported in the job summary but never gates.

## Non-goals

Per FR-011, the workflow does not test authentication/authorization (none exists), does not run load or performance tests, and does not cover VideoMix. It also does not deploy, publish images, or write to any environment.
