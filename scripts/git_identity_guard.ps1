$ErrorActionPreference = "Stop"

$approvedUserName = "3VILALLIUM"
$approvedUserEmail = "128642648+3VILALLIUM@users.noreply.github.com"
$approvedHooksPath = ".githooks"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

function Get-GitExecutable {
    $command = Get-Command git -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }

    $candidates = @()
    if ($env:ProgramFiles) {
        $candidates += (Join-Path $env:ProgramFiles "Git\cmd\git.exe")
        $candidates += (Join-Path $env:ProgramFiles "Git\bin\git.exe")
    }
    if (${env:ProgramFiles(x86)}) {
        $candidates += (Join-Path ${env:ProgramFiles(x86)} "Git\cmd\git.exe")
        $candidates += (Join-Path ${env:ProgramFiles(x86)} "Git\bin\git.exe")
    }

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "git is required but was not found."
}

$gitExe = Get-GitExecutable

function Get-LocalGitConfigValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Key,
        [switch]$AsBool
    )

    $script:LASTEXITCODE = 0
    if ($AsBool) {
        $value = & $gitExe config --local --type=bool --get $Key 2>$null
    } else {
        $value = & $gitExe config --local --get $Key 2>$null
    }
    if ($LASTEXITCODE -ne 0) {
        return ""
    }
    return ($value | Out-String).Trim()
}

function Show-IdentityFix {
    Write-Host "Fix:"
    Write-Host '  git config --local user.name "3VILALLIUM"'
    Write-Host '  git config --local user.email "128642648+3VILALLIUM@users.noreply.github.com"'
    Write-Host "  git config --local user.useConfigOnly true"
    Write-Host "  git config --local core.hooksPath .githooks"
}

function Fail-RepoPolicy {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    Write-Error $Message
    Show-IdentityFix
    exit 1
}

$localUserName = Get-LocalGitConfigValue -Key "user.name"
$localUserEmail = Get-LocalGitConfigValue -Key "user.email"
$useConfigOnly = Get-LocalGitConfigValue -Key "user.useConfigOnly" -AsBool
$hooksPath = Get-LocalGitConfigValue -Key "core.hooksPath"

if ($localUserName -ne $approvedUserName) {
    Fail-RepoPolicy -Message "git identity does not match repo policy."
}
if ($localUserEmail -ne $approvedUserEmail) {
    Fail-RepoPolicy -Message "git identity does not match repo policy."
}
if ($useConfigOnly.ToLowerInvariant() -ne "true") {
    Fail-RepoPolicy -Message "git identity does not match repo policy."
}
if ($hooksPath -ne $approvedHooksPath) {
    Fail-RepoPolicy -Message "git hooks are not configured for this repository."
}
