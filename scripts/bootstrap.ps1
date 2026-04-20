param(
    [switch]$Plan,
    [switch]$InstallMissingDependencies,
    [switch]$Yes
)

$ErrorActionPreference = "Stop"

$EXIT_MISSING_DEPS = 2
$EXIT_NO_PACKAGE_MANAGER = 3
$EXIT_DEP_INSTALL_FAILED = 4

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

function Format-Command {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Command
    )
    return ($Command | ForEach-Object {
            if ($_ -match '\s') { '"' + $_ + '"' } else { $_ }
        }) -join " "
}

function Invoke-NativeStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Title,
        [Parameter(Mandatory = $true)]
        [string[]]$Command
    )
    Write-Host "== $Title =="
    Write-Host ("   " + (Format-Command -Command $Command))
    $global:LASTEXITCODE = 0
    $exe = $Command[0]
    $cmdArgs = @()
    if ($Command.Length -gt 1) {
        $cmdArgs = $Command[1..($Command.Length - 1)]
    }
    & $exe @cmdArgs
    if (-not $?) {
        throw "$Title failed."
    }
    if ($LASTEXITCODE -ne 0) {
        throw "$Title failed with exit code $LASTEXITCODE."
    }
}

function Get-OSFamily {
    # PowerShell Core 6+ has $IsWindows, $IsMacOS, $IsLinux
    # Windows PowerShell 5.1 does not, so we need fallback detection
    if (Get-Variable -Name IsWindows -ErrorAction SilentlyContinue) {
        if ($IsWindows) { return "windows" }
        if ($IsMacOS) { return "macos" }
        if ($IsLinux) { return "linux" }
    } else {
        # Windows PowerShell 5.1 fallback (only runs on Windows)
        if ($env:OS -match "Windows") {
            return "windows"
        }
    }
    return "unknown"
}

function Get-PythonBootstrapCommand {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        return @("python")
    }

    $pyLauncherCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncherCmd) {
        return @("py", "-3")
    }

    return $null
}

function Test-Dependency {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("python", "ffmpeg", "git")]
        [string]$Dependency
    )

    switch ($Dependency) {
        "python" { return $null -ne (Get-PythonBootstrapCommand) }
        "ffmpeg" { return $null -ne (Get-Command ffmpeg -ErrorAction SilentlyContinue) }
        "git" { return $null -ne (Get-Command git -ErrorAction SilentlyContinue) }
    }
}

function Get-MissingDependencies {
    $deps = @("python", "ffmpeg", "git")
    $missing = New-Object System.Collections.Generic.List[string]
    foreach ($dep in $deps) {
        if (-not (Test-Dependency -Dependency $dep)) {
            [void]$missing.Add($dep)
        }
    }
    return @($missing.ToArray())
}

function Get-PackageManagerChain {
    param(
        [Parameter(Mandatory = $true)]
        [string]$OSFamily
    )

    switch ($OSFamily) {
        "windows" { return @("winget", "choco", "scoop") }
        "macos" { return @("brew", "port") }
        "linux" { return @("apt-get", "dnf", "yum", "pacman", "zypper") }
        default { return @() }
    }
}

