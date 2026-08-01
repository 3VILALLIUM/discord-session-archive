$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$envFile = Join-Path $repoRoot ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $repoRoot ".env.example") $envFile
    Write-Host "Created .env from .env.example"
} else {
    Write-Host ".env already exists; leaving unchanged"
}

$configDir = Join-Path $repoRoot "_local/config"
if (-not (Test-Path $configDir)) {
    New-Item -ItemType Directory -Path $configDir -Force | Out-Null
    Write-Host "Created _local/config"
}

$nameMapsDir = Join-Path $configDir "name_maps"
if (Test-Path $nameMapsDir) {
    if (-not (Test-Path $nameMapsDir -PathType Container)) {
        throw "_local/config/name_maps exists but is not a directory"
    }
    Write-Host "_local/config/name_maps already exists; leaving unchanged"
} else {
    New-Item -ItemType Directory -Path $nameMapsDir -Force | Out-Null
    Write-Host "Created _local/config/name_maps"
}

$utf8NoBom = New-Object System.Text.UTF8Encoding $false

$nameReplaceMapPath = Join-Path $configDir "name_replace_map.json"
if (-not (Test-Path $nameReplaceMapPath)) {
    $nameReplaceMapContent = @'
{
  "__comment_1": "Unified replacement map for handle aliases and spoken-name aliases.",
  "__comment_2": "Keys are aliases; values are canonical output speaker labels.",
  "__comment_3": "Add variants (with/without @, hyphen, underscore, spacing) for reliability.",
  "@speaker-one": "Example Preferred Name One",
  "speaker one": "Example Preferred Name One",
  "example person one": "Example Preferred Name One",
  "speaker two": "Example Preferred Name Two"
}
'@
    [System.IO.File]::WriteAllText($nameReplaceMapPath, $nameReplaceMapContent, $utf8NoBom)
    Write-Host "Created _local/config/name_replace_map.json"
} else {
    Write-Host "_local/config/name_replace_map.json already exists; leaving unchanged"
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Edit .env and set OPENAI_API_KEY"
Write-Host "2. Edit _local/config/name_replace_map.json, or create _local/config/name_maps/<profile>.json"
Write-Host "3. Run default replacement, or add --name-map-profile <profile>"
Write-Host "4. Use --name-map-mode none to disable replacement"
