---

description: "Task list for LLM-Optional Mode"
---

# Tasks: LLM-Optional Mode

**Input**: Design documents from `/specs/006-llm-optional-mode/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included. The repo has an established pytest + Vitest suite, and
research finding R-000 makes a test the *first* deliverable rather than a
follow-up — the plan's premise must be disconfirmed cheaply before code is
written against it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3, or PRE/FND for prerequisite and foundational work

## Status: 41/47 complete

The six open tasks all need something the implementation session could not
provide — GPU-less hardware, or a human looking at a screen. Everything
code-shaped is done and verified by the suite (75 backend + 18 SPA passing).

| Open | Needs |
|---|---|
| T001, T002, T006 | A machine with no NVIDIA container toolkit. The fixes (T003-T005) are written from the compose-file evidence but the failure they address has not been reproduced. |
| T026 | Someone to upload a corrupt PDF and look at the sidebar badge. |
| T045, T047 | A clean machine, a stopwatch, and the `quickstart.md` walkthrough. |

---

## Phase 1: Prerequisite — Unblock slim mode (R-007)

**Purpose**: Feature 005 has two suspected defects that make 006's acceptance
criteria (SC-001, SC-006) untestable on the only hardware this feature targets.

**⚠️ BLOCKING**: These are not 006 bugs, but 006 cannot be validated without them.

- [ ] **T001** [PRE] Reproduce on a machine with no NVIDIA runtime: run
      `start-lite.bat` and record whether all six services reach healthy.
      Confirms or refutes that `driver: nvidia` reservations at
      `docker-compose.yml:48-54` and `:93-99` block startup.
- [ ] **T002** [PRE] Reproduce defect 2: `docker exec dev-app-1 printenv EMBEDDING_DEVICE`.
      Expect `cuda` (wrong) — `presets/slim.env` is overridden because compose
      `environment:` outranks `.env` in pydantic-settings.
- [X] **T003** [PRE] Create `docker-compose.slim.yml` override nulling the device
      reservations (`devices: []`) and setting `EMBEDDING_DEVICE=cpu` via
      `environment:` on `app` and `worker`. Mirror the existing
      `docker-compose.cpu.yml` pattern rather than inventing a new one.
- [X] **T004** [PRE] Update `start-lite.bat:74` to compose both files:
      `docker-compose -f docker-compose.yml -f docker-compose.slim.yml up -d --wait`
- [X] **T005** [PRE] Remove or comment the now-inert `EMBEDDING_DEVICE=cpu` line
      in `presets/slim.env` so it does not read as working configuration.
- [ ] **T006** [PRE] Re-run T001 and T002; both must now pass.
- [X] **T007** [PRE] Update `specs/005-slim-deployment-mode/quickstart.md` with the
      corrected launch command so the 005 maintainer checklist is not stale.

**Checkpoint**: Slim mode starts on GPU-less hardware. 006 work can now be validated.

---

## Phase 2: Foundational — Verify the premise, then make stage records truthful

**Purpose**: Confirm R-000 before building on it, then fix the one backend defect
every downstream decision depends on.

**⚠️ CRITICAL**: T008 gates the entire plan. If it fails, revise before proceeding.

- [X] **T008** [FND] Write `tests/tasks/test_pipeline_no_llm.py`: process a small
      document with an unreachable LLM endpoint; assert `status == 'completed'`,
      chunks persisted with embeddings, `error_message is None`.
      **If this fails, STOP** — R-000 is wrong and `plan.md` needs revision.
- [X] **T009** [FND] Change `_generate_summary_logic` (`app/tasks/processing.py:96-105`)
      to report its outcome instead of swallowing silently — return a
      success/failure result or re-raise a typed exception. Keep it non-fatal to
      the task; the goal is observability, not failure propagation.
- [X] **T010** [FND] Update `stage_summarize` (`app/tasks/pipeline.py:291-297`) to
      record `completed` or `failed` based on T009's outcome, with the error
      string, matching the shape `stage_hypergraph` already uses at `:300-309`.
      This is the load-bearing fix — today `:297` records `completed`
      unconditionally.
- [X] **T011** [P] [FND] Extend `tests/tasks/test_pipeline_no_llm.py`: assert
      `metadata_['pipeline']['summarize']['status'] == 'failed'` with no LLM, and
      `'completed'` with a working fake.
- [X] **T012** [FND] Expose the stage record on `GET /api/documents/<id>/status`
      (`app/api/documents.py:202-214`) as an additive `pipeline` key per
      `contracts/api-llm-availability.md`. **Depends on T010** — exposing it
      earlier would publish a field that lies.

**Checkpoint**: The backend can distinguish "no summary because no LLM" from
"summary generated". User story work can begin.

---

## Phase 3: User Story 1 — Index and search with no LLM (P1) 🎯 MVP

**Goal**: A user with no LLM uploads a document and searches it successfully.

**Independent Test**: Start with no LLM reachable, upload a PDF, run a search,
confirm results and a non-error document state.

### Tests

- [X] **T013** [P] [US1] Integration test in `tests/api/test_search_no_llm.py`:
      semantic and keyword search return results with no LLM configured.
      Covers FR-005.
- [X] **T014** [P] [US1] Regression test asserting a fixed query set returns
      identical results with and without an LLM available (SC-003) — proves the
      retrieval stack is untouched.

### Implementation

- [X] **T015** [US1] Verify `RAGService` construction succeeds with no reachable
      LLM. Expected to already hold — `llm_client.py:165` builds an `OpenAI`
      object with no network call — so this is a confirmation task, not new code.
- [X] **T016** [US1] Confirm no code path sets `error_message` for an absent LLM
      (FR-012 backend half). Audit `processing.py:82-93`.

**Checkpoint**: US1 complete. This is the shippable MVP — search over a private
library with zero LLM setup.

---

## Phase 4: User Story 2 — Dormant features are legible (P2)

**Goal**: Chat, graph, wiki, and summary panel explain themselves instead of
appearing broken.

**Independent Test**: With no LLM, visit each view; each shows an explanatory
state with a route to settings and no raw error.

### Tests

- [X] **T017** [P] [US2] Contract tests in `tests/api/test_llm_availability.py`
      covering every row of the contract test table in
      `contracts/api-llm-availability.md`: three states, timeout behaviour, cache
      hit/invalidation, and **no API key in any response body**.
- [X] **T018** [P] [US2] SPA test pinning the `Document['status']` union against
      the backend `status_enum` values, so R-005 cannot recur silently.

### Implementation — availability service

- [X] **T019** [US2] Create `app/services/llm_availability.py`: three-state probe
      against `{base_url}/models` with an **explicit short timeout** (mandatory —
      no LLM client sets one, so the inherited SDK default is 600s, per R-006).
      Hosted providers resolve on key presence without a live request.
- [X] **T020** [US2] Add short-TTL caching (~30s) to the probe.
- [X] **T021** [US2] Wire cache invalidation into the existing `reset_client()`
      seam (`app/api/connections.py:134`, imported at `app/api/settings.py:74`) so
      there is one invalidation point, not two that can drift.
- [X] **T022** [US2] Add `GET /api/settings/llm-availability` in
      `app/api/settings.py` per the contract. Always `200`; never `503`.

### Implementation — SPA status correctness (R-005)

- [X] **T023** [P] [US2] Fix `frontend_spa/src/app/core/models/document.model.ts:6`:
      `'failed'` → `'error'`.
- [X] **T024** [P] [US2] Fix `components/sidebar/sidebar.component.html:139`
      (`badge-error` binding).
- [X] **T025** [P] [US2] Fix `components/documents/document-item.component.ts:32,48`
      (`case 'failed':`).
- [ ] **T026** [US2] Manually confirm a genuinely failed document (upload a corrupt
      PDF) now renders an error badge — it never has, because the string never
      matched.

### Implementation — dormant states

- [X] **T027** [US2] Create `frontend_spa/src/app/services/llm-availability.service.ts`
      consuming the endpoint, exposing a signal the views can read.
- [X] **T028** [P] [US2] Chat dormant state — extend the existing
      `features/chat/components/chat-empty-state/chat-empty-state.component.ts`
      rather than adding a new component; disable input via
      `features/chat/components/chat-input/chat-input.component.ts`.
- [X] **T029** [P] [US2] Graph dormant state in
      `shared/components/graph-visualizer/graph-visualizer.component.ts` — must
      not render an empty Cytoscape canvas.
- [X] **T030** [P] [US2] Wiki dormant state in `features/wiki/wiki-index.component.ts`
      and `features/wiki/wiki-article.component.ts`.
- [X] **T031** [P] [US2] Summary panel dormant state in
      `features/library/library-document-modal/library-document-modal.component.ts`,
      driven by the `pipeline` field from T012.
- [X] **T032** [US2] Ensure `unconfigured` and `unreachable` render *different*
      messages (FR-006) — the corrective action differs.
- [X] **T033** [US2] Confirm nav entries stay visible (R-004 / FR-011); no
      conditional hiding.
- [X] **T034** [US2] Fix "Connect a model" (`shared/components/llm-dormant/llm-dormant.component.ts`)
      landing on Settings' default tab (Installed Models) instead of Chat
      Settings, where the AI Provider form actually is (FR-010). Settings tab
      state moved to a `?tab=` query param (`settings-page.component.ts`):
      read on init, written on every `switchTab`, `replaceUrl: true` so tab
      switches don't pollute browser history.

      Taken further per follow-up request: `?create=custom-connection` opens
      the tab straight onto a blank "Create New Connection" form instead of
      just the tab, since that's the field the dormant CTA actually wants
      the user at. `settings-page` reads it into `openCreateConnection`
      and passes it as an `@Input` to `SettingsChatTabComponent`, which
      forces its `LlmSelectorComponent` (`#chatSelector`) into
      `updateProvider('custom')` + `selectedConnectionId.set('new')` (so it
      lands on the *create* form even if the user already has connections)
      and scrolls the "AI Provider" panel into view. Guarded by
      `didAutoCreate` so it fires once, not on every signal change. The CTA
      link now passes `[queryParams]="{ tab: 'chat', create: 'custom-connection' }"`.

      Verified: `tsc --noEmit` clean (does not catch template-binding
      errors — see below); a *cold* `ng serve` build (killed the stale
      process actually holding the port, cleared `.angular/` cache) compiles
      clean and serves `/settings?tab=chat` at HTTP 200; the shipped
      `settings-page` chunk contains `autoCreateConnection`,
      `openCreateConnection`, `custom-connection`, `didAutoCreate` and
      `scrollIntoView` together, confirming the wiring reached the bundle,
      not just the source.

      One real finding along the way: a warm `ng serve` incremental rebuild
      threw `NG8002: Can't bind to 'autoCreateConnection'` — a template-type
      error `tsc --noEmit` cannot see, since it doesn't check Angular
      bindings — even with the correct `input()` present in source. It
      persisted across further saves and did not self-heal; only killing the
      dev-server process actually holding the port and clearing `.angular/`
      fixed it. Stale Angular incremental-build cache, not a source bug —
      but it means a green `tsc --noEmit` is not sufficient signal for a
      change touching a child component's inputs; recompiling cold and
      grepping the shipped chunk is what actually confirmed this.

      **Still not click-tested in an actual browser** — no browser-automation
      tool was available in this session (Chrome extension declined, no
      Playwright MCP configured). Someone should open
      `/settings?tab=chat&create=custom-connection` once by hand — confirm
      the connection form is visibly open and scrolled into view, not just
      present in the DOM — before calling this closed.
