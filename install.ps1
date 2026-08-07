<#
    MNEMOS one-command installer.

        irm https://raw.githubusercontent.com/qepri/mnemos/main/install.ps1 | iex

    Takes a stock Windows 11 machine to a running MNEMOS: checks WSL2, installs
    a container runtime only if none exists, downloads the repo (no git needed),
    and hands off to start-lite.bat.

    Every step checks its own postcondition first, so re-running after an
    interruption (or after the WSL2 reboot) resumes instead of redoing.

    This script bootstraps and delegates. It deliberately contains NO runtime
    detection or compose logic - runtime-detect.bat owns that, and duplicating
    it is how the two copies drift apart.
#>

[CmdletBinding()]
param(
    [string]$InstallDir = "$env:USERPROFILE\mnemos",
    [string]$Repo       = 'qepri/mnemos',
    [string]$Branch     = 'main'
)

$ErrorActionPreference = 'Stop'

function Say    { param($m) Write-Host "  $m" }
function Step   { param($m) Write-Host "`n[MNEMOS] $m" -ForegroundColor Cyan }
function Ok     { param($m) Write-Host "  OK  $m" -ForegroundColor Green }
function Warn   { param($m) Write-Host "  !   $m" -ForegroundColor Yellow }
function Fail   { param($m) Write-Host "`n[ERROR] $m" -ForegroundColor Red; exit 1 }

