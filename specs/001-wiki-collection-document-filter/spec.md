# Feature Specification: Wiki Collection & Document Filter

**Feature Branch**: `001-wiki-collection-document-filter`

**Created**: 2026-05-31

**Status**: Draft

**Input**: User description: "Add collection and document filter to wiki page on frontend"

## User Scenarios & Testing

### User Story 1 - Filter concepts by collection (Priority: P1)

A user browsing the wiki wants to see only concepts extracted from documents that belong to a specific collection (e.g., "Machine Learning" or "Project Alpha"). They select a collection from a dropdown or picker, and the concept list updates to show only concepts that originate from documents in that collection.

**Why this priority**: Collections are the primary organizational unit for documents. This filter gives users a direct way to scope wiki browsing to a specific knowledge domain or project without manually scanning the entire concept list.

**Independent Test**: Can be fully tested by selecting a collection from the filter and verifying the displayed concepts all trace back to documents within that collection. Delivers immediate narrowing of the knowledge base.

**Acceptance Scenarios**:

1. **Given** the wiki page is loaded with concepts, **When** the user selects a collection from the collection filter, **Then** the concept list updates to show only concepts whose source documents belong to the selected collection
2. **Given** a collection filter is active, **When** the user clears the filter (selects "All" or equivalent), **Then** the concept list returns to showing concepts from all collections
3. **Given** no concepts exist for the selected collection, **When** the filter is applied, **Then** the user sees a clear empty state message indicating no concepts match the filter

---

### User Story 2 - Filter concepts by document (Priority: P2)

A user wants to see all wiki concepts that were extracted from a particular document (e.g., "attention_paper.pdf"). They select a document from a dropdown or picker (optionally scoped by a previously selected collection), and the concept list updates accordingly.

**Why this priority**: Document-level filtering gives users the most granular control, allowing them to trace what knowledge was extracted from a single source. This is valuable for assessing a document's contribution to the knowledge graph and for focused review.

**Independent Test**: Can be fully tested by selecting a document from the filter and verifying the displayed concepts all have that document as a source. Delivers per-document knowledge graph visibility.

**Acceptance Scenarios**:

1. **Given** the wiki page is loaded with concepts, **When** the user selects a document from the document filter, **Then** the concept list updates to show only concepts that cite the selected document as a source
2. **Given** a document filter is active, **When** the user clears the filter, **Then** the concept list returns to showing concepts from all documents
3. **Given** a collection filter is active, **When** the user opens the document filter, **Then** the document list is scoped to documents within the selected collection

---

### User Story 3 - Combine filters with existing search and letter navigation (Priority: P3)

A user combines collection and/or document filters with the existing text search and alphabetical letter navigation to find specific concepts more precisely. All active filters work together to narrow the result set.

**Why this priority**: Power users benefit from layered filtering to drill down to specific concepts when the knowledge base is large. This story builds on the existing functionality rather than replacing it.

**Independent Test**: Can be tested by applying a collection filter, typing a search query, and clicking a letter button, then verifying the displayed concepts satisfy all three constraints simultaneously.

**Acceptance Scenarios**:

1. **Given** a collection filter and a document filter are both active, **When** the user types a search query, **Then** the concept list shows only concepts that match all three constraints (collection + document + text search)
2. **Given** one or more filters are active, **When** the user clicks a letter tab, **Then** the concept list is further scoped to concepts starting with that letter, while respecting the active filters
3. **Given** filters are active, **When** the user clears all filters, **Then** the concept list returns to the unfiltered state

## Edge Cases

- What happens when a concept is extracted from multiple documents that belong to different collections? Concept appears when its collection filter matches at least one of its source documents' collections.
- How does the system handle a document that has been deleted but whose concepts remain? Concepts whose source documents no longer exist should not appear under that document filter.
- What happens when the collections or documents list is very large? Filter dropdowns should be searchable or lazily loaded to remain usable.
- How does the page behave while filter results are loading? A loading indicator should be shown during data fetch.

## Requirements

### Functional Requirements

- **FR-001**: Users MUST be able to select a collection from a list of available collections to filter the displayed wiki concepts
- **FR-002**: Users MUST be able to select a specific document from a list of available documents to filter the displayed wiki concepts
- **FR-003**: The collection filter and document filter MUST be independently usable (either can be used alone)
- **FR-004**: When both collection and document filters are active, the concept list MUST satisfy both constraints (AND logic)
- **FR-005**: The document filter options MUST be scoped to documents within the currently selected collection, if any
- **FR-006**: Active filters MUST combine with the existing text search and alphabetical letter navigation
- **FR-007**: Each filter MUST have a clear way to reset/clear it (e.g., "All collections" / "All documents" option)
- **FR-008**: The system MUST provide the list of available collections and documents for the filter controls
- **FR-009**: Users MUST receive clear feedback when no concepts match the current filter combination (empty state)
- **FR-010**: Filter interactions MUST feel responsive, with loading indicators during data fetches

### Key Entities

- **Collection**: A named grouping of documents (e.g., "Machine Learning Papers", "Project Alpha"). Each document belongs to zero or one collection.
- **Document**: An uploaded file (PDF, audio, video, YouTube, EPUB) that has been processed. Documents are the source of wiki concepts and belong to collections.
- **Wiki Concept**: A unique knowledge entity/term automatically extracted from document content. Concepts are displayed in the wiki index and can originate from multiple source documents.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Users can narrow the wiki concept list to a specific collection in 2 clicks or fewer (select collection, view results)
- **SC-002**: Users can narrow the wiki concept list to a specific document in 2 clicks or fewer (select document, view results)
- **SC-003**: Filtered results load within 3 seconds for a knowledge base of up to 10,000 concepts
- **SC-004**: Users can successfully combine collection filter, document filter, text search, and letter navigation without confusing behavior
- **SC-005**: Users can clear any active filter and return to the full concept list in 1 click

## Assumptions

- The backend provides the necessary endpoints to fetch the list of available collections and documents
- The backend wiki concept listing endpoint can be extended to accept collection and document filter parameters
- Existing text search and alphabetical letter filtering continue to work as before
- A concept that originates from multiple documents appears when any of its source documents matches the filter criteria
- Filter options (collections list, documents list) are fetched on page load and/or when the user interacts with the filter controls
- Deleting a document or collection removes the association for filtering purposes
