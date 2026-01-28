# Quick build script for Mnemos Windows Installer
# This script automates the build process

param(
    [switch]$BundleImages = $false,
    [switch]$SkipTests = $false
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Mnemos Installer Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
Write-Host "Checking prerequisites..." -ForegroundColor Yellow

# Check NSIS
$nsisPath = $null
$possiblePaths = @(
    "C:\Program Files (x86)\NSIS\makensis.exe",
    "C:\Program Files\NSIS\makensis.exe",
    "$env:ProgramFiles\NSIS\makensis.exe",
    "${env:ProgramFiles(x86)}\NSIS\makensis.exe"
)

foreach ($path in $possiblePaths) {
    if (Test-Path $path) {
        $nsisPath = $path
        break
    }
}

if (-not $nsisPath) {
    try {
        makensis /VERSION 2>&1 | Out-Null
        $nsisPath = "makensis"
    }
    catch {
        Write-Host "X NSIS not found!" -ForegroundColor Red
        Write-Host "  NSIS is installed but not in PATH" -ForegroundColor Yellow
        Write-Host "  Try restarting PowerShell or manually add to PATH" -ForegroundColor Yellow
        exit 1
    }
}

try {
    $nsisVersion = & $nsisPath /VERSION 2>&1
    Write-Host "OK NSIS found: v$nsisVersion" -ForegroundColor Green
}
catch {
    Write-Host "X NSIS execution failed!" -ForegroundColor Red
    exit 1
}

# Check Docker (for building images)
if ($BundleImages) {
    try {
        $dockerVersion = docker --version
        Write-Host "OK Docker found: $dockerVersion" -ForegroundColor Green
    }
    catch {
        Write-Host "X Docker not found!" -ForegroundColor Red
        Write-Host "  Docker is required for bundling images" -ForegroundColor Yellow
        exit 1
    }
}

# Navigate to project root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
Set-Location $projectRoot

Write-Host "Project root: $projectRoot" -ForegroundColor Gray
Write-Host ""

# Create dist directory
Write-Host "Creating dist directory..." -ForegroundColor Yellow
if (-not (Test-Path "dist")) {
    New-Item -ItemType Directory -Path "dist" | Out-Null
}
Write-Host "OK Dist directory ready" -ForegroundColor Green

# Bundle images if requested
if ($BundleImages) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Bundling Container Images" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "This will take several minutes and produce a ~3-5GB installer" -ForegroundColor Yellow
    Write-Host ""

    $images = @(
        @{Name="mnemos-app"; Build=$true; Dockerfile="."; Output="dist\mnemos-app.tar"},
        @{Name="mnemos-frontend"; Build=$true; Dockerfile="frontend_spa"; Output="dist\mnemos-frontend.tar"},
        @{Name="pgvector/pgvector:pg16"; Build=$false; Output="dist\pgvector.tar"},
        @{Name="redis:7-alpine"; Build=$false; Output="dist\redis.tar"},
        @{Name="ollama/ollama:latest"; Build=$false; Output="dist\ollama.tar"},
        @{Name="adminer"; Build=$false; Output="dist\adminer.tar"}
    )

    foreach ($img in $images) {
        Write-Host "Processing: $($img.Name)" -ForegroundColor Yellow

        if ($img.Build) {
            Write-Host "  Building image..." -ForegroundColor Gray
            docker build -t "$($img.Name):latest" $img.Dockerfile
        }
        else {
            Write-Host "  Pulling image..." -ForegroundColor Gray
            docker pull $img.Name
        }

        Write-Host "  Saving to tar..." -ForegroundColor Gray
        docker save $img.Name -o $img.Output

        $size = (Get-Item $img.Output).Length / 1MB
        Write-Host "  OK Saved ($([math]::Round($size, 2)) MB)" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "OK All images bundled" -ForegroundColor Green
}

# Build installer
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Building NSIS Installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Running makensis..." -ForegroundColor Yellow
& $nsisPath installer\mnemos-installer.nsi

if ($LASTEXITCODE -eq 0) {
    Write-Host "OK Installer built successfully" -ForegroundColor Green

    # Calculate file size
    $installerPath = "dist\Mnemos-Setup.exe"
    $size = (Get-Item $installerPath).Length / 1MB
    Write-Host ""
    Write-Host "Installer: $installerPath" -ForegroundColor White
    Write-Host "Size: $([math]::Round($size, 2)) MB" -ForegroundColor White

    # Generate SHA256 checksum
    Write-Host ""
    Write-Host "Generating checksum..." -ForegroundColor Yellow
    $hash = (Get-FileHash $installerPath -Algorithm SHA256).Hash
    $hash | Out-File "$installerPath.sha256" -Encoding ASCII
    Write-Host "OK Checksum: $hash" -ForegroundColor Green

}
else {
    Write-Host "X Installer build failed" -ForegroundColor Red
    exit 1
}

# Run basic tests
if (-not $SkipTests) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Running Basic Tests" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""

    Write-Host "Checking installer integrity..." -ForegroundColor Yellow

    # Verify file exists and is not empty
    if ((Test-Path $installerPath) -and ((Get-Item $installerPath).Length -gt 0)) {
        Write-Host "OK Installer file valid" -ForegroundColor Green
    }
    else {
        Write-Host "X Installer file invalid" -ForegroundColor Red
        exit 1
    }

    # Check if installer is executable
    $fileInfo = Get-Item $installerPath
    if ($fileInfo.Extension -eq ".exe") {
        Write-Host "OK Installer is executable" -ForegroundColor Green
    }
    else {
        Write-Host "X Installer is not executable" -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "OK All tests passed" -ForegroundColor Green
}

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Build Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Installer: dist\Mnemos-Setup.exe" -ForegroundColor White
Write-Host "Checksum: dist\Mnemos-Setup.exe.sha256" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Test the installer on a clean Windows machine" -ForegroundColor White
Write-Host "  2. (Optional) Sign the executable with a code signing certificate" -ForegroundColor White
Write-Host "  3. Distribute via GitHub Releases or your website" -ForegroundColor White
Write-Host ""
