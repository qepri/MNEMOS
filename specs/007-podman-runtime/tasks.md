---

description: "Task list for Podman Runtime Support"
---

# Tasks: Podman Runtime Support

**Input**: Design documents from `/specs/007-podman-runtime/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Verification here is mostly **empirical gates and manual checks**, not
new automated tests — this is a deployment feature, and the thing being verified
is runtime behaviour on real hardware. The one automated requirement is FR-010:
the existing suite must pass unchanged under Podman.

**Organization**: By user story. US1b (the one-command bootstrap) is the
distribution artifact and is tracked separately from US1 because it can only be
built after the launcher it delegates to.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US1b / US2 / US3; setup, foundational and polish carry no label

---

## Phase 1: Setup

**Purpose**: Get a real Podman install onto the gate machine.

- [ ] T001 Install Podman: `winget install RedHat.Podman`, then confirm `podman --version` resolves on PATH
- [ ] T002 Initialise the machine: `podman machine init` — note whether the orphaned `podman-machine-default` (research R-000) is adopted, reused, or must be removed first with `wsl --unregister podman-machine-default`; record the outcome in `specs/007-podman-runtime/research.md`
- [ ] T003 Start it and confirm `podman machine start` then `podman info` both succeed
- [ ] T004 Record the Docker-compat socket path from `podman machine inspect` into `specs/007-podman-runtime/research.md` (needed verbatim by every gate and by `runtime-detect.bat`)

**Checkpoint**: Podman usable from the terminal on the gate machine.

---

## Phase 2: Foundational — Empirical gates (BLOCKING)

**Purpose**: Answer the four questions the spec could not. Every later phase
cites a gate; none may start before its gate is recorded.

**⚠️ CRITICAL**: No 007 code is written until T009 records results. A failed
gate changes the plan, not just a task.

- [ ] T005 [P] Run gate **G1** (compose provider) per `specs/007-podman-runtime/quickstart.md`: with `DOCKER_HOST` set, verify `docker-compose -f docker-compose.yml -f docker-compose.slim.yml config --services` lists 6 services without `llamacpp`, that `--profile local-llm` includes it, that `up -d --wait` reaches healthy, and that `EMBEDDING_DEVICE` is `cpu` inside `dev-app-1`
- [ ] T006 [P] Run gate **G2** (host reachability — highest risk) per quickstart.md: from inside `dev-app-1`, reach a listener on the Windows host via `host.docker.internal`; on failure also try `host.containers.internal` and capture the gateway IP from `podman machine ssh` → `ip route`
- [ ] T007 [P] Run gate **G3** (rootless bind mounts): upload a document under Podman, confirm it appears in `./data/uploads/` on the host and that `/home/mnemos/.cache/*` is writable by uid 1000
- [ ] T008 [P] Run gate **G4** (testcontainers): with `DOCKER_HOST` set, run `.venv\Scripts\python.exe -m pytest tests/api/test_health.py -q`; note whether `TESTCONTAINERS_RYUK_DISABLED=true` was required
- [ ] T009 Append a `## Gate results` section to `specs/007-podman-runtime/research.md` with date, Podman version, and pass/fail plus evidence for G1-G4 — **Phase 3 is blocked until this exists**

### Folded-in 005 verification (carried from 006 tasks T001/T002/T006)

- [ ] T010 [P] With Docker Desktop stopped, confirm `docker-compose -f docker-compose.yml up -d` fails on the `driver: nvidia` reservation while adding `-f docker-compose.slim.yml` succeeds; record both outcomes in `specs/006-llm-optional-mode/tasks.md` and tick T001/T002/T006 there
- [ ] T011 [P] Confirm `EMBEDDING_DEVICE=cpu` inside the container under the slim override, closing 006's T002

**Checkpoint**: All four gates recorded. The plan is now either confirmed or revised.

---

## Phase 3: User Story 1 — Podman-only install works (P1) 🎯 MVP

**Goal**: On a machine with Podman and no Docker, the existing launcher brings
up MNEMOS with 005/006 behaviour intact.

**Independent Test**: Podman-only machine → run `start-lite.bat` → all six
services healthy, `/api/ready` 200, upload and search a PDF.

### Implementation

- [ ] T012 [US1] Create `runtime-detect.bat` implementing the detection order in `specs/007-podman-runtime/contracts/launcher-runtime-detection.md`: `MNEMOS_RUNTIME` override → `docker info` → Docker-installed-but-stopped wait loop → `podman` on PATH → guidance+exit 1
- [ ] T013 [US1] In `runtime-detect.bat`, export `MNEMOS_DETECTED_RUNTIME` and set `DOCKER_HOST` for the podman branch only, leaving it untouched for docker
- [ ] T014 [US1] In `runtime-detect.bat`, handle the podman branch's machine lifecycle: `podman machine start` if not running, `podman machine init` if none exists, printing honest progress for the first-run VM image download (FR-012)
- [ ] T015 [US1] In `runtime-detect.bat`, handle the orphaned-distro case from research R-000 — a `podman-machine-default` WSL distro with no `podman` on PATH must fall through to guidance, never be used
- [ ] T016 [US1] Write the no-runtime guidance message in `runtime-detect.bat` naming both options, with Podman as the terminal-only path and its `winget` command (FR-003)
- [ ] T017 [US1] Replace the inline Docker Desktop check in `start-lite.bat` with a call to `runtime-detect.bat`, preserving current behaviour when Docker is present
- [ ] T018 [US1] Replace the inline Docker Desktop check in `start.bat` with the same call, keeping its `--profile local-llm` GGUF logic unchanged
- [ ] T019 [US1] **Conditional on G2 failing**: add `docker-compose.podman.yml` at repo root as an **override only** (deltas, never a full copy) carrying the `extra_hosts` remap G2 identified; if G2 passed, create no file and note that in research.md
- [ ] T020 [US1] **Conditional on G3 failing**: add the `:U` flag or `--userns=keep-id` to the podman override for the affected bind mounts — do NOT convert uploads to named volumes (that is what broke the old fork's backup path)
- [ ] T021 [US1] **Conditional on G2 failing at both the compose and remap level**: extend `_normalize_local_url()` in `app/services/llm_client.py` to try `host.containers.internal` — last resort, since this file is shared with Docker deployments

### Verification

- [ ] T022 [US1] On the Podman-only machine, run `start-lite.bat` end to end: six services healthy, `/api/ready` 200, upload a PDF, run a search (SC-001)
- [ ] T023 [US1] Verify `db`, `redis` and `adminer` are bound to `127.0.0.1` only under Podman via `docker-compose ps` / `podman port` (FR-004, SC-003)
- [ ] T024 [US1] Verify slim-mode chat reaches a host Ollama under Podman (SC-004), and that 006's dormant states behave identically (FR-006)

**Checkpoint**: MNEMOS runs on Podman. This is the MVP.

---

## Phase 4: User Story 1b — One command from nothing to running (P1)

**Goal**: A single pasteable PowerShell line takes a stock Windows 11 machine
to a working MNEMOS in the browser.

**Independent Test**: clean Windows 11 VM, paste the one-liner, end with the
browser open on working MNEMOS and no other user action.

**Depends on Phase 3** — the bootstrap's last line is the launcher.

### Implementation

- [ ] T025 [US1b] Create `install.ps1` at repo root with an idempotent step skeleton: every step checks its own postcondition first and no-ops if already satisfied (FR-011)
- [ ] T026 [US1b] In `install.ps1`, implement the WSL2 step: detect, and if absent either enable it and state that a reboot is needed, or print exactly what to enable — re-running after reboot must resume cleanly (US1b scenario 3)
- [ ] T027 [US1b] In `install.ps1`, implement the runtime step: skip entirely if `docker info` or `podman info` already succeeds, else `winget install RedHat.Podman` (US1b scenario 2)
- [ ] T028 [US1b] In `install.ps1`, implement the repo step: download the archive from GitHub and extract to a target directory — **git must not be required** (US1b scenario 1)
- [ ] T029 [US1b] In `install.ps1`, hand off to `start-lite.bat` and exit; the script must contain no runtime-detection or compose logic of its own (FR-011 — the launcher stays the single owner)
- [ ] T030 [US1b] In `install.ps1`, print what will be installed before installing it, and print honest progress for the long steps — VM image, container builds, first-index model download (FR-012)

### Verification

- [ ] T031 [US1b] On a clean Windows 11 VM with no runtime and no git, paste the one-liner and confirm it ends with the browser open on working MNEMOS (SC-001b)
- [ ] T032 [US1b] Interrupt the bootstrap at each step (Ctrl-C during WSL2, runtime install, download) and confirm re-running resumes without damage (US1b scenario 4)
- [ ] T033 [US1b] Run the bootstrap on a machine that already has Docker and confirm it skips the runtime install and reuses Docker (US1b scenario 2)

**Checkpoint**: The distribution artifact exists and is proven on a clean machine.

---

## Phase 5: User Story 2 — Docker users undisturbed (P2)

**Goal**: Existing Docker Desktop installs notice nothing.

**Independent Test**: Docker machine, run both launchers, observe identical behaviour to pre-007.

- [ ] T034 [US2] On a Docker Desktop machine, run `start.bat` and `start-lite.bat` and confirm behaviour is unchanged from before 007, including the installed-but-stopped wait loop (FR-009, SC-006)
- [ ] T035 [US2] On a machine with both runtimes, confirm Docker is selected by default per the data-safety ordering in `specs/007-podman-runtime/data-model.md`, and that `MNEMOS_RUNTIME=podman` overrides it
- [ ] T036 [US2] Confirm `MNEMOS_RUNTIME=podman` with Podman absent errors out naming the override, rather than silently falling back to Docker (contract requirement)

**Checkpoint**: No regression for the entire existing user base.

---

## Phase 6: User Story 3 — Docker→Podman data migration (P3)

**Goal**: A user can deliberately move an indexed library between runtimes.

**Independent Test**: index under Docker, follow the documented steps, serve the same library under Podman.

- [ ] T037 [US3] Verify the `pg_dump` → restore path in `specs/007-podman-runtime/quickstart.md` end to end with a real indexed library
- [ ] T038 [US3] Confirm no re-embedding occurs — vectors travel inside the dump — and that `./data/uploads` carries over untouched (US3 scenario 2)
- [ ] T039 [US3] Add the migration steps to `README.md` in both the Spanish and English halves, matching the placement convention used by the 005/006 sections

**Checkpoint**: All stories complete.

---

## Phase 7: Polish & Cross-Cutting

- [ ] T040 Delete `installer/docker-compose.podman.yml` and `installer/docker-compose.podman.test.yml` — a security fix, not tidying: they publish `db`/`redis` on all interfaces with no auth layer (FR-002, R-006)
- [ ] T041 Audit `installer/README.md` for references to the deleted forks and the obsolete Docker-only assumptions; update or remove
- [ ] T042 [P] Add the one-liner as the headline install path in `README.md` (Spanish and English), with the three-command manual path kept below it
- [ ] T043 [P] Add the G2 host-reachability one-liner to the README troubleshooting tables so "no LLM configured" and "Podman networking" are distinguishable
- [ ] T044 [P] Document the GPU-under-Podman position in `README.md`: CDI setup is manual, slim mode is the recommended path
- [ ] T045 Update `CLAUDE.md` with the runtime detection order and the data-safety rule from `data-model.md` (named volumes are runtime-bound)
- [ ] T046 Document the `DOCKER_HOST` / `TESTCONTAINERS_RYUK_DISABLED` env vars for running the suite under Podman in `specs/004-test-suite/quickstart.md` and `CLAUDE.md`
- [ ] T047 Run the full suite under Podman: `.venv\Scripts\python.exe -m pytest` and `cd frontend_spa && npm test` (FR-010, SC-005)
- [ ] T048 Confirm `git grep` shows no full-copy compose fork remains in the repo (SC-002)
- [ ] T049 Run the complete `specs/007-podman-runtime/quickstart.md` maintainer checklist end to end

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no dependencies
- **Phase 2 (Gates)**: needs Phase 1; **blocks everything else** — T009 is the gate on the gate
- **Phase 3 (US1)**: needs T009. T019/T020/T021 are conditional on specific gate failures
- **Phase 4 (US1b)**: needs Phase 3 — the bootstrap delegates to the launcher
- **Phase 5 (US2)**: needs Phase 3 (detection block exists); independent of US1b
- **Phase 6 (US3)**: needs Phase 3; independent of US1b and US2
- **Phase 7**: T040/T041/T048 can run any time after Phase 2; the rest after the stories

### Critical path

```
T001-T004 (podman up) → T005-T008 (gates) → T009 (record)
   → T012-T018 (detection block) → T022-T024 (US1 verified)
   → T025-T030 (bootstrap) → T031 (clean-VM proof)
```

### Parallel opportunities

- T005/T006/T007/T008 — four independent gates, one session
- T010/T011 — the folded-in 005 checks, alongside the gates
- T042/T043/T044 — three independent README sections
- Phases 5 and 6 can proceed in parallel once Phase 3 lands

---

## Implementation Strategy

### MVP — Phases 1-3

MNEMOS runs on Podman with no Docker Desktop. Delivers the feature's core claim
and is independently shippable even if the bootstrap slips.

### The actual goal — through Phase 4

US1b is what gets pasted into a forum post. Without it the user still runs three
commands and needs git. Phases 1-4 are the real ship target.

### Risk note

**T006 (G2) is the task most likely to change the plan.** If
`host.docker.internal` does not reach the Windows host from inside
`podman machine`, T019 and possibly T021 activate, and slim mode's LLM path
needs rework under Podman. Everything else is mechanical by comparison.

### Notes

- T019/T020/T021 are **conditional**. If the gates pass, they close as "not
  needed" with a note in research.md — their absence should read as success,
  not omission.
- Phase 7's T040 is a security fix and can be done immediately; do not let it
  wait on the gates.
- Per CLAUDE.md, never run tests against the live/dev database — the
  testcontainers fixtures provision a disposable instance under either runtime.
