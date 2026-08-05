# Implementation Plan: Prebuilt Container Images

**Branch**: `008-prebuilt-images` | **Date**: 2026-08-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-prebuilt-images/spec.md`

## Summary

Build the backend and frontend images once in GitHub Actions, publish them to
GHCR, and make the end-user install pull instead of compile — cutting install
from an observed 40+ minutes (with one mid-build death) to a download that fits
under the spec's 5-minute UI budget. Four artifacts: one workflow, one small
Dockerfile addition (a default-off build arg), one release compose override,
and a version-resolution step in `install.ps1`. The developer build-from-source
path is untouched by construction — every new mechanism is off unless a
release variable is present.

## Technical Context

**Language/Version**: GitHub Actions YAML, Dockerfile, PowerShell
(`install.ps1`), Windows batch (`start-lite.bat`). No Python/TypeScript
changes.

**Primary Dependencies**: GHCR (`ghcr.io`), the workflow-automatic
`GITHUB_TOKEN` (`packages: write`), existing two-stage `Dockerfile`, PyTorch
CPU wheel index (mechanism already proven in `.github/workflows/tests.yml`)

**Storage**: none. No schema, no data entities. The only "state" is image tags
in a registry and `MNEMOS_VERSION` in the installed `.env`.

**Testing**: empirical gates G1-G3 (local CPU-image build + size measurement;
release-tag resolution; first real workflow run). Existing suites must stay
green untouched — this feature adds no runtime code paths.

**Target Platform**: `linux/amd64` images only (spec resolution #3). Consumed
via Docker or Podman per 007's runtime detection — image provenance is
orthogonal to runtime choice, so 007's gate results remain valid.

**Project Type**: build/release infrastructure. No API, no SPA, no schema.

**Performance Goals**: UI usable < 5 min on normal broadband from a clean
machine (SC-001); registry-unreachable failure reported within seconds
(SC-006).

**Constraints**: zero compile on user machines (SC-002); dev loop byte-identical
(SC-003, achieved by default-off); CPU-only torch in the published image (spec
resolution #4); tag-locked repo+image versioning, no `:latest` (spec
resolution #2); no user-managed CI secrets (FR-010).

**Scale/Scope**: 1 new workflow, ~6 Dockerfile lines, 1 compose override
(~20 lines), ~30 lines in `install.ps1`, ~5 in `start-lite.bat`, docs.

## Constitution Check

`.specify/memory/constitution.md` is still an unfilled template (unchanged
since the 006 check). CLAUDE.md constraints applied instead:

| CLAUDE.md constraint | Compliance |
|---|---|
| Compose overrides use `!reset null`, never `[]`; verify with `config` | The release override adds keys (`image`, `pull_policy`) and clears none — but the verify-with-`config` rule applies and is a task |
| Infra ports loopback-only; no auth layer | Untouched; FR-007 makes it an explicit acceptance check on the pulled image |
| Non-root uid 1000, caches under `/home/mnemos` | The published image is built from the same Dockerfile — same user, same paths |
| Alembic-only migrations; `RUN_MIGRATIONS` only on `app` | Untouched — and tag-locking exists precisely so migrations and code can never skew |
| Either-runtime rule (`runtime-detect.bat` owns detection) | Installer gains version *resolution* only; runtime detection stays in the launcher |

**Post-Phase-1 re-check**: passing. No service graph changes, no ports, no
schema, no new launcher logic beyond one conditional flag.

## Project Structure

### Documentation (this feature)

```text
specs/008-prebuilt-images/
├── spec.md              # All four clarification markers resolved in-spec
├── plan.md              # This file
├── research.md          # R-000..R-005, gates G1-G3
├── data-model.md        # No entities — version-pinning invariant recorded
├── quickstart.md        # Release runbook + gate checklist
├── contracts/
│   └── release-artifacts.md
└── tasks.md             # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
.github/workflows/release-images.yml   # NEW — tag-triggered build+push (R-001, R-003)
Dockerfile                             # MODIFY — TORCH_INDEX build arg, default off (R-002)
docker-compose.release.yml             # NEW — image:+pull_policy override only (R-004)
install.ps1                            # MODIFY — resolve latest release tag, download that
                                       #   tag's zip, write MNEMOS_VERSION to .env (R-003)
start-lite.bat                         # MODIFY — if MNEMOS_VERSION in .env: add release
                                       #   override + --no-build (R-004)
README.md                              # MODIFY — FR-009 local-data statement; release path note
CLAUDE.md                              # MODIFY — release/versioning note
```

**Structure Decision**: no new directories beyond the workflow file's standard
location. The override file follows the 005/007 override discipline
(`docker-compose.slim.yml` precedent); the workflow follows the existing
`tests.yml` precedent. Every mechanism is gated on `MNEMOS_VERSION` being
present, so its absence — the state of every dev machine — is the unchanged
path.

## Implementation Approach

**Phase 1 — Local proof (gate G1).** Add the `TORCH_INDEX` build arg and build
the CPU image locally. Measure both sizes, verify `torch.__version__` ends in
`+cpu`, verify an embedding runs. This is the only gate runnable before the
repo is public, and it de-risks the size claim everything else rests on.
*Socket discipline from 007: do not run this while another build or the test
suite holds the same Docker/Podman pipe.*

**Phase 2 — Release artifacts.** The workflow (checkout → login with
`GITHUB_TOKEN` → build backend with `TORCH_INDEX` → build frontend → push
`:vX.Y.Z` + `:sha-<commit>` → `gh release create`), the release override, and
the torch-pin drift check (lock file vs Dockerfile RUN line).

**Phase 3 — Installer and launcher wiring.** `install.ps1`: resolve
`releases/latest` via the GitHub API with a short timeout → download that tag's
zip → write `MNEMOS_VERSION` → on API/registry failure, print the
build-from-source fallback within seconds (FR-006/SC-006). `start-lite.bat`:
the conditional override + `--no-build`.

**Phase 4 — Docs.** README (ES+EN): the FR-009 statement — pulling hosts
software, not data; offline after install — plus the release-vs-source table.
CLAUDE.md: tagging runbook pointer.

**Phase 5 — Live verification (gates G2, G3).** Needs the repo public with
Actions enabled — the owner's step, not tooling's. First tag, watch the
workflow, `releases/latest` resolution check, then the SC-001 clean-machine
timing.

## Complexity Tracking

No constitution violations. Deliberate scope notes:

| Item | Why | Simpler alternative rejected because |
|---|---|---|
| `--no-build` on the release path | SC-002's guarantee must be structural: if the pull fails, error loudly rather than silently falling into a 40-minute compile | Relying on `pull_policy` alone leaves compose free to build when the image is absent — the exact failure mode this feature exists to kill |
| Commit-SHA tag alongside the version tag | FR-004 traceability at zero marginal cost | Version tag alone breaks provenance if a tag is ever moved |
| Torch version pinned in two places (lock + Dockerfile RUN) with a CI drift check | Deterministic CPU-wheel resolution requires install-first (R-002) | Single-source via `--extra-index-url` on the lock leaves pip's CUDA-vs-CPU choice ambiguous |
