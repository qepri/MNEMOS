# Feature Specification: Podman Runtime Support

**Feature Branch**: `007-podman-runtime`

**Created**: 2026-08-04

**Status**: Draft

**Input**: User description: "Run MNEMOS with Podman from the terminal instead of Docker Desktop, so the user doesn't need to install Docker. Keep the same compose service graph."

## Why this feature exists

Docker Desktop is the single heaviest install in MNEMOS's setup: a licensed GUI
product with a background daemon, required today even though the user never
interacts with it beyond "is it running". Podman provides the same container
runtime as a daemonless CLI (`winget install RedHat.Podman`), which fits the
audience features 005/006 target — people comfortable running a `.bat` file but
not administering infrastructure.

**Honest scope statement**: Podman on Windows still runs containers inside a
WSL2-backed VM (`podman machine`). This feature removes the Docker Desktop
*product* — its license terms, GUI, and always-on daemon — not virtualization
itself. The user experience is "install a CLI, run the launcher" instead of
"install and keep a desktop application running".

**Why the container runtime stays at all** (recorded so the alternative is not
re-litigated later): the anchor is the data layer. Postgres needs the compiled
pgvector extension at a pinned version, and Redis has no official Windows build.
Replacing those with native installs makes every user machine a unique support
case; replacing them in code (sqlite-vec, a Redis-free queue) is a rewrite of
the retrieval core, not a deployment change. Swapping the runtime keeps
everything and changes one dependency.

## Prior art in this repo (constraint, not greenfield)

`installer/docker-compose.podman.yml` and `docker-compose.podman.test.yml`
already exist from an earlier attempt — and they are the cautionary tale this
spec must not repeat. As full copies of the service graph they have drifted
badly, and dangerously:

- `db` and `redis` published on **all interfaces** (`5433:5432`, `6380:6379`)
  where the maintained file binds `127.0.0.1` only — a real security regression
  in a system with **no authentication layer** (per CLAUDE.md).
- `adminer` always on; missing the `local-llm` profile from 005; `mcp` runs an
  SSE server the maintained file doesn't.

The 005 research already chose overrides-not-forks for exactly this reason
(`docker-compose.cpu.yml` was the first warning; the podman forks are the
second, worse one). This feature MUST follow the same rule and MUST retire the
stale forks.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fresh install with Podman only (Priority: P1)

A new user with no Docker Desktop installs Podman from the terminal, runs the
MNEMOS launcher, and gets the same six services, the same URLs, and the same
first-run experience as a Docker user — including slim/LLM-optional mode from
005/006.

**Why this priority**: this is the feature. If a Podman-only machine cannot
reach first search, nothing else here matters.

**Independent Test**: on a machine with Podman and no Docker, run the launcher;
upload a PDF; search it; confirm all 006 acceptance behaviour holds.

**Acceptance Scenarios**:

1. **Given** Podman installed and no Docker, **When** the user runs the
   launcher, **Then** all six default services start and `/api/ready` reaches
   `200`.
2. **Given** the stack running under Podman, **When** the user uploads and
   searches a document, **Then** behaviour is identical to Docker (including
   LLM-optional dormant states).
3. **Given** a host Ollama server and slim mode, **When** the user chats,
   **Then** the container reaches the host endpoint — the 005 mechanism
   (`host.docker.internal`) works or is transparently remapped.
4. **Given** neither runtime installed, **When** the user runs the launcher,
   **Then** they get a clear message telling them what to install, with the
   Podman terminal path presented as the lighter option.

---

### User Story 1b - One command from nothing to running (Priority: P1)

A user with a stock Windows 11 machine — no Podman, no Docker, no git — pastes
a single command into PowerShell. When it finishes, MNEMOS is open in their
browser and they can upload and search.

**Why this priority**: this is the distribution artifact. Everything else in
005-007 exists so that this command can end in a working app; it is the line
that gets pasted into a forum post.

**Independent Test**: on a clean Windows VM, paste the one-liner; verify the
browser opens on a working MNEMOS with no other user action.

**Acceptance Scenarios**:

1. **Given** a machine with no container runtime and no git, **When** the user
   runs the bootstrap one-liner, **Then** it installs Podman, downloads MNEMOS
   (as an archive — git must not be required), and hands off to the launcher,
   ending with the browser open on the running app.
2. **Given** a machine that already has Docker or Podman, **When** the
   bootstrap runs, **Then** it skips runtime installation and reuses what is
   there (same detection order as the launcher).
