# Phase 0 Research: LLM-Optional Mode

All four `[NEEDS CLARIFICATION]` markers from `spec.md` are resolved below. Two
additional findings (R-005, R-006) emerged during research and change the shape
of the work; one dependency risk (R-007) is carried from feature 005.

---

## R-000: Correction — ingestion may already survive without an LLM

**This reverses an earlier assumption and shrinks the backend work substantially.**

The assumption going in was that `stage_summarize` is an unguarded LLM call that
fails the document. It is not.

`pipeline.py:291-297` calls `summary_fn(doc.id)` with no try/except, which is
true. But the injected function is `_generate_summary_logic`
(`processing.py:65`), and that function already swallows:

```python
def _generate_summary_logic(document_id):
    from app.services.summary_service import SummaryService
    try:
        SummaryService.generate_summary(document_id)
    except Exception as e:
        logger.error(f"Failed to generate summary (wrapper): {e}")
```

`SummaryService.generate_summary` does raise (`summary_service.py:178-180`), but
the wrapper catches it. So the exception never reaches `stage_summarize`, never
reaches the handler at `processing.py:82-93`, and the document is **not** marked
`status='error'`.

`stage_hypergraph` (`pipeline.py:300-309`) is independently wrapped.

**Consequence**: the ingestion path is likely already LLM-tolerant. The real
defect is that `pipeline.py:297` then records `summarize: completed`
unconditionally — a failed summary is recorded as a success, so
`metadata_['pipeline']` lies, and nothing downstream can tell "no summary because
no LLM" from "summary generated". FR-002 is therefore mostly about making the
stage record truthful, not about adding a guard.

**Decision**: treat "ingestion completes without an LLM" as an assumption to be
*verified first*, not built. Task 1 of implementation is an integration test that
proves it. If it passes, that is FR-001 and FR-012 largely satisfied at zero cost
and the feature collapses to stage-record accuracy plus UI.

**Alternatives considered**: wrapping `stage_summarize` in try/except anyway.
Rejected — it would be dead code guarding an exception that cannot arrive, and
would obscure where the real handling lives.

---

## R-001: Terminal status for an LLM-free document (resolves FR-003)

**Decision**: reuse `completed`. Do not add a new status value.

**Rationale**: `Document.status` is a PostgreSQL ENUM, not a free-text column:

```python
# app/models/document.py:17
status = Column(Enum('pending', 'processing', 'completed', 'error', name='status_enum'),
                default='pending')
```

Adding `indexed` requires an Alembic revision doing `ALTER TYPE status_enum ADD
VALUE`. Per CLAUDE.md, Alembic is the only migration path, and `ADD VALUE` is
effectively irreversible — there is no `DROP VALUE`, so the downgrade path cannot
be written honestly. That alone disqualifies it for a presentation concern.

The information is already available without a schema change:
`metadata_['pipeline']` records per-stage outcomes (`pipeline.py:44-56`), so
"completed, summarize skipped" is fully representable today.

**Alternatives considered**:
- New `indexed` enum value — rejected: irreversible migration, breaks the SPA
  union type, and every existing `status === 'completed'` check (at least
  `documents.service.ts:20`, `document-item.component.html:3`,
  `collection-modal.component.ts:109`, `sidebar.component.html:138`) would need
  auditing to decide whether `indexed` counts as usable.
- A separate boolean column — rejected: duplicates what `metadata_['pipeline']`
  already stores.

---

## R-002: Authoritative availability signal (resolves FR-004)

**Decision**: a cached live reachability probe, invalidated on settings change.
Not the deploy-time setting, not `UserPreferences` alone.

**Rationale**: the three candidate signals genuinely disagree, and FR-006
requires distinguishing three states that only a probe can separate:

| State | `settings.LLM_PROVIDER` | `UserPreferences` | Probe |
|---|---|---|---|
| Nothing configured | says `lm_studio` (slim default) | empty | fails |
| Configured, server down | says `lm_studio` | populated | fails |
| Configured and working | says `lm_studio` | populated | succeeds |

