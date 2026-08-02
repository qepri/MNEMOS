# Feature Specification: Fix MCP Uploads Volume Mount

**Feature Branch**: `002-fix-mcp-uploads-volume`

**Created**: 2026-08-01

**Status**: Draft

**Input**: User description: "En mnemos/dev/docker-compose.yml, el servicio `mcp` no monta el volumen de uploads, a diferencia de `app` y `worker`. Por eso upload_document (MCP) copia el PDF a un `/app/uploads` local del contenedor que el worker no ve, y el documento queda en `status: error` con 'no such file: /app/uploads/...'. Hacer el cambio mínimo: añadir el volumen al servicio mcp, recrear el contenedor, verificar que los PDFs son visibles y confirmar con una subida real que llega a status completed."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upload a document via MCP and have it fully processed (Priority: P1)

A user working from Claude Desktop uploads a PDF through the MCP `upload_document` tool. The document is stored in a location shared with the processing pipeline, so the background worker can find the file, process it, and the document reaches a terminal "completed" status instead of failing with a file-not-found error.

**Why this priority**: This is the entire feature — today every MCP upload silently lands in `status: error`, making the MCP upload path unusable.

**Independent Test**: Upload a small PDF via the MCP `upload_document` tool and poll the document status endpoint until it reaches "completed" (not "error").

**Acceptance Scenarios**:

1. **Given** the MCP service is running with the shared uploads storage attached, **When** a user uploads a PDF via `upload_document`, **Then** the file is visible to the worker service and the document status progresses to "completed".
2. **Given** a PDF was uploaded via MCP, **When** the user queries `GET /api/documents/{id}/status`, **Then** the response never reports the "no such file: /app/uploads/..." error.

---

### User Story 2 - MCP service sees previously uploaded documents (Priority: P2)

Files already uploaded through the web app (stored in the shared uploads directory) are visible from inside the MCP service container, confirming both services operate on the same storage.

**Why this priority**: Verification/diagnostic value — proves the shared storage is correctly attached; secondary to the upload flow itself.

**Independent Test**: List the uploads directory from inside the MCP container and confirm it shows the same files present in the host `data/uploads` directory.

**Acceptance Scenarios**:

1. **Given** existing PDFs in the host uploads directory, **When** the uploads directory is listed from inside the recreated MCP container, **Then** those same files appear.

### Edge Cases

- MCP container already running with the old configuration: it must be recreated for the storage change to take effect; a restart alone is insufficient.
- Documents uploaded via MCP *before* the fix remain in `status: error`; re-uploading (or reprocessing) them is out of scope for this change.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The MCP service MUST store uploaded files in the same shared uploads storage used by the app and worker services.
- **FR-002**: A document uploaded via the MCP `upload_document` tool MUST be readable by the worker service for processing.
- **FR-003**: The MCP service configuration change MUST be applied by recreating the running MCP container so the shared storage is attached.
- **FR-004**: The fix MUST be verified with a real end-to-end upload: a small PDF uploaded via MCP whose status reaches "completed".

### Key Entities

- **Document**: An uploaded file tracked with a processing status (`pending` → `processing` → `completed`/`error`) and a stored file path under the uploads directory.
- **Uploads storage**: The single host directory (`data/uploads`) that all services (app, worker, mcp) must share so file paths recorded by one service resolve in another.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of documents uploaded via the MCP tool after the fix reach "completed" status (given valid files), with zero "no such file" errors.
- **SC-002**: Files listed inside the MCP service's uploads directory match the host uploads directory exactly.
- **SC-003**: The end-to-end verification (upload small PDF via MCP → status "completed") passes on the first attempt after the fix.

## Assumptions

- The app and worker services already mount the shared uploads storage correctly; only the MCP service is missing it.
- The Docker environment (compose stack) is running in dev mode and can recreate the MCP container without disrupting other services.
- Existing documents stuck in `status: error` from before the fix do not need automatic remediation.
- A small valid PDF is available (or can be created) for the end-to-end verification.
