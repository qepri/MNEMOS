# Feature Specification: Prebuilt Container Images

**Feature Branch**: `008-prebuilt-images`

**Created**: 2026-08-04

**Status**: Draft

**Input**: User description: "The one-command install works but takes ages because every user builds the backend image from source. Publish prebuilt images so end users pull instead of building."

## Why this feature exists

Features 005-007 made MNEMOS installable in one command. This one makes that
command finish in minutes instead of tens of minutes.

`docker-compose.yml` declares `build: .` for `app`, `worker`, `mcp` and
`frontend`. Every end user therefore *compiles* the backend image on their own
machine: ~140 Debian packages, then torch, sentence-transformers, PyMuPDF and
Whisper from PyPI. Observed on the 007 gate machine: **over 40 minutes, and the
build died partway** (a buildkit session healthcheck failure under concurrent
socket load — recoverable, but the user would just see a hang).

Note the asymmetry that makes this obviously wrong: the compose file already
pulls `pgvector/pgvector:pg16`, `redis:7-alpine` and `adminer` in seconds
because those are prebuilt and published. **MNEMOS's own images are the only
ones being compiled on user hardware.**

Building once in CI and letting everyone pull the result converts a long,
fragile, CPU-bound compile into a plain download.

### What this does NOT change

MNEMOS stays entirely local. A registry hosts the *software*, not the *data* —
the same relationship an installer download has to the app it installs.
Documents, database, embeddings, queries and chat all remain on the user's
machine, and the stack still runs offline once pulled. This is recorded
explicitly because "downloads from a server" and "runs on a server" are easy to
conflate, and local-first is the product's premise.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Install finishes in minutes (Priority: P1)

A new user runs the one-command install. Images download rather than compile,
and MNEMOS is usable in a few minutes on a normal connection.

**Why this priority**: this is the feature. The install already works; this is
the difference between a stranger trying MNEMOS and abandoning it at a progress
bar.

**Independent Test**: on a clean machine with no MNEMOS images cached, run the
one-liner and measure wall-clock time to first search.

**Acceptance Scenarios**:

1. **Given** a machine with no cached MNEMOS images, **When** the user runs the
   installer, **Then** no compile step runs — output shows pulls, not apt/pip.
2. **Given** a normal broadband connection, **When** the install runs, **Then**
   time from command to a usable UI is **under 5 minutes**. The embedding model
   is **not** baked into the image — it downloads on first index, inside the
   existing per-stage processing UX, and is reported as a separate number.
   *(Resolved 2026-08-04. Decisive reason: the hardware presets use different
   models — MiniLM / bge-base / bge-m3 — so no single baked model is right, and
   the `./data/hf_cache` bind mount already persists the download across image
   updates and even runtime migrations. Baking would re-ship gigabytes on every
   release for a file that downloads once ever.)*
3. **Given** the images are already cached, **When** the user re-runs the
   launcher, **Then** startup is near-instant with no re-download.
4. **Given** an interrupted download, **When** the user re-runs, **Then** it
   resumes from cached layers rather than restarting.

---

### User Story 2 - Developers still build from source (Priority: P1)

A developer changes `app/` and runs the stack; their change is picked up.
Nothing about the current dev loop regresses.

**Why this priority**: equal to US1. A published image that makes local
development harder is a bad trade — and it is the whole team's daily path.

**Independent Test**: edit a file, start the dev stack, confirm the change is
live and no published image is pulled.

**Acceptance Scenarios**:

1. **Given** the dev compose invocation, **When** a developer starts the stack,
   **Then** images build from local source exactly as today.
2. **Given** the bind mounts on `app/` and `config/`, **When** a developer edits
   a file, **Then** behaviour is unchanged from today (no rebuild required).
3. **Given** a developer wants to test the published image, **When** they use
   the release path, **Then** they get exactly what an end user gets.

---

### User Story 3 - Releases are reproducible and inspectable (Priority: P2)

A user (or a suspicious reader on r/LocalLLaMA) can see exactly what is inside
the image they are running and confirm it was built from the public source.

**Why this priority**: P2 for function, high for trust. A local-first privacy
tool asking people to pull a binary blob should make that blob accountable.

**Acceptance Scenarios**:

1. **Given** a published image tag, **Then** it is traceable to the exact commit
   it was built from.
2. **Given** two users installing weeks apart at the same version, **Then** they
   run identical images — unlike today, where each build resolves dependencies
   afresh.
3. **Given** a published image, **Then** the CI workflow that produced it is
   publicly readable.

---

### Edge Cases

- Registry unreachable or rate-limited at install time: the installer must say
  so plainly and offer the build-from-source fallback, not hang.
- Image and repo out of step: a user pulls image `v1.2` but their downloaded
  repo is `main` — compose files, migrations and the SPA must agree.
  **Resolved (2026-08-04): pin them together.** The installer downloads the
  release zip for a tag, and that tag's compose override references image
  `:same-tag` — repo and images always travel as one versioned unit, and
  `:latest` is never what an end user runs. The cost is a release step (tag →
  CI builds → images published); the benefit is that a migration in the repo
  can never meet a container that predates it.
