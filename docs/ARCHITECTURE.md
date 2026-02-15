# Architecture

Back to docs index: `docs/README.md`

## Pipeline Overview

`discord-session-archive` uses one primary pipeline script:

- `src/discord_session_archive.py`

Flow:
1. Discover audio files from a Craig export folder or direct file paths.
2. Split audio into overlapping chunks.
3. Transcribe chunks with OpenAI `whisper-1`.
4. Merge and sort timestamped segments.
5. Write local outputs (`.md`, optional cleaned `.md`, optional `.json`, optional NotebookLM `.md`).

## Data Flow

`input folder/files` -> `chunking + whisper-1` -> `_local/runs/<run_id>/`

Generated artifacts are local-only by policy.

## Output Contract

Default output root:

```text
_local/runs/<run_id>/
```

Files:
- `transcript.md` (always)
- `transcript.cleaned.md` (optional)
- `transcript.json` (optional)
- `notebooklm.md` (optional)
- `run.log`

## Testing Surface

Automated tests target the primary script:

- `tests/test_discord_session_archive.py`

Run:

```powershell
python -m pytest -q
```
