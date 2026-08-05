@echo off
:: MNEMOS Lite - slim mode. No bundled llama.cpp, no GPU required.
:: Uses an OpenAI-compatible LLM server you already run (Ollama / LM Studio).
:: For the fully self-contained GPU version, use start.bat instead.

:: --- CONTAINER RUNTIME (Docker or Podman) ---
call "%~dp0runtime-detect.bat"
if %errorlevel% neq 0 (
    pause
    exit /b 1
)
echo [lite] Using container runtime: %MNEMOS_DETECTED_RUNTIME%
:: --------------------------------------------

:: --- FIRST-RUN .env BOOTSTRAP (slim preset, no prompt) ---
if not exist ".env" (
    echo [lite] No .env found. Applying 'slim' preset.
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0presets\apply.ps1" -Preset slim
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create .env. Copy .env.example to .env manually.
        pause
        exit /b 1
    )
)
:: ---------------------------------------------------------

:: --- LLM SERVER CHECK ---
:: Slim mode has no bundled model server, so an unreachable endpoint is the
:: number one failure mode. Warn but don't block: the user may be pointing at
:: a remote or non-default endpoint that this check can't see.
echo [lite] Looking for a local LLM server...
:: Note: no caret before the pipe - cmd does not unescape ^ inside a quoted
:: argument, so ^| would reach PowerShell literally and fail to parse.
powershell -NoProfile -Command "$found = @(11434,1234) | Where-Object { $c = New-Object Net.Sockets.TcpClient; try { $c.Connect('127.0.0.1', $_); $true } catch { $false } finally { $c.Dispose() } }; if ($found) { Write-Host ('[lite] Found a server on port ' + ($found -join ', ')) } else { exit 1 }"
if %errorlevel% neq 0 (
    echo.
    echo =================================================================
    echo   [!] No LLM server found on port 11434 ^(Ollama^) or 1234 ^(LM Studio^).
    echo.
    echo   That's fine - MNEMOS runs without one.
    echo.
    echo   Working now:     upload, indexing, semantic + keyword search.
    echo   Needs a model:   chat, summaries, the concept graph and wiki.
    echo.
    echo   Those features will explain themselves in the UI and link to
    echo   Settings. Connect Ollama or LM Studio whenever you want them.
    echo =================================================================
    echo.
)
:: ------------------------

echo Starting MNEMOS Lite ^(no bundled llama.cpp^)...
echo.
:: The slim override is required, not optional: the base file requests an nvidia
:: device driver on app/worker, which fails container creation on a machine
:: without the NVIDIA toolkit — exactly the machines slim mode targets.
docker-compose -f docker-compose.yml -f docker-compose.slim.yml up -d --wait
:: Note: docker-compose (the Go binary) drives Podman too - runtime-detect.bat
:: points DOCKER_HOST at Podman's compat socket. Same command, either runtime.
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Services failed to start. Inspect logs with:
    echo         docker-compose logs app
    pause
    exit /b 1
)

echo.
echo [OK] MNEMOS Lite is running.
echo      UI:   http://localhost:5200
echo      API:  http://localhost:5000/api/ready
echo.
echo      Logs:  docker-compose logs -f app
echo      Stop:  docker-compose down
echo.
start http://localhost:5200
