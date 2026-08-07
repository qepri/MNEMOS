# Installer Constitution

Rules governing `install.ps1`, `update.ps1`, the `mnemos` command shim,
`start-lite.bat`, `start.bat` and `runtime-detect.bat`.

These are not style preferences. Each one is here because breaking it either
did cost, or would cost, a user their library. The person running these
scripts is not a developer, has no backup, and cannot read a stack trace.

---

## Core Principles

### I. The user's data is not ours to risk

Uploads, the database and `.env` are the only irreplaceable things on the
machine. Every other file can be re-downloaded in minutes.

- **Never delete a directory.** Overlay new files on top; do not clear first.
- **Never write `.env` wholesale.** It holds the user's API keys and tuning.
  Rewrite the single line that must change and leave every other byte alone.
- **Back up the database before anything that can run a migration**, and print
  the backup path before proceeding, not after. Migrations run automatically
  on container start (`RUN_MIGRATIONS=true`) — by the time the app is up, the
  schema has already changed.
- `docker-compose down -v` never appears in a script. Only in documentation,
  with a warning next to it.

### II. Fail loudly, never half-way

A script that guesses is worse than one that stops.

- No silent fallbacks. If the pull fails, error — do not quietly build from
  source for 40 minutes (this is why `--no-build` is mandatory on the release
  path).
- No automatic rollback. Rollback logic runs only when things are already
  broken, is the least-tested path in the program, and can turn a recoverable
  failure into an unrecoverable one. Print the backup path and the exact
  restore command instead, and let a human decide.
- Every failure message names the next command to run. "Failed" is not a
  message; "Failed — restore with `X`" is.

### III. Nothing happens that the user did not ask for

- **No auto-update.** No update-on-start, no background checks, no "installing
  in the background". An update mutates the user's only copy of their data.
- Any destructive or irreversible step confirms first, unless the user passed
  an explicit non-interactive flag.
- No telemetry, no phone-home. The only outbound calls are: the GitHub API to
  resolve a release, and the registry to pull images. Both are visible in the
  script and both happen only during install/update.

### IV. Idempotent, resumable, re-runnable

Every step checks its own postcondition before acting. Re-running after a
crash, a reboot, or a closed terminal resumes; it does not redo and it does not
double-apply. Running an update when already current is a no-op that says so
and exits 0.

### V. One source of truth per concern

Duplication between scripts is how two copies drift into disagreement.

- Runtime selection (Docker vs Podman) lives **only** in `runtime-detect.bat`.
  No script re-implements it; they all `call` it.
- The compose invocation lives **only** in the launchers. `update.ps1` does not
  assemble its own `-f` chain to start the stack — it hands off to
  `start-lite.bat`, which already knows the release path.
- Version pinning lives **only** in `MNEMOS_VERSION` in `.env`.
- The compose overrides are deltas, never forks of the service graph. (The
  deleted `installer/docker-compose.podman.yml` is the precedent: a forked
  compose file published the database on every interface, in an app with no
  authentication layer.)

### VI. Verify the mechanism, do not reason about it

Container tooling does not behave the way reading it suggests.

- Compose **merges** sequences instead of replacing them: `devices: []` is a
  silent no-op and `!reset null` is the only thing that clears an inherited
  list. This shipped broken, twice, and was invisible until
  `docker-compose config` was actually run.
- `pip install --prefix=` is not visible to a later `pip` run, so "install the
  right thing first" silently gets overwritten. This published a 7 GB CUDA
  image on the first release attempt.
- `cmd.exe` expands `%VAR%` at parse time for a whole parenthesized block, so a
  variable set inside an `if (...)` is empty where it is used.

Therefore: **claims about behaviour are unproven until a command demonstrates
them.** A change to an installer script ships with the output of the command
that proves it, not with an argument that it should work.

### VII. Documentation states what is not automatic

A user who believes the app updates itself will not update it. The docs say
plainly: updates are manual, a backup is taken, here is where it lands, here is
how to restore it. Accuracy over reassurance — if a path is untested on a given
platform, the docs say so rather than implying coverage.

---

## Platform Scope

Windows 10/11 with WSL2 is the only supported end-user platform today, on
either Docker Desktop or Podman. macOS and Linux users are developers who clone
the repo — they are explicitly not the audience for these scripts, and the docs
must not imply they are.

## Change Process

A change to any script named above must state, in the commit body:

1. what a user loses if it is wrong, and
2. the command that was run to prove it is not.

Amendments to this document belong in the same commit as the change that
motivated them.

**Ratified**: 2026-08-07
