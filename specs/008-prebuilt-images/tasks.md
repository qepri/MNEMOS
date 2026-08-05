---

description: "Task list for Prebuilt Container Images"
---

# Tasks: Prebuilt Container Images

**Input**: Design documents from `/specs/008-prebuilt-images/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: No new automated tests — this feature adds no runtime code paths.
Verification is the gate checklist (G1 local, G2/G3 live) plus the existing
suites staying green untouched.

**Organization**: By user story. US1 (fast install) is the feature; US2 (dev
loop untouched) is mostly satisfied *by construction* (default-off mechanisms)
and its tasks are verification; US3 (traceability) rides inside the workflow.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Foundational — the build arg and its local gate

**Purpose**: prove the CPU image is real and small before wiring anything to it.

- [X] T001 Add the `TORCH_INDEX` build arg to `Dockerfile` (builder stage): default empty; when set, `pip install --no-cache-dir --prefix=/install --index-url "$TORCH_INDEX" torch==2.13.0` **before** the lock-file install, per research R-002 (install-first beats `--extra-index-url` ambiguity). Comment must state the pin must match `requirements.lock.txt` and why
- [ ] T002 Run gate **G1** per `specs/008-prebuilt-images/quickstart.md`: build with and without the arg, record both sizes in `specs/008-prebuilt-images/research.md`, verify `torch.__version__` ends in `+cpu`, verify `sentence_transformers` imports on the CPU image. **Socket discipline: wait until the 007 background build releases the Docker/Podman pipe — one build at a time**
- [X] T003 Verify the no-arg build is byte-compatible with today (same lock file, no new layers before the torch step that would bust dev build cache unnecessarily)

**Checkpoint**: CPU image proven; sizes recorded; everything below builds on it.

---

## Phase 2: User Story 1 — Install pulls instead of compiling (P1) 🎯 MVP

**Goal**: tag-triggered CI publishes images; the installer resolves a release
and the launcher pulls it with no compile.

**Independent Test**: clean machine, one-liner → UI usable < 5 min, install
output shows pulls only (SC-001/SC-002).

- [X] T004 [US1] Create `.github/workflows/release-images.yml`: trigger on tag push `v*` + `workflow_dispatch`; `permissions: packages: write`; login to ghcr.io with `GITHUB_TOKEN`; build backend with `TORCH_INDEX=https://download.pytorch.org/whl/cpu`; build frontend from `./frontend_spa`; push both as `:$TAG` and `:sha-<commit>`; end with `gh release create "$TAG" --generate-notes` (gate G2: `releases/latest` ignores bare tags)
- [X] T005 [US1] Add the torch-pin drift check as the workflow's first step: fail if `grep -oP 'torch==\S+' requirements.lock.txt` differs from the pin in the Dockerfile RUN line (research R-002)
- [X] T006 [P] [US1] Create `docker-compose.release.yml`: for `app`, `worker`, `mcp` → `image: ghcr.io/qepri/mnemos-backend:${MNEMOS_VERSION}` + `pull_policy: missing`; for `frontend` → `ghcr.io/qepri/mnemos-frontend:${MNEMOS_VERSION}`. Exactly two keys per service, nothing restated (contract + FR-008)
- [X] T007 [US1] Verify the triple merge: `docker-compose -f docker-compose.yml -f docker-compose.slim.yml -f docker-compose.release.yml config` with `MNEMOS_VERSION=v0.0.0` set — images resolve, db/redis/adminer stay on `127.0.0.1` (FR-007), no `build:` behaviour change for unnamed services. (Config-only — does not need the container socket)
- [X] T008 [US1] Update `install.ps1`: resolve `https://api.github.com/repos/qepri/mnemos/releases/latest` with a short timeout; on success download **that tag's** zip instead of `main` and append `MNEMOS_VERSION=<tag>` to the install's `.env` after the preset step; on failure print the build-from-source fallback and continue with `main` as today (FR-006 — degrade loudly to the current behaviour, never hang)
- [X] T009 [US1] Update `start-lite.bat`: if `.env` contains `MNEMOS_VERSION`, append `-f docker-compose.release.yml --no-build` to the compose invocation (findstr the `.env`, set a variable); absent → invocation byte-identical (SC-003 by construction). `--no-build` is the structural zero-compile guarantee: failed pull = loud error, never a silent 40-minute compile
- [X] T010 [US1] In `start-lite.bat`'s release branch, run `docker-compose ... pull` before `up` so download progress is visible (FR-012 honesty rule from 007 applies to pulls too)

