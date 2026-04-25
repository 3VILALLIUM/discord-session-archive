# Troubleshooting

Back to docs index: `docs/README.md`

Maintenance note:

- This document owns symptom-to-fix recipes.
- Canonical CLI flag definitions/defaults live in `docs/SETUP.md` under `Runtime flags (canonical from parse_args)`.
- When CLI behavior changes, update `docs/SETUP.md` first, then update this file for symptom guidance.

## Setup Failures

### Bootstrap exits with code `2`

Cause:

- Missing dependency (`python`, `ffmpeg`, or `git`) and install mode is disabled/declined.

Fix:

```powershell
.\scripts\bootstrap.ps1 -InstallMissingDependencies
```

```bash
bash ./scripts/bootstrap.sh --install-missing-dependencies
```

or install manually and re-run bootstrap.

### Bootstrap exits with code `3`

Cause:

- Install mode requested but no supported package manager detected.

Fix:

- Install dependencies manually, then re-run.

### Bootstrap exits with code `4`

Cause:

- Dependency installation was attempted but failed.

Fix:

- Run the printed install commands manually to inspect package-manager errors.

### `OPENAI_API_KEY not set`

Fix:

```powershell
Copy-Item .env.example .env
```

Then set `OPENAI_API_KEY` in `.env`.

### `ffmpeg not found in PATH`

Fix:

1. Install `ffmpeg`.
2. Ensure `ffmpeg` is on `PATH`.
3. Restart terminal.

## Runtime Failures

For canonical flag defaults and definitions, see `docs/SETUP.md` under `Runtime flags (canonical from parse_args)`.

### Input path/picker confusion (`--input`, `--pick-folder`)

Cause:

- `--input` and `--pick-folder` were mixed in a way that does not match your intent.
- Tkinter picker may be unavailable in your environment.

Fix:

1. For explicit paths, use only `--input`:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport"
```

2. To force picker flow, use `--pick-folder` with no `--input`:

```powershell
python .\src\discord_session_archive.py --pick-folder
```

3. If picker is unavailable, always pass `--input` manually.

### Existing run directory error (`--label`, `--force`)

Cause:

- The computed run folder already exists under the output root.

Fix:

1. Change label to produce a new run folder:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --label "session-2026-02-23"
```

2. Or overwrite the existing run folder intentionally:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --force
```

### Output location confusion (`--output-root`)

Cause:

- Output is being written to a non-default root, or you expected a different destination.

Fix:

1. Pin output root explicitly:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --output-root "C:\transcripts\runs"
```

2. Check artifacts at:

```text
<output-root>/<run_id>/<run_id>_transcript.md
<output-root>/<run_id>/<run_id>_log.md
```

### Invalid `--name-map-mode` value

Cause:

- The CLI only supports `replace` and `none`.

Fix:

- Use `--name-map-mode replace` for alias replacement.
- Use `--name-map-mode none` to disable replacements.
- Edit `_local/config/name_replace_map.json` when using `replace`.

### Name map file missing

Cause:

- `--name-map-mode replace` is active but map file is missing.

Fix:

```powershell
.\scripts\init_local_config.ps1
```

```bash
bash ./scripts/init_local_config.sh
```

Then edit:

- `_local/config/name_replace_map.json`

### Invalid name map JSON

Fix:

- Ensure map is valid JSON object with non-empty string keys/values.

Example:

```json
{
  "@speaker-one": "Example Preferred Name One",
  "speaker one": "Example Preferred Name One",
  "example person one": "Example Preferred Name One"
}
```

### Where are run logs?

Each non-dry run writes a markdown log file alongside the transcript:

```text
_local/runs/<run_id>/<run_id>_log.md
```

### No supported audio files found

Fix:

- Confirm input has `.mp3`, `.wav`, `.m4a`, `.aac`, or `.flac`.
- If you used the default picker flow, re-run and choose the correct Craig export folder.
- Pass explicit input path:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport"
```

### File picker unavailable

Cause:

- GUI/Tkinter is unavailable in your Python environment.

Fix:

- Use manual input mode:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport"
```

## Flag quick-reference by symptom

Use these symptom-to-flag mappings as a fast path before deep debugging.

### Wrong folder or picker behavior (`--input`, `--pick-folder`)

```powershell
# Deterministic path input (no picker)
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport"

# Explicit picker flow
python .\src\discord_session_archive.py --pick-folder
```

### Output written to an unexpected location (`--output-root`, `--label`)

```powershell
# Pin a custom output root
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --output-root "D:\session-archive\runs"

# Provide a label prefix for the run folder (a timestamp suffix is appended automatically)
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --output-root "D:\session-archive\runs" --label "campaign-12-session-03"
```

### Run folder already exists (`--force`, `--label`)

