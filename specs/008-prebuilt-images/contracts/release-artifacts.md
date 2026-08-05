# Contract: Release Artifacts

What a release consists of and what each consumer may rely on.

## Published images

| Image | Contents |
|---|---|
| `ghcr.io/<owner>/mnemos-backend:<tag>` | Flask app + Celery worker + MCP (one image, as today), **CPU-only torch**, Whisper `base` baked in, non-root uid 1000 |
| `ghcr.io/<owner>/mnemos-frontend:<tag>` | Built SPA behind nginx |

Guarantees per image:

- Tagged both `vX.Y.Z` and `sha-<commit>`; the commit tag is never moved
  (FR-004 traceability).
- Built from the public workflow on the tagged commit — no out-of-band pushes.
- `linux/amd64` only (spec resolution #3). No arm64 manifest until it can be
  tested on real hardware.
- Backend `python -c "import torch; print(torch.__version__)"` ends in `+cpu`
  (spec resolution #4).
- Embedding model NOT included — first index downloads it into the mounted
  cache (spec resolution #1).
- Same security posture as a source build: `USER mnemos` (uid 1000), caches
  under `/home/mnemos/.cache` (FR-007).
- `:latest` is never published. Nothing may reference it.

## `docker-compose.release.yml`

Override only — per built service exactly two keys:

```yaml
services:
  app:
    image: ghcr.io/<owner>/mnemos-backend:${MNEMOS_VERSION}
    pull_policy: missing
  # worker, mcp: same image; frontend: mnemos-frontend
```

- MUST NOT restate ports, volumes, environment, healthchecks, or profiles —
  they inherit from `docker-compose.yml` (FR-008, the 005/007 override rule).
- MUST be verified with `docker-compose -f docker-compose.yml -f
  docker-compose.slim.yml -f docker-compose.release.yml config` before release
  (the CLAUDE.md override rule — `config` is what caught the `devices: []`
  no-op in 007).
- Invoked only when `MNEMOS_VERSION` is set; combined with `--no-build` so a
  failed pull errors loudly instead of falling back to a 40-minute compile
  (SC-002 made structural).

## `install.ps1` additions

- Resolves the latest release via the GitHub API with a short timeout; on
  failure prints the build-from-source fallback within seconds and exits —
  never hangs, never silently degrades (FR-006 / SC-006).
- Downloads the **tag's** zip, not `main` (the data-model invariant).
- Writes `MNEMOS_VERSION=<tag>` into the install's `.env`.
- Still contains no runtime detection or compose logic — the launcher owns
  those (007 contract, unchanged).

## `start-lite.bat` addition

- If `.env` contains `MNEMOS_VERSION`: append `-f docker-compose.release.yml`
  and `--no-build` to the existing compose invocation.
- If absent (every dev machine): invocation is byte-identical to 007's
  (FR-003 / SC-003 by construction).

## Workflow (`release-images.yml`)

- Trigger: push of tag `v*`. Manual `workflow_dispatch` permitted for re-runs.
- Auth: workflow `GITHUB_TOKEN` with `permissions: packages: write` — no
  user-managed secrets (FR-010).
- MUST create a GitHub Release for the tag (gate G2: `releases/latest` ignores
  bare tags).
- MUST fail if the torch pin in the Dockerfile RUN line differs from
  `requirements.lock.txt` (the R-002 drift check).
- Publicly readable, like everything else in `.github/workflows/` (SC-005).

## Verification hooks

| Claim | Check |
|---|---|
| Zero compile on user machine | Install output contains pulls only — no apt/pip lines from MNEMOS images (SC-002) |
| CPU torch | `docker run --rm <backend> python -c "import torch; print(torch.__version__)"` → `+cpu` |
| Traceability | `sha-<commit>` tag resolves to the same digest as `vX.Y.Z` (SC-005 / FR-004) |
| Ports unchanged | `docker-compose ... config` shows db/redis/adminer on `127.0.0.1` only (FR-007) |
| Registry down | Block ghcr.io → installer names the problem and the fallback in seconds (SC-006) |
