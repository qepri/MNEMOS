# Feature Specification: RAG Refactor, Dead-Route Audit & Search Error State

**Feature Branch**: `009-refactor-ragservice-query`

**Created**: 2026-09-10

**Status**: Draft

**Input**: User description: "Three focused maintainability and correctness improvements to MNEMOS: (1) decompose the RAGService.query god-method and fix its O(n²) token-budget trimming loop without changing behavior; (2) audit and clean up stale/dead API routes and retired-provider remnants, keeping the MCP/swagger/README mirrors in sync; (3) fix the Search page swallowing request errors so a failed search no longer looks identical to an empty library."

## Overview

This is a **maintainability and correctness** effort, not a new-feature effort. It bundles three independent, low-risk improvements to existing MNEMOS behavior. Each can ship on its own. No new user-facing capabilities, endpoints, or UX redesigns are introduced.

**Explicitly out of scope**: authentication / the no-auth LAN-exposed posture (deferred to a separate spec); any new features or endpoints; broad test-coverage expansion beyond the paths touched here.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A failed search is visibly distinct from an empty library (Priority: P1)

A user searches their library from the Search page. When the request fails (backend down, network error, server error), the page tells them the search failed and invites them to retry — instead of showing "No matching passages found.", which today is indistinguishable from a genuinely empty result.

**Why this priority**: This is the only item with a directly user-visible correctness defect. A user cannot currently tell "your search broke" from "nothing matched," which erodes trust and causes people to wrongly conclude their library is empty or their query is bad. Smallest change, highest immediate user value.

**Independent Test**: Force the search request to fail and confirm the page shows a distinct error state; run a query that legitimately returns zero results and confirm it still shows the empty-state message; run a query that returns results and confirm they render. All three are observable without touching items 2 or 3.

**Acceptance Scenarios**:

1. **Given** a working library, **When** a search returns one or more passages, **Then** the results list renders and the header reports the passage count.
2. **Given** a working library, **When** a search returns zero matches, **Then** the page shows the "No matching passages found." empty state (unchanged).
3. **Given** the search request fails (network/server error), **When** the user submits a query, **Then** the page shows a distinct error message (e.g. "Search failed — please try again") and does **not** show the empty-results message.
4. **Given** a prior error state is displayed, **When** the user submits a new successful search, **Then** the error state clears and results (or a genuine empty state) render.

---

### User Story 2 - The RAG answer path is maintainable and does not degrade on large queries (Priority: P2)

A developer maintaining MNEMOS opens the RAG query path to fix a bug or add a capability and finds a readable orchestrator delegating to well-named steps, rather than a single 200-line method. A user asking a question over many/large documents gets the same answer as before, without the answer path doing needless repeated work to fit the model's context window.

**Why this priority**: Highest-risk code in the app and where future bugs hide, but the change is behavior-preserving so it delivers no new user-visible capability — value is in maintainability plus removing a quadratic slowdown on over-budget queries. Ranked below the user-visible defect.

**Independent Test**: Run the existing RAG behavior with a fixed set of inputs before and after the refactor and confirm identical retrieval sets, prompts, sources, and answers. Separately, exercise the budget-fitting step with an over-budget input and confirm it selects the same chunks as the old loop would have, without rebuilding the full prompt once per dropped chunk.

**Acceptance Scenarios**:

1. **Given** identical inputs (question, selected documents, history, options), **When** the RAG query runs before vs. after the refactor, **Then** the produced retrieval set, final prompt text, sources list, and answer are identical.
2. **Given** a query whose assembled context exceeds the model's token budget, **When** the answer path trims context to fit, **Then** the resulting set of retained chunks matches what the previous trim logic would have retained.
3. **Given** the same over-budget query, **When** trimming runs, **Then** the full prompt string is assembled at most a small constant number of times (not once per dropped chunk).
4. **Given** the public entry point to RAG querying, **When** callers invoke it, **Then** its call signature and return shape are unchanged.

---

### User Story 3 - The API surface has no confirmed dead routes, and its mirrors agree (Priority: P3)

A developer surveying the backend API can trust that every exposed route is reachable and used, that retired-provider remnants are gone, and that the three hand-maintained mirrors (MCP tools, `swagger.json`, README) match the live routes.

**Why this priority**: Reduces long-term maintenance tax but has no user-visible effect and carries the most judgment/risk (deleting a route that turns out to be used). Lowest priority; must be conservative.

**Independent Test**: Produce an inventory of backend routes annotated with whether each is referenced by the frontend, MCP tools, or tests. For each route confirmed unused, confirm its removal leaves the app, MCP tools, swagger, and README internally consistent; for each ambiguous route, confirm it is flagged and retained with a documented reason.

**Acceptance Scenarios**:

1. **Given** the set of backend routes, **When** the audit runs, **Then** each route is classified as used, unused, or ambiguous, with the evidence for its classification recorded.
2. **Given** a route confirmed unused (including retired-provider remnants), **When** it is removed, **Then** the corresponding MCP tool entry (if any), `swagger.json` path entry, and both language halves of the README are updated in the same change.
3. **Given** a route whose usage cannot be confirmed (e.g. reached only via a string-built URL or an external caller), **When** the audit completes, **Then** it is retained and documented rather than deleted.
4. **Given** the audit is complete, **When** the app and its MCP tools start, **Then** they operate exactly as before aside from the removed dead routes.

---

### Edge Cases

