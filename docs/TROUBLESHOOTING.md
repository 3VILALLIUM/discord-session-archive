# Troubleshooting

Back to docs index: `docs/README.md`

## Common Setup Failures

### `OPENAI_API_KEY not set`

Symptom:
- Stage scripts exit with key-related error.

Fix:

```powershell
Copy-Item .env.example .env
```

Set `OPENAI_API_KEY` in `.env`, then re-run.

### `ffmpeg not found in PATH`

Symptom:
- Transcription CLI exits with ffmpeg error.

Fix:

1. Install `ffmpeg`.
2. Ensure install directory is on `PATH`.
3. Restart terminal and re-run command.

### Tkinter unavailable errors

Symptom:
- Script requests `--session` or explicit path when GUI picker fails.

Fix:
- Pass explicit CLI arguments instead of relying on GUI picker.

Examples:

```powershell
python .\stage1_transcribe_dotmm_v6.py --session session_001_audio
python .\stage2_merge_dotmm_transcripts_v6.py --session session_001_transcript --force
python .\stage3_clean_names_v3.py ..\dotmm_output\session_001_transcript\_raw .\handle_map.csv .\realname_map.csv --force
```

## Privacy Guard Failures

### `ERROR: privacy guard blocked commit`

Cause:
- You staged a forbidden path or extension.

Fix:

```powershell
git restore --staged <path>
git status --short
bash .githooks/pre-commit; echo PRECOMMIT_EXIT_$LASTEXITCODE
```

Allowed text-file exception:
- `requirements.txt` is allowed.

### CI `Privacy Guard` fails on PR

Cause:
- Forbidden tracked file exists in branch history state.

Fix:

```powershell
git ls-files -- "campaigns/**/dotmm_output/**" "campaigns/**/dotmm_transcripts/**" "campaigns/**/dotmm_session_output_overviews/**" "*.json" "*.log" "*.mp3" "*.wav" "*.txt"
```

Untrack violations, commit, and push again.

## Hooks Not Running

Symptom:
- Local commit succeeds when it should fail.

Fix:

```powershell
git config core.hooksPath .githooks
git config --get core.hooksPath
```

Expected value: `.githooks`

## Encoding and Line Ending Warnings

### LF/CRLF warning on commit

Symptom:
- Git warns that LF will be replaced by CRLF.

Fix:
- Usually informational on Windows.
- Normalize with repository `.gitattributes` if needed for a future cleanup PR.
