# TASKS — Hardware presets + re-embed migration

Goal: let a user start MNEMOS on modest hardware and later migrate to better hardware (export/import DB, swap embedding model) without losing extracted text, summaries, or the hypergraph. Non-breaking for existing installs.

## Phase 1 — Hardware presets at first run ✅

- [x] `presets/low.env`
- [x] `presets/medium.env`
- [x] `presets/high.env`
- [x] `presets/apply.ps1` helper (one place to merge example + preset + random `SECRET_KEY`)
- [x] `start.bat`: prompt `1/2/3` (default 2) on first run
- [x] `start-dev.bat`: silent medium default

Acceptance: delete `.env`, run `start.bat` → prompted; pick 2 → `.env` exists with bge-base settings and a non-default `SECRET_KEY`. Run again → no prompt.

## Phase 2 — Re-embed task ✅

- [x] `Document.embedding_model_used` column + startup `ALTER ... ADD COLUMN IF NOT EXISTS`.
- [x] `app/tasks/reembed.py::reembed_all`: resizes pgvector column if dimension changed, re-embeds chunks + concepts in batches, recreates HNSW index, stamps `embedding_model_used`.
- [x] Self-check (`python -m app.tasks.reembed`): asserts embedder output dim matches settings and that both pgvector columns are aligned.

## Phase 3 — Trigger surface ✅

- [x] CLI: `flask reembed-all` (with `--sync` flag for in-process runs).
- [x] API: `POST /api/settings/reembed` → enqueues. `GET /api/settings/reembed/status/<task_id>` → polls.
- [x] UI: button + progress bar in Settings → Chat tab → "Re-embed Library" card. Confirm dialog mentions backup. Disabled while a task is running. Polls every 2s.

## Phase 4 — Stale indicator

- [ ] In document list, badge docs where `embedding_model_used != settings.EMBEDDING_MODEL OR IS NULL`. Single SQL filter; no new endpoint.

Acceptance: after changing model but before re-embedding, all docs show the badge. After re-embed, none do.

## Explicitly skipped (YAGNI)

- Per-document embedding models (Option C from the discussion). Add when a real user requests mixed corpora.
- Hypergraph / summary rebuild button. Different problem (LLM change, not embedder change). Add when needed.
- `start.bat --reconfigure` flag. `del .env && start.bat` does the same thing.
- Alembic migration for the new column. Repo already uses `ADD COLUMN IF NOT EXISTS` at startup for dev. Matches convention.
- Automatic `pg_dump` before re-embed. CLAUDE.md documents the command; the confirm dialog will mention it.

## Ship order

1 → 2 → 3 (CLI only) → test on real corpus → 3 (UI) → 4.

Stop after 3-CLI if UI work feels premature; CLI alone covers the migration story end-to-end.
