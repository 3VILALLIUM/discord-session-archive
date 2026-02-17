# Architecture

Back to docs index: `docs/README.md`

## Pipeline Overview

`discord-session-archive` uses one primary pipeline script:

- `src/discord_session_archive.py`

Flow:

1. Select input folder from picker by default (or use `--input` to provide paths manually), then discover audio files.
2. Parse Craig `info.txt` (if available) for metadata, run naming, and Craig notes.
3. Split each track into overlapping chunks.
4. Transcribe chunks with OpenAI `whisper-1`.
5. Merge segments, apply quality filtering, and dedupe overlap artifacts.
6. Apply unified speaker/name replacement (`name_replace_map.json`).
7. Write cleaned transcript and run log files.

## Concurrency Model

There are three concurrency controls:

- `--track-workers`: number of tracks processed in parallel.
- `--max-workers`: per-track chunk worker pool.
- `--api-workers`: global semaphore cap for concurrent paid API calls.

The global cap prevents API overrun even when multiple tracks/chunks are active.

## Naming and Run IDs

Run ID precedence:

1. `--label` (highest precedence)
2. Craig `info.txt` metadata as `<Guild_Name>_<StartTimeISOWithColonsReplacedByDash>`
3. UTC timestamp fallback

## Output Contract

Default output root:

```text
_local/runs/<run_id>/
```

Saved artifacts per run:

```text
_local/runs/<run_id>/<run_id>_transcript.md
_local/runs/<run_id>/<run_id>_log.md
```

No JSON, NotebookLM, or raw transcript file is generated.

## Replacement Map Contract

Runtime supports one map file:

- `_local/config/name_replace_map.json`

`--name-map-mode` supports only:

- `replace` (default)
- `none`

## Testing Surface

Primary tests:

- `tests/test_discord_session_archive.py`

Run:

```powershell
python -m pytest -q
```
