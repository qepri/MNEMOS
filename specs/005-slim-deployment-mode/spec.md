# Feature Specification: Slim Deployment Mode

**Feature Branch**: `005-slim-deployment-mode`

**Created**: 2026-08-03

**Status**: Draft

**Input**: User description: "Slim deployment mode: run MNEMOS without the bundled llama.cpp container. Put the llamacpp service behind a compose profile ("local-llm") so the default `docker compose up` starts only app, worker, db, redis, mcp. Add a `presets/slim.env` preset that defaults LLM_PROVIDER to a user-provided OpenAI-compatible endpoint (Ollama at host.docker.internal:11434/v1 or LM Studio at :1234/v1) and sets EMBEDDING_DEVICE=cpu so the worker runs without CUDA. Fix /api/ready so the llama.cpp health probe is skipped when the active LLM provider is not llamacpp — otherwise slim deployments report 503 forever. Goal: faster startup, smaller pull, no GPU requirement; this becomes the recommended "bring your own LLM server" path for r/LocalLLaMA users."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start MNEMOS without a GPU or bundled model server (Priority: P1)

A user who already runs a local LLM server (e.g. Ollama or LM Studio) on their machine wants to try MNEMOS without downloading a second multi-gigabyte model or needing a CUDA-capable GPU. They start the stack with the default command and it comes up pointed at their existing server.

**Why this priority**: This is the entire point of the feature — it's the path being recommended to the target audience (privacy-conscious local-LLM users). Without it, nothing else in this feature has value.

**Independent Test**: On a machine with no GPU and an Ollama (or LM Studio) server already running, start MNEMOS using the slim preset and confirm it becomes ready and can answer a query using the external model, without pulling or starting a bundled inference container.

**Acceptance Scenarios**:

1. **Given** a clean checkout with no `.env` file, **When** the user applies the slim preset and starts the stack with the default (no-profile) command, **Then** the bundled inference service does not start and total containers started is reduced (app, worker, db, redis, mcp only).
2. **Given** the slim preset is active and an OpenAI-compatible local server (Ollama or LM Studio) is running and reachable from the container network, **When** the user asks a question against an ingested document, **Then** the system generates an answer using that external server.
3. **Given** the slim preset is active, **When** documents are processed, **Then** embedding generation completes successfully on CPU without requiring a GPU.

---

### User Story 2 - Accurate readiness status without the bundled inference service (Priority: P2)

An operator or the startup script checks whether MNEMOS is ready to serve requests. In slim mode there is no bundled inference container to check, so readiness must reflect the services actually in use rather than perpetually failing on a component that was intentionally not started.

**Why this priority**: Without this, the health-polling startup flow (already used by `start-dev.bat`-style scripts) times out and reports failure even though the application is fully functional — a critical usability bug for the exact audience this feature targets, but secondary to the core "it starts and works" story above.

**Independent Test**: With the slim preset active and no bundled inference container running, poll the readiness endpoint and confirm it reports ready (assuming database and cache are reachable), instead of waiting on a health check for a service that was never started.

**Acceptance Scenarios**:

1. **Given** slim mode is active (external LLM provider configured, bundled inference service not started), **When** the readiness check runs, **Then** it reports ready based on database/cache reachability and does not wait on or fail due to the unstarted bundled inference service.
2. **Given** the bundled inference service is intentionally in use (not slim mode), **When** the readiness check runs, **Then** it continues to include that service's health as it does today (no regression for existing users).

---

### User Story 3 - Opt back into the bundled inference service (Priority: P3)

A user who wants the fully self-contained, no-external-dependencies experience (or who lacks any existing local LLM server) can still start MNEMOS with the bundled inference service included, using one explicit flag/option rather than a separate, divergent configuration file.

**Why this priority**: Preserves the existing "just works, fully bundled" experience for users who prefer it or don't already run a local server. Lower priority because it is largely "don't break what exists," not new behavior.

**Independent Test**: Start the stack with the bundled-inference option explicitly enabled and confirm behavior matches the current (pre-feature) default: the bundled inference container starts and is used.

**Acceptance Scenarios**:

1. **Given** a user explicitly opts into the bundled inference service, **When** they start the stack, **Then** the bundled inference container starts and readiness checks include it, matching current behavior.

### Edge Cases

- What happens when slim mode is active but no external LLM server is actually reachable at the configured endpoint? System should surface a clear connection error at query time rather than a silent hang or a misleading readiness "success."
- What happens when a user switches from slim mode to bundled mode (or back) on an existing installation? Existing documents, embeddings, and chunks must remain valid — switching inference backend does not require re-processing already-ingested content (only the language-model calls are affected; the embedding model change from GPU to CPU device is a performance setting, not a different embedding model, so vector dimensions and existing embeddings remain compatible).
- What happens if the configured external endpoint is reachable but is not actually OpenAI-compatible or returns malformed responses? Existing LLM client error handling applies; no new requirement beyond surfacing the failure clearly.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow starting the full application (API, background processing, database, cache, and MCP access) without also starting the bundled local inference service.
- **FR-002**: Starting the application without the bundled inference service MUST be the default behavior when no explicit opt-in for that service is given.
- **FR-003**: The system MUST provide a ready-to-use configuration preset that targets a user-supplied, already-running, OpenAI-compatible local LLM server as the default language-model provider.
- **FR-004**: That preset MUST configure embedding generation to run without requiring GPU/CUDA availability.
- **FR-005**: The system MUST allow a user to explicitly opt into starting the bundled inference service alongside the rest of the application, preserving today's fully self-contained behavior.
- **FR-006**: The system's readiness/health reporting MUST NOT depend on, wait for, or be blocked by the bundled inference service when that service was not started.
- **FR-007**: The system's readiness/health reporting MUST continue to include the bundled inference service's health when that service is running (no regression to current behavior).
- **FR-008**: Documentation MUST describe how to point the application at a common local LLM server (at minimum, Ollama and LM Studio) as part of using the reduced-footprint startup path.

### Key Entities

- **Deployment mode**: Whether the bundled local inference service is started alongside the application (full) or not (slim). Determines which services start and how readiness is evaluated.
- **LLM provider configuration**: The existing setting that determines which language-model backend the application talks to (bundled local service vs. an external OpenAI-compatible endpoint); slim mode changes this configuration's default, it does not introduce a new mechanism.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with an existing local LLM server and no GPU can go from a clean checkout to a working, answered query in under 5 minutes, without downloading a bundled model.
- **SC-002**: The default (slim) startup pulls and starts at least one fewer container image than the current full startup, and does not require any GPU/CUDA-specific setup.
- **SC-003**: Readiness reporting reaches a "ready" state in slim mode without any wait tied to the unstarted bundled inference service, and continues to correctly reflect degraded/ready state for the services that are running.
- **SC-004**: 100% of existing (non-slim) deployments observe no change in startup behavior or readiness semantics after this feature ships.

## Assumptions

- The user has, or is willing to install, a local OpenAI-compatible LLM server (e.g. Ollama, LM Studio) reachable from the application's container network; setting that server up is outside this feature's scope.
- "Bundled inference service" and "bundled local model server" refer to the project's existing self-hosted local inference container (today: llama.cpp); this spec describes it functionally rather than by implementation to keep the spec technology-agnostic, per template guidance.
- Switching between slim and full deployment mode is a configuration-time decision (at startup), not something that needs to change while the application is running.
- CPU-based embedding generation is an accepted (if slower) trade-off for slim-mode users; no new embedding model or provider is required to satisfy this feature.
- No changes to authentication, multi-tenancy, or data retention are in scope — this feature only changes which services start by default and how readiness is evaluated.
