# Phase 1 Data Model: LLM-Optional Mode

## No new entities, no schema change

This feature adds no tables, no columns, and no migration. That is a deliberate
design outcome, not an oversight — recorded here so a future reader does not
assume it was missed.

The one change that *looked* like it needed schema is the terminal status for a
document indexed without an LLM. R-001 rejected it: `Document.status` is a
PostgreSQL ENUM (`document.py:17`), `ALTER TYPE ... ADD VALUE` has no inverse, so
the Alembic downgrade could not be written honestly. The information is already
representable in the existing `metadata_` JSONB column.

## Existing entities this feature reads and writes

### Document

| Field | Type | Role in this feature |
|---|---|---|
| `status` | ENUM(`pending`,`processing`,`completed`,`error`) | Unchanged set of values. An LLM-free document terminates at `completed` (R-001). |
| `summary` | text | Nullable. `NULL` now carries meaning: no LLM was available, or summarization failed. Distinguished via `metadata_['pipeline']`, not by the null itself. |
| `metadata_` | JSONB | Carries `pipeline` — the per-stage record. This is where LLM-optionality is actually represented. |
| `error_message` | text | Reserved for genuine failures (unparseable file). Must NOT be populated for an absent LLM. |

**Mutation rule**: `metadata_` is mutated in place, so `flag_modified(doc, "metadata_")`
is required — already handled by `record_stage` (`pipeline.py:44-56`), which is
the only writer.

### The `pipeline` stage record

Written by `record_stage`. Shape per stage:

```json
{
  "pipeline": {
    "extract":         {"status": "completed", "at": "...", "chunks": 412},
    "detect_language": {"status": "completed", "at": "...", "language": "english"},
    "embed":           {"status": "completed", "at": "...", "chunks": 412},
    "summarize":       {"status": "failed",    "at": "...", "error": "Connection refused"},
    "hypergraph":      {"status": "failed",    "at": "...", "error": "Connection refused"}
  }
}
```

`status` values in use: `completed`, `skipped`, `failed`. Only `failed` gains new
significance here.

**The defect this feature fixes**: `stage_summarize` (`pipeline.py:291-297`)
records `completed` unconditionally, because `_generate_summary_logic`
(`processing.py:102-105`) swallows the exception without reporting it. Today a
failed summary is recorded as a success. Every downstream decision — the dormant
summary panel, backfill eligibility — depends on this record being truthful, so
correcting it is the load-bearing backend change.

## Derived, non-persisted state

### LLM availability

Computed per request and cached briefly (R-002). Never stored.

| State | Meaning | User's next action |
|---|---|---|
| `unconfigured` | No provider credentials or endpoint set | Install/choose a provider |
| `unreachable` | Configured, but the endpoint does not respond | Start the server you already have |
| `available` | Configured and responding | None |

The three-way split is required by FR-006 — collapsing `unconfigured` and
`unreachable` into a single "off" would tell a user to install Ollama when Ollama
is installed but not running.

Cache invalidation reuses the existing `reset_client()` seam
(`connections.py:134`, imported at `settings.py:74`) so there is one invalidation
point rather than two that can drift.

### Backfill eligibility

A query, not a stored flag. A document is eligible when:

- `status = 'completed'`, **and**
- `summary IS NULL` (summary backfill), **or** it has no `HyperEdgeMember` rows
  (hypergraph backfill)

Derivable from existing columns and relations. No `needs_backfill` column — it
would be a denormalization that can go stale against the data it describes.

## State transitions

```
                    upload
                      │
                      ▼
                   pending
                      │  process_document_task starts
                      ▼
                 processing
                      │
        ┌─────────────┴─────────────┐
        │                           │
   extract/embed              extract fails
   succeed                    (corrupt file)
        │                           │
        ▼                           ▼
  summarize + hypergraph          error
  attempted                    (error_message set)
        │
   ┌────┴────┐
   │         │
 LLM ok   LLM absent
   │         │
   │         │  stages recorded as failed;
   │         │  document NOT failed
   └────┬────┘
        ▼
    completed
        │
        │  user connects a provider, requests backfill
        ▼
  generate_summary_task / reprocess_hypergraph_task
  (re-runs LLM stages only; never re-extracts or re-embeds — FR-009)
```

The key invariant: **an absent LLM never moves a document to `error`.** The
`error` state is reserved for failures that make the document unusable. A
document with chunks and embeddings but no summary is fully usable for search,
which is the entire premise of this feature (FR-001, FR-012).

## Preservation guarantee

FR-014 requires that disconnecting or changing a provider preserves existing
summaries and concepts. This holds without new code: `Document.summary`,
`Concept`, `HyperEdge`, and `HyperEdgeMember` are persisted rows with no
lifecycle tied to provider configuration. The requirement is therefore a
regression test, not an implementation task — nothing in this feature may add
cleanup logic keyed on provider state.