function Get-InstallCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Manager,
        [Parameter(Mandatory = $true)]
        [ValidateSet("python", "ffmpeg", "git")]
        [string]$Dependency
    )

    switch ($Manager) {
        "winget" {
            switch ($Dependency) {
                "python" { return @("winget", "install", "--id", "Python.Python.3", "-e", "--source", "winget") }
                "ffmpeg" { return @("winget", "install", "--id", "Gyan.FFmpeg", "-e", "--source", "winget") }
                "git" { return @("winget", "install", "--id", "Git.Git", "-e", "--source", "winget") }
            }
        }
        "choco" {
            switch ($Dependency) {
                "python" { return @("choco", "install", "-y", "python") }
                "ffmpeg" { return @("choco", "install", "-y", "ffmpeg") }
                "git" { return @("choco", "install", "-y", "git") }
            }
        }
        "scoop" {
            switch ($Dependency) {
                "python" { return @("scoop", "install", "python") }
                "ffmpeg" { return @("scoop", "install", "ffmpeg") }
                "git" { return @("scoop", "install", "git") }
            }
        }
        "brew" {
            switch ($Dependency) {
                "python" { return @("brew", "install", "python") }
                "ffmpeg" { return @("brew", "install", "ffmpeg") }
                "git" { return @("brew", "install", "git") }
            }
        }
        "port" {
            switch ($Dependency) {
                "python" { return @("sudo", "port", "install", "python311") }
                "ffmpeg" { return @("sudo", "port", "install", "ffmpeg") }
                "git" { return @("sudo", "port", "install", "git") }
            }
        }
        "apt-get" {
            switch ($Dependency) {
                "python" { return @("sudo", "apt-get", "install", "-y", "python3", "python3-venv") }
                "ffmpeg" { return @("sudo", "apt-get", "install", "-y", "ffmpeg") }
                "git" { return @("sudo", "apt-get", "install", "-y", "git") }
            }
        }
        "dnf" {
            switch ($Dependency) {
                "python" { return @("sudo", "dnf", "install", "-y", "python3") }
                "ffmpeg" { return @("sudo", "dnf", "install", "-y", "ffmpeg") }
                "git" { return @("sudo", "dnf", "install", "-y", "git") }
            }
        }
        "yum" {
            switch ($Dependency) {
                "python" { return @("sudo", "yum", "install", "-y", "python3") }
                "ffmpeg" { return @("sudo", "yum", "install", "-y", "ffmpeg") }
                "git" { return @("sudo", "yum", "install", "-y", "git") }
            }
        }
        "pacman" {
            switch ($Dependency) {
                "python" { return @("sudo", "pacman", "-S", "--noconfirm", "python") }
                "ffmpeg" { return @("sudo", "pacman", "-S", "--noconfirm", "ffmpeg") }
                "git" { return @("sudo", "pacman", "-S", "--noconfirm", "git") }
            }
        }
        "zypper" {
            switch ($Dependency) {
                "python" { return @("sudo", "zypper", "install", "-y", "python3") }
                "ffmpeg" { return @("sudo", "zypper", "install", "-y", "ffmpeg") }
                "git" { return @("sudo", "zypper", "install", "-y", "git") }
            }
        }
    }

    return $null
}

function Show-BootstrapPlan {
    param(
        [Parameter(Mandatory = $true)]
        [string]$OSFamily,
        [string[]]$MissingDependencies
    )

    Write-Host "Bootstrap plan summary"
    Write-Host "- Repo root: $repoRoot"
    Write-Host "- OS family: $OSFamily"
    Write-Host "- Plan mode: $Plan"
    Write-Host "- Install missing deps mode: $InstallMissingDependencies"
    Write-Host "- Non-interactive confirmation: $Yes"
    Write-Host ""
    Write-Host "Steps:"
    Write-Host "1. Detect required external dependencies: python, ffmpeg, git"
    Write-Host "2. Optionally install missing dependencies (explicit opt-in only)"
    Write-Host "3. Create .venv if missing"
    Write-Host "4. Install pip requirements into .venv"
    Write-Host "5. Set git hooks path and safe git identity defaults"
    Write-Host "6. Initialize local templates (.env + _local/config/*.json)"
    Write-Host "7. Print Python version"
    Write-Host "8. Run privacy guard"
    Write-Host ""
    Write-Host "Network actions:"
    Write-Host "- pip install --upgrade pip"
    Write-Host "- pip install --require-hashes -r requirements.lock.txt"
    Write-Host "- optional package-manager installs for python/ffmpeg/git"
    Write-Host ""
    Write-Host "Possible side effects:"
    Write-Host "- create or update .venv/"
    Write-Host "- local git config update: core.hooksPath"
    Write-Host "- local git config update: user.useConfigOnly"
    Write-Host "- create .env if missing"
    Write-Host "- create _local/config/name_replace_map.json if missing"
    Write-Host ""
    if ($MissingDependencies.Count -eq 0) {
        Write-Host "Dependency status: all required external dependencies are present."
    } else {
        Write-Host ("Dependency status: missing -> " + (($MissingDependencies | Sort-Object) -join ", "))
    }
    Write-Host ""
}