The deploy-time setting cannot distinguish any of them — slim mode ships
`LLM_PROVIDER=lm_studio` pointing at `host.docker.internal`, whether or not
anything listens there. `UserPreferences` separates row 1 from rows 2-3 but not
2 from 3, and FR-006 needs exactly that split because the user's corrective
action differs (install a server vs. start the one you have).

Note this is a *different* decision from 005's, which keyed the `/api/ready`
llama.cpp probe on `settings.LLM_PROVIDER`. That was correct there for a
different reason: readiness must reflect deploy-time infrastructure and must not
flap when a user toggles a runtime preference. Feature availability is the
opposite — it *should* track runtime reality. Both can hold; they answer
different questions.

**Cache invalidation**: `reset_client()` already exists as the settings-change
seam and is called from `connections.py:134` and imported in `settings.py:74`.
The availability cache should be cleared from the same place, so there is one
invalidation point rather than two.

**Cache lifetime**: short TTL (order of 30s) plus explicit invalidation. Long
enough that a document list render does not fan out into probes; short enough
that starting Ollama is reflected without a page reload.

**Probe target**: the OpenAI-compatible `/models` endpoint on the resolved base
URL, with an explicit short timeout — see R-006, which is the reason the timeout
must be stated rather than inherited.

**Alternatives considered**:
- Deploy-time setting only — rejected, cannot distinguish any of the three states.
- `UserPreferences` only — rejected, cannot satisfy FR-006.
- Probe with no cache — rejected, the document list would issue one probe per
  render.

---

## R-003: Backfill trigger (resolves FR-008)

**Decision**: manual and on-demand. After a provider is connected, offer backfill
as an explicit action showing how many documents are eligible. Never start
automatically.

**Rationale**: `SummaryService.generate_summary` fans out to
`ThreadPoolExecutor(max_workers=5)` (`summary_service.py:98`) — five concurrent
LLM calls per document. Auto-backfilling a library of any size against a local
Ollama would saturate the user's GPU for an unbounded period immediately after
they connected it, without asking. That is a hostile first impression of a
feature whose entire point is user control.

**Reuse**: the per-document primitives already exist and need no new task code —
`generate_summary_task` (`processing.py:107`) and `reprocess_hypergraph_task`
(`processing.py:145`). Bulk backfill is an enqueue loop over eligible documents,
not new pipeline work. FR-009 is satisfied for free: neither task runs extraction
or embedding.

**Eligibility query**: documents with `status='completed'` and no summary, or
with no hypergraph members. Derivable without a schema change.

**Alternatives considered**:
- Automatic on provider connect — rejected per above.
- Manual per-document only — rejected as insufficient for FR-008, though it is
  the fallback if bulk orchestration slips.

---

## R-004: Dormant treatment (resolves FR-011)

**Decision**: navigation entries stay visible; each dependent view renders an
in-place explanatory state with a route to provider settings.

**Rationale**: the feature's purpose is a progressive path from "search works" to
"graph works". Hiding the graph and chat entries makes the upgrade invisible —
a user would have no way to discover that connecting a provider adds anything.
Visible-but-dormant is self-documenting and turns an absence into an offer.

**Alternatives considered**:
- Hide nav entries — rejected: undiscoverable, and re-appearing menu items are a
  disorienting UI event.
- Disable with a tooltip — rejected: tooltips are invisible on touch, and mobile
  SPA access over LAN is an explicitly supported use case per CLAUDE.md.

---

## R-005: The SPA and backend already disagree on the error status string

**Finding**: pre-existing bug, in scope because FR-012 depends on it.

Backend emits `'error'` (`document.py:17`). The SPA type declares `'failed'`:

```typescript
// frontend_spa/src/app/core/models/document.model.ts:6
status: 'pending' | 'processing' | 'completed' | 'failed';
```

and the templates test for `'failed'`:
- `sidebar.component.html:139` — `[class.badge-error]="doc.status === 'failed'"`
- `document-item.component.ts:32,48` — `case 'failed':`

The union type is a compile-time assertion over untyped JSON, so TypeScript
cannot catch the mismatch. The practical effect is that **the error badge never
renders** — no document has ever displayed as failed in the sidebar.

