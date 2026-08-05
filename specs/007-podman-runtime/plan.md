# Implementation Plan: Podman Runtime Support

**Branch**: `007-podman-runtime` | **Date**: 2026-08-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-podman-runtime/spec.md`

## Summary

Let MNEMOS run under Podman driven from the terminal, removing the Docker
Desktop requirement while keeping the single maintained compose service graph.
The working hypothesis from research is that **almost no new artifacts are
needed**: the Go `docker-compose` binary drives Podman's Docker-compatible
socket, so the deltas are launcher runtime-detection, an env var, possibly a
tiny override file, and the deletion of two dangerous stale forks. The plan is
gated: four empirical checks (G1-G4) on a real Podman install come first, and
every later task states which gate it depends on.

## Technical Context

**Language/Version**: Windows batch (launchers), YAML (compose), Python 3.11
(only if G2 forces a `_normalize_local_url` extension — avoided if possible)

**Primary Dependencies**: Podman ≥ 5.x for Windows (WSL2-backed `podman
machine`), standalone Go `docker-compose` (v5.0.2 already present on the dev
machine), existing compose files from 005/006

**Storage**: unchanged. Named volumes (`postgres_data`, `redis_data`) are
runtime-bound — the basis of the R-001 preference decision; bind mounts are
runtime-neutral

**Testing**: existing pytest/testcontainers suite pointed at the Podman socket
via `DOCKER_HOST` (G4); manual gate checklist in quickstart.md

**Target Platform**: Windows 11 + WSL2, Podman-only machines; Docker Desktop
machines must be byte-for-byte unaffected

**Project Type**: deployment/infrastructure feature — no schema, no API, no SPA
changes expected (one contingency: R-003 fallback (b) touches
`llm_client.py`, taken only if G2 fails and the override remap also fails)

**Performance Goals**: launcher detection adds no perceptible delay when Docker
is present (order: docker first, it's the common case)

**Constraints**: `db`/`redis`/`adminer` stay loopback-only under Podman (FR-004);
no full-copy compose forks (FR-002); zero behavior change for Docker users
(FR-009)

**Scale/Scope**: 2 launchers, 1 shared detection block, ≤1 override file, 2
deletions, docs. The smallest feature since 005 — if the gates pass.

## Constitution Check

`.specify/memory/constitution.md` remains an unfilled template (unchanged since
006's check). Binding constraints applied from CLAUDE.md instead:

| CLAUDE.md constraint | Compliance |
|---|---|
| Infra ports (`db`, `redis`, `adminer`) bound to `127.0.0.1` only | ENFORCED by FR-004/SC-003 — and the feature *deletes* the forks that violate it |
| Ports 5000/5200 LAN-reachable on purpose | Preserved — port mappings untouched |
| Alembic-only migrations, `RUN_MIGRATIONS` only on `app` | Untouched — service graph identical |
| Non-root uid 1000, cache paths under `/home/mnemos` | The subject of gate G3; no Dockerfile changes |
| Never test against the live dev DB | testcontainers guard rails are runtime-agnostic; G4 verifies |

**Post-Phase-1 re-check**: still passing; design adds no service, port, or
schema changes.

## Project Structure

### Documentation (this feature)

```text
specs/007-podman-runtime/
├── spec.md
├── plan.md              # This file
├── research.md          # R-000..R-007, gates G1-G4
├── data-model.md        # No entities — records why
├── quickstart.md        # Gate checklist + user install path
├── contracts/
│   └── launcher-runtime-detection.md
└── tasks.md             # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
install.ps1                   # NEW — one-command bootstrap (FR-011/FR-012):
                              #   WSL2 check → runtime install if absent →
                              #   repo download (zip, no git) → start-lite.bat.
                              #   Bootstraps and hands off; owns no launcher logic.
runtime-detect.bat            # NEW — shared detection block (R-007)
start.bat                     # MODIFY — call detection block instead of inline Docker check
start-lite.bat                # MODIFY — same
docker-compose.podman.yml     # NEW, CONTINGENT — only if G1-G3 show a needed delta
installer/docker-compose.podman.yml        # DELETE (security fix, R-006)
installer/docker-compose.podman.test.yml   # DELETE
app/services/llm_client.py    # CONTINGENT — only if G2 fails AND override remap fails
README.md                     # MODIFY — Podman install path (ES + EN), Docker→Podman migration
CLAUDE.md                     # MODIFY — runtime detection note
tests/conftest.py             # CONTINGENT — only if G4 shows DOCKER_HOST env is insufficient
```

**Structure Decision**: no new directories. The one genuinely new artifact is
`runtime-detect.bat`; everything else is modification, deletion, or contingent
on a gate result. Contingent files are listed so their *absence* after
implementation reads as "gate passed", not "forgotten".

## Implementation Approach

**Phase 1 — Gates (blocking, one session, real Podman install).**
`winget install RedHat.Podman`, `podman machine init` (or adopt the orphaned
`podman-machine-default` from R-000 — itself a test case), then run G1-G4 from
quickstart.md. Also fold in the three unverified 005 checks (006 tasks
T001/T002/T006) — same session, same hardware. Every gate records its result in
research.md before Phase 2 starts.

**Phase 2 — Launcher detection (R-007).** `runtime-detect.bat`: Docker running →
as today; Docker stopped-but-installed → existing wait loop; Podman → machine
start + `DOCKER_HOST` export; neither → FR-003 guidance. Both launchers call it.
The R-000 orphan state (machine distro, no CLI) must fall through to guidance.

**Phase 3 — Deltas the gates demanded.** Possibly nothing. Otherwise: the
podman override (G1/G2/G3 remedies), in override-only form.

**Phase 4 — Deletions and docs.** Remove both stale forks. README: Podman as
the terminal-only install path (ES + EN), explicit Docker→Podman migration
(`pg_dump` → restore; uploads carry over), GPU-under-Podman
detect-and-message note. CLAUDE.md: detection order and the R-001 data rule.

**Phase 4b — Bootstrap (`install.ps1`).** After the launcher work is proven,
because the bootstrap's last line *is* the launcher. Idempotent steps: WSL2
present (message or enable+reboot note) → runtime present (else
`winget install RedHat.Podman`) → repo present (else download the release/main
zip and extract — git must not be required) → run `start-lite.bat`. The
published one-liner (`irm <raw-url>/install.ps1 | iex`) goes in the README as
the headline install path.

**Phase 5 — Verification.** SC-001..SC-006, including the full suite under a
Podman-provided testcontainers session and the zero-change check on a Docker
machine.

## Complexity Tracking

No constitution violations. One deliberate scope note:

| Item | Why | Simpler alternative rejected because |
|---|---|---|
| Gate-first sequencing (G1-G4 before any code) | All four clarifications are empirical facts about a runtime not present on the dev machine; assuming any of them and coding ahead risks building remedies for problems that don't exist | "Assume-and-fix-later" is how the abandoned `installer/` Podman attempt produced two drifted forks with a security hole |
| Deleting (not archiving) the stale forks | They publish db/redis on all interfaces; `installer/` placement invites use | Archiving preserves a copy-pasteable security regression |
