$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

if (Test-Path ".venv\Scripts\python.exe") {
    $py = ".venv\Scripts\python.exe"
} elseif (Test-Path ".venv/bin/python") {
    $py = ".venv/bin/python"
} else {
    $py = "python"
}

function Invoke-NativeStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Title,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )
    Write-Host "== $Title =="
    $global:LASTEXITCODE = 0
    & $Command
    if (-not $?) {
        throw "$Title failed."
    }
    if ($LASTEXITCODE -ne 0) {
        throw "$Title failed with exit code $LASTEXITCODE."
    }
}

Invoke-NativeStep "git status --short" { git status --short }

Invoke-NativeStep "git ls-files" { git ls-files }

Invoke-NativeStep "git_identity_guard.ps1" { & (Join-Path $PSScriptRoot "git_identity_guard.ps1") }

Invoke-NativeStep "docs_consistency_check.ps1" { & (Join-Path $PSScriptRoot "docs_consistency_check.ps1") -ValidateTroubleshooting }

Invoke-NativeStep "privacy_guard_check.ps1" { & (Join-Path $PSScriptRoot "privacy_guard_check.ps1") }

$bashCmd = Get-Command bash -ErrorAction SilentlyContinue
if (-not $bashCmd) {
    throw "bash is required for shell guard parity checks. Install Git Bash and retry."
}

Invoke-NativeStep "privacy_guard_check.sh" { bash "./scripts/privacy_guard_check.sh" }

Invoke-NativeStep "pip check" { & $py -m pip check }

Invoke-NativeStep "pip-audit" { & $py -m pip_audit --progress-spinner off }

Invoke-NativeStep "compileall src tests" { & $py -m compileall src tests }

Invoke-NativeStep "pytest -q" { & $py -m pytest -q }

Invoke-NativeStep "CLI --help" { & $py (Join-Path "src" "discord_session_archive.py") --help }

Invoke-NativeStep "CLI --version" { & $py (Join-Path "src" "discord_session_archive.py") --version }
