# Contributing

Back to docs index: `docs/README.md`

## Branch and PR Workflow

1. Sync `main`:

```powershell
git switch main
git pull --ff-only origin main
```

2. Create a branch:

```powershell
git switch -c <type/short-description>
```

3. Make focused changes, then run checks.
4. Commit with a clear message.
5. Push and open a PR.

## Commit Scope Expectations

- Keep commits scoped to one change objective.
- Avoid unrelated refactors in the same PR.
- Keep local-only generated artifacts out of commits.
- Prefer small, reviewable diffs.

## Required Checks Before PR

```powershell
git status --short
python -m pytest -q
bash .githooks/pre-commit; echo PRECOMMIT_EXIT_$LASTEXITCODE
```

If pre-commit reports forbidden files, unstage them and re-run checks.

## Docs Style Guide

- Use concise headings and task-oriented sections.
- Prefer Windows PowerShell examples first.
- Use backticks for commands and file paths.
- Keep canonical docs in `docs/`; keep historical references in `docs/archive/`.
- Do not include transcript content, recap excerpts, or map values in docs.

## PR Body Minimum

Include:

- Summary of changes.
- Why the change is needed.
- Validation performed.
- Privacy confirmation that no local-only artifacts were added.
