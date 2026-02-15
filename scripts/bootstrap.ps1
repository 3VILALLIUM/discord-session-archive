$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

if (-not (Test-Path ".venv\Scripts\python.exe") -and -not (Test-Path ".venv/bin/python")) {
    python -m venv .venv
}

if (Test-Path ".venv\Scripts\python.exe") {
    $py = ".venv\Scripts\python.exe"
} elseif (Test-Path ".venv/bin/python") {
    $py = ".venv/bin/python"
} else {
    throw "Python executable not found in .venv."
}

& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt
git config core.hooksPath .githooks
git config --get core.hooksPath
& (Join-Path $PSScriptRoot "init_local_config.ps1")
& $py -c "import sys; print(sys.version)"
& (Join-Path $PSScriptRoot "privacy_guard_check.ps1")
