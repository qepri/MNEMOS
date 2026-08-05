# Phase 1 Data Model: Prebuilt Container Images

## No entities, no schema, no persisted state

Release infrastructure only. Recorded so a future reader knows it was
considered: nothing in this feature reads or writes the database, and no
runtime Python/TypeScript code changes.

## The one invariant that shapes the design

**A given install is a single versioned unit: repo tree, compose files,
migrations, SPA build, and container images all come from the same git tag.**

Carried by three links:

```
git tag vX.Y.Z
  ├── workflow builds images FROM that commit → ghcr.io/...:vX.Y.Z (+ :sha-<commit>)
  ├── installer downloads the zip OF that tag (never main)
  └── installer writes MNEMOS_VERSION=vX.Y.Z into .env
        └── release override resolves image: ...:${MNEMOS_VERSION}
```

Why it must hold: `entrypoint.sh` runs `flask db upgrade` at startup. If repo
and image could skew, an image's model code could meet a migration state it has
never seen — the least debuggable failure class on a stranger's machine. The
invariant makes that unrepresentable rather than unlikely.

## Derived, non-persisted state

| State | Where | Lifetime |
|---|---|---|
| `MNEMOS_VERSION` | the install's `.env` | permanent for that install; absent on every dev machine — its absence IS the dev/release switch |
| Latest release tag | GitHub API `releases/latest`, resolved at install time | one resolution per install; never re-resolved silently (no auto-update) |
| Pulled image layers | runtime's local store | cached; re-pull only on version change |

Deliberately NOT stored: any "channel" or auto-update preference. Updating is a
future feature; this one only guarantees that whatever version you installed is
internally consistent.
