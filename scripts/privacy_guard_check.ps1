$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$tracked = git ls-files
$violations = New-Object System.Collections.Generic.List[string]

foreach ($path in $tracked) {
    $lower = $path.ToLowerInvariant()

    if ($path -eq ".env") {
        [void]$violations.Add("$path [secret env file]")
        continue
    }

    if ($path -like "_local/*" -or $path -like "*/_local/*") {
        [void]$violations.Add("$path [local runtime output]")
        continue
    }

    if ($lower -match '\.(aac|flac|m4a|mp3|wav|mp4|ogg|opus|webm|log|key|pem)$') {
        [void]$violations.Add("$path [forbidden extension]")
        continue
    }

    if ($lower -match '(^|/)transcript(\.cleaned)?\.md$' -or
        $lower -match '(^|/)transcript\.json$' -or
        $lower -match '(^|/)notebooklm\.md$' -or
        $lower -match '(^|/)[^/]+_(transcript|log)\.md$') {
        [void]$violations.Add("$path [generated transcript artifact]")
        continue
    }
}

if ($violations.Count -gt 0) {
    Write-Host "ERROR: privacy guard blocked due to forbidden tracked files:"
    $violations | ForEach-Object { Write-Host " - $_" }
    exit 1
}

Write-Host "Privacy guard check passed: no forbidden tracked paths found."
