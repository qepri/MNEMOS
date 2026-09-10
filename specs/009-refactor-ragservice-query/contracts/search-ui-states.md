# Contract: Search page UI states (Item 3)

The Search page (`frontend_spa/src/app/features/search/search.component.ts`) surfaces exactly one of four mutually-exclusive states. Only the **error** state is new; the others are unchanged.

## State signals

```
query:       Signal<string>
results:     Signal<SearchResult[]>
loading:     Signal<boolean>
searched:    Signal<boolean>
error:       Signal<string | null>   // NEW
```

## State table

| State | Precondition | Visible content |
|---|---|---|
| Idle | `!searched() && !loading() && !error()` | just the search form |
| Loading | `loading()` | "Searching…" |
| Error | `!loading() && error() != null` | distinct error message, e.g. "Search failed — please try again." |
| Empty | `!loading() && searched() && !error() && results().length === 0` | "No matching passages found." |
| Results | `!loading() && searched() && !error() && results().length > 0` | count header + result cards |

## Transition contract

- **Submit** (`onSubmit`): `error.set(null)` and `loading.set(true)` before dispatch. (Clears any prior error — spec edge case.)
- **Success** (`next`): `results.set(res.results)`, `error.set(null)`, `searched.set(true)`, `loading.set(false)`.
- **Failure** (`error` callback): `error.set('Search failed — please try again.')`, `searched.set(true)`, `loading.set(false)`. Results are not shown alongside the error.
- Template checks **error before empty** so a failure never renders as "No matching passages found." (FR-001/FR-002).

## Test obligations (`search.component.spec.ts`, NEW)

Stub `DocumentsService.searchChunks` to cover:
1. **Results** — returns `{ results: [<≥1 SearchResult>] }` → results branch renders, count header correct.
2. **Empty** — returns `{ results: [] }` → "No matching passages found." renders; error branch absent.
3. **Error** — returns a throwing/erroring `Observable` → error message renders; empty/results branches absent.

Covers FR-005 and SC-002 (all three outcomes exercised).
