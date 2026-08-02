# Feature Specification: Automated Test Suite

**Feature Branch**: `004-test-suite`

**Created**: 2026-08-02

**Status**: Draft

**Input**: User description: "Add a test suite to MNEMOS. Currently there are zero automated tests — all verification is manual (curl, docker exec, manual DB queries). This is a Flask + Celery + PostgreSQL/pgvector + Angular 21 system. Scope: backend pytest suite for API routes, services, and Celery pipeline stages against a real disposable test database (no DB mocking; mock only external LLM/embedding network calls); migration round-trip tests; frontend component/smoke tests; CI wiring on PR with Postgres+pgvector and Redis services. Out of scope: auth/authz testing, load/performance testing, VideoMix. Constraints: never touch the live/dev database; test DB must be fresh per run; must not slow down `docker-compose up`. Success: `pytest` and `npm test` pass locally and in CI from a clean checkout with no manual setup; coverage baseline established for the RAG and document-processing pipelines."

## Clarifications

### Session 2026-08-02

- Q: Does the pull-request check fail when coverage on the RAG / document-processing pipelines drops, or only report the number? → A: Report now, fail on regression — the check reports coverage and fails only if it drops below the recorded baseline; no fixed percentage target.
- Q: Does the backend suite run from the developer's host environment or entirely inside a container? → A: Host-side test runner against a containerized disposable database — the developer runs tests from their local environment; the throwaway database and cache are provided by containers started by the test harness, not installed by hand.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Maintainer verifies a change before merging (Priority: P1)

A maintainer changes code in the RAG query pipeline, an API route, or a Celery pipeline stage. Instead of manually curling endpoints, exec-ing into containers, and eyeballing database rows, they run a single documented command and get a pass/fail verdict that reflects real system behavior (real database, real migrations, real chunking/retrieval logic), with only external network calls (LLM/embedding providers) faked.

**Why this priority**: This is the core problem statement — replacing manual verification is the entire point of the feature. Without this, nothing else matters.

**Independent Test**: Run the documented test command from a clean checkout with no manual setup beyond what's documented; observe that it exercises API routes, services, and pipeline stages against a real disposable database and reports clear pass/fail results.

**Acceptance Scenarios**:

1. **Given** a clean checkout of the repository, **When** the maintainer follows the documented setup and runs the backend test command, **Then** a disposable test database is created automatically, tests execute against it, and the run completes with a clear pass/fail result — no manual database setup or seeding required.
2. **Given** the test suite is running, **When** a test exercises RAG query logic or document processing, **Then** it reads/writes real Postgres/pgvector data and only the outbound calls to the LLM/embedding provider are faked.
3. **Given** the test run has finished, **When** the maintainer checks their existing dev environment (the one used for daily work), **Then** its data is unchanged — no documents, chunks, or other records were added, modified, or removed.

---

### User Story 2 - Maintainer verifies a schema change is safe (Priority: P2)

A maintainer adds a new Alembic migration. They need confidence that the full migration chain (baseline through the newest revision) applies cleanly to a fresh database, and that it can be rolled back without leaving the schema in a broken state, before merging.

**Why this priority**: Schema mistakes are highest-blast-radius (they can corrupt or lock out the live system) but occur less frequently than routine code changes, so it ranks below the general test suite.

**Independent Test**: Point the migration test at a scratch database; confirm it applies every revision in order from empty schema to head, then downgrades cleanly, without touching any pre-existing database.

**Acceptance Scenarios**:

1. **Given** an empty scratch database, **When** the migration test suite runs, **Then** every revision from baseline to the latest applies in order without error.
2. **Given** a database at the latest migration revision, **When** the downgrade path is exercised, **Then** the schema returns to its prior state without error.
3. **Given** a new migration is added, **When** the maintainer runs the migration tests, **Then** failures clearly identify which revision broke the upgrade or downgrade path.

---

### User Story 3 - Maintainer verifies the frontend still works (Priority: P3)

