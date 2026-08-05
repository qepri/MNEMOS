# Phase 1 Data Model: Podman Runtime Support

## No entities, no schema, no persisted state

This is a deployment feature. It touches launchers, compose invocation, and
documentation — nothing that stores data. Recorded so a future reader knows it
was considered, not skipped.

## The one data fact that shapes the design

**Named volumes are runtime-bound; bind mounts are not.**

| Data | Where it lives | Survives a runtime switch? |
|---|---|---|
| Database (vectors, documents, graph) | named volume `postgres_data` | **No** — Docker's and Podman's volume stores are separate; the other runtime boots an empty database |
| Redis (task queue, cache) | named volume `redis_data` | No — and doesn't need to; it's rebuildable state |
| Uploaded files, archives | bind mount `./data/uploads`, `./data/archive` | **Yes** — plain host directories |
| Model caches (Whisper, HF) | bind mounts under `./data/` | Yes — re-downloadable anyway |
| `.env`, presets | host files | Yes |

This asymmetry produces two of the feature's rules:

1. **R-001 (prefer Docker when both present)**: the runtime that owns
   `postgres_data` is the only one that can see the user's library. Defaulting
   to the other one makes the library "disappear" — not lost, but invisible,
   which a user cannot distinguish from lost.
2. **US3 (migration is dump/restore + nothing)**: only the database needs
   moving, via the `pg_dump`/restore path the README already documents.
   Embeddings travel inside the dump — no re-embedding, no re-upload.

## Derived, non-persisted state

**Detected runtime**: computed by `runtime-detect.bat` on every launch, exported
as `COMPOSE_CMD` / `DOCKER_HOST` for that invocation only. Deliberately not
remembered in a file: persisting it would let a stale preference point at a
runtime whose volumes no longer exist, recreating the "empty library" failure
the detection order exists to prevent. `MNEMOS_RUNTIME` (env var) is the
explicit override for users migrating on purpose.
