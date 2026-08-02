# Baseline Metrics — captured before implementation

## Stack versions
NAME             IMAGE                                    STATUS
dev-adminer-1    adminer                                  Up 2 hours
dev-app-1        mnemos-backend:latest                    Up 2 hours
dev-db-1         pgvector/pgvector:pg16                   Up 2 hours (healthy)
dev-llamacpp-1   ghcr.io/ggml-org/llama.cpp:server-cuda   Up 2 hours (healthy)
dev-mcp-1        mnemos-backend:latest                    Up 2 hours
dev-redis-1      redis:7-alpine                           Up 2 hours
dev-worker-1     mnemos-backend:latest                    Up 2 hours

## Data safety gate (Phase 2 / US0)
- Backup used: backups/mnemos_db_20260801-185843.sql (232MB, predates this session's changes)
- Restore verified: chunks=6150 in restore_test (matches live)
- Row counts: documents=58 chunks=6150 collections=8 conversations=143
- Vector integrity: 6150 populated, 0 null, dim=1024

## Python file sizes (before)
 12389 total
  1783 app/mcp_server/server.py
  1278 app/api/settings.py
   723 app/services/rag.py
   500 app/tasks/processing.py
   422 app/services/videomix_script_generator.py
   418 app/api/videomix.py
   412 app/api/documents.py
   387 app/services/llm_client.py
   347 app/services/hypergraph_extractor.py
   319 app/services/transcription.py
   317 app/services/summary_service.py
   313 app/services/reasoning_engine.py
   304 app/services/embedder.py
   289 app/api/wiki.py
   283 app/tasks/videomix_tasks.py
   279 app/services/ffmpeg_service.py
   253 app/api/chat.py
   235 app/services/web_search.py
   227 app/models/videomix.py

## Complexity baseline (radon cc, measured — differs slightly from spec's cited figures)
- process_document_task: F (47)  [spec cited 44]
- save_chat_settings: F (51)  [spec cited 45]
- map_hf_to_ollama: D (26)
- LLMClient.__init__: F (68)
- LLMClient.chat: E (32)
- LLMClient class: E (39)

## Ollama / render_template grep counts (before)
- ollama file hits: 63
- render_template hits: 12
- ollama file hits: 47 total (36 excluding specs/ docs)
- render_template hits: 12 (app/web.py x3, chat.py x2, conversations.py x3, documents.py x4)
- NOTE: 4 files not in original task enumeration: swagger.json, installer.bat,
  installer/test-podman.ps1, installer/README.md
