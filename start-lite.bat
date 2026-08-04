@echo off
:: MNEMOS Lite - slim mode. No bundled llama.cpp, no GPU required.
:: Uses an OpenAI-compatible LLM server you already run (Ollama / LM Studio).
:: For the fully self-contained GPU version, use start.bat instead.

:: --- DOCKER DESKTOP CHECK ---
docker info >nul 2>&1
if %errorlevel% neq 0 (
    if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
        echo Docker Desktop is installed but not running. Launching it...
        start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        echo Waiting for Docker to be ready...
        :wait_docker
        timeout /t 5 /nobreak >nul
        docker info >nul 2>&1
        if %errorlevel% neq 0 goto wait_docker
        echo Docker Desktop is now ready.
    ) else (
        cls
        echo =================================================================
        echo   MNEMOS requires Docker Desktop to run.
        echo.
        echo   It looks like Docker Desktop is not installed.
        echo.
        echo   Official download:
        echo   https://docs.docker.com/desktop/setup/install/windows-install/
        echo.
        echo   Opening the URL in your browser...
        echo =================================================================
        start "" "https://docs.docker.com/desktop/setup/install/windows-install/"
        pause
        exit /b 1
    )
)
:: ----------------------------

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
    echo   MNEMOS Lite does not include one - it uses yours. Start Ollama or
    echo   LM Studio, or set LOCAL_LLM_BASE_URL in .env to your endpoint.
    echo.
    echo   Uploads and search will still work. Chat answers will fail until
    echo   a server is reachable.
    echo =================================================================
    echo.
)
:: ------------------------

echo Starting MNEMOS Lite ^(no bundled llama.cpp^)...
echo.
docker-compose -f docker-compose.yml up -d --wait
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
