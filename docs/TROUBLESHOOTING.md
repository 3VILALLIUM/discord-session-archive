# Troubleshooting

Back to docs index: `docs/README.md`

## Setup Failures

### `OPENAI_API_KEY not set`

Symptom:
- CLI exits with key-related error.

Fix:

```powershell
Copy-Item .env.example .env
```

Set `OPENAI_API_KEY` in `.env`, then re-run.

### `ffmpeg not found in PATH`

Symptom:
- CLI exits with ffmpeg error.

Fix:
1. Install `ffmpeg`.
2. Ensure install directory is on `PATH`.
3. Restart terminal and run again.

### `ERROR: no supported audio files found`

Symptom:
- Input path exists but has no supported audio.

Fix:
- Confirm your Craig export folder contains `.mp3`, `.wav`, `.m4a`, `.aac`, or `.flac`.
- Pass explicit input:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport"
```

### Tkinter unavailable for picker

Symptom:
- `--pick-folder` fails on minimal/headless Python builds.

Fix:
- Use explicit `--input` path instead of picker mode.

## Output/Run Failures

### Existing run directory error

Symptom:
- Output folder already exists for a run ID.

Fix:
- Use `--force`, or choose a different `--label`.

### Partial transcription errors

Symptom:
- Run completes but includes chunk errors.

Fix:
- Re-run with stable network.
- Reduce parallelism:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --max-workers 1 --force
```

## Privacy Guard Failures

### `ERROR: privacy guard blocked commit`

Cause:
- Staged or tracked files match blocked artifact patterns.

Fix:

```powershell
git restore --staged <path>
git status --short
.\scripts\privacy_guard_check.ps1
```

## Hooks Not Running

Symptom:
- Local commit succeeds when it should fail.

Fix:

```powershell
git config core.hooksPath .githooks
git config --get core.hooksPath
```

Expected value: `.githooks`.
