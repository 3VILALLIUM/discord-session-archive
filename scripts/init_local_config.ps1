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

$utf8NoBom = New-Object System.Text.UTF8Encoding $false

$handleMapPath = Join-Path $configDir "handle_map.json"
if (-not (Test-Path $handleMapPath)) {
    $handleMapContent = @'
{
  "__comment_1": "Handle map: replace Discord handles/labels with your preferred names.",
  "__comment_2": "Keys are aliases; values are the preferred output speaker labels.",
  "__comment_3": "Add variants (with/without @, hyphen, underscore, spacing) for reliability.",
  "speaker one": "Example Preferred Name One",
  "@speaker-one": "Example Preferred Name One",
  "speaker two": "Example Preferred Name Two"
}
'@
    [System.IO.File]::WriteAllText($handleMapPath, $handleMapContent, $utf8NoBom)
    Write-Host "Created $handleMapPath"
} else {
    Write-Host "$handleMapPath already exists; leaving unchanged"
}

$realnameMapPath = Join-Path $configDir "realname_map.json"
if (-not (Test-Path $realnameMapPath)) {
    $realnameMapContent = @'
{
  "__comment_1": "Real-name map: optionally replace spoken-name labels with preferred real names.",
  "__comment_2": "Keys are aliases; values are canonical output speaker labels.",
  "__comment_3": "Transcript text is unchanged; only speaker labels are remapped.",
  "speaker one": "Example Person One",
  "example person one": "Example Person One",
  "speaker two": "Example Person Two"
}
'@
    [System.IO.File]::WriteAllText($realnameMapPath, $realnameMapContent, $utf8NoBom)
    Write-Host "Created $realnameMapPath"
} else {
    Write-Host "$realnameMapPath already exists; leaving unchanged"
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Edit .env and set OPENAI_API_KEY"
Write-Host "2. Edit _local/config/handle_map.json and _local/config/realname_map.json"
Write-Host "3. Choose map mode per run with --name-map-mode none|handle|real"
