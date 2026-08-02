# Contract: pytest Fixture API

**Feature**: 004-test-suite

The suite's public interface is its fixture set. Test authors depend on these names and semantics; changing them breaks every test file, so they are specified here.

---

## Session-scoped

### `postgres_url` / `redis_url` → `str`
Container URLs. Depended on (directly or transitively) by everything.

**Guarantees**: containers are running and accepting connections; ports are random, never 5432/6379 on the host; both are destroyed at session end even on failure/interrupt.

### `migrated_schema` → `str`
Runs the full Alembic chain to head against `postgres_url`. Returns the head revision.

**Guarantees**: schema matches what production runs, including the `update_chunk_search_vector` trigger and pgvector indexes. Never calls `db.create_all()`.

**Fails when**: any revision errors — the failure names the offending revision (FR-009).

### `app` → `Flask`
Application built by the real `create_app()` after env vars point at the containers.

**Precondition (load-bearing)**: no test module may import `app` or `config.settings` at module scope — settings are instantiated at import time (research D4), so an early import binds the dev database URL. Import inside functions or rely on this fixture.

---

## Function-scoped

### `db_session` → `Session`
SQLAlchemy session in a nested transaction, rolled back at teardown. **Default choice for all tests.**

**Guarantees**: nothing written by a test survives it; no cross-test leakage.

### `committing_db` → `Session`
Commits for real; truncates affected tables at teardown. Use **only** when commit-time behavior is under test (e.g. asserting the `search_vector` trigger fired).

### `client` → `FlaskClient`
Test client bound to `app`, sharing `db_session`'s transaction.

### `tmp_uploads` → `Path`
Temporary upload directory; `UPLOAD_FOLDER` points here for the test's duration. Prevents tests writing into the real `uploads/`.

### `fake_llm` → `ExternalProviderFake`
Intercepts outbound LLM HTTP calls at transport level.

```
fake_llm.completion(text=..., provider="openai")   # queue a response
fake_llm.calls                                     # assert what was sent
```

**Guarantees**: `LLMClient` runs for real — provider dispatch via `PROVIDER_SPECS`, unknown-provider→llamacpp fallback, response parsing. Only the socket is faked (FR-003).

### `fake_embeddings` → `ExternalProviderFake`
Deterministic vectors of exactly `EMBEDDING_DIMENSION` (1024). Same content ⇒ same vector, so similarity assertions are stable. No `sentence-transformers` model is loaded.

### `document_factory` / `chunk_factory`
Build persisted `Document` / `Chunk` rows with sensible defaults and keyword overrides. `chunk_factory` never sets `search_vector` — that is the trigger's job.

---

## Autouse guards

### `no_external_network` (autouse)
Fails any test that opens a connection to a host that is neither a test container nor a registered fake.

**Rationale**: implements the spec edge case — a missing stub must fail loudly rather than silently pass or hang on a live provider call.

### `assert_not_dev_database` (autouse, session)
Asserts the configured database host/port is the container's. Aborts the entire run otherwise.

**Rationale**: FR-002 is a hard constraint (58 documents / 6150 chunks must survive), so it is enforced structurally, not by convention.

---

## Markers

| Marker | Meaning |
|---|---|
| `@pytest.mark.api` | Flask route tests |
| `@pytest.mark.service` | Service-layer tests |
| `@pytest.mark.pipeline` | Celery pipeline stage tests |
| `@pytest.mark.migration` | Migration chain tests (manage their own DB) |
| `@pytest.mark.slow` | Deselectable during fast local iteration |

Markers back FR-009's layer attribution and let CI jobs select subsets.

---

## Stability

`db_session`, `client`, `app`, `fake_llm`, `fake_embeddings`, and the factories are the surface test authors touch. Treat renames as breaking changes to the suite.