function Show-RemediationHints {
    param(
        [Parameter(Mandatory = $true)]
        [string]$OSFamily,
        [string[]]$MissingDependencies
    )

    if ($MissingDependencies.Count -eq 0) {
        return
    }

    Write-Host "Missing required dependencies: $(($MissingDependencies | Sort-Object) -join ", ")"
    Write-Host "Re-run with -InstallMissingDependencies to let bootstrap attempt installation."
    Write-Host "Manual command examples:"
    $chain = Get-PackageManagerChain -OSFamily $OSFamily
    foreach ($dep in ($MissingDependencies | Sort-Object)) {
        Write-Host "- $dep"
        foreach ($manager in $chain) {
            $command = Get-InstallCommand -Manager $manager -Dependency $dep
            if ($null -ne $command) {
                Write-Host ("  " + (Format-Command -Command $command))
            }
        }
    }
    Write-Host ""
}

function Install-MissingDependencies {
    param(
        [Parameter(Mandatory = $true)]
        [string]$OSFamily,
        [string[]]$MissingDependencies
    )

    $chain = Get-PackageManagerChain -OSFamily $OSFamily
    $availableManagers = @()
    foreach ($manager in $chain) {
        if (Get-Command $manager -ErrorAction SilentlyContinue) {
            $availableManagers += $manager
        }
    }

    if ($availableManagers.Count -eq 0) {
        return @{
            Status = "no_manager"
            Failed = @()
        }
    }

    Write-Host ("Available package managers: " + ($availableManagers -join ", "))
    $failed = New-Object System.Collections.Generic.List[string]

    foreach ($dep in ($MissingDependencies | Sort-Object)) {
        if (Test-Dependency -Dependency $dep) {
            continue
        }

        $installed = $false
        foreach ($manager in $availableManagers) {
            $command = Get-InstallCommand -Manager $manager -Dependency $dep
            if ($null -eq $command) {
                continue
            }

            try {
                Invoke-NativeStep -Title "Install $dep via $manager" -Command $command
            } catch {
                Write-Warning "Install via $manager failed for ${dep}: $($_.Exception.Message)"
                continue
            }

            if (Test-Dependency -Dependency $dep) {
                $installed = $true
                break
            }

            Write-Warning "$dep still appears missing after running $manager command."
        }

        if (-not $installed) {
            [void]$failed.Add($dep)
        }
    }

    if ($failed.Count -gt 0) {
        return @{
            Status = "failed"
            Failed = @($failed.ToArray())
        }
    }

    return @{
        Status = "ok"
        Failed = @()
    }
}

function Get-VenvPythonPath {
    if (Test-Path ".venv\Scripts\python.exe") {
        return ".venv\Scripts\python.exe"
    }
    if (Test-Path ".venv/bin/python") {
        return ".venv/bin/python"
    }
    throw "Python executable not found in .venv."
}

$osFamily = Get-OSFamily
$missingDependencies = @(Get-MissingDependencies)

Show-BootstrapPlan -OSFamily $osFamily -MissingDependencies $missingDependencies

if ($Plan) {
    if ($missingDependencies.Count -gt 0) {
        Show-RemediationHints -OSFamily $osFamily -MissingDependencies $missingDependencies
    }
    Write-Host "Plan mode enabled; no commands were executed."
    exit 0
}

