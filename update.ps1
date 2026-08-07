<#
    MNEMOS updater.  Run it as:  mnemos update

    Moves an installed MNEMOS from the release it is pinned to onto the latest
    published one: backs up the database, overlays the new tag's files, repins
    MNEMOS_VERSION, and hands off to start-lite.bat to pull and restart.

    Deliberately manual. Nothing here runs on a schedule or at startup - an
    update mutates the user's only copy of their library, so a human asks for
    it (INSTALLER-CONSTITUTION.md, principle III).

    No automatic rollback either, on purpose: rollback code runs only when
    things are already broken and would be the least-tested path in the
    program. The backup is taken first and its path is printed, so recovery is
    a decision a person makes with the data still on disk (principle II).

    Self-overwrite is safe: PowerShell parses a script file completely before
    executing it, so replacing update.ps1 mid-run does not affect this run.
#>

[CmdletBinding()]
param(
    [string]$Repo = 'qepri/MNEMOS',
    [switch]$Yes            # non-interactive: skip the confirmation prompt
)

$ErrorActionPreference = 'Stop'

function Say  { param($m) Write-Host "  $m" }
function Step { param($m) Write-Host "`n[MNEMOS] $m" -ForegroundColor Cyan }
function Ok   { param($m) Write-Host "  OK  $m" -ForegroundColor Green }
function Warn { param($m) Write-Host "  !   $m" -ForegroundColor Yellow }
function Fail { param($m) Write-Host "`n[ERROR] $m" -ForegroundColor Red; exit 1 }

# The script lives in the install directory, so it needs no baked-in path.
$root    = $PSScriptRoot
$envFile = Join-Path $root '.env'
Set-Location $root

# ------------------------------------------------- 1. What is installed? ---
if (-not (Test-Path $envFile)) { Fail "No .env in $root - this does not look like a MNEMOS install." }

$envLines = Get-Content $envFile
$current  = ($envLines | Where-Object { $_ -match '^MNEMOS_VERSION=' } |
             Select-Object -First 1) -replace '^MNEMOS_VERSION=', ''

if (-not $current) {
    Write-Host @"

  This install has no MNEMOS_VERSION pin, which means it builds from source -
  a development checkout, not a release install.

  Update it with git instead:

      git pull
      start.bat

"@ -ForegroundColor Yellow
    exit 1
}
Say "Installed: $current"

# ------------------------------------------------------ 2. What is new? ---
Step 'Checking for a newer release...'
try {
    $rel    = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" `
                                -TimeoutSec 10 -ErrorAction Stop
    $latest = $rel.tag_name
} catch {
    Fail "Could not reach the GitHub API to check for updates.`n        $($_.Exception.Message)"
}

if ($latest -eq $current) {
    Ok "Already on the latest release ($current). Nothing to do."
    exit 0
}
Say "Available: $latest"

if (-not $Yes) {
    Write-Host @"

  This will update MNEMOS from $current to $latest.

    - your database is backed up first, and the path printed
    - your documents, uploads and .env settings are left untouched
    - the app restarts on the new version, which may apply schema migrations

"@
    $answer = Read-Host '  Continue? [y/N]'
    if ($answer -notmatch '^(y|yes)$') { Say 'Cancelled. Nothing was changed.'; exit 0 }
}

# ---------------------------------------------------------- 3. Back up ---
# Before anything else. Migrations run automatically when the app container
# starts, so once the new images are up the schema has already changed.
# backup.ps1 is the one implementation of "dump the database"; it verifies the
# dump is non-empty and fails loudly by itself (principle V).
$stamp  = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $root "backups\mnemos_db_${current}_$stamp.sql"

& powershell -NoProfile -ExecutionPolicy Bypass `
    -File (Join-Path $root 'backup.ps1') -OutFile $backup
if ($LASTEXITCODE -ne 0) { Fail 'Database backup failed - stopping before anything was changed.' }

# ------------------------------------------------- 4. Overlay new files ---
Step "Downloading $latest..."
$tmpZip = Join-Path $env:TEMP "mnemos-$latest.zip"
$tmpDir = Join-Path $env:TEMP "mnemos-update-$([guid]::NewGuid().ToString('N'))"
try {
    Invoke-WebRequest -Uri "https://github.com/$Repo/archive/refs/tags/$latest.zip" `
                      -OutFile $tmpZip -UseBasicParsing
    Expand-Archive -Path $tmpZip -DestinationPath $tmpDir -Force
} catch {
    Fail "Download failed - nothing was changed.`n        $($_.Exception.Message)`n        Your backup is at $backup"
}

$inner = Get-ChildItem -Path $tmpDir -Directory | Select-Object -First 1
if (-not $inner) { Fail "Downloaded archive looked empty - nothing was changed." }

# Overlay, never clear. Copy-Item -Force overwrites only files present in the
# archive; .env, uploads/, backups/ and models/ are not in it and so survive
# untouched (principle I).
Step 'Installing new files...'
Copy-Item -Path (Join-Path $inner.FullName '*') -Destination $root -Recurse -Force
Remove-Item $tmpZip -Force -ErrorAction SilentlyContinue
Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
Ok 'Files updated.'

# Repin: rewrite exactly the one line, preserving every other byte of .env.
(Get-Content $envFile) -replace '^MNEMOS_VERSION=.*', "MNEMOS_VERSION=$latest" |
    Set-Content $envFile
Ok "Pinned to $latest."

# --------------------------------------------------------- 5. Restart ---
# start-lite.bat already knows the release path (it reads MNEMOS_VERSION) and
# passes --no-build, so a failed pull errors instead of compiling for an hour.
Step 'Pulling images and restarting...'
& cmd.exe /c (Join-Path $root 'start-lite.bat')
if ($LASTEXITCODE -ne 0) {
    Write-Host @"

[ERROR] MNEMOS did not come back up on $latest.

  Your data is intact on disk and your backup is at:
    $backup

  See what went wrong:
    mnemos logs

  To restore the database from the backup:
    cd $root
    docker-compose up -d --wait db
    cmd /c 'docker-compose exec -T db psql -U mnemos_user mnemos_db < "$backup"'

"@ -ForegroundColor Red
    exit 1
}

Write-Host @"

[MNEMOS] Updated $current -> $latest. The app is at http://localhost:5200

  Backup of the previous database: $backup

"@ -ForegroundColor Green
