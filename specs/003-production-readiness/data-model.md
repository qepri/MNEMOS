# Phase 1 Data Model: Production Readiness

**Feature**: `003-production-readiness` | **Date**: 2026-08-01

This feature adds almost no new data. Its data work is (a) capturing the **existing** schema as a migration baseline, (b) three small additive changes, and (c) one data migration affecting exactly one row. Everything here was verified against the live `mnemos_db`.

## Live schema inventory (baseline scope)

The baseline revision must reproduce these 17 tables exactly as they exist today:

`chunks`, `collection_documents`, `collections`, `concepts`, `conversations`, `document_sections`, `documents`, `hyper_edge_members`, `hyper_edges`, `llm_connections`, `messages`, `system_prompts`, `user_memories`, `user_preferences`, `videomix_projects`, `videomix_render_jobs`, `videomix_scripts`

Plus the `vector` extension and the two custom enums observed on `documents` (`file_type_enum`, `status_enum`).

**VideoMix tables are included in the baseline** even though VideoMix code is out of scope (HC-5). A baseline that omits them would make the next autogenerate propose dropping them — the exact destructive-diff failure mode FR-033 guards against.

### `chunks` — the protected table

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| document_id | uuid FK → documents ON DELETE CASCADE | |
| content | text NOT NULL | |
| chunk_index | integer | |
| start_time / end_time | double precision | media offsets |
| page_number | integer | |
| **embedding** | **vector(1024)** | **6,150 rows populated, zero NULL — never drop, never re-embed (HC-3)** |
| language | varchar(50) | drives FTS config choice |
| **search_vector** | **tsvector** | **6,150 rows NULL — see "FTS repair" below** |
| metadata_ | jsonb | |

Indexes to reproduce verbatim:
- `chunks_pkey` — btree(id)
- `ix_chunks_embedding` — **hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)**
- `ix_chunks_search_vector` — gin(search_vector)

The HNSW index must be declared in the baseline with its exact operator class and build parameters. If a later autogenerate sees a different definition it may propose dropping and rebuilding it — an expensive and unnecessary operation on populated vectors.

### Already-applied state to encode (not to re-apply)

The baseline reflects the database **as it is**, which means these columns are **absent** and must not appear in the baseline model (per research F3 — `phase2_strip_embeddings.sql` was applied):

- `document_sections.embedding` — gone
- `documents.summary_embedding` — gone
- `documents.summary_search_vector` — gone
- `hyper_edges.embedding` — gone

Likewise these columns **are** present (added by the startup ALTERs) and must appear in the baseline, not as later migrations:

- `user_preferences.retrieval_top_k` — integer NOT NULL DEFAULT 10
- `user_preferences.hypergraph_llm_provider` — varchar(50) DEFAULT ''
- `user_preferences.hypergraph_llm_model` — varchar(255) DEFAULT ''
- `documents.embedding_model_used` — varchar(255)

The startup ALTER blocks in `create_app()` are therefore **deleted, not converted** — the columns they create already exist and are captured by the baseline. This corrects spec FR-031's framing, which assumed they still needed applying.

Similarly the `collection_documents` backfill INSERT is **idempotent and already applied** (it runs `ON CONFLICT DO NOTHING` on every boot). It becomes a one-time data revision purely so the logic lives in migration history rather than startup, and it is a no-op against the current data.

## Changes this feature makes

### C1. `user_preferences.local_llm_model` — ADD COLUMN (additive)

Verified absent from the live table. `app/models/user_preferences.py` declares it, which is why the codebase carries the documented `getattr(db_prefs, 'local_llm_model', None)` workaround.

```
ALTER TABLE user_preferences ADD COLUMN local_llm_model VARCHAR(255)
```

Nullable, no default, no backfill. Once applied, the `getattr` workaround is removed and normal attribute access is used.

**Safety**: additive; zero risk to existing rows.

### C2. Ollama preference fallback — DATA migration (1 row)

Live audit of ollama-valued data:

| Location | Finding |
|---|---|
| `user_preferences.llm_provider` | `custom` — no action |
| `user_preferences.memory_provider` | **`ollama` — 1 row, needs migration** |
| `llm_connections.provider_type` | `openai` (1 row total) — no action |

```
UPDATE user_preferences SET memory_provider = 'llamacpp' WHERE memory_provider = 'ollama';
UPDATE user_preferences SET llm_provider   = 'llamacpp' WHERE llm_provider   = 'ollama';
UPDATE llm_connections  SET provider_type  = 'custom'   WHERE provider_type  = 'ollama';
```

