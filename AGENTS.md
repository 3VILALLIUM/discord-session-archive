# AGENTS Guide

This file defines how coding assistants should operate in this repository.

## Goal

Maintain a lean, safe, public-facing `discord-session-archive` tool while preventing sensitive artifacts from being committed.

## Repository Boundaries

Public code and docs should center on:
- `src/`
- `tests/`
- `scripts/`
- `.github/workflows/`
- `.githooks/`
- `README.md`
- `docs/`
- `requirements.txt`

Local-only artifacts must never be committed, including:
- `_local/**`
- audio/video files
- generated transcripts/JSON/log outputs
- `.env` and key material

## Non-Negotiable Privacy Rules

1. Never stage or commit local runtime outputs from `_local/`.
2. Never stage or commit secrets (`.env`, keys, PEM files).
3. Before proposing a commit, run checks listed in "Pre-Commit Safety Checks".
4. If a requested change conflicts with privacy rules, prioritize privacy.

## Identity and Metadata Privacy

1. Never commit, amend, merge, rebase, cherry-pick, or push with an auto-generated git identity.
2. Never allow local usernames, personal names, personal emails, hostnames, `.localdomain` addresses, or root-derived identifiers in author or committer metadata.
3. This repository must use the exact repo-local git identity:
   - `user.name`: `3VILALLIUM`
   - `user.email`: `128642648+3VILALLIUM@users.noreply.github.com`
4. Require `git config --local user.useConfigOnly true` so Git refuses fallback identity generation.
5. Require `git config --local core.hooksPath .githooks` so identity/privacy hooks stay active.
6. Never echo rejected local identity values in public PR text, commit messages, docs, workflow logs, or screenshots.

## Working Style for Agents

1. Prefer minimal, targeted diffs.
2. Do not refactor unrelated code.
3. Do not rewrite project history unless explicitly requested.
4. Keep docs and commands PowerShell-first.
5. Keep naming/source references aligned to `discord-session-archive`.

## Skill Usage

1. At the start of every task, check whether there is a relevant available skill for the work being requested.
2. If a relevant skill exists, use it rather than skipping straight to an ad hoc workflow.
3. Do not skip an obvious relevant skill just because the task seems familiar; prefer the skill-backed workflow for repeatability and reliability.

## PR Review Gate

- Closing and merging pull requests are separate, explicit user-authorized actions, never routine cleanup.
- Do not close a pull request unless the user gives an explicit close instruction for that pull request.
- Do not merge a pull request unless the user gives an explicit instruction containing the standalone word `MERGE` for that pull request.
- Do not infer close or merge permission from phrases like "ship it", "looks good", "approved", "done", "superseded", "replace it", "clean up", or "go ahead".
- Do not get clever about this rule. If the exact close or `MERGE` instruction is missing, stop and ask.
- Before inspecting PR details, reviewing comments, changing labels or branches, closing, merging, or otherwise acting on a pull request, first verify GitHub Copilot code review has completed and has been checked.
- The only permitted pre-review action is checking whether GitHub Copilot code review has completed.
- Even with explicit close or `MERGE` instruction, do not close or merge pull requests until GitHub Copilot code review has completed and has been checked.
- If Copilot review is pending, missing, incomplete, or unchecked, do not act on the pull request; wait for review completion and ask the user to proceed once it is complete and checked.
- Before merging, read every pull request conversation, review thread, and comment after GitHub Copilot code review has completed.
- Before merging, address every actionable comment with code, docs, tests, or a documented no-change rationale.
- Before merging, reply to every actionable comment with what was done or why no change was made, then resolve the thread only after it has been addressed and replied to.
- Do not merge while any pull request conversation is unread, unaddressed, unreplied, or unresolved.
- GitHub may auto-close superseded PRs independently, but agents must not proactively close superseded PRs before Copilot review has completed and been checked.

This section is enforced by:
- `scripts/pr_action_policy_check.ps1`
- `scripts/pr_action_policy_check.sh`
- `.githooks/pre-commit`
- `.githooks/pre-push`
- `.github/workflows/guard-raw-transcripts.yml`
- `tests/test_pr_action_policy.py`

## Pre-Commit Safety Checks

Run these before preparing changes:

```powershell
git status --short
git ls-files
git config --local user.name
git config --local user.email
git config --local user.useConfigOnly
git config --local core.hooksPath
.\scripts\git_identity_guard.ps1
.\scripts\pr_action_policy_check.ps1
.\scripts\privacy_guard_check.ps1
python -m pytest -q
```

## Project Policy

Repository is provided as-is.
No external issues, PRs, discussions, or suggestions are accepted.

## Docs and Entry Points

Start with:
- `README.md`
- `docs/README.md`

## If You Are Unsure

Default to the safer action:
- keep sensitive artifacts local,
- avoid staging ambiguous files,
- ask for user confirmation before destructive actions.
