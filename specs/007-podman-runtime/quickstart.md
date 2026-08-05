# Quickstart: Podman Runtime Support

Two parts: the **gate checklist** (Phase 1 of implementation — must run before
any 007 code is written) and the **user install path** this feature will ship.

---

## Gate checklist (maintainer, one session, blocking)

Prerequisites: a Windows machine with WSL2. The primary dev machine is ideal —
it already carries the orphaned `podman-machine-default` distro (research
R-000), which is itself a required test case.

### Setup

```powershell
winget install RedHat.Podman
podman machine init      # or adopt the existing orphaned machine if offered
podman machine start
podman info              # must succeed before continuing
```

Record the Docker-compat socket path (`podman machine inspect` →
ConnectionInfo / named pipe, typically `npipe:////./pipe/docker_engine` or
`npipe:////./pipe/podman-machine-default`).

### G1 — compose provider drives Podman correctly (R-002)

```powershell
$env:DOCKER_HOST = "<socket from above>"
docker-compose -f docker-compose.yml -f docker-compose.slim.yml config --services
docker-compose -f docker-compose.yml -f docker-compose.slim.yml up -d --wait
```

- [ ] `config --services` lists the 6 default services, **no** `llamacpp`
- [ ] `--profile local-llm config --services` **includes** `llamacpp`
- [ ] `up -d --wait` reaches healthy on all services
- [ ] `docker exec dev-app-1 printenv EMBEDDING_DEVICE` → `cpu` (slim override merged)
- [ ] `/api/ready` returns 200

### G2 — host.docker.internal reaches the Windows host (R-003) ⚠ highest risk

Start any listener on the Windows host (Ollama, or `python -m http.server 11434`).

```powershell
docker exec dev-app-1 python -c "import requests; print(requests.get('http://host.docker.internal:11434', timeout=3).status_code)"
```

- [ ] Connects (any HTTP status is a pass; timeout/refused is a FAIL)
- [ ] If FAIL: retry with `host.containers.internal` — record which name works
- [ ] If FAIL: `podman machine ssh` → `ip route` — record the gateway IP and
      whether an `extra_hosts` remap to it works

**A failure here renders as 006's dormant "unreachable" state.** Whatever the
outcome, record the one-liner above in the README troubleshooting table so
"no LLM configured" and "Podman networking broken" can be told apart.

### G3 — bind mounts writable by uid 1000 (R-004)

- [ ] Upload a PDF through the UI; it appears in `./data/uploads/` on the host
- [ ] Worker logs show no `Permission denied` on `/home/mnemos/.cache/*`
- [ ] `docker exec dev-app-1 touch /app/uploads/gate-g3-probe && del data\uploads\gate-g3-probe` round-trips

### G4 — testcontainers under Podman (R-005)

```powershell
$env:DOCKER_HOST = "<socket>"
$env:TESTCONTAINERS_RYUK_DISABLED = "true"   # try without first; enable if Ryuk fails
.venv\Scripts\python.exe -m pytest tests/api/test_health.py -q
```

- [ ] Suite passes; note whether the Ryuk disable was needed

### Folded-in 005 checks (006 tasks T001/T002/T006)

With Docker Desktop fully stopped (so the GPU-less condition is approximated by
Podman's VM, which has no NVIDIA toolkit):

- [ ] `start-lite.bat` path: `up -d --wait` with the slim override succeeds
      where the base file alone fails on the `nvidia` device reservation —
      record both outcomes
- [ ] `EMBEDDING_DEVICE=cpu` inside the container (same check as G1)

### Recording results

Append a `## Gate results` section to `research.md` with date, Podman version,
and pass/fail + evidence per gate. Phase 2 starts only after that section
exists.

---

## User install path (what this feature ships)

### Fresh install, no Docker

```powershell
winget install RedHat.Podman
git clone <repo-url> mnemos
cd mnemos
start-lite.bat
```

The launcher detects Podman, creates and starts its machine (first run
downloads a small VM image — it says so), and brings up MNEMOS. Same URLs
(<http://localhost:5200>), same LLM-optional behaviour: upload and search work
immediately; chat/graph/wiki explain themselves until a model is connected.

### Already on Docker Desktop?

Nothing changes. The launcher prefers Docker when it's present, because that's
where your existing library lives.

### Deliberately moving from Docker to Podman

Your uploads carry over automatically (they live in `./data/uploads`). The
database moves by dump and restore:

```bat
:: 1. With Docker still running - dump
docker-compose exec -T db pg_dump -U mnemos_user mnemos_db > backups\migrate.sql

:: 2. Stop Docker stack, start under Podman
docker-compose down
set MNEMOS_RUNTIME=podman
start-lite.bat

:: 3. Restore into Podman's database
type backups\migrate.sql | docker-compose exec -T db psql -U mnemos_user mnemos_db
```

Embeddings travel inside the dump — nothing is re-embedded or re-uploaded.
Keep `MNEMOS_RUNTIME=podman` set (or uninstall Docker Desktop) so future
launches don't flip back.

### GPU note

The bundled llama.cpp (`--profile local-llm`) needs NVIDIA CDI setup under
Podman/WSL2, which is manual and fiddly. Slim mode (Ollama/LM Studio on the
host) is the recommended path under Podman — it needs none of that.

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Launcher says no runtime, but a `podman-machine-default` WSL distro exists | Orphaned machine from an old install — the CLI is gone. Reinstall Podman or remove the distro (`wsl --unregister podman-machine-default`). |
| Library empty after switching runtime | Volumes are runtime-bound. Your data is safe in the other runtime — see the migration steps. |
| Chat dormant under Podman but Ollama is running | Run the G2 one-liner; if it fails, this is host-gateway resolution, not 006's no-LLM state. |
| `docker-compose` not found | Install it or Podman ≥5 which bundles a compat client; the launcher will name the missing piece. |
