# Quickstart: Prebuilt Container Images

Two parts: the **gate checklist** (before/while implementing) and the
**release runbook** (what the maintainer does per release, forever).

---

## Gate checklist (maintainer)

### G1 — CPU image builds, is small, and works (local, runnable now)

*Socket discipline from 007: nothing else may use the Docker/Podman pipe while
this builds — the 007 build was killed by a concurrent pytest run.*

```powershell
# CUDA baseline (today's behaviour, no arg):
docker-compose build app
docker image ls mnemos-backend   # record size

# CPU variant:
docker build --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cpu -t mnemos-backend:cpu .
docker image ls mnemos-backend   # record size
docker run --rm mnemos-backend:cpu python -c "import torch; print(torch.__version__)"
```

- [ ] CPU build succeeds from the unchanged lock file
- [ ] torch version ends in `+cpu`
- [ ] Size drop recorded (expected: roughly 6-8 GB → 2-3 GB)
- [ ] A quick embed works on the CPU image:
      `docker run --rm mnemos-backend:cpu python -c "from sentence_transformers import SentenceTransformer"` imports cleanly
- [ ] Plain `docker-compose build` (no arg) still produces the CUDA image —
      the dev path is untouched

### G2 — release resolution (needs the repo public)

- [ ] `gh release create` (or the workflow's release step) produces a Release
      object, and `https://api.github.com/repos/<owner>/<repo>/releases/latest`
      returns the tag — bare git tags do NOT appear here
- [ ] `install.ps1` resolves it, downloads the tag zip, writes `MNEMOS_VERSION`

### G3 — first real workflow run (needs the repo public + Actions)

- [ ] Workflow completes on the standard runner without disk exhaustion
      (CPU-only torch should fit; if not, add the free-disk-space step)
- [ ] Both images appear in GHCR with `vX.Y.Z` and `sha-<commit>` tags
- [ ] Package visibility set to **public** (one-time, in GHCR package settings)
- [ ] Anonymous `docker pull` works from a machine with no GitHub login

### End-to-end (SC-001)

- [ ] Clean machine, one-liner → UI open: **under 5 minutes**, zero apt/pip in
      the output
- [ ] First PDF upload → model downloads inside the processing UX → search works
- [ ] `docker-compose -f docker-compose.yml -f docker-compose.slim.yml -f
      docker-compose.release.yml config` verified before the tag (the rule that
      caught the `devices: []` no-op)
- [ ] With ghcr.io blocked (hosts file), the installer names the problem and
      the build-from-source fallback within seconds (SC-006)

---

## Release runbook (per release)

```powershell
# 1. Make sure main is green and the compose config check passes
docker-compose -f docker-compose.yml -f docker-compose.slim.yml -f docker-compose.release.yml config > $null

# 2. Tag and push - this IS the release trigger
git tag v0.1.0
git push origin v0.1.0

# 3. Watch the workflow (builds both images, pushes to GHCR, creates the Release)
gh run watch

# 4. Verify the artifacts
docker pull ghcr.io/<owner>/mnemos-backend:v0.1.0
docker run --rm ghcr.io/<owner>/mnemos-backend:v0.1.0 python -c "import torch; print(torch.__version__)"
```

First release only: set both GHCR packages to **public** in the package
settings, or anonymous pulls fail with an auth error that looks like a network
problem.

What users get from then on: `irm .../install.ps1 | iex` resolves the newest
release, downloads that tag's zip and images, and never sees a compiler.

---

## What did NOT change

- Dev loop: `docker-compose up -d --build`, dev/cpu/slim overrides, bind-mounted
  `app/` — all byte-identical. No `MNEMOS_VERSION` in your `.env` means no
  release machinery runs.
- Data locality: the registry hosts software, not data. Documents, database,
  embeddings, queries never leave the machine; the stack runs offline once
  pulled (FR-009).
- Security posture: same Dockerfile, same uid 1000, same loopback-only infra
  ports.