- **Search:** request fails *after* a previous successful search — the stale results must not remain alongside an error, and the error must supersede any prior empty/results state.
- **Search:** an empty/whitespace query is already blocked by the disabled submit button; behavior there is unchanged.
- **RAG:** a query with no documents selected (vanilla chat) or with images present must still bypass the "no context" abort exactly as today.
- **RAG:** trimming must never remove non-chunk context (conversation history, system prompt, web results) — only retrieved chunks, matching current behavior.
- **RAG:** an already-under-budget query must not trigger any trimming work.
- **Audit:** a route that appears orphaned in a static graph but is actually invoked via a dynamically constructed URL must be treated as ambiguous, not dead.

## Requirements *(mandatory)*

### Functional Requirements

**Search error state (Item 3)**

- **FR-001**: The Search page MUST render a distinct, human-readable error state when a search request fails, separate from the zero-results empty state.
- **FR-002**: The Search page MUST continue to show the existing empty state ("No matching passages found.") only when a request succeeds and returns zero results.
- **FR-003**: The Search page MUST clear any displayed error state when a subsequent search is submitted, and reflect the new outcome (results, empty, or error).
- **FR-004**: The existing loading and results states MUST remain unchanged; only the failure path is altered.
- **FR-005**: Automated frontend tests MUST cover all three outcomes of a search: results returned, genuine empty result, and request failure.

**RAG query decomposition (Item 1)**

- **FR-006**: The RAG query flow MUST be reorganized so its entry point reads as an orchestrator delegating to cohesive, individually understandable steps (retrieval, context/prompt building, budget fitting, generation).
- **FR-007**: The behavior of the RAG query flow MUST remain identical for identical inputs: the same retrieval set, the same final prompt, the same sources, and the same answer.
- **FR-008**: The public entry point's call signature and return shape MUST remain unchanged.
- **FR-009**: The context-trimming step MUST reduce retrieved chunks to fit the model's token budget without re-assembling the entire prompt once per dropped chunk; the full prompt MAY be assembled only a small constant number of times.
- **FR-010**: The set of chunks retained after trimming MUST match the set the previous trim logic would have retained for the same input.
- **FR-011**: Trimming MUST affect only retrieved chunks and MUST leave conversation history, system prompt, and web-search context intact, as today.
- **FR-012**: Automated tests MUST cover the extracted budget-fitting logic and the retrieval/prompt-building steps.

**API surface audit (Item 2)**

- **FR-013**: Every backend route MUST be classified as used, unused, or ambiguous, based on references from the frontend, MCP tools, and tests, with the classifying evidence recorded.
- **FR-014**: A route MUST NOT be removed solely because a static graph shows it unreferenced; genuine non-use MUST be verified (including dynamically built URLs and external callers) before removal.
- **FR-015**: Retired-provider remnants (e.g. lingering `ollama`-era references now that the provider is retired) MUST be identified and, where confirmed dead, removed.
- **FR-016**: For each removed route, the corresponding MCP tool (if any), the `swagger.json` path entry, and both language halves of `README.md` MUST be updated in the same change to stay consistent.
- **FR-017**: Any seemingly-orphaned route that is retained MUST have a documented reason.
- **FR-018**: The audit MUST NOT change the behavior of any route that is retained.

### Key Entities

- **RAG query request**: the inputs to an answer request — question, selected document scope, conversation history, and toggles (web search, graph, images). Its shape is unchanged.
- **Retrieved chunk set**: the ranked passages selected for context; the unit that trimming removes from, lowest-ranked first.
- **Route classification record**: per backend route, its path, whether it is used/unused/ambiguous, and the evidence (frontend/MCP/test reference, or reason for ambiguity/retention).
- **Search outcome**: one of results / genuine-empty / error, as surfaced on the Search page.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user whose search request fails sees a message that clearly indicates failure and is worded differently from the zero-results message — verifiable by forcing a failure and inspecting the page.
- **SC-002**: 100% of the three search outcomes (results, empty, error) are exercised by automated frontend tests and pass.
- **SC-003**: For a fixed battery of RAG inputs, the retrieval set, final prompt, sources, and answer are byte-for-byte identical before and after the refactor (0 divergences).
- **SC-004**: For an over-budget query, the full prompt is assembled no more than a small constant number of times regardless of how many chunks are dropped (i.e. no longer scales with the number of dropped chunks).
- **SC-005**: The chunk set retained after trimming matches the legacy trim result for every test case (0 mismatches).
- **SC-006**: Every backend route is accounted for in the audit inventory (100% classified), and no route is deleted without recorded evidence of non-use.
- **SC-007**: After the audit, the MCP tool list, `swagger.json`, and both README language halves reference exactly the same set of live routes (0 discrepancies), and `swagger.json` parses as valid JSON.
- **SC-008**: The application, worker, and MCP server start and operate identically to before, minus the removed dead routes (all existing tests pass).

## Assumptions

- The refactor of Item 1 targets the existing RAG answer path and preserves its externally observable behavior exactly; "identical prompt/answer" is asserted against the current implementation as the reference oracle.
- "A small constant number of times" for prompt assembly means the count does not grow with the number of chunks dropped; one or two full assemblies is acceptable.
- The Search error message wording is a reasonable default (e.g. "Search failed — please try again"); exact copy can be adjusted during implementation without changing scope.
- The dead-route audit is conservative by design: when usage is uncertain, the route is retained and flagged rather than removed, accepting that some genuinely-dead routes may survive this pass.
- Retired-provider cleanup is limited to remnants that are confirmed unused; a defensive fallback that is still reached at runtime (e.g. mapping a stale stored provider value to a supported one) is retained.
- The three items are independent and may be implemented, tested, and merged separately; there is no ordering dependency between them.
- Existing test infrastructure (disposable Postgres/Redis for backend, the frontend unit-test runner) is reused; no new test framework is introduced.
