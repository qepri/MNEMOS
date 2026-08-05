# Phase 0 Research: Podman Runtime Support

Unlike 006, this feature's four clarification markers are **empirical questions
about a runtime that is not installed on the dev machine**. Each decision below
is therefore split into a *working decision* (what the plan assumes) and an
*empirical gate* (the specific check that confirms or overturns it). The gates
are collected in quickstart.md as the first implementation phase — no code that
depends on a gate may be written before the gate is run.

## R-000: Evidence found on this dev machine

Checked during planning:

- `podman.exe` is **not** installed (not on PATH, not in `C:\Program Files\RedHat\Podman`).
- Yet `wsl -l -v` shows a **`podman-machine-default` distro, state Running** —
  and it is the *default* WSL distribution.
- `docker-compose` v5.0.2 (the standalone Go binary) is installed and on PATH.
- `docker-desktop` WSL distro also present and running.

Two conclusions. First, the earlier Podman attempt (the one that left
`installer/docker-compose.podman.yml`) was real, got as far as a working
machine, and was abandoned by uninstalling the CLI **without** removing the WSL
distro — so "Podman half-uninstalled, orphaned VM present" is not a
hypothetical edge case, it is the state of the primary dev machine. The
launcher must not be confused by a `podman-machine-default` distro existing
when `podman` itself is absent.

Second, the Go `docker-compose` binary being independently installed means the
compose-provider decision (R-002) has zero new installs on machines like this
one.

## R-001: Dual-runtime preference (resolves US2 marker)

**Working decision**: prefer Docker when its daemon is reachable; use Podman
otherwise. No prompt. An explicit `MNEMOS_RUNTIME=podman|docker` environment
variable (or launcher flag) overrides detection for users migrating on purpose.

**Rationale**: the sharp edge is data. Docker and Podman volumes are separate
stores — `postgres_data` under one runtime does not exist under the other. Every
existing MNEMOS install is a Docker install, so preferring Podman on a
dual-runtime machine would boot an **empty database** and the user's library
would "disappear". Preferring the runtime that owns the existing data is the
only default that cannot destroy anything. Detection order: `docker info`
succeeds → Docker; else `podman info` (starting the machine if needed) →
Podman; else the FR-003 guidance message.

`./data/uploads` and the other bind mounts are runtime-neutral — only the named
volumes (`postgres_data`, `redis_data`) are runtime-bound, which is why US3's
migration is a `pg_dump`/restore plus nothing.

**Alternatives considered**: prompt-and-remember — more state, and the answer is
derivable; prefer Podman — data loss by default; hard fork of launchers
(`start-podman.bat`) — kept as *fallback posture only* if detection proves
flaky, since two launchers is how the compose forks happened.

## R-002: Compose provider (resolves the provider marker)

