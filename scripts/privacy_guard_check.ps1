$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$tracked = git ls-files
$violations = New-Object System.Collections.Generic.List[string]

foreach ($path in $tracked) {
    $lower = $path.ToLowerInvariant()

    if ($lower -match '(^|/)\.env($|\..+)' -and $lower -notmatch '(^|/)\.env\.example$') {
        [void]$violations.Add("$path [secret env file variant]")
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

$secretPatterns = @(
    'sk-[A-Za-z0-9]{20,}',
    'gh[pousr]_[A-Za-z0-9]{20,}',
    'AKIA[0-9A-Z]{16}',
    'ASIA[0-9A-Z]{16}',
    'xox[baprs]-[A-Za-z0-9-]{10,}',
    '-----BEGIN (RSA|DSA|EC|OPENSSH|PGP) PRIVATE KEY-----'
)

foreach ($pattern in $secretPatterns) {
    $grepHits = @(& git grep -nI -E -- $pattern)
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        foreach ($hit in $grepHits) {
            [void]$violations.Add("$hit [possible secret content]")
        }
        continue
    }

    if ($exitCode -ne 1) {
        throw "git grep failed for pattern '$pattern' with exit code $exitCode."
    }
}

$global:LASTEXITCODE = 0

if ($violations.Count -gt 0) {
    Write-Host "ERROR: privacy guard blocked due to forbidden tracked files:"
    $violations | Sort-Object -Unique | ForEach-Object { Write-Host " - $_" }
    exit 1
}

Write-Host "Privacy guard check passed: no forbidden tracked paths found."