- Architecture: the gate machine is x86_64, but Podman/Docker on Apple Silicon
  is arm64. **Resolved (2026-08-04): amd64-only for v1, arm64 explicitly
  deferred.** Not for CI cost — because an arm64 image would ship unverified
  (no Apple Silicon hardware to boot it on, and QEMU-emulated builds of
  torch/PyMuPDF/Whisper are exactly the kind that build fine and misbehave at
  runtime), and because the install path itself is Windows-only today
  (`install.ps1`, WSL2), so a Mac user cannot run the one-liner regardless.
  Deferring is additive: `platforms: linux/arm64` on the same workflow later,
  no breaking change. Documented fallback: Apple Silicon builds from source
  (`build: .` remains for developers, and macOS builds arm64 natively).
  Revisit trigger: real Mac demand appears (e.g. from the r/LocalLLaMA post)
  AND someone can test the image on M-series hardware.
- Image size: the backend carries torch and Whisper. Pulling several GB is still
  much faster than compiling, and CUDA-vs-CPU torch is the single biggest lever.
  **Resolved (2026-08-04): publish ONE image, CPU-only torch. Never ask the
  user.** "CPU or CUDA torch?" is a maintainer-vocabulary question an end user
  cannot answer, a wrong answer costs a 4+ GB download or a broken start (CUDA
  image without the container toolkit — the exact failure class 005/007
  eliminated), and every installer prompt costs completions. The default path
  already decides it: the one-liner runs slim mode with `EMBEDDING_DEVICE=cpu`,
  where CUDA torch is dead weight — and a GPU user's GPU is still fully used in
  slim mode, by their LLM server, which does not go through torch. GPU
  embedding users self-select onto `start.bat` + build-from-source, which gives
  them CUDA torch exactly as today. A published `-cuda` variant is additive
  later if demand appears — same deferral shape as arm64.
- First index still downloads the embedding model (~2 GB for `bge-m3`) unless it
  is baked in. Relevant to the US1 time budget.
- A stale local `mnemos-backend:latest` from a previous source build could
  shadow the published image; the release path must be unambiguous about which
  it uses.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Backend and frontend images MUST be built by CI and published to a
  public container registry.
- **FR-002**: The end-user install path MUST pull published images and MUST NOT
  compile anything on the user's machine.
- **FR-003**: The developer path MUST continue to build from local source with
  no change to today's edit-reload loop (bind mounts on `app/`, `config/`).
- **FR-004**: Published images MUST be traceable to the source commit that
  produced them.
- **FR-005**: Image and repository contents MUST be version-consistent for a
  given install (see the clarification in Edge Cases).
- **FR-006**: If the registry is unreachable, the installer MUST report it
  clearly and offer the build-from-source fallback rather than hanging.
- **FR-007**: Publishing MUST NOT change the runtime security posture from 007 —
  non-root uid 1000, `db`/`redis`/`adminer` on loopback only.
- **FR-008**: The release compose path MUST follow the override discipline
  established in 005/007: overrides carrying deltas, never a forked copy of the
  service graph.
- **FR-009**: Documentation MUST state plainly that pulling an image does not
  send any user data anywhere and that MNEMOS runs offline after install.
- **FR-010**: The CI workflow MUST be publicly readable and MUST NOT require
  secrets beyond the registry token the platform provides automatically.

### Key Entities

No data entities. Artifacts: a CI workflow, published image tags, a release
compose override, and installer changes.

## Success Criteria *(mandatory)*

- **SC-001**: Clean-machine install time from command to first search drops from
  the observed 40+ minutes to the agreed budget (see FR/US1 clarification).
- **SC-002**: Zero compile steps on the user's machine — install output contains
  no apt or pip activity for MNEMOS's own images.
- **SC-003**: The developer edit-reload loop is measurably unchanged.
- **SC-004**: Two clean installs of the same version produce byte-identical
  images.
- **SC-005**: A published image is traceable to its commit, and the workflow that
  built it is readable by anyone.
- **SC-006**: With the registry blocked, the installer explains the problem and
  the fallback within a few seconds rather than hanging.

## Assumptions

- Depends on `007-podman-images` completing its gates: this branch is cut from
  007, and 008 changes only *where the image comes from*, not how it runs — so
  007's gate results stay valid. Merge order: 005 → 006 → 007 → 008.
- **Registry: GHCR** (`ghcr.io`, GitHub Container Registry) under the project's
  existing GitHub account — free for public images, no additional account, and
  CI authentication is automatic. Not a hard requirement; any public OCI
  registry satisfies FR-001.
- Publishing images is an outward-facing act tied to the maintainer's identity
  and cannot be done by tooling on their behalf without explicit approval.
- The repository must be public for the install one-liner and public image pulls
  to work at all — an existing precondition from 007, not introduced here.
- CI build time is not a user-visible cost; a slow workflow is acceptable if the
  pull is fast.
