# Quick Test Script for Podman
# Run this to test Podman alongside your existing Docker setup

param(
    [switch]$Stop,
    [switch]$Status,
    [switch]$Logs
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Mnemos Podman Test Helper" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Podman is installed
try {
    $podmanVersion = podman --version
    Write-Host "Podman: $podmanVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Podman not found!" -ForegroundColor Red
    Write-Host "Install with: winget install RedHat.Podman" -ForegroundColor Yellow
    exit 1
}

# Check if Podman machine exists
$machines = podman machine list --format json 2>&1
if ($LASTEXITCODE -eq 0) {
    $machineList = $machines | ConvertFrom-Json
    $testMachine = $machineList | Where-Object { $_.Name -eq "test-machine" }

    if (-not $testMachine) {
        Write-Host "Creating Podman test machine..." -ForegroundColor Yellow
        podman machine init test-machine --cpus 4 --memory 8192 --disk-size 100
        Write-Host "Starting machine..." -ForegroundColor Yellow
        podman machine start test-machine
        Write-Host "Machine created and started." -ForegroundColor Green
    } else {
        if (-not $testMachine.Running) {
            Write-Host "Starting Podman machine..." -ForegroundColor Yellow
            podman machine start test-machine
        } else {
            Write-Host "Podman machine is running." -ForegroundColor Green
        }
    }
}

Write-Host ""

# Handle commands
if ($Stop) {
    Write-Host "Stopping Podman containers..." -ForegroundColor Yellow
    $scriptDir = Split-Path -Parent $PSScriptRoot
    Set-Location $scriptDir
    podman-compose -f installer\docker-compose.podman.test.yml down
    Write-Host ""
    Write-Host "Containers stopped." -ForegroundColor Green
    Write-Host "Your Docker setup is unaffected and ready to use." -ForegroundColor Cyan
    exit 0
}

if ($Status) {
    Write-Host "Podman Container Status:" -ForegroundColor Cyan
    Write-Host ""
    $scriptDir = Split-Path -Parent $PSScriptRoot
    Set-Location $scriptDir
    podman-compose -f installer\docker-compose.podman.test.yml ps
    Write-Host ""
    Write-Host "Port Mappings:" -ForegroundColor Cyan
    Write-Host "  Frontend:  http://localhost:5201" -ForegroundColor White
    Write-Host "  API:       http://localhost:5001" -ForegroundColor White
    Write-Host "  Database:  localhost:5434" -ForegroundColor White
    Write-Host "  Redis:     localhost:6381" -ForegroundColor White
    Write-Host "  Adminer:   http://localhost:8081" -ForegroundColor White
    Write-Host "  Ollama:    http://localhost:11436" -ForegroundColor White
    Write-Host "  MCP:       http://localhost:3001" -ForegroundColor White
    exit 0
}

if ($Logs) {
    Write-Host "Showing container logs (Ctrl+C to exit)..." -ForegroundColor Yellow
    Write-Host ""
    $scriptDir = Split-Path -Parent $PSScriptRoot
    Set-Location $scriptDir
    podman-compose -f installer\docker-compose.podman.test.yml logs -f
    exit 0
}

# Default: Start containers
Write-Host "Port Configuration (avoids Docker conflicts):" -ForegroundColor Cyan
Write-Host "  Frontend:  5201 (Docker: 5200)" -ForegroundColor Gray
Write-Host "  API:       5001 (Docker: 5000)" -ForegroundColor Gray
Write-Host "  Database:  5434 (Docker: 5433)" -ForegroundColor Gray
Write-Host "  Redis:     6381 (Docker: 6380)" -ForegroundColor Gray
Write-Host "  Adminer:   8081 (Docker: 8080)" -ForegroundColor Gray
Write-Host "  Ollama:    11436 (Docker: 11435)" -ForegroundColor Gray
Write-Host "  MCP:       3001 (Docker: 3000)" -ForegroundColor Gray
Write-Host ""

Write-Host "Starting Podman containers..." -ForegroundColor Yellow
Write-Host "(This may take a few minutes on first run)" -ForegroundColor Gray
Write-Host ""

# Navigate to project root
$scriptDir = Split-Path -Parent $PSScriptRoot
Set-Location $scriptDir

podman-compose -f installer\docker-compose.podman.test.yml up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Podman Stack Started!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Access your application:" -ForegroundColor Yellow
    Write-Host "  Frontend:  http://localhost:5201" -ForegroundColor White
    Write-Host "  API:       http://localhost:5001/api" -ForegroundColor White
    Write-Host "  Adminer:   http://localhost:8081" -ForegroundColor White
    Write-Host ""
    Write-Host "Useful commands:" -ForegroundColor Yellow
    Write-Host "  View status:   .\test-podman.ps1 -Status" -ForegroundColor White
    Write-Host "  View logs:     .\test-podman.ps1 -Logs" -ForegroundColor White
    Write-Host "  Stop:          .\test-podman.ps1 -Stop" -ForegroundColor White
    Write-Host ""
    Write-Host "Your Docker setup on ports 5000, 5200, etc. is unaffected!" -ForegroundColor Cyan
    Write-Host ""

    # Wait a moment then open browser
    Start-Sleep -Seconds 3
    Write-Host "Opening browser..." -ForegroundColor Yellow
    Start-Process "http://localhost:5201"
} else {
    Write-Host ""
    Write-Host "ERROR: Failed to start containers" -ForegroundColor Red
    Write-Host "Check logs with: .\test-podman.ps1 -Logs" -ForegroundColor Yellow
    exit 1
}