**Relevance**: FR-012 says documents indexed without an LLM must not display as
errors. That currently passes for the wrong reason — nothing displays as an
error. Fixing the string is a prerequisite to FR-012 being a meaningful
assertion rather than a vacuous one.

**Decision**: fix the string to `'error'` as part of this feature, and add a test
that pins the SPA union type against the backend enum so they cannot drift again.

---

## R-006: No timeouts are configured on any LLM client (relates to FR-013)

**Finding**: neither `OpenAI(...)` construction (`llm_client.py:132`, `:165`) nor
`Anthropic(...)` (`llm_client.py:56`) passes `timeout=` or `max_retries=`. The
SDK defaults apply — a 600-second request timeout with automatic retries.

**Severity, honestly stated**: lower than it first appears. The common
no-LLM case is a refused TCP connection, which fails in milliseconds, and a
failure to resolve `host.docker.internal` also fails fast. The 600s default bites
only when an endpoint accepts the connection and then stalls — a wrong-port
match, a proxy, or a loaded server. Combined with
`ThreadPoolExecutor(max_workers=5)` in the summary path and a `--pool=solo`
Celery worker, a stalled endpoint could occupy the single worker for a long time.

**Decision**: set an explicit, short connect/read timeout on the *availability
probe* (required — a probe that can block for 600s is not a probe). Setting
timeouts on the main generation clients is a real improvement but is a broader
change affecting normal chat, where long generations are legitimate. Recommend
raising it separately rather than folding it in here.

FR-013 is therefore satisfied for the probe path in this feature; the general
ingestion-timeout concern is documented and deferred.

---

## R-007: Dependency risk carried from feature 005

Two suspected defects in `005-slim-deployment-mode`, which this branch is built
on top of. Both need verification on a machine without an NVIDIA runtime, which
has not been done:

1. **GPU reservations likely block slim startup.** `start-lite.bat:74` runs
   `docker-compose -f docker-compose.yml up -d --wait` — the base file only.
   That file requests `driver: nvidia` on `app` (`docker-compose.yml:48-54`) and
   `worker` (`:93-99`). `docker-compose.cpu.yml` exists solely to null these out
   with `devices: []`, which is strong circumstantial evidence they do block
   startup without the toolkit.

2. **`presets/slim.env`'s `EMBEDDING_DEVICE=cpu` is overridden.**
   `docker-compose.yml:29` and `:75` set `EMBEDDING_DEVICE=cuda` in
   `environment:`. Pydantic-settings ranks environment variables above `.env`
   file values, so compose wins and the preset line is inert. Note that
   `docker-compose.cpu.yml` also sets this via `environment:` rather than the env
   file — consistent with that precedence.

**Impact on this feature**: if slim mode cannot start on a GPU-less machine, then
SC-006 ("first launch to first search under five minutes") is untestable and
SC-001 cannot be demonstrated on the target hardware. These are not 006 bugs, but
they gate 006's acceptance.

**Decision**: fix as a prerequisite, tracked in `tasks.md` as blocking work
before 006's own acceptance criteria can be evaluated. The likely fix mirrors the
existing pattern — a slim compose override that nulls the device reservations and
sets `EMBEDDING_DEVICE=cpu` via `environment:`, with `start-lite.bat` composing
both files.

---

## Summary of decisions

| ID | Question | Decision |
|---|---|---|
| R-000 | Does ingestion already work LLM-free? | Probably yes — verify first, don't build |
| R-001 | Terminal status | Reuse `completed`; enum change is irreversible |
| R-002 | Availability signal | Cached live probe, invalidated via `reset_client()` |
| R-003 | Backfill trigger | Manual/on-demand, reusing existing retry tasks |
| R-004 | Dormant treatment | Nav visible, in-place explanatory state |
| R-005 | SPA/backend status mismatch | Fix `'failed'` → `'error'`, pin with a test |
| R-006 | Client timeouts | Explicit timeout on probe only; defer the rest |
| R-007 | 005 defects | Fix as blocking prerequisite |
