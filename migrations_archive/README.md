# Archived pre-Alembic migrations

`phase2_strip_embeddings.sql` was applied by hand before Alembic existed.
Verified applied against the live database on 2026-08-01: all four columns it
drops (`document_sections.embedding`, `documents.summary_embedding`,
`documents.summary_search_vector`, `hyper_edges.embedding`) are absent.

Its effect is baked into the Alembic baseline revision — those columns are
simply not declared there. Kept for historical reference only; do not re-run.