3. **Given** WSL2 is not enabled, **When** the bootstrap runs, **Then** it says
   exactly what to enable (or enables it and requests the reboot), and is safe
   to re-run afterwards — every step is idempotent.
4. **Given** the bootstrap is interrupted at any point, **When** it is run
   again, **Then** it resumes without damage (no half-installed states that
   block a retry).
5. **Given** the first run, **Then** the script is honest about time: image
   pulls and builds take minutes, and the script says so rather than sitting
   silent.

---

### User Story 2 - Existing Docker users are not disturbed (Priority: P2)

A user already running MNEMOS under Docker Desktop pulls this version and
notices nothing. Same launcher, same behaviour, same data.

**Why this priority**: every existing install is a Docker install. A runtime
*addition* must never be a migration *demand*.

**Acceptance Scenarios**:

1. **Given** Docker Desktop present and running, **When** the user runs the
   launcher, **Then** Docker is used exactly as before.
2. **Given** both runtimes installed, **When** the launcher runs, **Then**
   [NEEDS CLARIFICATION: preference order — prefer Docker for continuity with
   existing data volumes, prefer Podman as the blessed path, or prompt once and
   remember? Data location is the sharp edge: Docker and Podman volumes are
   separate stores, so silently switching runtimes makes an existing library
   "disappear".]

---

### User Story 3 - Existing data survives a runtime switch (Priority: P3)

A user who started on Docker Desktop deliberately moves to Podman and brings
their indexed library with them.

**Why this priority**: P3 because it is an explicit, documented, one-time
operation — not something the launcher does implicitly. The existing
`pg_dump`/restore path in the README already covers the mechanics.

**Acceptance Scenarios**:

1. **Given** a Docker install with indexed documents, **When** the user follows
   the documented migration steps, **Then** the Podman deployment serves the
   same library (bind-mounted `./data/uploads` carries over untouched; the
   database moves via dump/restore).
2. **Given** a completed migration, **Then** re-embedding is NOT required —
   vectors travel inside the dump.

---

### Edge Cases

