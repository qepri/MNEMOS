@echo off

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

:: --- FIRST-RUN .env BOOTSTRAP (silent, medium preset) ---
if not exist ".env" (
    echo [dev] No .env found. Applying 'medium' preset. Edit .env to change.
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0presets\apply.ps1" -Preset medium
)
:: ---------------------------------------------------------

echo Starting MNEMOS in Dev Mode (Hot Reload)...
echo.

:: --- LLAMACPP PREFLIGHT ---
echo [llamacpp] Checking for updates with fallback protection...
powershell -ExecutionPolicy Bypass -File "%~dp0llamacpp-preflight.ps1"
if %errorlevel% neq 0 (
    echo [llamacpp] Preflight warning - continuing anyway
)
:: ---------------------------

:: --- AUTO CLEANUP ORPHANED IMAGES ---
echo Cleaning up orphaned images...
docker image prune -f >nul 2>&1
echo Cleaning up old unused images (keeps running containers)...
docker image prune -a -f --filter "until=168h" >nul 2>&1
:: -------------------------------------

:: --- SMART BUILD LOGIC ---
echo Checking for dependency changes...
powershell -Command "$last = Get-Item .last_build_dev -ErrorAction SilentlyContinue; $files = @('requirements.txt', 'Dockerfile', 'docker-compose.yml', 'docker-compose.dev.yml'); $newest = $files | ForEach-Object { Get-Item $_ -ErrorAction SilentlyContinue } | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if (-not $last -or ($newest.LastWriteTime -gt $last.LastWriteTime)) { exit 1 } else { exit 0 }"

if %errorlevel%==1 (
    echo [SMART BUILD] Changes detected. Rebuilding backend...
    set DOCKER_ARGS=up --no-deps --build
    type nul > .last_build_dev
) else (
    echo [SMART BUILD] No changes detected. Fast start...
    set DOCKER_ARGS=up --no-deps
)
:: -------------------------

echo Starting backend containers...
docker-compose -f docker-compose.yml %DOCKER_ARGS% app worker llamacpp mcp db redis adminer -d

echo Waiting for backend to be ready (15s)...
timeout /t 15 /nobreak >nul

:: --- LLAMACPP HEALTHCHECK ---
echo [llamacpp] Checking container health (will fall back if broken)...
powershell -ExecutionPolicy Bypass -File "%~dp0llamacpp-healthcheck.ps1"
:: ---------------------------

echo Starting Angular dev server in new window...
cd frontend_spa
if not exist node_modules (
    echo Installing frontend dependencies...
    call npm install
)
start "Angular Dev Server" cmd /k "npx ng serve -o --port 5200"
cd ..

echo Showing backend logs (Ctrl+C to stop)...
docker-compose -f docker-compose.yml logs -f app worker llamacpp
