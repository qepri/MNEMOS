# Phase 0 Research: Prebuilt Container Images

All four spec-level clarifications were resolved in spec.md before planning.
This research covers the implementation unknowns, following 007's format:
working decision + empirical gate where the answer needs a real build to
confirm. Repo facts were verified directly, not assumed.

## R-000: Facts verified in the repo

- `requirements.in:17` pins bare `torch`; `requirements.lock.txt` pins
  `torch==2.13.0` with **no hashes** (0 `sha256` lines). The Dockerfile
  installs the lock from default PyPI — meaning **the current image carries
  CUDA torch**, confirming the size lever the spec describes.
- CI precedent already exists: `.github/workflows/tests.yml` installs with
  `--extra-index-url https://download.pytorch.org/whl/cpu` for host-side test
  runs. The CPU-wheel mechanism is proven in this repo; it has just never been
  applied to the *image* build.
- The Dockerfile is two-stage, already bakes the Whisper `base` model in the
  builder stage, and runs as uid 1000. Nothing about the stage structure needs
  to change.
- `.github/workflows/` exists with one workflow (`tests.yml`) — adding a second
  workflow follows an established pattern, not new infrastructure.

## R-001: Registry and authentication

**Decision**: GHCR (`ghcr.io/<owner>/mnemos-backend`, `.../mnemos-frontend`),
pushed from GitHub Actions using the workflow's automatic `GITHUB_TOKEN` with
`permissions: packages: write`. No user-managed secrets (satisfies FR-010).

**Rationale**: the repo is already on GitHub; GHCR is free for public images;
`GITHUB_TOKEN` auth removes the entire secret-management surface. Images must
be set public once in the package settings (a one-time manual step by the
owner — publishing is identity-bound and stays a human act).

**Alternatives**: Docker Hub — second account, rate limits on anonymous pulls
(the exact failure FR-006 guards against, self-inflicted); self-hosted — no.

## R-002: Getting CPU-only torch into the image

**Working decision**: install torch explicitly from the PyTorch CPU index
*before* the lock file, controlled by a build arg that defaults to today's
behaviour:

```dockerfile
ARG TORCH_INDEX=""
RUN if [ -n "$TORCH_INDEX" ]; then \
      pip install --no-cache-dir --prefix=/install --index-url "$TORCH_INDEX" \
        torch==2.13.0; \
    fi
RUN pip install --no-cache-dir --prefix=/install -r requirements.lock.txt
```

CI passes `TORCH_INDEX=https://download.pytorch.org/whl/cpu`; a plain
`docker-compose build` passes nothing and produces exactly today's CUDA image —
FR-003's dev-loop guarantee holds by default-off.

**Why install-first rather than `--extra-index-url` on the lock install**: with
both indexes visible, `torch==2.13.0` matches both the PyPI CUDA wheel and the
CPU index's `2.13.0+cpu`, and pip's choice between them is not guaranteed. Two
sequential installs make the resolution deterministic: torch is already
satisfied when the lock installs, so PyPI never gets asked for it. The pinned
version in the RUN line must match the lock — a drift check belongs in the
workflow (grep the lock for `torch==` and compare).

**Empirical gate G1**: build the image with and without the arg; verify
`import torch; torch.__version__` reports `+cpu` in the CPU build, record both
image sizes, and confirm embedding a test string works on the CPU image. Also
gates SC-001's realism: the pull-time estimate depends on the measured size.

## R-003: Tag flow — how repo and images stay pinned together

**Decision** (implementing the spec's resolved marker #2):

1. Owner tags: `git tag v0.1.0 && git push --tags`
2. Workflow triggers on `tags: ['v*']`, builds both images, pushes
   `ghcr.io/<owner>/mnemos-backend:v0.1.0` (+ commit-SHA tag for FR-004
   traceability)
3. `docker-compose.release.yml` in the tagged tree references
   `${MNEMOS_VERSION}` as the image tag
4. `install.ps1` resolves the latest release tag via the GitHub API
   (`releases/latest`), downloads **that tag's** zip (not `main`), and writes
   `MNEMOS_VERSION=<tag>` into the install's `.env`

Repo contents and image contents therefore always come from the same commit.
`:latest` is never referenced anywhere (spec: end users never run `latest`).

**Empirical gate G2**: `releases/latest` only returns tags that have a GitHub
*Release* object, not bare git tags — the release step must create one
(`gh release create` in the workflow, or documented as part of tagging).
Verify once against the real repo.

## R-004: Release compose path — override, not fork

**Decision**: `docker-compose.release.yml` contains, per built service
(`app`, `worker`, `mcp`, `frontend`): `image: ghcr.io/...:${MNEMOS_VERSION}`
and `pull_policy: missing`. Nothing else — ports, volumes, env, healthchecks
all inherit from `docker-compose.yml`. Compose ignores `build:` when the image
is present and pull succeeds only if needed.

One subtlety: the base file names three services `image: mnemos-backend:latest`
*and* `build: .`. When the release override renames the image, compose will
still want to build if the GHCR image isn't pulled — so the installer/launcher
must `pull` before `up` (or use `--no-build`) to guarantee SC-002's
zero-compile claim. `--no-build` is the stronger guarantee: if the pull failed,
`up --no-build` errors instead of silently compiling for 40 minutes — which is
exactly the FR-006 behaviour (fail loudly, offer fallback).

**Launcher wiring**: `start-lite.bat` gains a conditional: if `.env` contains
`MNEMOS_VERSION`, add `-f docker-compose.release.yml` and `--no-build` to the
compose invocation. Dev machines have no `MNEMOS_VERSION`, so nothing changes
for them (FR-003/SC-003 by construction).

## R-005: CI runner constraints

**Working decision**: standard `ubuntu-latest` runner, single job, two
`docker build`s. Known risk: the runner ships ~14 GB free disk, and a CUDA
torch layer alone can blow it — **but the CI build is CPU-only by decision**,
which keeps the backend image in the 2-3 GB range and inside runner limits.
If it still trips, the documented mitigation is the well-known
free-disk-space step (delete preinstalled toolchains), not a bigger runner.

**Empirical gate G3**: first real workflow run on GitHub — watch for disk
exhaustion and total duration. CI duration is explicitly not a user-facing
cost (spec assumption), so slow-but-green passes.

## Summary

| ID | Question | Decision | Gate |
|---|---|---|---|
| R-001 | Registry/auth | GHCR + automatic `GITHUB_TOKEN`, no secrets | — |
| R-002 | CPU torch mechanism | install-first via `TORCH_INDEX` build arg, default = today's CUDA behaviour | G1: build both, measure, verify `+cpu` |
| R-003 | Tag flow | tag → workflow → `:vX.Y.Z` images; installer pins zip+image to same tag | G2: `releases/latest` needs a Release object |
| R-004 | Release compose | override with `image:` + `pull_policy` only; `--no-build` for the zero-compile guarantee | — |
| R-005 | Runner limits | fits because CPU-only; free-disk step as mitigation | G3: first real run |

**Sequencing**: G1 is runnable locally now (needs the Podman/Docker build to be
free — same socket-contention lesson as 007). G2 and G3 need the repo public on
GitHub with Actions enabled, which is the owner's call and the feature's real
external dependency.