**Working decision**: the standalone Go `docker-compose` binary, pointed at the
Podman socket (`DOCKER_HOST=npipe:////./pipe/podman-machine-default` on Windows,
or Podman's Docker-API compatibility socket). Explicitly **not**
`podman-compose` (the Python reimplementation).

**Rationale**: the launchers already shell out to `docker-compose`, and the
same binary drives either runtime when `DOCKER_HOST` points at the right
socket — meaning the *invocation* barely changes between runtimes, only the
environment does. `podman-compose` has documented gaps in exactly the features
005/006 rely on: `profiles:` handling and `deploy.resources` parsing — the
slim override's `devices: []` merge is the kind of corner it gets wrong.
Podman's own `podman compose` command is just a delegator to whichever
provider is installed, so pinning the provider is what actually removes
variance.

**Empirical gate G1**: `docker-compose -f docker-compose.yml -f
docker-compose.slim.yml config` and `up` against a real Podman socket — profiles
excluded by default, `--profile local-llm` included, `devices: []` override
honored, `--wait` working with healthchecks.

## R-003: `host.docker.internal` under Podman (resolves the host-gateway marker)

The single highest-risk item: slim mode's entire LLM path is
`extra_hosts: ["host.docker.internal:host-gateway"]` plus
`_normalize_local_url()` rewriting user-typed `localhost` to
`host.docker.internal` (`llm_client.py:27-30`). And a failure here renders as
006's dormant "unreachable" state — indistinguishable from the supported
no-LLM configuration unless someone checks.

**Working decision**: keep the service graph unchanged and make the Podman
override carry whatever remap is needed. Modern Podman (4.1+) accepts the
`host-gateway` special value for API compatibility, and `podman machine` on
Windows is set up so the gateway route reaches the Windows host (the same
mechanism that makes its Docker-compat mode usable). So the *expected* outcome
is that it works as-is and the override needs nothing.

**Empirical gate G2** (must run before any UI-adjacent work): from inside a
container under Podman, `curl http://host.docker.internal:11434/v1/models`
against an Ollama (or any listener) on the Windows host. If it fails, fallback
ladder: (a) `extra_hosts` remap in the podman override to the machine's gateway
IP; (b) extend `_normalize_local_url()` to also try
`host.containers.internal`. (b) touches app code shared with Docker, so (a) is
preferred.

**Diagnosability requirement** (carried into the plan regardless of G2's
outcome): the 006 availability probe already names the endpoint it failed to
reach; the Podman quickstart documents the one-liner to test host reachability
from inside a container, so "dormant because no LLM" and "dormant because
Podman networking" can be told apart in one command.

## R-004: Rootless uid mapping vs bind mounts (resolves the mounts marker)

The images run as uid 1000 (`Dockerfile:39-40,64`); `./app`, `./config`,
`./migrations`, `./data/*`, and both caches are host-owned `:rw` bind mounts.

**Working decision**: target `podman machine` on Windows first and assume its
9p/virtiofs mount path makes host bind mounts writable regardless of container
uid (file ownership is mediated by the VM's mount, not by subuid mapping the
way native Linux rootless is). Keep the bind mounts exactly as they are — do
NOT switch uploads to named volumes; that is the change that broke the old
fork's backup story.

**Rationale**: the old fork's named-volume workaround solved a Linux-rootless
problem at the cost of hiding `./data/uploads` from the user on every platform.
Windows-under-podman-machine is the target this feature ships for; native
Linux rootless is documented, not engineered around.

**Empirical gate G3**: under Podman, upload a document and confirm it lands in
`./data/uploads` on the host and that Whisper/HF caches are writable. If Linux
rootless is ever promoted to a supported target, the fix is the `:U` volume
flag or `--userns=keep-id` in the podman override — noted for that future, not
built now.

## R-005: testcontainers under Podman (resolves FR-010 marker)

**Working decision**: no fixture changes. testcontainers-python speaks the
Docker API; Podman machine exposes a Docker-compatible socket, and pointing
`DOCKER_HOST` at it (plus `TESTCONTAINERS_RYUK_DISABLED=true` if Ryuk's
privileged reaper misbehaves under rootless) is configuration, not code.
Document the two env vars in the quickstart; change `tests/conftest.py` only if
G4 proves it necessary.

**Empirical gate G4**: `pytest tests/api/test_health.py` on a Podman-only
machine with `DOCKER_HOST` set. The conftest guard rails (random port, never
5432) are runtime-agnostic already.

## R-006: Retiring the stale forks (from FR-002)

**Decision**: delete `installer/docker-compose.podman.yml` and
`docker-compose.podman.test.yml` outright; the new
`docker-compose.podman.yml` (repo root, if G1-G3 show any delta is needed at
all) is an override containing only deltas. If the gates show zero deltas
needed, ship **no** podman compose file — the best override is none.

The forks are not harmless dead files: they publish `db`/`redis` on all
interfaces with no auth layer, and anyone finding them in `installer/` might
plausibly use them. Deletion is a security fix, not tidying.

## R-007: Launcher detection shape

**Decision**: one shared detection block used by both `start.bat` and
`start-lite.bat` (`runtime-detect.bat` emitting `COMPOSE_CMD` + env), not a
third launcher. The block handles: Docker running → as today; Docker installed
but stopped → today's wait loop; else Podman on PATH → `podman machine start`
if needed, export `DOCKER_HOST`; else → FR-003 message naming both installs,
Podman presented as the terminal-only option. The R-000 orphan case (machine
distro exists, CLI gone) falls out naturally: no `podman` on PATH means the
distro is ignored and the guidance message shows.

## Summary

| ID | Question | Working decision | Gate |
|---|---|---|---|
| R-001 | Both runtimes installed | Prefer Docker (owns existing data); env override | — |
| R-002 | Compose provider | Go `docker-compose` over Podman socket; never podman-compose | G1 |
| R-003 | host.docker.internal | Expect it works; override remap as fallback; never touch shared app code first | G2 |
| R-004 | Rootless mounts | Keep bind mounts; podman-machine mediates ownership | G3 |
| R-005 | testcontainers | `DOCKER_HOST` env only, no fixture code | G4 |
| R-006 | Stale forks | Delete both; new override only if gates show a delta | — |
| R-007 | Launcher | Shared detection block, no third launcher | — |

**Sequencing consequence**: G1-G4 form Phase 1 of implementation and need one
session on a machine with Podman actually installed (`winget install
RedHat.Podman`). This dev machine is ideal — it already carries the orphaned
machine distro (R-000) that the launcher must tolerate. The unverified 005
hardware checks (006 tasks T001/T002/T006) fold into the same session.
