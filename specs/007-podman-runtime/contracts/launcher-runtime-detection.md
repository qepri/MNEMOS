# Contract: Launcher Runtime Detection

## `runtime-detect.bat`

Shared block called by `start.bat` and `start-lite.bat` before any compose
command. One detection implementation, two consumers — the compose forks
happened because this rule wasn't followed for YAML; it applies to launchers
too.

### Inputs

| Input | Source | Meaning |
|---|---|---|
| `MNEMOS_RUNTIME` | env var, optional | `docker` or `podman` — skip detection, use this runtime or fail loudly. For deliberate migrations. |

### Outputs (environment for the calling script)

| Variable | Value |
|---|---|
| `MNEMOS_DETECTED_RUNTIME` | `docker` \| `podman` |
| `DOCKER_HOST` | set only for podman (its Docker-compat socket); left untouched for docker |
| errorlevel | `0` on success; `1` when no runtime is usable (caller prints nothing extra — the block has already explained) |

The compose invocation itself does not change: both runtimes are driven by the
same `docker-compose` binary, differing only in `DOCKER_HOST`.

### Detection order (R-001 — data safety, not preference)

```
1. MNEMOS_RUNTIME set?          → use it; if unusable, error out explaining why
                                  (never silently fall through: the user made
                                  an explicit choice about where their data is)
2. docker info succeeds?        → docker  (owns every existing install's volumes)
3. Docker Desktop installed
   but not running?             → today's launch-and-wait loop, then docker
4. podman on PATH?              → podman machine start if needed, export
                                  DOCKER_HOST, then podman
5. none of the above            → guidance message, exit 1
```

Docker outranks Podman **because named volumes are runtime-bound**: on a
dual-runtime machine, preferring Podman boots an empty database and the user's
indexed library "disappears". Not a style choice — do not reorder.

### Required behaviours

| Situation | Required outcome |
|---|---|
| Docker running | Identical to today, zero added latency beyond one `docker info` |
| Docker installed, stopped | Existing wait loop (unchanged behaviour) |
| Podman only, machine stopped | `podman machine start`, wait until `podman info` succeeds, proceed |
| Podman only, no machine yet | `podman machine init` + start, with progress messages (first init downloads a VM image — say so) |
| **Orphaned machine distro** (WSL `podman-machine-default` exists, `podman` not on PATH) | Fall through to guidance (step 5). Must NOT attempt to use the distro. This is a real state — the primary dev machine is in it (research R-000). |
| Neither runtime | Guidance naming both options, Podman presented as the terminal-only path with its install command, exit 1 |
| `MNEMOS_RUNTIME=podman`, podman absent | Error naming the override and what's missing; do NOT fall back to docker |

### Guidance message (step 5) — required content

- MNEMOS needs a container runtime; two options.
- **Podman** (lighter, no GUI): `winget install RedHat.Podman`, then rerun.
- **Docker Desktop** (GUI): the download URL used by today's launchers.
- Which one the user picks changes nothing about MNEMOS's behaviour.

### Non-goals

- No persisted runtime preference (see data-model.md — a stale preference can
  point at a runtime whose volumes don't exist).
- No automatic data migration between runtimes; US3 is documented and manual.
- No `podman-compose`/`podman compose` invocation — provider is pinned (R-002).

### Verification

| Check | Expected |
|---|---|
| Docker machine, run both launchers | Behaviour identical to pre-007 (SC-006) |
| Podman-only machine, machine stopped | Launcher starts it and reaches `/api/ready` 200 (SC-001) |
| Orphan-distro machine, no podman CLI | Guidance message, exit 1, no crash |
| `MNEMOS_RUNTIME=podman` on dual-runtime machine | Podman used despite Docker running |
| Neither runtime | Guidance message names both installs |
