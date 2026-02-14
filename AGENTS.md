# AGENTS Guide

This file defines how AI coding assistants should work in this repository.
It is written to be tool-agnostic and usable by Codex, Claude Code, GitHub Copilot agents, and similar tools.

## Goal

Help contributors modify scripts, tests, and docs safely while preventing sensitive local artifacts from being committed.

## Repository Boundaries

Public code and docs should center on:
- `campaigns/dungeon_of_the_mad_mage/dotmm_scripts/`
- `tests/`
- `.github/workflows/`
- `.githooks/`
- `README.md`
- `docs/`
- `requirements.txt`

Local-only artifacts must never be committed, including anything in or similar to:
- `campaigns/dungeon_of_the_mad_mage/dotmm_output/`
- `campaigns/dungeon_of_the_mad_mage/dotmm_transcripts/`
- `campaigns/dungeon_of_the_mad_mage/dotmm_session_output_overviews/`
- Audio, transcript chunks, logs, merged outputs, temporary files, and name-mapping data.

## Non-Negotiable Privacy Rules

1. Never stage or commit transcripts, recaps, audio, logs, chunk JSON, merged output artifacts, or session overviews.
2. Never stage or commit handle-map or realname-map source data.
3. Before proposing a commit, run checks listed in "Pre-Commit Safety Checks".
4. If a requested change conflicts with these rules, prioritize privacy and ask for clarification.

## Working Style for Agents

1. Prefer minimal, targeted diffs.
2. Do not refactor unrelated code.
3. Do not rewrite project history unless explicitly requested.
4. Keep changes consistent with existing script and test style.
5. When adding commands to docs, prefer Windows PowerShell examples first.

## Pre-Commit Safety Checks

Run these before preparing a PR:

```powershell
git status --short
git ls-files
git check-ignore -v campaigns/dungeon_of_the_mad_mage/dotmm_output/session_001_transcript 2>$null
```

Privacy-focused scans:

```powershell
rg -n -i "transcript|recap|session_output|dotmm_output|raw_audio|chunk|deepgram|whisper|handle_map|realname_map" .
```

If scan hits are in generated artifacts that are ignored, do not add them. If hits are in tracked files unexpectedly, stop and resolve before commit.

## PR Expectations

PRs should include:
- What changed.
- Why the change is needed.
- Validation performed (tests, lint, or command outputs).
- Confirmation that no local-only artifacts were added.

## Docs and Entry Points

Start with:
- `README.md`
- `docs/README.md`

Use canonical docs under `docs/` and treat `docs/archive/` as historical reference only.

## If You Are Unsure

Default to the safer action:
- keep sensitive artifacts local,
- avoid staging ambiguous files,
- ask for user confirmation before any destructive action.