**Checkpoint**: A tag would produce pullable images and the install path would
consume them. Live proof blocked on repo publicity (Phase 4).

---

## Phase 3: User Stories 2+3 — Dev loop untouched, releases traceable (P1/P2)

**Goal**: confirm the by-construction guarantees actually hold.

- [X] T011 [P] [US2] Run the existing suites untouched: `.venv\Scripts\python.exe -m pytest` and `cd frontend_spa && npm test` — zero changes expected (SC-003)
- [X] T012 [P] [US2] Confirm `docker-compose config` (base file alone, no `MNEMOS_VERSION`) is unchanged from before this feature — `git stash`-free check via config diff against `007` tree if needed
- [X] T013 [P] [US3] Confirm the workflow tags both `:vX.Y.Z` and `:sha-<commit>` and that the workflow file itself carries a comment mapping tag→commit traceability to FR-004 (reviewable now; live check in Phase 4)

---

## Phase 4: Live verification — needs the repo public (owner's step)

**⚠️ Every task here is blocked on**: repo public on GitHub, Actions enabled,
and the owner cutting the first tag. Publishing is identity-bound — not
tooling's call.

- [ ] T014 Run gate **G3**: push tag `v0.1.0`, watch the workflow complete without disk exhaustion, confirm both images in GHCR with both tag forms
- [ ] T015 One-time: set both GHCR packages to public; verify anonymous `docker pull` from a logged-out machine
- [ ] T016 Run gate **G2** live: `releases/latest` returns the tag; `install.ps1` resolves it, downloads the tag zip, writes `MNEMOS_VERSION`
- [ ] T017 SC-001 timing: clean machine, one-liner → UI open, record wall-clock; must be < 5 min with zero apt/pip in the output (SC-002)
- [ ] T018 SC-006: block ghcr.io via hosts file, run the installer, confirm it names the problem and the fallback within seconds
- [ ] T019 SC-004/SC-005: `sha-` tag digest equals version-tag digest; `torch.__version__` on the pulled image ends `+cpu`

---

## Phase 5: Polish

- [X] T020 [P] README (ES + EN): add the FR-009 statement — the registry hosts software, not data; MNEMOS runs offline after install — plus a release-vs-source row in the install section pointing GPU/dev users at build-from-source
- [X] T021 [P] Update `CLAUDE.md`: release runbook pointer (`specs/008-prebuilt-images/quickstart.md`), the `MNEMOS_VERSION` switch, and the torch-pin-in-two-places drift rule
- [ ] T022 Run the full `specs/008-prebuilt-images/quickstart.md` checklist end to end and mark gate results in `research.md`

---

## Dependencies & Execution Order

- **Phase 1**: T001 now; T002 blocked on the 007 build releasing the socket; T003 with T002
- **Phase 2**: T004-T010 need only T001 (not T002) — all writable now; T007 is config-only and runnable immediately
- **Phase 3**: T011-T013 after Phase 2 files exist
- **Phase 4**: all blocked on the owner making the repo public + first tag
- **Phase 5**: T020/T021 any time; T022 last

### Parallel opportunities

- T006 alongside T004/T005 (different files)
- T011/T012/T013 together
- T020/T021 together

### Critical path

```
T001 → T004/T005/T006 → T007/T008/T009/T010 → [repo public] → T014-T019
         (T002 G1 joins whenever the socket frees — gates the size claim,
          not the code)
```

## Implementation Strategy

Everything except T002 and Phase 4 is writable in one sitting — none of it
touches the container socket. T002 (G1) slots in the moment the 007 build
lands. Phase 4 is the owner's: make the repo public, push `v0.1.0`, and the
machinery proves itself.
