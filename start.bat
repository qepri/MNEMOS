@echo off

:: --- CONTAINER RUNTIME (Docker or Podman) ---
call "%~dp0runtime-detect.bat"
if %errorlevel% neq 0 (
    pause
    exit /b 1
)
echo Using container runtime: %MNEMOS_DETECTED_RUNTIME%
:: --------------------------------------------

:: --- FIRST-RUN .env BOOTSTRAP ---
if not exist ".env" (
    echo.
    echo =================================================================
    echo   First run detected. Choose a hardware profile:
    echo.
    echo     [1] Low     - CPU-only laptop (MiniLM-L6, 384 dims)
    echo     [2] Medium  - Modern laptop, optional GPU (bge-base, 768)   [default]
    echo     [3] High    - Desktop with GPU (bge-large, 1024 dims, fp16)
    echo.
    echo   You can re-embed your library later from Settings to switch.
    echo =================================================================
    set /p PROFILE_CHOICE="Choice (1/2/3, Enter for default): "
    if "%PROFILE_CHOICE%"=="1" (set PRESET=low) else if "%PROFILE_CHOICE%"=="3" (set PRESET=high) else (set PRESET=medium)
    echo Applying preset: %PRESET%
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0presets\apply.ps1" -Preset %PRESET%
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create .env. Copy .env.example to .env manually.
        pause
        exit /b 1
    )
)
:: --------------------------------

echo Starting MNEMOS in Default Mode (GPU Enabled)...
echo.

:: --- AUTO CLEANUP ORPHANED IMAGES ---
echo Cleaning up orphaned images...
docker image prune -f >nul 2>&1
:: -------------------------------------

:: --- SMART BUILD LOGIC ---
echo Checking for dependency changes...
powershell -Command "$last = Get-Item .last_build -ErrorAction SilentlyContinue; $files = @('requirements.txt', 'Dockerfile', 'docker-compose.yml', 'frontend_spa\package.json', 'frontend_spa\Dockerfile'); $newest = $files | ForEach-Object { Get-Item $_ -ErrorAction SilentlyContinue } | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if (-not $last -or ($newest.LastWriteTime -gt $last.LastWriteTime)) { exit 1 } else { exit 0 }"

if %errorlevel%==1 (
    echo [SMART BUILD] Changes detected. Rebuilding images...
    set DOCKER_CMD=up --build -d --wait
    type nul > .last_build
) else (
    echo [SMART BUILD] No changes detected. Fast start...
    set DOCKER_CMD=up -d --wait
)
:: -------------------------

:: Check if any .gguf model exists
dir /b models\*.gguf >nul 2>&1
if %errorlevel%==0 (
    echo Model detected. Starting with llamacpp...
    docker-compose -f docker-compose.yml --profile local-llm %DOCKER_CMD%
) else (
    echo No model found. Starting without llamacpp.
    docker-compose -f docker-compose.yml %DOCKER_CMD%
)

echo Opening browser...
start http://localhost:5200

:: Show logs
docker-compose -f docker-compose.yml logs -f
