# Implementation Plan: Wiki Collection & Document Filter

**Branch**: `001-wiki-collection-document-filter` | **Date**: 2026-05-31

## Summary

Add collection and document filter dropdowns to the wiki index page. The backend `GET /api/wiki/concepts` endpoint will accept optional `collection_id` and `document_id` query params. The frontend wiki-index component will show filter dropdowns above the letter tabs. Document filter options scope to the selected collection.

## Technical Context

**Backend**: Flask (Python) + SQLAlchemy. Concepts relate to Documents via HyperEdge → HyperEdgeMember chain. Collections relate to Documents via M2M junction table.

**Frontend**: Angular 21 standalone component, signals, inline template. WikiService uses HttpClient.

**Storage**: PostgreSQL + pgvector

**Target Platform**: Web (Angular SPA)

## Constitution Check

No violations. Minimal changes, backward-compatible, no new dependencies.

## Implementation Steps

### Backend: `dev/app/api/wiki.py`
- Add `collection_id` (UUID) and `document_id` (UUID) optional query params to `list_concepts()`
- Filter by joining: Concept → HyperEdgeMember → HyperEdge → Document (by document_id)
- For collection filter: join Document → collection_documents → Collection

### Frontend: Wiki Service (`frontend_spa/src/app/services/wiki.service.ts`)
- Add `collectionId` and `documentId` params to `listConcepts()`
- Add `getCollections()` and `getDocuments()` methods for filter dropdowns
  - Reuse existing `/api/collections/` endpoint
  - Reuse existing `/api/documents` endpoint with `?collection_id=` param

### Frontend: Wiki Index Component
- Add signals: `collections`, `documents`, `selectedCollectionId`, `selectedDocumentId`
- Add filter section in template between header and letter tabs
- Fetch collections on init; fetch documents when collection changes
- Re-fetch concepts when filters change
- Reset document filter when collection changes

### Frontend: CSS
- Style for filter dropdowns (inline with search, responsive)
