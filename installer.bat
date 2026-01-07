@echo off
setlocal EnableDelayedExpansion

echo ===================================================
echo     MNEMOS: Context Daemon Installer & Launcher
echo ===================================================
echo.

:: 1. Check for Container Engine (Docker or Podman)
echo [*] Checking for Container Engine...
docker --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Docker detected.
    set ENGINE=docker
    goto :GPU_CHECK
)

podman --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Podman detected.
    set ENGINE=podman
    goto :GPU_CHECK
)

:: 2. If neither, auto-install Podman
echo [!] No container engine found (Docker or Podman).
echo.
echo    This application requires a container engine.
echo    I can automatically install Podman Desktop for you.
echo.
set /p INSTALL_PODMAN="Do you want to install Podman now? (Y/N): "
if /i "%INSTALL_PODMAN%" neq "Y" (
    echo.
    echo Installation aborted by user. 
    echo Please install Docker Desktop or Podman manually.
    pause
    exit /b 1
)

echo.
echo [*] Downloading and Installing Podman...
echo     This may take a few minutes. Please wait...
echo.

:: PowerShell script to download and install Podman
powershell -Command ^
    "$url = 'https://github.com/containers/podman/releases/download/v4.9.3/podman-remote-release-windows-amd64.zip'; " ^
    "$output = 'podman-installer.zip'; " ^
    "Write-Host 'Downloading Podman...'; " ^
    "Invoke-WebRequest -Uri $url -OutFile $output; " ^
    "Write-Host 'Installing Podman...'; " ^
    "Expand-Archive -Path $output -DestinationPath 'C:\Program Files\Podman' -Force; " ^
    "Write-Host 'Adding to PATH...'; " ^
    "[Environment]::SetEnvironmentVariable('Path', $env:Path + ';C:\Program Files\Podman\bin', [EnvironmentVariableTarget]::Machine); "

:: NOTE: The above is a simplified manual install attempt for cli. 
:: A better "One Click" for Windows user is the Podman Desktop installer .exe
:: Let's switch to the Podman Desktop MSI/EXE installer for a proper GUI experience
:: Using winget is often cleaner if available, but let's stick to powershell download of the installer.

echo.
echo [!] RETRYING WITH PODMAN DESKTOP INSTALLER (More reliable)
echo.

powershell -Command ^
    "$setup = 'podman-desktop-setup.exe'; " ^
    "Write-Host 'Downloading Podman Desktop Installer...'; " ^
    "Invoke-WebRequest -Uri 'https://podman-desktop.io/api/latest/windows' -OutFile $setup; " ^
    "Write-Host 'Running Installer (Silent Mode)...'; " ^
    "Start-Process -FilePath $setup -ArgumentList '/currentuser', '/S' -Wait; " 

echo.
echo [*] Initializing Podman Machine (WSL2)...
echo     This is required for running containers.
podman machine init
podman machine start

echo.
echo [OK] Podman installed and started.
set ENGINE=podman


:GPU_CHECK
echo.
echo [*] Checking for GPU capabilities...

:: Check for nvidia-smi
where nvidia-smi >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] nvidia-smi not found.
    echo.
    echo    Hardware wont support gpu, using cpu instead.
    echo.
    goto :RUN_CPU
)

:: GPU Found - Ask User
echo [?] NVIDIA GPU detected.
set /p USE_GPU="   Hardware compatible, using GPU? (Y/N): "
if /i "%USE_GPU%"=="Y" goto :RUN_GPU
if /i "%USE_GPU%"=="YES" goto :RUN_GPU

:: User chose NO (or invalid) -> CPU
echo.
echo    Using CPU mode as requested.
goto :RUN_CPU

:RUN_GPU
echo.
echo [*] Starting MNEMOS with GPU support (%ENGINE%)...
if "%ENGINE%"=="podman" (
    :: Podman usually aliases docker commands or we use podman-compose
    :: Check for podman-compose first
    podman-compose --version >nul 2>&1
    if !errorlevel! equ 0 (
        podman-compose -f docker-compose.yml up -d --build
    ) else (
        echo [!] podman-compose not found, trying docker-compose alias...
        docker-compose -f docker-compose.yml up -d --build
    )
) else (
    docker-compose -f docker-compose.yml up -d --build
)
goto :END

:RUN_CPU
echo.
echo [*] Starting MNEMOS with CPU optimizations (%ENGINE%)...
if "%ENGINE%"=="podman" (
    podman-compose --version >nul 2>&1
    if !errorlevel! equ 0 (
        podman-compose -f docker-compose.yml -f docker-compose.cpu.yml up -d --build
    ) else (
        docker-compose -f docker-compose.yml -f docker-compose.cpu.yml up -d --build
    )
) else (
    docker-compose -f docker-compose.yml -f docker-compose.cpu.yml up -d --build
)
goto :END


:END
echo.
echo ===================================================
echo    Application is running in the background.
echo    Access it at: http://localhost:5000
echo ===================================================
pause