- `podman machine` exists but is stopped: the launcher must start it (the
  Podman analogue of today's "Docker Desktop installed but not running" loop).
- WSL2 absent or disabled: `podman machine init` fails; the message must say
  what to enable, not dump a stack trace.
- Rootless uid mapping: the images run as uid 1000 (`mnemos`), and every `:rw`
  bind mount (`./app`, `./config`, `./data/uploads`, caches) is host-owned.
  Under rootless Podman, container uid 1000 maps to a high subuid, not the
  host user — writes fail unless handled. [NEEDS CLARIFICATION: strategy —
  `podman machine` on Windows may make this moot (the VM mounts are
  root-mediated), but on native Linux it bites. Options: `:U` volume flag,
  `--userns=keep-id`, or switching uploads/caches to named volumes as the old
  fork did (which changes where user-visible files live and breaks the
  documented backup path). Must be resolved by testing on both Windows and
  Linux, not assumed.]
- `host.docker.internal`: slim mode's entire LLM path routes through it —
  compose `extra_hosts: host-gateway` plus `_normalize_local_url()` rewriting
  user-typed `localhost`. Podman's support for `host-gateway` and its own
  `host.containers.internal` has varied by version, and inside `podman machine`
  "the host" is the VM, not Windows. [NEEDS CLARIFICATION: verified behaviour on
  current Podman/Windows — and if it resolves to the VM rather than the Windows
  host, whether the fix is an extra_hosts remap in the podman override or an
  extension of `_normalize_local_url()`. A silent failure here is
  indistinguishable from 006's dormant state, which is why 006 shipped first.]
- GPU profile (`--profile local-llm`): CDI setup for NVIDIA under Podman/WSL2 is
  the ugly path the old installer README documented. Out of scope to automate;
  in scope to detect and message ("GPU passthrough under Podman requires manual
  setup — see X, or use slim mode").
- Compose provider: `podman compose` delegates to an external provider and its
  behaviour depends on what is installed. [NEEDS CLARIFICATION: pin
  `docker-compose` (the Go binary, which speaks the Podman socket and needs no
  Docker) as the single supported provider, or also support the Python
  `podman-compose` reimplementation, which has known gaps in `deploy:` and
  profile handling — the exact features 005/006 rely on?]

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST run its full service graph under Podman on
  Windows with no Docker components installed.
- **FR-002**: There MUST be exactly one maintained definition of the service
  graph. Podman-specific deltas live in an override file; full-copy forks are
  prohibited, and `installer/docker-compose.podman*.yml` MUST be deleted or
  regenerated as overrides.
- **FR-003**: The launcher MUST detect the available runtime and use it; with
  neither present it MUST name both options and how to get them.
- **FR-004**: `db`, `redis`, and `adminer` MUST remain bound to `127.0.0.1`
  under Podman — parity with the security posture of the maintained compose
  file, and the specific regression the old fork shipped.
- **FR-005**: Slim mode's host-LLM path MUST work under Podman: a server
  reachable at the configured endpoint from inside the containers, with
  user-typed `localhost` URLs still transparently corrected.
- **FR-006**: All 005/006 behaviour (profiles, slim override, LLM-optional
  dormant states, `/api/ready` semantics) MUST hold identically under Podman.
- **FR-007**: The launcher MUST handle "Podman installed but machine not
  running" by starting it, mirroring today's Docker Desktop wait loop.
- **FR-008**: Documentation MUST present the Podman terminal path as the
  lightweight option and include the explicit Docker→Podman data migration
  steps (US3).
- **FR-009**: Existing Docker deployments MUST continue to work with zero
  changes to their invocation or data.
- **FR-011**: A bootstrap script (`install.ps1`, fetchable and runnable as a
  single PowerShell command) MUST take a machine from "no runtime, no git, no
  repo" to the running app: verify/enable WSL2, install Podman only if no
  runtime exists, download the repo as an archive, delegate to the launcher.
  Every step MUST be idempotent — re-running after any interruption resumes
  safely — and the script MUST NOT duplicate launcher logic (it bootstraps,
  then hands off; the launcher stays the single owner of runtime detection and
  compose invocation).
- **FR-012**: The bootstrap MUST state what it is about to install before
  installing it, and long steps (VM image, container builds) MUST print
  progress honestly rather than appearing hung.
- **FR-010**: The test suite MUST remain runtime-agnostic: testcontainers
  sessions run against whichever runtime the host provides, and no test may
  hardcode Docker-only assumptions. [NEEDS CLARIFICATION: current
  testcontainers-python behaviour against a Podman socket on Windows — works
  via `DOCKER_HOST` remap, or needs fixture changes? Gates CI strategy.]

### Key Entities

No data entities. The artifacts are: one compose override
(`docker-compose.podman.yml`, rebuilt as an override), launcher runtime
detection, and documentation.

## Success Criteria *(mandatory)*

- **SC-001**: A machine with Podman and no Docker goes from launcher to first
  search result — the 006 walkthrough — with no manual container commands.
- **SC-001b**: A clean Windows 11 VM goes from pasting the one-liner to a
  browser open on working MNEMOS with zero further user action (reboot for
  WSL2 enablement being the one permitted interruption, after which re-running
  the same command completes the job).
- **SC-002**: `git grep` shows no full-copy compose fork in the repo; the
  podman override contains only deltas.
- **SC-003**: Port exposure under Podman is identical to Docker (`db`/`redis`/
  `adminer` on loopback only), verified by inspecting the running stack.
- **SC-004**: Slim mode chat works under Podman against a host Ollama — the
  `host.docker.internal` chain is proven, not assumed.
- **SC-005**: The full backend suite passes against a Podman-provided
  testcontainers session.
- **SC-006**: A Docker Desktop user upgrading to this version observes zero
  behaviour change.

## Assumptions

- Builds on `006-llm-optional-mode` (this branch is cut from it). Merge order:
  005 → 006 → 007.
- WSL2 remains a base requirement on Windows under either runtime; removing
  virtualization entirely is out of scope (see "Why the container runtime
  stays").
- GPU/CUDA under Podman is detect-and-message, not automate (the old
  `installer/README.md` path documents how ugly automation gets).
- The unverified 005 hardware checks (T001/T002/T006 in 006's tasks.md) should
  be folded into this feature's verification pass — same GPU-less test machine,
  one session.
- The four `[NEEDS CLARIFICATION]` markers (dual-runtime preference, rootless
  mount strategy, host-gateway behaviour, compose provider + testcontainers)
  are all empirical questions about current Podman behaviour, not design
  choices — clarify by testing on a real Podman install, not by discussion.
