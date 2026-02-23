param(
    [switch]$ValidateTroubleshooting
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$sourcePath = Join-Path $repoRoot "src/discord_session_archive.py"
$setupPath = Join-Path $repoRoot "docs/SETUP.md"
$troubleshootingPath = Join-Path $repoRoot "docs/TROUBLESHOOTING.md"

function Compare-FlagSets {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Expected,
        [Parameter(Mandatory = $true)]
        [string[]]$Actual
    )
    $missing = @($Expected | Where-Object { $_ -notin $Actual } | Sort-Object)
    $extra = @($Actual | Where-Object { $_ -notin $Expected } | Sort-Object)
    return [pscustomobject]@{
        Missing = $missing
        Extra = $extra
    }
}

function Write-FlagList {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Title,
        [Parameter(Mandatory = $true)]
        [string[]]$Flags
    )
    Write-Host $Title
    foreach ($flag in $Flags) {
        Write-Host "  - $flag"
    }
}

function Get-ParseArgsFlagData {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )
    $source = Get-Content $Path -Raw
    $parseArgsMatch = [regex]::Match($source, "(?sm)^def parse_args\(.*?^\s*return args\s*$")
    if (-not $parseArgsMatch.Success) {
        throw "Unable to locate parse_args block in $Path."
    }

    $parseArgsBlock = $parseArgsMatch.Value
    $addArgumentCalls = [regex]::Matches($parseArgsBlock, "(?s)parser\.add_argument\((.*?)\)")
    if ($addArgumentCalls.Count -eq 0) {
        throw "No parser.add_argument(...) calls found in parse_args at $Path."
    }

    $allFlagsMap = @{}
    $userFacingFlagsMap = @{}
    foreach ($call in $addArgumentCalls) {
        $callText = $call.Value
        $callFlags = [regex]::Matches($callText, '["''](--[a-z0-9-]+)["'']') | ForEach-Object { $_.Groups[1].Value }
        foreach ($flag in $callFlags) {
            $allFlagsMap[$flag] = $true
        }

        if ($callText -match "help\s*=\s*argparse\.SUPPRESS") {
            continue
        }
        foreach ($flag in $callFlags) {
            $userFacingFlagsMap[$flag] = $true
        }
    }

    return [pscustomobject]@{
        AllFlags = @($allFlagsMap.Keys | Sort-Object)
        UserFacingFlags = @($userFacingFlagsMap.Keys | Sort-Object)
    }
}

function Get-SetupCanonicalFlags {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )
    $lines = Get-Content $Path
    $headingIndex = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i].Trim() -eq 'Runtime flags (canonical from `parse_args`):') {
            $headingIndex = $i
            break
        }
    }
    if ($headingIndex -lt 0) {
        throw "Unable to locate canonical runtime-flags heading in $Path."
    }

    $sectionEnd = $lines.Count
    for ($i = $headingIndex + 1; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^## ") {
            $sectionEnd = $i
            break
        }
    }

    $sectionLines = @()
    if ($sectionEnd -gt ($headingIndex + 1)) {
        $sectionLines = $lines[($headingIndex + 1)..($sectionEnd - 1)]
    }

    $tableRows = $sectionLines | Where-Object {
        $_ -match "^\|" -and $_ -notmatch "^\|\s*---"
    }
    if ($tableRows.Count -eq 0) {
        throw "No markdown table rows found under canonical runtime-flags heading in $Path."
    }

    $flagsMap = @{}
    foreach ($row in $tableRows) {
        $rowFlagMatches = [regex]::Matches($row, "--[a-z0-9-]+")
        foreach ($match in $rowFlagMatches) {
            $flagsMap[$match.Value] = $true
        }
    }

    return [pscustomobject]@{
        Flags = @($flagsMap.Keys | Sort-Object)
        HeadingLine = $headingIndex + 1
    }
}

function Get-TroubleshootingCliFlags {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )
    $lines = Get-Content $Path
    $flagsMap = @{}
    foreach ($line in $lines) {
        if ($line -notmatch "^\s*python\s+\.\\src\\discord_session_archive\.py\b") {
            continue
        }
        $lineFlagMatches = [regex]::Matches($line, "--[a-z0-9-]+")
        foreach ($match in $lineFlagMatches) {
            $flagsMap[$match.Value] = $true
        }
    }
    return @($flagsMap.Keys | Sort-Object)
}

$parseArgFlags = Get-ParseArgsFlagData -Path $sourcePath
$setupFlags = Get-SetupCanonicalFlags -Path $setupPath
$setupCompare = Compare-FlagSets -Expected $parseArgFlags.UserFacingFlags -Actual $setupFlags.Flags

$failed = $false
if ($setupCompare.Missing.Count -gt 0 -or $setupCompare.Extra.Count -gt 0) {
    $failed = $true
    Write-Host "ERROR: docs drift detected between parse_args and canonical runtime flags."
    Write-Host "Source of truth: src/discord_session_archive.py (parse_args)"
    Write-Host "Target section: docs/SETUP.md:$($setupFlags.HeadingLine)"
    if ($setupCompare.Missing.Count -gt 0) {
        Write-FlagList -Title "Add these flags to docs/SETUP.md canonical runtime table:" -Flags $setupCompare.Missing
    }
    if ($setupCompare.Extra.Count -gt 0) {
        Write-FlagList -Title "Remove/update these flags in docs/SETUP.md canonical runtime table:" -Flags $setupCompare.Extra
    }
}

if ($ValidateTroubleshooting) {
    $troubleshootingFlags = Get-TroubleshootingCliFlags -Path $troubleshootingPath
    $unknownTroubleshootingFlags = @($troubleshootingFlags | Where-Object { $_ -notin $parseArgFlags.AllFlags })
    if ($unknownTroubleshootingFlags.Count -gt 0) {
        $failed = $true
        Write-Host "ERROR: docs/TROUBLESHOOTING.md references CLI flags not present in parse_args."
        Write-Host "Target file: docs/TROUBLESHOOTING.md"
        Write-FlagList -Title "Unknown troubleshooting flags:" -Flags $unknownTroubleshootingFlags
    }

}

if ($failed) {
    exit 1
}

Write-Host ("OK: canonical runtime flags are in sync ({0} flags)." -f $parseArgFlags.UserFacingFlags.Count)
Write-Host ("Validated docs/SETUP.md:{0} against src/discord_session_archive.py parse_args." -f $setupFlags.HeadingLine)
if ($ValidateTroubleshooting) {
    Write-Host "Validated troubleshooting CLI flag references for unknown flag drift."
}
