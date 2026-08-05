# Feature Specification: LLM-Optional Mode

**Feature Branch**: `006-llm-optional-mode`

**Created**: 2026-08-04

**Status**: Draft

**Input**: User description: "MNEMOS should be fully usable without any LLM configured. On first run the user uploads documents and gets extraction, chunking, embedding, semantic search and keyword search — no LLM server, no GPU, no API key. Summaries, chat answers and the concept graph/wiki are opt-in features that light up once the user connects an LLM provider in Settings. The app must clearly show which features are dormant and how to enable them, and must be able to backfill summaries and hypergraph for already-indexed documents when a provider is connected later."

## Why this feature exists

Feature `005-slim-deployment-mode` removed the *bundled* llama.cpp container. This feature removes the *requirement* for an LLM at all. The difference matters for first-run experience: today a new user must install and start an LLM server before MNEMOS does anything useful. After this feature, a new user uploads a PDF and searches it within a minute, then decides whether the graph and chat are worth connecting a provider for.

The capability is largely already present in the code — extraction, chunking, embedding, and the entire retrieval stack are LLM-free. One unguarded call and the absence of any UI affordance are what make it unavailable today.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Index and search with no LLM at all (Priority: P1)

A new user starts MNEMOS with no LLM server running and no API key configured. They upload a PDF. Processing completes. They search for a phrase from the document and get ranked, highlighted results with page references. Nothing in the interface presents this as a failure.

**Why this priority**: This is the whole feature. It converts MNEMOS from "install an LLM first" to "works immediately", which is the single biggest barrier to a stranger trying it. Every other story is an enhancement on top of a system that already delivers value here.

**Independent Test**: Start the stack with no LLM reachable, upload a PDF, run a search, confirm results return and the document is not in an error state.

**Acceptance Scenarios**:

1. **Given** no reachable LLM provider, **When** the user uploads a PDF, **Then** the document reaches a non-error terminal state and its chunks are searchable.
2. **Given** a document indexed without an LLM, **When** the user runs a semantic or keyword search, **Then** matching chunks are returned with document, page, and score.
3. **Given** no reachable LLM provider, **When** the user views the document list, **Then** no document displays an error badge or error message caused solely by the absent LLM.
4. **Given** no reachable LLM provider, **When** processing finishes, **Then** the per-stage record on the document shows summarize and hypergraph as skipped with the reason, not as failures.

---

### User Story 2 - Dormant features are legible, not broken (Priority: P2)

The same user opens the chat view, the graph view, and a document's summary panel. Each explains that it needs an LLM provider and offers a direct route to Settings. Nothing throws, spins forever, or shows a raw error.

**Why this priority**: Without this, story 1 ships a product that looks half-broken. A user who clicks "Graph" and sees an empty canvas concludes the app is buggy, not that they have a choice to make. This converts absence into an invitation.

**Independent Test**: With no LLM reachable, visit chat, graph, and a document detail page; confirm each shows an explanatory state with a link to provider settings and no console or network error surfaced to the user.

**Acceptance Scenarios**:

1. **Given** no configured LLM provider, **When** the user opens the chat view, **Then** an explanatory state appears with a route to provider settings, and the message input is disabled or clearly marked unavailable.
2. **Given** no configured LLM provider, **When** the user opens the graph view, **Then** an explanatory state appears rather than an empty graph canvas.
3. **Given** a document with no summary, **When** the user opens its detail view, **Then** the summary area explains why it is empty and offers to generate it if a provider is available.
4. **Given** a configured but unreachable provider, **When** the user sends a chat message, **Then** the failure is reported as a connection problem naming the configured endpoint, not as a generic error.

---

### User Story 3 - Connect a provider later and backfill (Priority: P3)

The user has already indexed twenty documents without an LLM. They install Ollama, connect it in Settings, and want summaries and the concept graph for the documents they already have.

**Why this priority**: This is what makes the progressive path real rather than a one-way door. It is P3 because a user can already achieve it document-by-document with the existing retry actions; this story is about making it obvious and bulk-capable.

**Independent Test**: Index documents with no LLM, connect a provider, trigger backfill, confirm summaries and concepts appear for previously-indexed documents without re-extracting or re-embedding.

**Acceptance Scenarios**:

1. **Given** documents indexed without an LLM, **When** a provider is connected and backfill is requested, **Then** summaries and hypergraph data are generated without re-running extraction or embedding.
2. **Given** a backfill in progress, **When** the user views the document list, **Then** per-document progress is visible.
3. **Given** a backfill where some documents fail, **When** it completes, **Then** successful documents keep their results and failed ones are individually retryable.

---

### Edge Cases