All three statements are written even though only the first matches today, so the revision is correct against any database state (including the older backup, should it ever be restored).

**Downgrade**: not reversible in a meaningful sense (the original value is not recoverable per-row once overwritten). The revision's `downgrade()` is a documented no-op rather than a fake inverse.

**Runtime pairing**: code must tolerate a stray `ollama` value even before this runs (FR-022), because `RUN_MIGRATIONS` may be false. Provider resolution falls back to `llamacpp` on an unrecognized value instead of raising.

### C3. `user_preferences.ollama_num_ctx` — DROP COLUMN ⚠ DESTRUCTIVE

Live column: `integer NOT NULL DEFAULT 2048`, currently holding `2048` in the single row.

This is the one place the Ollama purge implies a destructive schema operation on a populated table. FR-033 requires such operations to be *explicitly intended and called out* — this document is that callout.

**Decision**: drop it, in its own clearly-named revision, separate from every additive change, so it can be reviewed and reverted independently. The value is a dead Ollama tuning knob (llama.cpp context is set via `LLAMACPP_NUM_CTX` in compose); no code will read it after the purge.

**Downgrade is exact and safe**: `ADD COLUMN ollama_num_ctx INTEGER NOT NULL DEFAULT 2048` restores both the column and its only value.

**Resolved (clarification 2026-08-01)**: **drop it.** The alternative of keeping it as a harmless orphan was considered and declined — the spec's "zero Ollama traces" goal wins, and the drop is exactly reversible. Recorded as FR-024.

### C4. FTS repair — TRIGGER + BACKFILL (additive, CONFIRMED IN SCOPE)

**Resolved (clarification 2026-08-01)**: confirmed in scope. Recorded as FR-035 / SC-013.


Per research F2 the trigger never existed and all 6,150 `search_vector` values are NULL, making the keyword arm of hybrid retrieval permanently empty.

Revision contents:

1. `CREATE FUNCTION update_chunk_search_vector()` — builds `to_tsvector(<config>, NEW.content)`, choosing the config from `NEW.language` with a fallback to `'simple'` for unsupported languages.
2. `CREATE TRIGGER update_chunk_search_vector BEFORE INSERT OR UPDATE OF content, language ON chunks FOR EACH ROW EXECUTE FUNCTION update_chunk_search_vector()`
3. Backfill: `UPDATE chunks SET search_vector = to_tsvector(...)` over 6,150 rows.

**Safety analysis against the hard constraints**: writes only `search_vector`; does not read, write, or invalidate `embedding`; does not drop or recreate `chunks`; does not re-embed; does not change vector dimension. Compatible with HC-2 and HC-3.

**Verification**: after backfill, `count(*) filter (where search_vector is null)` must be 0, and a keyword search through the RAG path must return results where it previously returned none. The index-time text-search config must match `rag.py::_detect_query_language`'s query-time choice, or matches will silently be empty — this pairing is the main thing to test, not the row count.

**Downgrade**: drop trigger and function, `UPDATE chunks SET search_vector = NULL`. Returns to today's state exactly.

## Non-schema state

- **Per-stage processing status** (FR-050): the resumable pipeline stages need status persisted on `Document`. `documents.metadata_` is already `jsonb` and is the natural home — storing stage state there avoids a schema change entirely and keeps the migration surface minimal. If a dedicated column is preferred later it is a trivial additive migration. Note the existing project convention: call `flag_modified(obj, "metadata_")` after in-place mutation.
- **Backup artifact**: `backups/mnemos_db_<YYYYMMDD-HHMMSS>.sql`, produced by `pg_dump`. Directory exists and is already git-ignored (`.gitignore:230`). Two dumps are present, the newest from 2026-08-01 18:58 (232 MB); the plan takes a fresh one immediately before the first migration regardless.

## Migration ordering

The revision chain, each a separate reviewable revision:

```
baseline (stamped, never executed against the live DB)
  └── 001 add user_preferences.local_llm_model          [additive]
        └── 002 collection_documents backfill            [data, no-op today]
              └── 003 ollama provider fallback           [data, 1 row]
                    └── 004 drop ollama_num_ctx          [DESTRUCTIVE — reviewed, reversible]
                          └── 005 chunks FTS trigger + backfill  [additive, confirmed in scope]
```

`flask db upgrade` against the live DB after stamping the baseline must apply 001-005 and nothing else. Verification that the baseline itself is faithful: after stamping, `flask db migrate` must produce an **empty** autogenerated revision (no operations) — that empty-diff check is the real proof the baseline matches reality, and it should be run and then discarded before writing 001.
