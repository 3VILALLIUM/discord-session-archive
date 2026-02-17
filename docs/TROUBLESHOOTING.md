# Troubleshooting

Back to docs index: `docs/README.md`

## Setup Failures

### Bootstrap exits with code `2`

Cause:

- Missing dependency (`python`, `ffmpeg`, or `git`) and install mode is disabled/declined.

Fix:

```powershell
.\scripts\bootstrap.ps1 -InstallMissingDependencies
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

### Removed flag error for `--clean`, `--json`, `--notebooklm`

Cause:

- These flags were intentionally removed in single-run newbie mode.

Fix:

- Run without those flags. Cleaned Markdown output is always generated automatically.

### Removed mode error for `--name-map-mode handle|real`

Cause:

- `handle` and `real` were removed.

Fix:

- Use `--name-map-mode replace` (default) and edit `_local/config/name_replace_map.json`.

### Name map file missing

Cause:

- `--name-map-mode replace` is active but map file is missing.

Fix:

```powershell
.\scripts\init_local_config.ps1
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

### Existing run directory error

Fix:

- Use `--force` or choose a different `--label`.

### Where are run logs?

Each run writes a markdown log file alongside the transcript:

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

### Random language drift / gibberish

Fix options:

1. Force language:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --language en
```

2. Increase filtering:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --quality-filter strict
```

3. Disable filtering for debugging:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --quality-filter off
```

### Run is too slow

Tune workers:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --track-workers 4 --api-workers 4 --max-workers 4
```

If your machine/API rate limits are tight, reduce workers.

## Privacy Guard Failures

### `ERROR: privacy guard blocked commit`

Fix:

```powershell
git restore --staged <path>
git status --short
.\scripts\privacy_guard_check.ps1
```

## Hooks Not Running

Fix:

```powershell
git config core.hooksPath .githooks
git config --get core.hooksPath
```

Expected value: `.githooks`.