- [X] **T035** [US2] FR-015: "Install a local model" button in
      `shared/components/llm-selector/llm-selector.component.html`, shown
      next to "No models found. Check connection/key." only when
      `selectedProvider() === 'llamacpp'`. `installLocalModel()`
      (`llm-selector.component.ts`) gates on `window.confirm(...)` — same
      pattern already used for `handlePullGguf` and
      `handleReembedLibrary` elsewhere in Settings, no new modal component —
      then `router.navigate(['/settings'], { queryParams: { tab: 'discover' } })`
      to Discover Models, where the actual Hugging Face search + pull lives.

      This exposed a real bug in T034's tab-switching: `SettingsPage` read
      `?tab=` from `route.snapshot.queryParamMap` **once** in `ngOnInit`.
      That's correct for navigation *into* `/settings` from elsewhere (the
      dormant-state CTAs) but silently does nothing for navigation *within*
      `/settings` — Angular reuses the component instance for same-route
      navigations, so `ngOnInit` doesn't re-run, and this button (chat tab →
      discover tab, both under `/settings`) would have landed nowhere.
      Fixed by subscribing to `route.queryParamMap` for the component's
      lifetime (`takeUntilDestroyed`) instead of a one-time snapshot read.

      Verified: `tsc --noEmit` clean (doesn't catch template-binding errors,
      per T034's note). The dev server (`ng serve`) repeatedly failed to
      pick up the `llm-selector` edit into the `settings-page-component`
      chunk across three rebuilds, including two full cache-clears
      (`.angular/` and `node_modules/.vite`) — looked like a real bug at
      first. Ruled out with an independent, non-dev-server build:
      `ng build --configuration production` from a freshly cleared cache
      contains `installLocalModel` and the button text in its output
      (`chunk-WJ2V4UEJ.js`), confirming the source is correct and the dev
      server's incremental lazy-chunk splitting was the flaky part, not the
      change. **Not click-tested in a real browser**, same limitation as
      T034 — verify by hand: select llama.cpp with no models, click
      "Install a local model", confirm the dialog, confirm it lands on
      Discover Models.

**Checkpoint**: US1 + US2 both work. This is the realistic ship point.

---

## Phase 5: User Story 3 — Connect later and backfill (P3)

**Goal**: Generate summaries and concepts for already-indexed documents.

**Independent Test**: Index with no LLM, connect a provider, backfill, confirm
results appear without re-extraction or re-embedding.

### Tests

- [X] **T034** [P] [US3] Test that backfill triggers neither extraction nor
      embedding for documents that already have chunks (FR-009).
- [X] **T035** [P] [US3] Test that changing or clearing the provider preserves
      existing summaries and concepts (FR-014). This is a regression guard —
      nothing in this feature may add provider-keyed cleanup.

### Implementation

- [X] **T036** [US3] Eligibility query: `status='completed'` AND
      (`summary IS NULL` OR no `HyperEdgeMember` rows). Query only — no
      `needs_backfill` column (see data-model.md).
- [X] **T037** [US3] Backfill endpoint enqueuing the **existing**
      `generate_summary_task` (`processing.py:107`) and
      `reprocess_hypergraph_task` (`processing.py:145`). No new Celery tasks.
- [X] **T038** [US3] Endpoint returning the eligible count, so the UI can say
      "generate summaries for 20 documents" before the user commits.
- [X] **T039** [US3] SPA backfill action, surfaced after a provider becomes
      available. **Never auto-starts** (R-003) — `SummaryService` fans out to
      5 threads per document (`summary_service.py:98`) and would saturate a local
      GPU unasked.
- [X] **T040** [US3] Per-document progress in the document list (FR-008).
- [X] **T041** [US3] Partial-failure handling: successes retained, failures
      individually retryable.

**Checkpoint**: All three stories independently functional.

---

## Phase 6: Polish & Cross-Cutting

- [X] **T042** [P] README: add an "LLM-optional" section to both the Spanish and
      English halves, matching where the 005 slim-mode sections were placed
      (~line 280 and ~line 800).
- [X] **T043** [P] Update `start-lite.bat`'s no-LLM warning text — it currently
      says "Uploads and search will still work. Chat answers will fail", which
      becomes an understatement once dormant states exist.
- [X] **T044** Update `CLAUDE.md` with the LLM-optional behaviour and the
      availability endpoint, in the Health/Uploads/Workers section.
- [ ] **T045** Run the full `quickstart.md` maintainer checklist end to end.
- [X] **T046** Full regression: `.venv\Scripts\python.exe -m pytest` and
      `cd frontend_spa && npm test`.
- [ ] **T047** SC-006 timing check on a clean machine with no LLM installed:
      `start-lite.bat` → first search result in under five minutes.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Prerequisite)**: no dependencies; blocks *validation* of everything
  else, though Phase 2 coding can proceed in parallel against the test suite
