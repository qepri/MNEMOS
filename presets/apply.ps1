param(
    [Parameter(Mandatory=$true)][string]$Preset
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$example = Join-Path $root ".env.example"
$envFile = Join-Path $root ".env"
$presetFile = Join-Path $PSScriptRoot "$Preset.env"

if (-not (Test-Path $example))    { Write-Error ".env.example missing"; exit 1 }
if (-not (Test-Path $presetFile)) { Write-Error "Preset '$Preset' not found at $presetFile"; exit 1 }

$content = Get-Content $example -Raw

# Apply preset overrides: replace existing KEY=... line, or append.
Get-Content $presetFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $parts = $line -split "=", 2
    $key = $parts[0]
    $val = $parts[1]
    $pattern = "(?m)^" + [regex]::Escape($key) + "=.*$"
    $replacement = "$key=$val"
    if ([regex]::IsMatch($content, $pattern)) {
        $content = [regex]::Replace($content, $pattern, { param($m) $replacement })
    } else {
        $content = $content.TrimEnd() + "`n$replacement`n"
    }
}

# Randomize SECRET_KEY
$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$secret = [Convert]::ToBase64String($bytes)
$content = [regex]::Replace($content, "(?m)^SECRET_KEY=.*$", { param($m) "SECRET_KEY=$secret" })

Set-Content -Path $envFile -Value $content -Encoding utf8 -NoNewline
Write-Host "Created .env from preset '$Preset' with randomized SECRET_KEY."