- Provider is configured and reachable at upload time but goes down mid-document, after embedding and before summarizing. The document must still land in the same non-error terminal state as story 1, with the summarize stage recorded as failed.
- Provider is reachable but returns an error for every request (bad API key, model not loaded). This must be distinguishable in the UI from "no provider configured" — the user's next action is different in each case.
- A user connects a provider, backfills, then disconnects it. Existing summaries and concepts must be preserved, not cleared.
- Two documents are uploaded simultaneously with no LLM. Neither should block on a connection timeout long enough to stall the worker queue.
- The reachability signal is stale: the UI says dormant but a server has just started, or vice versa. The refresh path must be defined.
- A document that genuinely failed extraction (corrupt PDF) must remain a real error, clearly distinct from a document that merely has no summary.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST complete document ingestion — extract, chunk, detect language, embed, persist — without any LLM provider configured or reachable.
- **FR-002**: System MUST record summarization and hypergraph extraction as skipped-or-failed stage outcomes without failing the overall document.
- **FR-003**: A document whose only unmet stages are LLM-dependent MUST reach [NEEDS CLARIFICATION: terminal status for an LLM-free document — reuse `completed` and rely on the existing per-stage `metadata_['pipeline']` record, or introduce a distinct status such as `indexed`? Reusing `completed` avoids touching the API serializer, the SPA status filters, and every existing status check; a distinct status is more honest but is a breaking change for any consumer that treats the status list as closed.]
- **FR-004**: System MUST expose whether LLM-dependent features are currently available, determined by [NEEDS CLARIFICATION: which signal is authoritative — deploy-time `settings.LLM_PROVIDER`, the runtime `UserPreferences` row that `LLMClient` actually resolves against, or an active reachability probe of the configured endpoint? These three disagree: slim mode ships a provider value pointing at a host endpoint that may not exist, so "a provider is configured" is not the same as "an LLM is reachable". If a probe is chosen, its cache lifetime and refresh trigger must also be specified.]
- **FR-005**: Search — semantic, keyword, and their fusion — MUST function identically whether or not an LLM is available.
- **FR-006**: System MUST distinguish "no provider configured" from "provider configured but unreachable" from "provider returned an error" in what it reports to the user, because the corrective action differs for each.
- **FR-007**: Users MUST be able to generate a summary and extract concepts for an individual already-indexed document once a provider is available.
- **FR-008**: System MUST support backfilling LLM-dependent data across multiple already-indexed documents, triggered by [NEEDS CLARIFICATION: automatically on provider connection, offered as a prompt the user accepts, or purely manual and on-demand? Automatic backfill on a large library could saturate a local LLM server for hours without the user asking for it.]
- **FR-009**: Backfill MUST NOT re-run extraction or embedding for documents that already have chunks.
- **FR-010**: Views that depend on an LLM MUST present an explanatory dormant state with a route to provider settings, rather than an empty, erroring, or indefinitely-loading view. Affected views: chat, graph, wiki, and the document summary panel.
- **FR-011**: The dormant treatment MUST be [NEEDS CLARIFICATION: in-place explanatory state with the navigation entry still visible, or navigation entries hidden entirely until a provider is connected? Visible-but-dormant advertises the capability and supports the progressive path; hidden is cleaner but makes the feature undiscoverable.]
- **FR-012**: Documents indexed without an LLM MUST NOT display as errors in any list, filter, or badge.
- **FR-013**: Ingestion MUST NOT stall on connection attempts to an absent LLM endpoint; per-attempt timeouts MUST be bounded such that a queue of documents cannot be blocked by an unreachable server.
- **FR-014**: Disconnecting or changing a provider MUST preserve previously generated summaries and concepts.
- **FR-015**: First-run guidance MUST tell the user what works now and what connecting a provider would add.
- **FR-016**: Embedding generation is NOT an LLM feature and MUST remain unconditional — it runs locally on CPU and is required for retrieval. No part of this feature may make it optional.

### Key Entities

No new persisted entities. This feature changes state transitions and presentation over existing records:

- **Document**: gains a terminal state meaning "indexed, LLM-dependent stages not run". Per-stage outcomes already have a home in existing document metadata; this feature relies on that record rather than adding columns.
- **LLM availability**: a derived, non-persisted status the API reports and the SPA reacts to. Not a stored entity — it is computed from configuration and, depending on FR-004, live reachability.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with no LLM server and no API key can go from a fresh start to a successful search result over their own uploaded document without configuring an LLM at any point.
- **SC-002**: 100% of documents uploaded with no reachable LLM reach a non-error terminal state, given valid, parseable input files.
- **SC-003**: Search result relevance for a fixed query set is identical with and without an LLM available — the retrieval stack is provably untouched by this feature.
- **SC-004**: Every LLM-dependent view reachable in the UI presents a defined dormant state; zero of them show a raw error, an empty canvas with no explanation, or an unbounded loading state.
- **SC-005**: A user who connects a provider after indexing can obtain summaries and concepts for prior documents without re-uploading or re-embedding anything.
- **SC-006**: Time from first launch to first search result, with no LLM installed, is under five minutes on a machine that already has the container runtime available.

## Assumptions

- Builds on `005-slim-deployment-mode`, which is committed on its own branch but not yet merged. This branch was created from it. Merge order matters: 005 first.
- Local CPU embedding via sentence-transformers is a hard dependency and is explicitly not in scope for removal (FR-016).
- The existing per-document summary and hypergraph retry tasks are reusable as the per-document backfill primitive; bulk backfill orchestration is the new part.
- Single-user, local-first deployment. No multi-tenancy, no per-user provider isolation.
- **Container runtime is out of scope.** Replacing Docker Desktop with Podman or a rootless daemonless runtime is a separate concern with its own verification matrix (compose compatibility, volume permissions for the non-root `mnemos` uid 1000, host networking for `host.docker.internal`). It is worth a spec of its own and is a materially better proposition *after* this feature than before it — slim mode already dropped the GPU passthrough setup that was the ugliest part of the existing installer path, and an LLM-optional MNEMOS drops it further. Bundling it here would double the scope and couple two independent risks. Recommend a follow-on `007`.
- Existing documents already in an `error` state from a previous LLM failure are not automatically repaired by this feature; whether to offer a one-time reconciliation is deferred.
