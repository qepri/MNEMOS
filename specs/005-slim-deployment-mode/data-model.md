# Phase 1 Data Model: Slim Deployment Mode

**Branch**: `005-slim-deployment-mode` | **Date**: 2026-08-03

## No persistent entities

This feature introduces **no database entities, no schema changes, and no Alembic migration**.

That is a deliberate design outcome, not an oversight. The spec's two "Key Entities" (*Deployment mode*, *LLM provider configuration*) are both resolved to existing, non-persistent configuration:

| Spec entity | Where it actually lives | Persistence |
|---|---|---|
| Deployment mode | Derived at request time from `settings.LLM_PROVIDER`; expressed operationally by the presence/absence of the `local-llm` compose profile | None — derived, never stored |
| LLM provider configuration | Existing `LLM_PROVIDER` + `LOCAL_LLM_BASE_URL` settings (`config/settings.py`), already read by `LLMClient` | Env vars via `.env` |

## Why deployment mode is not stored

Storing a mode flag would create two sources of truth that can disagree: a database row saying "slim" while a `llamacpp` container is in fact running, or vice versa. Deriving the mode from `settings.LLM_PROVIDER` makes contradiction structurally impossible — the same value that tells `LLMClient` where to send inference tells `/api/ready` whether to probe llama.cpp.

Note the deliberate choice **not** to read `UserPreferences.llm_provider` (the DB-backed per-user override that `LLMClient` honours). Readiness answers an infrastructure question — "did this deployment start an inference container?" — which is fixed at `docker compose up` time. A user toggling providers in the Settings UI does not start or stop containers, so keying readiness on the DB value would make readiness flap with no infrastructure change behind it. See research.md R-003.

## Existing entities touched

None. `Document`, `Chunk`, `Concept`, `HyperEdge`, `HyperEdgeMember`, `UserPreferences`, and `LLMConnection` are all read and written exactly as before.

## Vector compatibility

Explicitly preserved. `presets/slim.env` does not set `EMBEDDING_MODEL` or `EMBEDDING_DIMENSION`, so the pgvector column size and all existing embeddings remain valid when switching between slim and full mode. Only `EMBEDDING_DEVICE` (a compute-placement setting) changes. See research.md R-002.