A maintainer changes SPA code (chat, document upload, or settings) and wants a fast automated check that the core screens still render and respond to basic interaction, without manually clicking through the app in a browser every time.

**Why this priority**: Valuable but lower risk than backend/data-layer regressions given the current single-user, no-auth deployment model; smoke-level coverage is enough to start.

**Independent Test**: Run the documented frontend test command; confirm it exercises the chat, document upload, and settings screens and reports pass/fail without requiring the full Docker stack to be running.

**Acceptance Scenarios**:

1. **Given** a clean checkout, **When** the maintainer runs the documented frontend test command, **Then** smoke-level checks for the chat, document upload, and settings screens execute and report pass/fail.
2. **Given** a frontend change breaks one of these screens, **When** the test command runs, **Then** the failure identifies which screen/behavior broke.

---

### User Story 4 - Pull request is automatically checked (Priority: P2)

A contributor opens a pull request. Reviewers want automated confirmation that backend, migration, and frontend tests all pass in a clean environment before spending review time on it.

**Why this priority**: Automates and enforces User Stories 1–3 as a gate; important for catching regressions but depends on those test suites existing first.

**Independent Test**: Open a pull request against the repository and confirm an automated check runs the full test suite (backend, migrations, frontend) against freshly provisioned database and cache services, reporting a single pass/fail status on the PR.

**Acceptance Scenarios**:

1. **Given** a pull request is opened or updated, **When** the automated check runs, **Then** it provisions its own database and cache, runs all test suites, and reports a pass/fail status visible on the PR.
2. **Given** the automated check is running, **When** it starts, **Then** it does not read from or write to any persistent/shared environment — its database and cache are created fresh and discarded after the run.
3. **Given** a test fails in the automated check, **When** a reviewer opens the check's output, **Then** they can identify which test and which layer (backend, migration, or frontend) failed without re-running anything locally.

---

### Edge Cases

- What happens when the test database fails to provision (e.g., port conflict, Docker not running)? The test run must fail fast with a clear error rather than silently falling back to another database.
- How does the suite behave if a developer's local dev stack (`docker-compose up`) is already running when tests start? Tests must not connect to, read from, or write to that stack's database, cache, or ports.
- What happens when a migration test reveals a revision that cannot be downgraded? The failure must name the offending revision rather than only reporting a generic error.
- What happens when an external LLM/embedding provider call is reached in a test without a corresponding fake/stub configured? The test must fail loudly (not silently pass or hang waiting on a real network call).
- How are flaky tests (e.g., timing-dependent pipeline stages) handled? Out of scope for this feature to solve generally, but any test proven flaky during implementation must be fixed or removed, not skipped silently.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide an automated test command that exercises Flask API routes, backend services (including RAG query and LLM client logic), and Celery pipeline stages.
- **FR-002**: Automated tests MUST run against a real, disposable database instance created fresh for each run — no test may run against or alter the developer's persistent/dev database or its existing data.
- **FR-003**: Automated tests MUST NOT mock or stub the database, ORM, or internal service logic; the only permitted fakes are for outbound network calls to external LLM/embedding providers.
- **FR-004**: The system MUST provide an automated way to verify that database migrations apply in order from an empty schema to the latest revision, and that they can be reversed without leaving an inconsistent schema.
- **FR-005**: The system MUST provide automated smoke-level checks confirming the chat, document upload, and settings screens of the frontend render and respond to basic interaction.
- **FR-006**: The system MUST provide an automated check that runs on every pull request, executing the backend, migration, and frontend test suites against freshly provisioned, disposable supporting services.
- **FR-007**: Running the automated test suite MUST require no manual setup beyond commands documented alongside the suite (e.g., no manual database creation, seeding, or service configuration by hand).
- **FR-013**: The backend suite MUST be runnable from the developer's own local environment, with the disposable database and cache supplied automatically by containers the test harness starts and tears down — the developer MUST NOT have to install, create, or configure those services by hand.
- **FR-008**: Running the automated test suite MUST NOT modify the normal local development workflow (starting the full stack via the existing compose-based flow) or slow it down.
- **FR-009**: Test failures MUST clearly identify which layer (API route, service, pipeline stage, migration, or frontend screen) and which specific check failed.
- **FR-010**: The test suite MUST establish and report a coverage baseline for the RAG query pipeline and the document processing pipeline, as the areas of highest risk to users.
- **FR-012**: The recorded coverage baseline for the RAG query and document processing pipelines MUST be stored in the repository, and the pull-request check MUST fail when measured coverage for either pipeline falls below its recorded baseline. No fixed percentage target is imposed — the baseline is whatever the suite achieves when first established, and it ratchets upward as coverage improves.
- **FR-011**: Authentication/authorization behavior, load/performance characteristics, and the VideoMix component are explicitly out of scope for this test suite.

