<#
    MNEMOS database backup.  Run it as:  mnemos backup

    The single implementation of "dump the database to a file". update.ps1
    calls this rather than carrying its own copy - two copies of a backup
    routine is two chances for one of them to silently produce an empty file
    (INSTALLER-CONSTITUTION.md, principle V).

    Only the db service is started; the app does not need to be running.
    Uploads and models are plain files on disk and are not included - this
    backs up the database, which is the part that cannot be recreated by
    re-uploading.
#>

[CmdletBinding()]
param(
    # Where to write the dump. Defaults to backups/mnemos_db_<timestamp>.sql.
    [string]$OutFile
)

$ErrorActionPreference = 'Stop'

$root = $PSScriptRoot
Set-Location $root

if (-not $OutFile) {
    $backups = Join-Path $root 'backups'
    New-Item -ItemType Directory -Force -Path $backups | Out-Null
    $OutFile = Join-Path $backups "mnemos_db_$(Get-Date -Format 'yyyyMMdd-HHmmss').sql"
} else {
    New-Item -ItemType Directory -Force -Path (Split-Path $OutFile -Parent) | Out-Null
}

Write-Host "`n[MNEMOS] Backing up the database..." -ForegroundColor Cyan

# runtime-detect.bat owns Docker-vs-Podman selection and exports DOCKER_HOST;
# it is called, never reimplemented.
$dump = "call `"$root\runtime-detect.bat`" >nul && " +
        "docker-compose up -d --wait db && " +
        "docker-compose exec -T db pg_dump -U mnemos_user mnemos_db > `"$OutFile`""
& cmd.exe /c $dump

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n[ERROR] Backup failed - the database was not dumped." -ForegroundColor Red
    Write-Host "        Check the stack is healthy:  mnemos logs`n"
    exit 1
}

# An empty or truncated dump is worse than none, because it looks like a backup.
$size = (Get-Item $OutFile -ErrorAction SilentlyContinue).Length
if (-not $size -or $size -lt 1024) {
    Write-Host "`n[ERROR] Backup at $OutFile is empty or truncated." -ForegroundColor Red
    exit 1
}

Write-Host ("  OK  $OutFile ({0:N1} MB)" -f ($size / 1MB)) -ForegroundColor Green
Write-Host @"

  Restore it with:
    docker-compose up -d --wait db
    cmd /c 'docker-compose exec -T db psql -U mnemos_user mnemos_db < "$OutFile"'

  (single quotes outside, double inside - PowerShell hands the whole line to
  cmd, which is what performs the `<` redirect. Do not swap them.)

"@ -ForegroundColor DarkGray
