# Quickstart: Fix MCP Uploads Volume Mount

**Feature**: 002-fix-mcp-uploads-volume | Run all commands from `mnemos/dev`.

## 1. Apply the change

In `docker-compose.yml`, under the `mcp` service's `volumes` list (currently `docker-compose.yml:144-146`), add the uploads mount so it matches `app` and `worker`:

```yaml
  mcp:
    ...
    volumes:
      - .\app:/app/app:rw
      - .\config:/app/config:rw
      - ./data/uploads:/app/uploads
```

## 2. Recreate the container

A restart is not enough — volume mounts are set at container creation.

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d mcp
```

## 3. Verify the mount

```powershell
docker exec dev-mcp-1 ls /app/uploads
```

**Expected**: the same files present in `dev/data/uploads` on the host.

## 4. Verify end-to-end (the real test)

1. Upload a small PDF through the MCP `upload_document` tool; note the returned document ID.
2. Poll the status endpoint until it reaches a terminal state:

   ```powershell
   curl http://localhost:5000/api/documents/<ID>/status
   ```

**Expected**: status reaches `completed`. **Failure signal**: status `error`, especially with `no such file: /app/uploads/...` — that means the container was restarted rather than recreated, or the volume line was not saved.

If processing stalls, check the worker: `docker compose logs -f worker`.

## Notes

- Documents that errored *before* this fix would stay in `status: error` and need re-uploading — but in this database there were none left to fix (all 58 documents are `completed`).
- No application code changes — the MCP server was already writing to the correct path.