- **Phase 2 (Foundational)**: T008 gates the plan; T009→T010→T012 is a strict chain
- **Phase 3 (US1)**: depends on Phase 2
- **Phase 4 (US2)**: depends on Phase 2; T031 depends on T012
- **Phase 5 (US3)**: depends on Phase 2; independent of US2
- **Phase 6**: depends on the stories being delivered

### Critical path

```
T008 (verify premise) → T009 → T010 → T012 → T031
                                    ↘ T019 → T020 → T021 → T022 → T027 → T028-T031
```

### Parallel opportunities

- T001/T002 together (both are observations)
- T013/T014 together (different test files)
- T023/T024/T025 together (three different files, one string fix each)
- T028/T029/T030/T031 together (four independent views) once T027 lands
- T034/T035 together
- T042/T043 together

---

## Implementation Strategy

### MVP — stop after Phase 3

Phases 1-3 deliver the headline claim: a private semantic search engine over
PDFs, EPUBs, audio, video, and YouTube with no GPU, no Ollama, and no API key.
Based on R-000 this is mostly *verification* rather than new code, which makes it
unusually cheap.

### Realistic ship — through Phase 4

Without US2 the MVP looks half-broken: a user who clicks "Graph" and sees an
empty canvas concludes the app is buggy, not that they have a choice. Phase 4 is
the largest surface but converts absence into an offer.

### Optional — Phase 5

US3 is P3 and the per-document retry path already exists. Ship without it if
scope pressure appears; the bulk enqueue loop is genuinely additive.

---

## Notes

- **T008 is a stop-the-line task.** It exists to disconfirm R-000 cheaply. If
  ingestion does *not* already survive without an LLM, the plan is wrong and
  Phase 2 needs rework before any UI investment.
- No schema migration anywhere in this list — that is deliberate (R-001), not an
  omission. If a task seems to need one, re-read `data-model.md` first.
- Phase 1 touches feature 005's files. Keep those commits separate and clearly
  labelled so they can be cherry-picked onto 005 if it merges first.
- Per CLAUDE.md, never run tests against the live/dev database — the existing
  testcontainers fixtures provision a disposable instance.
