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

## Working Style for Agents

1. Prefer minimal, targeted diffs.
2. Do not refactor unrelated code.
3. Do not rewrite project history unless explicitly requested.
4. Keep docs and commands PowerShell-first.
5. Keep naming/source references aligned to `discord-session-archive`.

## PR Review Gate

- Do not close or merge pull requests until GitHub Copilot code review has had a chance to appear and has been checked, unless the user explicitly instructs otherwise.
- If Copilot review is not yet visible, do not close or merge the pull request; wait for the review to appear and ask the user to proceed once it is visible.
- GitHub may auto-close superseded PRs independently, but agents must not proactively close superseded PRs before Copilot review has had a chance to finish and be checked.

## Pre-Commit Safety Checks

Run these before preparing changes:

```powershell
git status --short
git ls-files
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
