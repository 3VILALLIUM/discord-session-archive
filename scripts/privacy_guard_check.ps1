$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$tracked = git ls-files
$violations = New-Object System.Collections.Generic.List[string]

foreach ($path in $tracked) {
    $lower = $path.ToLowerInvariant()

    if ($path -eq ".env") {
        [void]$violations.Add($path)
        continue
    }

    if ($lower -match '\.(log|aac|flac|m4a|mp3|wav)$') {
        [void]$violations.Add($path)
        continue
    }

    if ($path -like "dotmm_output/*" -or $path -like "*/dotmm_output/*" -or
        $path -like "dotmm_transcripts/*" -or $path -like "*/dotmm_transcripts/*" -or
        $path -like "dotmm_sessions/*" -or $path -like "*/dotmm_sessions/*" -or
        $path -like "dotmm_session_output_overviews/*" -or $path -like "*/dotmm_session_output_overviews/*") {
        [void]$violations.Add($path)
        continue
    }
}

if ($violations.Count -gt 0) {
    $violations | ForEach-Object { Write-Host $_ }
    exit 1
}

Write-Host "Privacy guard check passed: no forbidden tracked paths found."
