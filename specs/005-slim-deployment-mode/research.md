# Phase 0 Research: Slim Deployment Mode

**Branch**: `005-slim-deployment-mode` | **Date**: 2026-08-03

Three findings materially changed the approach from the original feature description. They are listed first because they invalidate parts of the initial proposal.

---

## R-001: `LLM_PROVIDER=custom` cannot work from a preset — must use `lm_studio`

**Decision**: `presets/slim.env` sets `LLM_PROVIDER=lm_studio`, **not** `custom`.

**Rationale**: The `CUSTOM` provider is connection-driven. `LLMClient._build_connection_client` (`app/services/llm_client.py:124-128`) raises outright when the provider is `CUSTOM` and no active connection row exists:

```python
if self.provider == LLMProvider.CUSTOM:
    raise ValueError(
        "LLM Provider is set to 'Custom' but no active connection is "
        "selected. Please select a connection in Settings."
    )
```

A fresh install has no `LLMConnection` rows, so a preset shipping `LLM_PROVIDER=custom` produces a hard failure on the user's first chat message — the exact opposite of the "works in 5 minutes" goal (SC-001).

By contrast `LM_STUDIO` (`llm_client.py:164-166`) is purely env-driven:

```python
self.client = OpenAI(base_url=_normalize_local_url(local_base_url), api_key="lm-studio")
```

It builds a plain OpenAI-compatible client against `LOCAL_LLM_BASE_URL` with a dummy key. Despite the name, this path works against **any** OpenAI-compatible server — Ollama's `/v1`, LM Studio, vLLM, llama-server. The provider name is a misnomer, not a constraint.

**Alternatives considered**:
- `custom` — rejected, requires DB seeding (see above). Seeding a connection row from a preset would mean a migration or startup DDL, which the project explicitly forbids (CLAUDE.md: "`app/__init__.py` performs zero DDL at startup").
- Adding a new `ollama` provider enum value — rejected as unnecessary; `lm_studio` already does exactly this job. Adding an enum member also risks the stale-value fallback path already documented for the removed `ollama` value.

**Implication**: the only knobs slim mode needs are `LLM_PROVIDER=lm_studio` and `LOCAL_LLM_BASE_URL=<user's endpoint>`.

---

## R-002: Presets change `EMBEDDING_DIMENSION` — safe only because presets are fresh-install-only

**Decision**: `presets/slim.env` sets **only** `EMBEDDING_DEVICE=cpu` plus the two LLM keys. It must **not** set `EMBEDDING_MODEL` or `EMBEDDING_DIMENSION`.

**Rationale**: Existing presets do change the embedding model and dimension (`presets/medium.env`: `bge-base-en-v1.5` / 768; `.env.example`: `all-MiniLM-L6-v2` / 384; the live dev DB per CLAUDE.md runs `bge-m3` / 1024). Changing `EMBEDDING_DIMENSION` against an existing database is destructive — it requires dropping and recreating the `chunks` table and re-embedding everything.

This is safe in practice because `presets/apply.ps1` is only invoked when no `.env` exists (`start-dev.bat:35`), i.e. first run only. But slim mode's purpose is to be the *recommended* path, which means it will be applied by people who may already have data. Keeping the embedding model/dimension out of `slim.env` means slim mode never touches vector compatibility — it only changes *where inference happens* (`cpu` vs `cuda`), which is a performance setting, not a model change.

**Alternatives considered**:
- Shipping a smaller embedding model in slim mode for CPU speed — rejected. It changes dimension, breaks existing corpora, and trades away retrieval quality for a first-run speedup. If CPU embedding proves too slow, that is a follow-up with its own migration story.

---

## R-003: `/api/ready` fix is a 2-line gate, and existing tests constrain its shape

**Decision**: Gate the existing `_llamacpp_status()` call inside the `ready()` view on the configured provider; keep `_llamacpp_status` itself unchanged and module-level.

**Rationale**: The current readiness view (`app/__init__.py:177-185`) unconditionally probes llama.cpp and ANDs it into the verdict:

```python
payload["migrations"] = _migration_status()
payload["llamacpp"] = _llamacpp_status()

ok = (payload["db"] and payload["redis"]
      and payload["migrations"]["ok"] and payload["llamacpp"]["ok"])
```

With no llamacpp container the probe raises `ConnectionError`, `ok` is False forever, and `/api/ready` returns 503 permanently while the app is fully functional.

Existing tests (`tests/api/test_health.py:41-75`) monkeypatch `app._llamacpp_status` by name. Any refactor that inlines or renames that function breaks three passing tests for no benefit. The minimal change preserves the symbol and adds a conditional around the call site.

**Source of truth for "is llamacpp in use"**: `settings.LLM_PROVIDER`, not the DB-stored user preference. Readiness answers "did this *deployment* start an inference container", which is a deploy-time compose decision that tracks the env var. The DB preference (`UserPreferences`) can be changed at runtime by a user in Settings and does not start or stop containers, so keying readiness on it would make readiness flap without any infrastructure change.

**Alternatives considered**:
- A dedicated `SLIM_MODE=true` env var — rejected as redundant state that can contradict `LLM_PROVIDER`. Deriving from the provider means the two can never disagree.
- Reporting llamacpp status but excluding it from the `ok` verdict — rejected; the probe still costs a 2s timeout on every uncached readiness call in slim mode.

---

## R-004: Compose profile is the right mechanism over a second compose file

**Decision**: Add `profiles: ["local-llm"]` to the existing `llamacpp` service in `docker-compose.yml`.

**Rationale**: Docker Compose profiles exclude a service from `docker compose up` unless explicitly requested, which is exactly the semantics needed. A service with a profile is skipped by default; `--profile local-llm` includes it. One line, one file, no duplication.

The repo already has `docker-compose.cpu.yml` as a separate-file precedent, and it demonstrates the failure mode: divergence. A second slim compose file would need to be kept in sync with every future change to `app`, `worker`, `db`, `redis`, and `mcp`.

**Alternatives considered**:
- New `docker-compose.slim.yml` — rejected, drift risk as above.
- `replicas: 0` / manual service lists — rejected, more fragile and less discoverable than the built-in feature.

**Dependency note**: services that `depends_on: llamacpp` would fail to start when the profile is inactive. Must verify no service declares that dependency; if one does, the dependency needs removing (llama.cpp readiness is already handled by the health probe, not by compose ordering).

---

## Best-practice notes

**Reaching the host from inside a container**: `host.docker.internal` resolves to the host gateway. The compose file already declares `extra_hosts: ["host.docker.internal:host-gateway"]` on the app service (`docker-compose.yml:100-101`), so this works on Linux too, not just Docker Desktop. `_normalize_local_url()` (`llm_client.py:23`) exists specifically to rewrite user-supplied localhost URLs for container use — slim mode gets this handling for free.

**Ollama's OpenAI-compatible endpoint** is served at `:11434/v1`; LM Studio's at `:1234/v1`. Both accept a dummy API key, matching the hardcoded `"lm-studio"` key.

**Embedding on CPU**: `EMBEDDING_DEVICE` accepts `auto | cpu | cuda | mps` (`.env.example:25`). `auto` already falls back to CPU when CUDA is unavailable, so slim mode's explicit `cpu` is mostly documentation — but explicit is correct here, because `auto` on a machine with a GPU that llama.cpp is *not* using would silently claim VRAM the user expected to keep for their own Ollama instance.

---

## Resolved unknowns

| Unknown from Technical Context | Resolution |
|--------------------------------|------------|
| Which provider value for BYO endpoint | `lm_studio` (R-001) |
| Which env var carries the endpoint | `LOCAL_LLM_BASE_URL` |
| Whether slim changes embeddings | Device only, never model/dimension (R-002) |
| How readiness knows the mode | Derived from `settings.LLM_PROVIDER` (R-003) |
| Compose mechanism | `profiles:` on existing service (R-004) |

No NEEDS CLARIFICATION markers remain.
