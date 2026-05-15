$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$agentsPath = Join-Path $repoRoot "AGENTS.md"

if (-not (Test-Path $agentsPath)) {
    Write-Host "ERROR: AGENTS.md is required for repository PR action policy."
    exit 1
}

$lines = Get-Content $agentsPath
$headingIndex = -1
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i].Trim() -eq "## PR Review Gate") {
        $headingIndex = $i
        break
    }
}

if ($headingIndex -lt 0) {
    Write-Host "ERROR: AGENTS.md is missing the PR Review Gate section."
    exit 1
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

$requiredLines = @(
    "- Closing and merging pull requests are separate, explicit user-authorized actions, never routine cleanup.",
    "- Do not close a pull request unless the user gives an explicit close instruction for that pull request.",
    "- Do not merge a pull request unless the user gives an explicit instruction containing the standalone word ``MERGE`` for that pull request.",
    "- Do not infer close or merge permission from phrases like ""ship it"", ""looks good"", ""approved"", ""done"", ""superseded"", ""replace it"", ""clean up"", or ""go ahead"".",
    "- Do not get clever about this rule. If the exact close or ``MERGE`` instruction is missing, stop and ask.",
    "- Before inspecting PR details, reviewing comments, changing labels or branches, closing, merging, or otherwise acting on a pull request, first verify GitHub Copilot code review has completed and has been checked.",
    "- The only permitted pre-review action is checking whether GitHub Copilot code review has completed.",
    "- Even with explicit close or ``MERGE`` instruction, do not close or merge pull requests until GitHub Copilot code review has completed and has been checked.",
    "- If Copilot review is pending, missing, incomplete, or unchecked, do not act on the pull request; wait for review completion and ask the user to proceed once it is complete and checked.",
    "- Before merging, read every pull request conversation, review thread, and comment after GitHub Copilot code review has completed.",
    "- Before merging, address every actionable comment with code, docs, tests, or a documented no-change rationale.",
    "- Before merging, reply to every actionable comment with what was done or why no change was made, then resolve the thread only after it has been addressed and replied to.",
    "- Do not merge while any pull request conversation is unread, unaddressed, unreplied, or unresolved.",
    "- GitHub may auto-close superseded PRs independently, but agents must not proactively close superseded PRs before Copilot review has completed and been checked."
)

$allowedLines = @(
    $requiredLines
    "This section is enforced by:"
    "- ``scripts/pr_action_policy_check.ps1``"
    "- ``scripts/pr_action_policy_check.sh``"
    "- ``.githooks/pre-commit``"
    "- ``.githooks/pre-push``"
    "- ``.github/workflows/guard-raw-transcripts.yml``"
    "- ``tests/test_pr_action_policy.py``"
)

$missing = @($requiredLines | Where-Object { $_ -notin $sectionLines })
$forbidden = @($sectionLines | Where-Object {
    $_ -like "*unless the user explicitly instructs otherwise*" -or
    $_ -like "*has had a chance*" -or
    $_ -like "*had a chance to appear*" -or
    $_ -like "*Do not close or merge pull requests until*unless*"
})
$unexpected = @($sectionLines | Where-Object {
    $_ -ne "" -and $_ -notin $allowedLines
})

if ($missing.Count -gt 0 -or $forbidden.Count -gt 0 -or $unexpected.Count -gt 0) {
    Write-Host "ERROR: PR action policy guard failed."
    Write-Host "AGENTS.md must keep the hard completed-review, conversation, and close/MERGE gates in the PR Review Gate section."

    if ($missing.Count -gt 0) {
        Write-Host "Missing required lines:"
        $missing | ForEach-Object { Write-Host " - $_" }
    }

    if ($forbidden.Count -gt 0) {
        Write-Host "Forbidden soft-gate lines:"
        $forbidden | ForEach-Object { Write-Host " - $_" }
    }

    if ($unexpected.Count -gt 0) {
        Write-Host "Unexpected PR Review Gate lines:"
        $unexpected | ForEach-Object { Write-Host " - $_" }
    }

    exit 1
}

Write-Host "PR action policy check passed: completed-review, conversation, and close/MERGE gates are present."
