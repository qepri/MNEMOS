# Quickstart: Slim Deployment Mode

**Branch**: `005-slim-deployment-mode` | **Date**: 2026-08-03

Draft of the user-facing instructions (FR-008). Intended to land in `README.md` and to be the path linked from the r/LocalLLaMA post.

---

## Run MNEMOS with your own LLM server

MNEMOS ships with a bundled llama.cpp container, but you probably already run Ollama or LM Studio. Slim mode skips the bundled server entirely — no second model download, no GPU required by MNEMOS itself.

### Requirements

- Docker (Desktop on Windows/macOS, or native Docker on Linux)
- An OpenAI-compatible LLM server already running on your machine:
  - **Ollama** → `http://localhost:11434/v1`
  - **LM Studio** → `http://localhost:1234/v1` (start the server from the Developer tab)

### Setup

```bash
git clone <repo-url> mnemos
cd mnemos

# Create .env from the slim preset
powershell -ExecutionPolicy Bypass -File presets/apply.ps1 -Preset slim

# Start everything except the bundled LLM server
docker compose -f docker-compose.yml -f docker-compose.slim.yml up -d
```

The slim override is **required on a machine without an NVIDIA GPU**, not
optional: the base compose file requests an `nvidia` device driver on `app` and
`worker`, which fails container creation when the toolkit is absent. The override
clears those reservations and sets `EMBEDDING_DEVICE=cpu` at the right precedence
level. `start-lite.bat` composes both files for you.

Open <http://localhost:5200>.

### Point it at your server

`presets/slim.env` defaults to Ollama. If you use LM Studio, or a non-default port, edit `.env`:

```env
LLM_PROVIDER=lm_studio
LOCAL_LLM_BASE_URL=http://host.docker.internal:1234/v1
```

`host.docker.internal` is how the container reaches a server running on your host — use it instead of `localhost`, which inside a container refers to the container itself.

> `LLM_PROVIDER=lm_studio` works for **any** OpenAI-compatible server, including Ollama, vLLM, and llama-server. The name is historical; the code path is a generic OpenAI client.

### Verify

```bash
curl http://localhost:5000/api/ready
```

Expect `200` and `"status": "ready"`. In slim mode the response has no `llamacpp` field — that's correct, there's no bundled server to report on.

Then upload a PDF in the UI and ask a question about it. If generation fails, MNEMOS could not reach your LLM server — check `LOCAL_LLM_BASE_URL` and that the server is actually running.

### Want the bundled server instead?

```bash
docker compose --profile local-llm up -d
```

This starts llama.cpp too — the original fully self-contained setup. Needs an NVIDIA GPU. Set `LLM_PROVIDER=llamacpp` in `.env` to use it.

### Notes

- **Embeddings run on CPU** in slim mode (`EMBEDDING_DEVICE=cpu`). Slower on large documents, but leaves your GPU entirely to your own LLM server.
- **Switching modes is safe.** Slim mode does not change the embedding model or dimension, so your existing documents and vectors stay valid either way.
- **Already have data?** Applying a preset only writes `.env` when one doesn't exist. To switch an existing install, edit the three keys in `.env` by hand.

---

## Verification checklist (maintainer)

Before recommending this path publicly, confirm on a clean clone:

- [ ] `docker compose config --services` omits `llamacpp`
- [ ] `docker compose --profile local-llm config --services` includes `llamacpp`
- [ ] `docker compose up -d` starts 6 services (app, worker, db, redis, mcp, frontend) and pulls no llama.cpp image
- [ ] `presets/apply.ps1 -Preset slim` produces a `.env` with the 3 slim keys and a randomized `SECRET_KEY`
- [ ] `.env` from the slim preset leaves `EMBEDDING_MODEL` / `EMBEDDING_DIMENSION` at `.env.example` values
- [ ] `/api/ready` returns 200 with no `llamacpp` key, on a machine with no GPU
- [ ] A document uploads, embeds, and answers a query against a real Ollama instance
- [ ] `docker compose --profile local-llm up -d` still behaves exactly as before (SC-004)
- [ ] `pytest tests/api/test_health.py` passes
