# Mnemos Windows Installer Script
# Installs Podman, sets up WSL2, and launches the application

param(
    [string]$InstallDir = "$env:ProgramFiles\Mnemos",
    [switch]$SkipPodmanInstall = $false
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Mnemos Installation" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This installer must be run as Administrator" -ForegroundColor Red
    Write-Host "Please right-click and select 'Run as Administrator'" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Function to check if WSL2 is installed
function Test-WSL2 {
    try {
        $wslVersion = wsl --status 2>&1
        return $wslVersion -match "WSL 2"
    } catch {
        return $false
    }
}

# Function to install/enable WSL2
function Install-WSL2 {
    Write-Host "Checking WSL2 installation..." -ForegroundColor Yellow

    if (-not (Test-WSL2)) {
        Write-Host "Installing WSL2..." -ForegroundColor Yellow

        # Enable WSL feature
        dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart

        # Enable Virtual Machine Platform
        dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

        # Set WSL2 as default
        wsl --set-default-version 2

        Write-Host "WSL2 features enabled. A system restart may be required." -ForegroundColor Green
        $needsRestart = $true
    } else {
        Write-Host "WSL2 is already installed." -ForegroundColor Green
    }
}

# Function to check if Podman is installed
function Test-Podman {
    try {
        $podmanVersion = podman --version 2>&1
        return $podmanVersion -match "podman version"
    } catch {
        return $false
    }
}

# Function to install Podman
function Install-Podman {
    if ($SkipPodmanInstall) {
        Write-Host "Skipping Podman installation (--SkipPodmanInstall flag set)" -ForegroundColor Yellow
        return
    }

    Write-Host "Checking Podman installation..." -ForegroundColor Yellow

    if (-not (Test-Podman)) {
        Write-Host "Downloading Podman for Windows..." -ForegroundColor Yellow

        # Download Podman installer
        $podmanUrl = "https://github.com/containers/podman/releases/download/v5.0.0/podman-5.0.0-setup.exe"
        $podmanInstaller = "$env:TEMP\podman-setup.exe"

        try {
            Invoke-WebRequest -Uri $podmanUrl -OutFile $podmanInstaller -UseBasicParsing

            Write-Host "Installing Podman..." -ForegroundColor Yellow
            Start-Process -FilePath $podmanInstaller -ArgumentList "/quiet", "/norestart" -Wait

            # Refresh PATH
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

            Write-Host "Podman installed successfully." -ForegroundColor Green
        } catch {
            Write-Host "ERROR: Failed to download or install Podman" -ForegroundColor Red
            Write-Host "Please download manually from: https://podman.io/getting-started/installation" -ForegroundColor Yellow
            throw
        }
    } else {
        Write-Host "Podman is already installed." -ForegroundColor Green
    }
}

# Function to initialize Podman Machine
function Initialize-PodmanMachine {
    Write-Host "Initializing Podman Machine..." -ForegroundColor Yellow

    # Check if machine exists
    $machines = podman machine list --format json 2>&1 | ConvertFrom-Json
    $machineExists = $machines | Where-Object { $_.Name -eq "mnemos-machine" }

    if (-not $machineExists) {
        Write-Host "Creating Podman machine 'mnemos-machine'..." -ForegroundColor Yellow

        # Create machine with sufficient resources
        podman machine init mnemos-machine --cpus 4 --memory 8192 --disk-size 100

        Write-Host "Starting Podman machine..." -ForegroundColor Yellow
        podman machine start mnemos-machine
    } else {
        Write-Host "Podman machine already exists." -ForegroundColor Green

        # Check if running
        $runningMachine = $machines | Where-Object { $_.Name -eq "mnemos-machine" -and $_.Running -eq $true }
        if (-not $runningMachine) {
            Write-Host "Starting Podman machine..." -ForegroundColor Yellow
            podman machine start mnemos-machine
        }
    }

    Write-Host "Podman machine is ready." -ForegroundColor Green
}

# Function to check NVIDIA GPU support
function Test-NvidiaGPU {
    try {
        $nvidiaCheck = nvidia-smi 2>&1
        return $nvidiaCheck -match "NVIDIA"
    } catch {
        return $false
    }
}

# Function to setup GPU support
function Setup-GPUSupport {
    Write-Host "Checking NVIDIA GPU support..." -ForegroundColor Yellow

    if (Test-NvidiaGPU) {
        Write-Host "NVIDIA GPU detected." -ForegroundColor Green
        Write-Host "NOTE: Ensure NVIDIA Container Toolkit is installed in WSL2" -ForegroundColor Yellow
        Write-Host "Visit: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html" -ForegroundColor Cyan
    } else {
        Write-Host "WARNING: No NVIDIA GPU detected. GPU features will be disabled." -ForegroundColor Yellow
    }
}

# Function to copy application files
function Copy-ApplicationFiles {
    Write-Host "Copying application files to $InstallDir..." -ForegroundColor Yellow

    if (-not (Test-Path $InstallDir)) {
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }

    # Copy all application files (assumes this script is in installer/ subdirectory)
    $sourceDir = Split-Path -Parent $PSScriptRoot

    Copy-Item -Path "$sourceDir\*" -Destination $InstallDir -Recurse -Force -Exclude @("installer", "dist", "node_modules", ".git", "__pycache__", "*.pyc")

    Write-Host "Application files copied." -ForegroundColor Green
}

# Function to create startup script
function Create-StartupScript {
    Write-Host "Creating startup scripts..." -ForegroundColor Yellow

    $startScript = @"
@echo off
echo Starting Mnemos...
cd /d "$InstallDir"

REM Check if Podman machine is running
podman machine list | findstr /C:"mnemos-machine" | findstr /C:"Running" >nul
if errorlevel 1 (
    echo Starting Podman machine...
    podman machine start mnemos-machine
    timeout /t 10 /nobreak >nul
)

REM Start the application
echo Launching Mnemos containers...
podman-compose -f docker-compose.podman.yml up -d

echo.
echo ========================================
echo   Mnemos is starting!
echo ========================================
echo.
echo   Web Interface: http://localhost:5200
echo   API: http://localhost:5000
echo   Adminer: http://localhost:8080
echo.
echo Press any key to open the web interface...
pause >nul
start http://localhost:5200
"@

    $startScript | Out-File -FilePath "$InstallDir\start-mnemos.bat" -Encoding ASCII

    $stopScript = @"
@echo off
echo Stopping Mnemos...
cd /d "$InstallDir"
podman-compose -f docker-compose.podman.yml down
echo Mnemos stopped.
pause
"@

    $stopScript | Out-File -FilePath "$InstallDir\stop-mnemos.bat" -Encoding ASCII

    # Create desktop shortcut
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("$env:Public\Desktop\Mnemos.lnk")
    $Shortcut.TargetPath = "$InstallDir\start-mnemos.bat"
    $Shortcut.WorkingDirectory = $InstallDir
    $Shortcut.IconLocation = "$InstallDir\icon.ico,0"
    $Shortcut.Description = "Start Mnemos Application"
    $Shortcut.Save()

    Write-Host "Startup scripts created." -ForegroundColor Green
}

# Function to create environment file
function Create-EnvironmentFile {
    Write-Host "Creating environment configuration..." -ForegroundColor Yellow

    $envFile = "$InstallDir\.env"

    if (-not (Test-Path $envFile)) {
        $envContent = @"
# Mnemos Configuration
FLASK_ENV=production
DATABASE_URL=postgresql://mnemos_user:mnemos_pass@db:5432/mnemos_db
REDIS_URL=redis://redis:6379/0
OLLAMA_NUM_CTX=2048
EMBEDDING_PROVIDER=local
EMBEDDING_DEVICE=cuda
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIMENSION=1024
"@

        $envContent | Out-File -FilePath $envFile -Encoding ASCII
        Write-Host "Environment file created at $envFile" -ForegroundColor Green
    } else {
        Write-Host "Environment file already exists." -ForegroundColor Yellow
    }
}

# Main installation flow
try {
    Write-Host "Step 1: Installing WSL2..." -ForegroundColor Cyan
    Install-WSL2

    Write-Host ""
    Write-Host "Step 2: Installing Podman..." -ForegroundColor Cyan
    Install-Podman

    Write-Host ""
    Write-Host "Step 3: Initializing Podman Machine..." -ForegroundColor Cyan
    Initialize-PodmanMachine

    Write-Host ""
    Write-Host "Step 4: Checking GPU Support..." -ForegroundColor Cyan
    Setup-GPUSupport

    Write-Host ""
    Write-Host "Step 5: Installing Application..." -ForegroundColor Cyan
    Copy-ApplicationFiles
    Create-EnvironmentFile
    Create-StartupScript

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Installation Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Mnemos has been installed to: $InstallDir" -ForegroundColor White
    Write-Host ""
    Write-Host "To start Mnemos:" -ForegroundColor Yellow
    Write-Host "  - Use the desktop shortcut 'Mnemos'" -ForegroundColor White
    Write-Host "  - Or run: $InstallDir\start-mnemos.bat" -ForegroundColor White
    Write-Host ""
    Write-Host "To stop Mnemos:" -ForegroundColor Yellow
    Write-Host "  - Run: $InstallDir\stop-mnemos.bat" -ForegroundColor White
    Write-Host ""

    if ($needsRestart) {
        Write-Host "NOTE: A system restart is required to complete WSL2 installation." -ForegroundColor Red
        $restart = Read-Host "Would you like to restart now? (Y/N)"
        if ($restart -eq "Y" -or $restart -eq "y") {
            Restart-Computer
        }
    }

} catch {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "  Installation Failed" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Read-Host "Press Enter to exit"
