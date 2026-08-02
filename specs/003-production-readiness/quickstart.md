# Quickstart: Verification Runbook

**Feature**: `003-production-readiness` | **Date**: 2026-08-01

Copy-pasteable checks for every success criterion. Run the baseline capture **before** touching anything; run the rest as each phase lands. Commands assume the stack is up (`start-dev.bat`) and are written for Git Bash on the Windows host.

## 0. Baseline capture — DO THIS FIRST (SC-001, SC-002)

```bash
# Fresh pre-migration dump
TS=$(date +%Y%m%d-%H%M%S)
docker-compose exec -T db pg_dump -U mnemos_user mnemos_db > "backups/mnemos_db_${TS}.sql"
ls -la backups/

# Record reference row counts — expected today: 58 / 6150 / 8 / 143
docker exec dev-db-1 psql -U mnemos_user -d mnemos_db -t -c "
select 'documents='||(select count(*) from documents)
||' chunks='||(select count(*) from chunks)
||' collections='||(select count(*) from collections)
||' conversations='||(select count(*) from conversations);"

# Vector integrity reference — expected: 6150 populated, 0 null, dim 1024
docker exec dev-db-1 psql -U mnemos_user -d mnemos_db -t -c "
select count(*) filter (where embedding is not null) as with_emb,
       count(*) filter (where embedding is null)     as null_emb,
       vector_dims((select embedding from chunks where embedding is not null limit 1)) as dim
from chunks;"
```

**Verify the dump actually restores** — an unrestorable backup is not a backup:

```bash
docker exec dev-db-1 psql -U mnemos_user -d postgres -c "CREATE DATABASE restore_test;"
docker exec -i dev-db-1 psql -U mnemos_user -d restore_test < "backups/mnemos_db_${TS}.sql" > /dev/null 2>&1
docker exec dev-db-1 psql -U mnemos_user -d restore_test -t -c "select count(*) from chunks;"   # expect 6150
docker exec dev-db-1 psql -U mnemos_user -d postgres -c "DROP DATABASE restore_test;"
```

> **Never** run `docker-compose down -v`, and never remove `postgres_data` or `redis_data`. To stop the stack use `docker-compose stop` or `docker-compose down` **without** `-v`.

## 1. Dead code removed (SC-004)

```bash
# Expect zero hits
grep -rn "render_template" --include=*.py app | grep -v __pycache__
ls app/templates app/static app/web.py app/services/rag_method_dump.py 2>&1   # expect "No such file"
ls scripts/update_schema.py scripts/run_migration.py 2>&1                     # expect "No such file"
```

Then exercise the SPA at <http://localhost:5200>: list documents, open a conversation, send a chat message. All three must behave as before (they already used the JSON branch).

## 2. Ollama purged (SC-003)

```bash
# Expect zero hits. Exclusions are justified: dist/ is build output, .agent/ is
# dated design notes, backups/ and migrations/ are history.
grep -ril "ollama" \
  --exclude-dir=__pycache__ --exclude-dir=node_modules --exclude-dir=.git \
  --exclude-dir=dist --exclude-dir=backups --exclude-dir=.agent \
  --exclude-dir=migrations .

# No socket mount anywhere (SC-005)
grep -n "docker.sock" docker-compose*.yml    # expect zero hits
grep -n "^docker" requirements.txt           # expect zero hits
```

Runtime check — a stale stored value must not crash anything even before migrating:

```bash
docker exec dev-db-1 psql -U mnemos_user -d mnemos_db -c \
  "select llm_provider, memory_provider from user_preferences;"
```

Then open the SPA settings page and confirm it loads with no console 404s.

## 3. Alembic baseline (SC-006)

```bash
# Baseline faithfulness — THE critical gate. Must produce an EMPTY revision.
docker exec dev-app-1 flask db migrate -m "baseline-verification-DISCARD-ME"
# Inspect the generated file: upgrade() and downgrade() must both be `pass`.
# Any operation means the baseline is wrong. Delete the file either way.

# Upgrade reaches head
docker exec dev-app-1 flask db upgrade
docker exec dev-app-1 flask db current      # must equal `flask db heads`
docker exec dev-app-1 flask db heads

# Re-running is a no-op
docker exec dev-app-1 flask db upgrade      # no operations

# App performs no DDL at boot
docker-compose restart app
docker-compose logs app | grep -i "create_all\|ALTER TABLE\|tables created"   # expect zero hits
```

Confirm the protected structures survived:

```bash
docker exec dev-db-1 psql -U mnemos_user -d mnemos_db -c "\d chunks" | grep -E "vector\(1024\)|hnsw"
```

Re-run the row counts from step 0 — all four must be identical.

## 4. FTS repair (revision 005)

```bash
# Trigger now exists
docker exec dev-db-1 psql -U mnemos_user -d mnemos_db -c \
  "select tgname from pg_trigger where not tgisinternal;"

# Backfill complete — expect 0 null
docker exec dev-db-1 psql -U mnemos_user -d mnemos_db -t -c \
  "select count(*) filter (where search_vector is null) from chunks;"
```