```powershell
# Create a new run folder by changing label
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --label "session-2026-02-23-rerun"

# Or intentionally overwrite existing computed run folder
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --force
```

### Noisy transcript or language drift (`--language`, `--quality-filter`)

```powershell
# Force known language and stronger filtering
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --language en --quality-filter strict

# Keep language auto but disable filtering for raw debugging comparison
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --language auto --quality-filter off
```

### Slow runs or API pressure (`--track-workers`, `--api-workers`, `--max-workers`, `--chunk-sec`, `--overlap-sec`)

```powershell
# Lower concurrency to reduce machine/API pressure
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --track-workers 2 --api-workers 2 --max-workers 2

# Tune chunk geometry when boundary duplication or throughput needs adjustment
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --chunk-sec 90 --overlap-sec 1.5
```

### Debug run without file writes (`--dry-run`, `--quiet`)

```powershell
# Preview planned run behavior without writing transcript/log files
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --dry-run

# Combine dry-run with low-noise console mode
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --dry-run --quiet
```

### Verify CLI build/version (`--version`)

```powershell
python .\src\discord_session_archive.py --version
```

## Naming and Metadata

### Run name does not use guild/timestamp

Cause:

- `info.txt` not found or not parseable.

Fix:

1. Confirm `info.txt` exists in/near the Craig export.
2. Ensure it includes `Guild:` and `Start time:`.
3. Otherwise, use `--label`.

Fallback order:

1. `--label`
2. parsed `info.txt`
3. UTC timestamp

### Craig notes missing from frontmatter

Cause:

- `info.txt` has no `Notes`/`Note` entries, or note lines are outside the parsed section.

Fix:

1. Add notes through Craig during recording so they appear in `info.txt`.
2. Confirm `info.txt` includes `Notes:` or `Note ...:` entries.
3. Re-run transcription; notes appear in frontmatter under `craig_notes`.

### Timestamp contains invalid filename characters

Behavior:

- `:` is automatically replaced with `-` for Windows-safe naming.

## Transcript Quality

### Quality/language tuning (`--quality-filter`, `--language`)

Cause:

- Auto language detection picked the wrong language.
- Filtering profile is too strict or too permissive for your audio.

Fix:

1. Keep auto language and use balanced filtering:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --language auto --quality-filter balanced
```

2. Force known language when drift appears:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --language en --quality-filter strict
```

3. Temporarily relax filtering during investigation:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --quality-filter off
```

For current defaults, refer to `docs/SETUP.md` under `Runtime flags (canonical from parse_args)`.

### Run is too slow (worker/chunk tuning)

Cause:

- Worker settings are mismatched to local CPU, storage, or API rate limits.
- Chunk sizing is inefficient for the audio material.

Fix:

1. Start with moderate parallelism:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --track-workers 4 --api-workers 4 --max-workers 4
```

2. Tune chunking if needed:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --chunk-sec 90 --overlap-sec 1.5
```

3. If rate limits or machine pressure appear, reduce worker counts.

### Side-effect-safe debugging (`--dry-run`)

Use `--dry-run` to validate behavior without writing transcript/log files or making paid transcription calls:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --dry-run
```

Use `--quiet` only to reduce console output. By itself, it still performs normal run work and writes artifacts.

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --dry-run --quiet
```

## PR Action Policy Guard Failures

### `ERROR: PR action policy guard failed.`

Fix:

```powershell
git status --short
.\scripts\pr_action_policy_check.ps1
```

```bash
git status --short
bash ./scripts/pr_action_policy_check.sh
```

Keep `AGENTS.md` aligned with the required PR Review Gate:
- Copilot code review must be complete and checked before PR action.
- Conversations, review threads, and comments must be read before merge.
- Actionable comments must be addressed, replied to, and resolved before merge.
- Close requires explicit close instruction.
- Merge requires an explicit standalone `MERGE` instruction.

## Privacy Guard Failures

### `ERROR: privacy guard blocked commit`

Fix:

```powershell
git restore --staged <path>
git status --short
.\scripts\privacy_guard_check.ps1
```

### `ERROR: git identity does not match repo policy`

Fix:

```powershell
git config --local user.name "3VILALLIUM"
git config --local user.email "128642648+3VILALLIUM@users.noreply.github.com"
git config --local user.useConfigOnly true
git config --local core.hooksPath .githooks
.\scripts\git_identity_guard.ps1
```

### `ERROR: git hooks are not configured for this repository`

Fix:

```powershell
git config --local core.hooksPath .githooks
.\scripts\git_identity_guard.ps1
```

## Hooks Not Running

Fix:

```powershell
git config --local core.hooksPath .githooks
git config --local user.useConfigOnly true
git config --local core.hooksPath
```

Expected value: `.githooks`.