### Key Entities

- **Test Run**: A single execution of the automated suite (or a subset — backend, migration, frontend); has a pass/fail outcome, a set of individual test results, and a coverage measurement for the RAG and document-processing pipelines.
- **Disposable Test Database**: A database instance created fresh for a test run, pre-loaded only with schema (via migrations) and any data a given test creates; discarded after the run; distinct from and never overlapping with the persistent development database.
- **External Provider Fake**: A stand-in for an outbound network call to an LLM or embedding provider (e.g., OpenAI, Anthropic, llama.cpp), used so tests exercise real internal logic without depending on or paying for a live external service.
- **Pull Request Check**: The automated pass/fail status attached to a pull request, reflecting the outcome of the backend, migration, and frontend test suites run against freshly provisioned services.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A maintainer can go from a clean checkout to a completed, documented test run (setup + execution) with zero manual database or service configuration steps.
- **SC-002**: 100% of test runs — local and in the pull-request check — use a database created fresh for that run; zero test runs read or write the persistent development database's existing data.
- **SC-003**: Every pull request opened against the repository receives an automated pass/fail test result without any reviewer manually running tests themselves.
- **SC-004**: A regression introduced into the RAG query pipeline or the document processing pipeline is caught by the automated suite before merge, in at least the primary success path and one representative failure path for each pipeline.
- **SC-005**: Starting the existing local development stack (`docker-compose up -d --build`) takes the same amount of time as before this feature was added — the test suite runs on a separate path and does not participate in that startup.
- **SC-006**: A broken migration (one that fails to apply or fails to reverse cleanly) is caught by an automated check before it reaches the persistent development or production database.
- **SC-007**: A pull request that reduces measured coverage of the RAG query or document processing pipeline below the recorded baseline is flagged as failing, without a reviewer needing to compare coverage numbers by hand.

## Assumptions

- "Maintainer" and "contributor" refer to developers working on the MNEMOS codebase; there are no distinct end-user roles for this feature since it is a developer-facing capability.
- The existing persistent development database (currently holding 58 documents, 6150 chunks, etc.) must remain completely untouched by any test run; a fresh, disposable database is created and destroyed per run instead of reusing or branching from it.
- "Coverage baseline" means establishing and reporting a measurable coverage figure for the RAG and document-processing pipelines so future regressions in measured coverage are visible. Per the Session 2026-08-02 clarification, no fixed numeric target is imposed; the baseline is recorded in the repository and enforced only against regression, ratcheting upward as coverage improves.
- Per the Session 2026-08-02 clarification, tests are invoked from the developer's local environment rather than from inside the application container; a container runtime must therefore be available on the developer's machine to supply the disposable database and cache (already true, since the dev stack itself is container-based).
- Frontend testing scope is smoke-level (screens render, basic interactions work) rather than exhaustive component-by-component coverage, consistent with the user's "at minimum smoke tests" framing.
- Auth/authorization testing is excluded because no authentication layer currently exists in the system (per existing project documentation); it is deferred to a separate future effort.
- Load/performance testing and the VideoMix component are excluded per explicit user instruction.
- The pull-request check runs on every PR (not only on-demand), consistent with the goal of catching regressions before merge without relying on manual reviewer action.