**The check that actually matters**: run a keyword-heavy query through the SPA chat using a distinctive term you know appears in an indexed document. Before this revision the keyword arm returned nothing; it must now contribute results. Row counts alone do not prove the index-time and query-time text-search configs match.

Then confirm the trigger fires on new content by processing a small document and checking its chunks have non-NULL `search_vector`.

## 5. Docker & launcher (SC-007, SC-011, SC-012)

```bash
# Infrastructure ports must show 127.0.0.1, NOT 0.0.0.0
docker-compose ps --format "{{.Name}}\t{{.Ports}}"
netstat -ano | grep -E "5433|6380|8080"

# App (5000) and frontend (5200) must STAY on 0.0.0.0 — mobile access is
# a required capability (FR-041a / AR-001). Seeing 127.0.0.1 here is a BUG.
netstat -ano | grep -E "5000|5200"

# Adminer is opt-in
docker-compose ps adminer                       # expect not running
docker-compose --profile tools up -d adminer    # starts on demand

# Non-root
docker exec dev-app-1 id        # expect uid != 0
docker exec dev-worker-1 id

# Restart policy
docker kill dev-app-1 && sleep 10 && docker ps --filter name=dev-app-1
```

**No-network start (SC-007)** — the real test of the entrypoint change:

```bash
grep -n "pip install" entrypoint.sh    # expect zero hits
docker-compose stop
docker network disconnect bridge dev-app-1 2>/dev/null || true
# Or disable the host network adapter, then:
docker-compose up -d
docker-compose logs app | tail -30     # must start clean, no download attempts
```

**Launcher (SC-011)**: run `start-dev.bat` and time it — it must proceed within a few seconds of the API returning 200, not a fixed 15s. Then stop the `db` container and run it again: it must abort with a clear message at the cap, not hang or continue silently.

**Non-root regression check**: after the non-root change, upload and fully process a document. Model caches, `uploads/`, and `archive/` must all still be writable.

**LAN access check (SC-012)**: from a phone on the same network, open `http://<host-lan-ip>:5200` and confirm the SPA loads and can chat. This capability must survive the compose hardening — if it breaks, ports 5000/5200 were bound to localhost by mistake.

## 6. Readiness endpoint

```bash
curl -s localhost:5000/api/health | python -m json.tool    # unchanged shape
curl -s localhost:5000/api/ready  | python -m json.tool    # migrations + llamacpp

# Liveness stays green when llama.cpp is down
docker-compose stop llamacpp
curl -s -o /dev/null -w "health=%{http_code}\n" localhost:5000/api/health   # expect 200
curl -s -o /dev/null -w "ready=%{http_code}\n"  localhost:5000/api/ready    # expect 503
docker-compose start llamacpp
```

## 7. Refactors & hygiene (SC-008, SC-009, SC-010)

```bash
# No file over ~600 lines
find app -name "*.py" -not -path "*__pycache__*" -exec wc -l {} + | sort -rn | head -10

# Complexity — no refactored function above 20 (grade C+)
docker exec dev-app-1 pip install radon >/dev/null 2>&1
docker exec dev-app-1 radon cc -s -n C app/tasks/processing.py app/api/ app/services/llm_client.py
```

VideoMix files (`videomix_script_generator.py` 422, `videomix.py` 418) are exempt per HC-5 and are already under threshold anyway.

```bash
# Reproducible builds
docker-compose build --no-cache app && docker exec dev-app-1 pip freeze | sort > /tmp/f1.txt
docker-compose build --no-cache app && docker exec dev-app-1 pip freeze | sort > /tmp/f2.txt
diff /tmp/f1.txt /tmp/f2.txt        # expect no differences
grep -c "==" requirements.txt        # every line pinned
```

**Log correlation (SC-010)**: trigger an upload from the SPA, then

```bash
docker-compose logs app | tail -5 | python -m json.tool     # valid JSON, has request_id
# take that request_id and find it in the worker
docker-compose logs worker | grep "<request_id>"
```

## 8. Final data integrity gate (SC-002)

Re-run **step 0's** row-count and vector-integrity queries. All must match the recorded baseline exactly: 58 documents, 6,150 chunks, 8 collections, 143 conversations, 6,150 non-null 1024-dim embeddings.

Then confirm retrieval still works end-to-end: ask the SPA a question answerable from an existing document and verify it returns cited results from before the work began.

## Rollback

Per-revision: `docker exec dev-app-1 flask db downgrade -1`.

Full restore from the pre-migration dump (last resort — **drops and recreates the database**, so it is itself destructive and requires deliberate intent):

```bash
docker-compose stop app worker mcp
docker exec dev-db-1 psql -U mnemos_user -d postgres -c "DROP DATABASE mnemos_db;"
docker exec dev-db-1 psql -U mnemos_user -d postgres -c "CREATE DATABASE mnemos_db OWNER mnemos_user;"
docker exec -i dev-db-1 psql -U mnemos_user -d mnemos_db < backups/mnemos_db_<TS>.sql
docker-compose start app worker mcp
```

`restore_db.bat` at the repo root may already automate this — read it before use.
