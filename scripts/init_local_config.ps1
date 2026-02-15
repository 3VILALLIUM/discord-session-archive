$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$envFile = ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item ".env.example" $envFile
    Write-Host "Created .env from .env.example"
} else {
    Write-Host ".env already exists; leaving unchanged"
}

$configDir = "_local/config"
if (-not (Test-Path $configDir)) {
    New-Item -ItemType Directory -Path $configDir -Force | Out-Null
    Write-Host "Created $configDir"
}

$handleMapPath = Join-Path $configDir "handle_map.json"
if (-not (Test-Path $handleMapPath)) {
    @'
{
  "speaker one": "alpha_handle",
  "speaker two": "beta_handle"
}
'@ | Set-Content -Path $handleMapPath -Encoding utf8
    Write-Host "Created $handleMapPath"
} else {
    Write-Host "$handleMapPath already exists; leaving unchanged"
}

$realnameMapPath = Join-Path $configDir "realname_map.json"
if (-not (Test-Path $realnameMapPath)) {
    @'
{
  "speaker one": "Alice Carter",
  "speaker two": "Bob Rivera"
}
'@ | Set-Content -Path $realnameMapPath -Encoding utf8
    Write-Host "Created $realnameMapPath"
} else {
    Write-Host "$realnameMapPath already exists; leaving unchanged"
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Edit .env and set OPENAI_API_KEY"
Write-Host "2. Edit _local/config/handle_map.json and _local/config/realname_map.json"
Write-Host "3. Choose map mode per run with --name-map-mode none|handle|real"
