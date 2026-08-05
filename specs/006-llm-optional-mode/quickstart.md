# Quickstart: LLM-Optional Mode

Two audiences: the **user** walkthrough is what this feature promises; the
**maintainer** checklist is how to prove it before merging.

---

## For users — MNEMOS with no LLM

### 1. Start

```bat
start-lite.bat
```

No Ollama. No LM Studio. No API key. No GPU. The launcher will warn that it found
no LLM server — that is expected and not an error.

### 2. Upload and search

Open <http://localhost:5200>, upload a PDF, wait for processing to finish, then
search for a phrase from it. You get ranked results with page references.

This is the whole point: **your library is searchable without an LLM.**

### 3. What is dormant

Chat, the concept graph, the wiki, and document summaries need a language model.
Each shows an explanation and a link to settings rather than an empty screen.

### 4. Adding an LLM later (optional)

Install [Ollama](https://ollama.com) and pull a model:

```bash
ollama pull llama3.2
```

In MNEMOS, go to Settings → LLM Provider and point it at your server. Use
`host.docker.internal`, not `localhost` — inside a container `localhost` is the
container itself:

```
http://host.docker.internal:11434/v1
```

The dormant features activate. To generate summaries and concepts for documents
you already indexed, use the backfill action — it will not re-upload or re-embed
anything, so it is much faster than reprocessing.

You can disconnect the provider later; summaries and concepts you already
generated are kept.

---

## For maintainers — verification checklist

Ordered so the cheapest disconfirming test runs first. **Step 0 is a prerequisite
carried from feature 005 and is currently unverified.**

### Step 0 — Prerequisite: does slim mode start without a GPU? (R-007)

Two suspected defects gate everything below. On a machine with **no NVIDIA
runtime**:

```bat
start-lite.bat
```

- [ ] All six services reach healthy. If it fails with a device-driver error, the
      `driver: nvidia` reservations at `docker-compose.yml:48-54` and `:93-99`
      are blocking startup — `start-lite.bat:74` composes the base file only,
      with nothing nulling them out the way `docker-compose.cpu.yml` does.
- [ ] `docker exec dev-app-1 printenv EMBEDDING_DEVICE` prints `cpu`. If it
      prints `cuda`, `presets/slim.env` is being overridden by
      `docker-compose.yml:29`/`:75` — environment variables outrank `.env` values
      in pydantic-settings, so the preset line is inert.

**If either fails, stop.** SC-001 and SC-006 cannot be evaluated on the hardware
this feature targets until slim mode starts there.

### Step 1 — Verify the R-000 assumption before building on it

```bash
.venv\Scripts\python.exe -m pytest tests/tasks/test_pipeline_no_llm.py -v
```

- [ ] A document processed with an unreachable LLM reaches `status='completed'`
- [ ] Its chunks and embeddings are persisted
- [ ] `error_message` is `NULL`

If this fails, R-000 is wrong and the plan needs revision before any UI work.

### Step 2 — Stage records are truthful

- [ ] With no LLM, `metadata_['pipeline']['summarize']['status']` is `failed`
      (not `completed` — that is the current defect at `pipeline.py:297`)
- [ ] `metadata_['pipeline']['hypergraph']['status']` is `failed`
- [ ] With a working LLM, both record `completed`

### Step 3 — Availability endpoint

```bash
curl http://localhost:5000/api/settings/llm-availability
```

- [ ] No provider configured → `state: "unconfigured"`
- [ ] Configured, server stopped → `state: "unreachable"`, `detail` names the endpoint
- [ ] Configured, server running → `state: "available"`
- [ ] Endpoint that accepts then stalls → returns within the configured timeout,
      not the SDK's 600s default
- [ ] No API key appears in any response body, in any state
- [ ] Repeated calls within the TTL probe once; a call after `reset_client()` re-probes

### Step 4 — SPA status alignment (R-005)

- [ ] `document.model.ts` declares `'error'`, not `'failed'`
- [ ] A genuinely failed document (upload a corrupt PDF) now shows an error badge
      in the sidebar — it never did before, because the string never matched
- [ ] A test pins the SPA union against the backend `status_enum`

### Step 5 — Dormant states, with no LLM reachable

- [ ] Chat: explanatory state, input disabled or clearly marked, route to settings
- [ ] Graph: explanatory state, not an empty Cytoscape canvas
- [ ] Wiki: explanatory state
- [ ] Document summary panel: explains why it is empty
- [ ] Nav entries remain visible (R-004)
- [ ] No raw errors, stack traces, or unbounded spinners anywhere
- [ ] Configured-but-unreachable shows a *different* message than unconfigured

### Step 6 — Backfill

- [ ] Index documents with no LLM, connect a provider, run backfill
- [ ] Summaries and concepts appear
- [ ] No re-extraction or re-embedding occurs (check worker logs — FR-009)
- [ ] Per-document progress is visible
- [ ] Partial failure: successes are kept, failures are individually retryable
- [ ] Backfill never starts on its own (R-003)

### Regression — nothing about search changed

```bash
.venv\Scripts\python.exe -m pytest tests/ -v
cd frontend_spa && npm test
```

- [ ] Full suite passes
- [ ] A fixed query set returns identical results with and without an LLM
      available (SC-003). The retrieval stack must be provably untouched.
- [ ] Disconnecting a provider preserves existing summaries and concepts (FR-014)

### End-to-end (SC-006)

On a clean machine with no LLM installed, from `start-lite.bat` to a search
result over an uploaded PDF:

- [ ] Under five minutes
- [ ] Zero LLM configuration steps required

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Services fail to start with a device-driver error | Step 0 defect 1 — GPU reservations in the base compose file |
| Embedding is slow / OOMs | Step 0 defect 2 — `EMBEDDING_DEVICE` still `cuda` |
| Chat fails but availability says `available` | Probe hits `/models` but generation uses a different path — check the model name is actually loaded |
| Availability stuck on `unreachable` after starting Ollama | Cache TTL not yet expired, or `reset_client()` invalidation not wired |
| Everything dormant despite a running server | `localhost` in `LOCAL_LLM_BASE_URL` — must be `host.docker.internal` |