Write-Host @"

  MNEMOS - private document search and knowledge graph

  This will:
    1. check WSL2 (Windows' Linux layer)
    2. install Podman, only if you have no container runtime
    3. download MNEMOS to $InstallDir
    4. start it

  Nothing is sent anywhere. Everything runs on this machine.
  First run takes several minutes - it downloads and builds container images.

"@ -ForegroundColor White

# ---------------------------------------------------------------- 1. WSL2 ---
Step 'Checking WSL2...'
$wslOk = $false
try {
    wsl --status *> $null
    if ($LASTEXITCODE -eq 0) { $wslOk = $true }
} catch { $wslOk = $false }

if ($wslOk) {
    Ok 'WSL2 present.'
} else {
    Warn 'WSL2 is not enabled. Enabling it now (needs administrator rights).'
    try {
        Start-Process -FilePath 'wsl.exe' -ArgumentList '--install' -Verb RunAs -Wait
    } catch {
        Fail @"
Could not enable WSL2 automatically.
Open PowerShell as Administrator and run:  wsl --install
Then reboot and run this installer again.
"@
    }
    Write-Host @"

  WSL2 was installed. Windows needs to REBOOT before it works.

    1. Reboot now.
    2. Run this same command again - it will pick up where it left off.

"@ -ForegroundColor Yellow
    exit 0
}

# ------------------------------------------------------------- 2. Runtime ---
Step 'Checking for a container runtime...'

function Test-Cmd { param($n) [bool](Get-Command $n -ErrorAction SilentlyContinue) }

function Test-DockerUp {
    if (-not (Test-Cmd 'docker')) { return $false }
    docker info *> $null
    return ($LASTEXITCODE -eq 0)
}

if (Test-DockerUp) {
    Ok 'Docker is running - using it.'
} elseif (Test-Cmd 'podman') {
    Ok 'Podman is installed - using it.'
} elseif (Test-Path 'C:\Program Files\Docker\Docker\Docker Desktop.exe') {
    Ok 'Docker Desktop is installed (not running) - the launcher will start it.'
} else {
    Say 'No container runtime found. Installing Podman (free, no GUI, ~50 MB).'
    if (-not (Test-Cmd 'winget')) {
        Fail @"
winget is not available on this machine, so Podman cannot be installed automatically.
Install Podman manually from https://podman.io/ then run this installer again.
"@
    }
    winget install -e --id RedHat.Podman --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { Fail 'Podman installation failed.' }

    # winget updates the machine PATH but not this already-running process.
    $env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' +
                [System.Environment]::GetEnvironmentVariable('Path','User')
    if (-not (Test-Cmd 'podman')) {
        Fail 'Podman installed but is not on PATH. Open a new terminal and run this installer again.'
    }
    Ok 'Podman installed.'
}

# ---------------------------------------------------------------- 3. Repo ---
Step "Getting MNEMOS into $InstallDir ..."

# Prefer a tagged release: its zip and its published container images were
# built from the same commit, so compose files, migrations and images can
# never skew (specs/008-prebuilt-images/data-model.md). Falls back to main +
# build-from-source when the API is unreachable or no release exists yet -
# loudly, never hanging (FR-006).
$ReleaseTag = $null
try {
    $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" `
                             -TimeoutSec 10 -ErrorAction Stop
    $ReleaseTag = $rel.tag_name
    Ok "Latest release: $ReleaseTag (prebuilt images - nothing compiles on this machine)"
} catch {
    Warn 'Could not resolve a release (none published yet, or no connection to the GitHub API).'
    Warn 'Falling back to the development branch - the first start will BUILD the'
    Warn 'images from source, which takes considerably longer than pulling.'
}

if (Test-Path (Join-Path $InstallDir 'start-lite.bat')) {
    Ok 'Already downloaded - keeping what is there (your data lives here).'
} else {
    $zipUrl = if ($ReleaseTag) {
        "https://github.com/$Repo/archive/refs/tags/$ReleaseTag.zip"
    } else {
        "https://github.com/$Repo/archive/refs/heads/$Branch.zip"
    }
    $tmpZip  = Join-Path $env:TEMP "mnemos-$Branch.zip"
    $tmpDir  = Join-Path $env:TEMP "mnemos-extract-$([guid]::NewGuid().ToString('N'))"

    Say "Downloading $zipUrl"
    Say '(a few tens of MB - no git required)'
    try {
        Invoke-WebRequest -Uri $zipUrl -OutFile $tmpZip -UseBasicParsing
    } catch {
        Fail "Could not download MNEMOS from $zipUrl`n$($_.Exception.Message)"
    }

    Say 'Extracting...'
    Expand-Archive -Path $tmpZip -DestinationPath $tmpDir -Force

    # GitHub zips wrap everything in <repo>-<branch>/
    $inner = Get-ChildItem -Path $tmpDir -Directory | Select-Object -First 1
    if (-not $inner) { Fail 'Downloaded archive looked empty.' }

    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    Copy-Item -Path (Join-Path $inner.FullName '*') -Destination $InstallDir -Recurse -Force

    Remove-Item $tmpZip -Force -ErrorAction SilentlyContinue
    Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
    Ok "Downloaded to $InstallDir"
}

# -------------------------------------------------- 3b. Pin the version ---
# MNEMOS_VERSION in .env is what flips start-lite.bat onto the pulled-image
# path. The launcher normally creates .env on first run; when we install a
# release we create it here first (same preset script, called earlier, no
# duplicated logic) so the version can ride along. Idempotent: an existing
# pin is left alone.
if ($ReleaseTag) {
    $envFile = Join-Path $InstallDir '.env'
    if (-not (Test-Path $envFile)) {
        & powershell -NoProfile -ExecutionPolicy Bypass `
            -File (Join-Path $InstallDir 'presets\apply.ps1') -Preset slim
    }
    if (-not (Select-String -Path $envFile -Pattern '^MNEMOS_VERSION=' -Quiet -ErrorAction SilentlyContinue)) {
        Add-Content -Path $envFile -Value "MNEMOS_VERSION=$ReleaseTag"
        Ok "Pinned to $ReleaseTag - repo and images now come from the same commit."
    }
}

# ------------------------------------------------- 3c. The `mnemos` command ---
# A .cmd shim in WindowsApps, which is already on the user PATH on every
# Windows 10/11 box - so `mnemos` works in the shell that is open right now,
# with no PATH edit and no restart. The install path is baked in at write
# time (the shim lives outside InstallDir, so %~dp0 would point at the wrong
# place). Uninstalling the command is deleting one file.
Step 'Installing the `mnemos` command...'
$binDir = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps'
$shim   = Join-Path $binDir 'mnemos.cmd'
@"
@echo off
:: MNEMOS command shim - written by install.ps1. Holds no state; delete to remove.
setlocal
set "MNEMOS_HOME=$InstallDir"
if not exist "%MNEMOS_HOME%\start-lite.bat" goto :missing
cd /d "%MNEMOS_HOME%"

if /i "%~1"==""       goto :start
if /i "%~1"=="start"  goto :start
if /i "%~1"=="stop"   goto :stop
if /i "%~1"=="logs"   goto :logs
if /i "%~1"=="update" goto :update
if /i "%~1"=="backup" goto :backup
echo Usage: mnemos [start^|stop^|logs^|backup^|update]
exit /b 1

:start
call "%MNEMOS_HOME%\start-lite.bat"
exit /b %errorlevel%

:: stop/logs talk to compose directly, so they need the runtime picked first -
:: start-lite.bat does that itself, these do not.
:stop
call "%MNEMOS_HOME%\runtime-detect.bat" || exit /b 1
docker-compose down
exit /b %errorlevel%

:logs
call "%MNEMOS_HOME%\runtime-detect.bat" || exit /b 1
docker-compose logs -f app
exit /b %errorlevel%

:backup
powershell -NoProfile -ExecutionPolicy Bypass -File "%MNEMOS_HOME%\backup.ps1" %2 %3
exit /b %errorlevel%

:: update.ps1 does its own runtime detection where it needs one, and hands the
:: restart back to start-lite.bat rather than assembling its own compose call.
:update
powershell -NoProfile -ExecutionPolicy Bypass -File "%MNEMOS_HOME%\update.ps1"
exit /b %errorlevel%

:missing
echo MNEMOS is not installed at %MNEMOS_HOME%.
echo Reinstall:  irm https://raw.githubusercontent.com/$Repo/main/install.ps1 ^| iex
exit /b 1
"@ | Set-Content -Path $shim -Encoding ASCII

if (($env:PATH -split ';') -contains $binDir) {
    Ok 'Type `mnemos` from anywhere to start it (also: mnemos stop, mnemos logs).'
} else {
    Warn "Wrote $shim, but that folder is not on your PATH - use start-lite.bat instead."
}

# --------------------------------------------------------------- 4. Start ---
Step 'Starting MNEMOS...'
Write-Host @"
  The first start downloads and builds container images. Expect several
  minutes, and a lot of scrolling output - that is normal, not a hang.

"@ -ForegroundColor DarkGray

$launcher = Join-Path $InstallDir 'start-lite.bat'
if (-not (Test-Path $launcher)) { Fail "Launcher not found at $launcher" }

Set-Location $InstallDir
& cmd.exe /c $launcher

Write-Host @"

[MNEMOS] Done. The app is at http://localhost:5200

  Upload a PDF and search it - no AI model needed for that.
  For chat, summaries and the concept graph, connect a model in Settings.

  Start it again later:  mnemos          (stop it: mnemos stop)

"@ -ForegroundColor Green