if ($missingDependencies.Count -gt 0) {
    if (-not $InstallMissingDependencies) {
        Show-RemediationHints -OSFamily $osFamily -MissingDependencies $missingDependencies
        exit $EXIT_MISSING_DEPS
    }

    if (-not $Yes) {
        $answer = Read-Host "Install missing dependencies now? [y/N]"
        if ($answer -notmatch "^(y|yes)$") {
            Show-RemediationHints -OSFamily $osFamily -MissingDependencies $missingDependencies
            exit $EXIT_MISSING_DEPS
        }
    }

    $installResult = Install-MissingDependencies -OSFamily $osFamily -MissingDependencies $missingDependencies
    if ($installResult.Status -eq "no_manager") {
        Write-Host "No supported package manager was found for $osFamily."
        Show-RemediationHints -OSFamily $osFamily -MissingDependencies $missingDependencies
        exit $EXIT_NO_PACKAGE_MANAGER
    }
    if ($installResult.Status -eq "failed") {
        $failedList = @($installResult.Failed) -join ", "
        Write-Host "Dependency install attempts failed for: $failedList"
        Show-RemediationHints -OSFamily $osFamily -MissingDependencies $missingDependencies
        exit $EXIT_DEP_INSTALL_FAILED
    }

    $missingDependencies = @(Get-MissingDependencies)
    if ($missingDependencies.Count -gt 0) {
        Write-Host "Dependencies are still missing after install attempts."
        Show-RemediationHints -OSFamily $osFamily -MissingDependencies $missingDependencies
        exit $EXIT_DEP_INSTALL_FAILED
    }
}

$bootstrapPythonCommand = Get-PythonBootstrapCommand
if ($null -eq $bootstrapPythonCommand) {
    Write-Host "Python is required for bootstrap but was not found."
    exit $EXIT_MISSING_DEPS
}

if (-not (Test-Path ".venv\Scripts\python.exe") -and -not (Test-Path ".venv/bin/python")) {
    $venvCommand = @($bootstrapPythonCommand + @("-m", "venv", ".venv"))
    Invoke-NativeStep -Title "Create virtual environment" -Command $venvCommand
} else {
    Write-Host "== Virtual environment =="
    Write-Host "   .venv already exists; leaving unchanged"
}

$py = Get-VenvPythonPath
$detectedPython = & $py -c "import sys; print('.'.join(str(part) for part in sys.version_info[:3]))"
if (-not $?) {
    throw "Failed to detect Python version from virtual environment."
}
& $py -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if (-not $?) {
    throw "Python 3.11+ is required for requirements.lock.txt installs; found $detectedPython."
}
Write-Host "== Python requirement =="
Write-Host "   Detected Python $detectedPython (meets >= 3.11)"

Invoke-NativeStep -Title "Upgrade pip" -Command @($py, "-m", "pip", "install", "--upgrade", "pip")
Invoke-NativeStep -Title "Install requirements" -Command @($py, "-m", "pip", "install", "--require-hashes", "-r", "requirements.lock.txt")
Invoke-NativeStep -Title "Set git hooks path" -Command @("git", "config", "--local", "core.hooksPath", ".githooks")
Invoke-NativeStep -Title "Show git hooks path" -Command @("git", "config", "--local", "--get", "core.hooksPath")
Invoke-NativeStep -Title "Set git identity safety default" -Command @("git", "config", "--local", "user.useConfigOnly", "true")
Invoke-NativeStep -Title "Show git identity safety default" -Command @("git", "config", "--local", "--type=bool", "--get", "user.useConfigOnly")

Write-Host "== Initialize local config templates =="
& (Join-Path $PSScriptRoot "init_local_config.ps1")
if (-not $?) {
    throw "init_local_config.ps1 failed."
}

Invoke-NativeStep -Title "Show Python version" -Command @($py, "-c", "import sys; print(sys.version)")

Write-Host "== Privacy guard check =="
& (Join-Path $PSScriptRoot "privacy_guard_check.ps1")
if (-not $?) {
    throw "privacy_guard_check.ps1 failed."
}

Write-Host ""
Write-Host "Bootstrap completed."
Write-Host "Next steps:"
Write-Host '1. Set repo-local Git identity:'
Write-Host '   git config --local user.name "3VILALLIUM"'
Write-Host '   git config --local user.email "128642648+3VILALLIUM@users.noreply.github.com"'
Write-Host "2. Edit .env and set OPENAI_API_KEY"
Write-Host "3. Run: python .\src\discord_session_archive.py"
