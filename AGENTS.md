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

1. Do not merge a pull request until GitHub Copilot code review has appeared and has been checked.
2. If Copilot review is not yet visible, do not merge; wait for the review to appear first.
3. Before merge, review all Copilot feedback, take action where needed, reply in-thread, and resolve the related PR conversations unless the user explicitly says not to.
4. GitHub may auto-close superseded PRs independently, but agents must not proactively close or merge superseded PRs before Copilot review has appeared and been checked.

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
