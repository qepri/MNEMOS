@echo off
:: Shared container-runtime detection. Called by start.bat and start-lite.bat.
::
:: Sets, for the caller:
::   MNEMOS_DETECTED_RUNTIME = docker | podman
::   DOCKER_HOST             = podman's compat socket (podman branch only)
:: Exits 1 with a printed explanation when no runtime is usable.
::
:: Docker outranks Podman ON PURPOSE. Named volumes (postgres_data) are
:: runtime-bound: on a machine with both, preferring Podman boots an EMPTY
:: database and the user's indexed library appears to have vanished. Preferring
:: whichever runtime owns the existing data is the only default that cannot
:: lose anything. Do not reorder without reading specs/007-podman-runtime/data-model.md.

set "MNEMOS_DETECTED_RUNTIME="

:: --- Explicit override: the user made a deliberate choice about where their
::     data lives, so never silently fall through to the other runtime. ---
if /I "%MNEMOS_RUNTIME%"=="docker" goto :want_docker
if /I "%MNEMOS_RUNTIME%"=="podman" goto :want_podman
if not "%MNEMOS_RUNTIME%"=="" (
    echo [ERROR] MNEMOS_RUNTIME is set to "%MNEMOS_RUNTIME%" - expected "docker" or "podman".
    exit /b 1
)

:: --- 1. Docker already running? Common case, checked first, no added latency. ---
docker info >nul 2>&1
if %errorlevel% equ 0 (
    set "MNEMOS_DETECTED_RUNTIME=docker"
    exit /b 0
)

:: --- 2. Docker Desktop installed but stopped: launch and wait. ---
if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
    echo Docker Desktop is installed but not running. Launching it...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo Waiting for Docker to be ready...
    :wait_docker
    timeout /t 5 /nobreak >nul
    docker info >nul 2>&1
    if %errorlevel% neq 0 goto wait_docker
    echo Docker Desktop is now ready.
    set "MNEMOS_DETECTED_RUNTIME=docker"
    exit /b 0
)

:: --- 3. Podman. Note: a leftover podman-machine-default WSL distro can exist
::     with no podman.exe (an old install that was removed). Keying off the CLI
::     rather than the distro makes that state fall through to guidance. ---
where podman >nul 2>&1
if %errorlevel% equ 0 goto :use_podman

goto :no_runtime


:want_docker
docker info >nul 2>&1
if %errorlevel% equ 0 (
    set "MNEMOS_DETECTED_RUNTIME=docker"
    exit /b 0
)
echo [ERROR] MNEMOS_RUNTIME=docker but the Docker daemon is not reachable.
echo         Start Docker Desktop, or unset MNEMOS_RUNTIME to auto-detect.
exit /b 1


:want_podman
where podman >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] MNEMOS_RUNTIME=podman but podman is not installed.
    echo         Install it with:  winget install RedHat.Podman
    exit /b 1
)
goto :use_podman


:use_podman
:: Machine may be absent (fresh install) or merely stopped.
podman machine inspect podman-machine-default >nul 2>&1
if %errorlevel% neq 0 (
    echo [podman] No machine found. Creating one - this downloads a small Linux
    echo          image and takes a few minutes on first run.
    podman machine init
    if %errorlevel% neq 0 (
        echo [ERROR] podman machine init failed. WSL2 may not be enabled.
        echo         Enable it with:  wsl --install
        exit /b 1
    )
)

podman info >nul 2>&1
if %errorlevel% neq 0 (
    echo [podman] Starting the Podman machine...
    podman machine start >nul 2>&1
    podman info >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Podman is installed but its machine will not start.
        echo         Try:  podman machine start
        exit /b 1
    )
)

:: Podman publishes a Docker-compatible API socket. The named pipe is
:: machine-specific because Docker Desktop, when installed, already owns the
:: default docker_engine pipe.
set "DOCKER_HOST=npipe:////./pipe/podman-machine-default"
set "MNEMOS_DETECTED_RUNTIME=podman"
exit /b 0


:no_runtime
echo.
echo =================================================================
echo   MNEMOS needs a container runtime. Two options - either works,
echo   and MNEMOS behaves identically on both.
echo.
echo   Podman (lighter, no GUI, installs from the terminal):
echo       winget install RedHat.Podman
echo     ...then run this script again.
echo.
echo   Docker Desktop (graphical, heavier):
echo       https://docs.docker.com/desktop/setup/install/windows-install/
echo =================================================================
echo.
exit /b 1
