# Quickstart: Running the MNEMOS Test Suite

**Feature**: 004-test-suite

Verified against a real run: the full backend suite (47 tests), the migration chain tests (3 tests, isolated process), and the coverage ratchet all pass from a clean checkout following the commands below.

---

## Prerequisites

- **A container runtime running** — testcontainers starts a throwaway Postgres and Redis. Nothing to create by hand.
  Under Podman instead of Docker, point testcontainers at Podman's Docker-compatible socket first:
  ```powershell
  $env:DOCKER_HOST = 'npipe:////./pipe/podman-machine-default'
  # add this only if Ryuk (the container reaper) misbehaves under rootless Podman:
  # $env:TESTCONTAINERS_RYUK_DISABLED = 'true'
  ```
  No fixture changes are needed — the conftest guard rails (random port, refuse 5432) are runtime-agnostic.
- **Python 3.11** — matches the app's base image.
- **Node LTS** — frontend tests only.

You do **not** need the dev stack up. The suite never touches it.

---

## Backend

```bash
python -m venv .venv
source .venv/Scripts/activate     # Windows Git Bash; use .venv/bin/activate on Linux/macOS

# requirements.lock.txt pins CUDA-only NVIDIA wheels for the GPU container
# image and will not resolve on a plain host (Windows, or a CPU-only CI
# runner). Install from the unpinned requirements.in instead, with PyTorch's
# CPU wheel index added so torch resolves without CUDA:
pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.in -r requirements-dev.txt

pytest
```

First run pulls `pgvector/pgvector:pg16` and `redis:7-alpine` if absent, then applies the Alembic chain once per session. Subsequent runs reuse the cached images.

### Subsets

```bash
pytest -m api                    # Flask routes
pytest -m service                # RAG, LLM client, embedder
pytest -m pipeline               # Celery stages
pytest -m migration              # upgrade/downgrade round-trip
pytest -m "not slow"             # fast local iteration
pytest tests/services/test_rag.py::test_rrf_merge   # single test
```

### Coverage

```bash
pytest --cov                     # full report
```

Gated groups are the RAG pipeline and the document-processing pipeline; the run fails if either drops below `coverage-baseline.json`. Everything else is reported only.

To raise the baseline after genuinely improving coverage, update `coverage-baseline.json` in the same commit — it never moves automatically.

---

## Frontend

```bash
cd frontend_spa
npm ci
npm test                # Vitest via @angular/build:unit-test
npm test -- --watch     # watch mode
```

Smoke-level coverage of the chat, document upload, and settings screens. No backend or Docker needed.

---

## Safety

Your dev database is never at risk:

- Test containers bind **random host ports** — they cannot collide with the dev stack on 5432/6379.
- A session-scoped guard aborts the run if the configured database is not the test container.
- An autouse guard fails any test that reaches a real external host, so a missing LLM stub fails loudly instead of hanging.
- Containers are destroyed at session end, including on failure or Ctrl-C.

Running the suite while `docker-compose up` is active is safe.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `docker not available` at startup | Docker Desktop isn't running. The suite fails fast rather than falling back to another database — start Docker and retry. |
| First run is slow | One-time image pull. Cached afterward. |
| A test hangs or fails with an outbound-network error | Missing provider stub. Add the response to `fake_llm` / `fake_embeddings` — this guard is deliberate. |
| `dimension mismatch` on chunk insert | `EMBEDDING_DIMENSION` drifted from the pgvector column (1024). Real bug — do not paper over it in the fixture. |
| Migration test names a failing revision | That revision doesn't apply or reverse cleanly. Fix the revision, not the test. |
| `npm test` fails to start | Run `npm ci` first; the test deps are new to the project. |

---

## CI

Every pull request runs three jobs — `backend`, `migrations`, `frontend` — using the same commands as above. See [contracts/ci-workflow.md](./contracts/ci-workflow.md).
