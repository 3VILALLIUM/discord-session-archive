# Architecture

Back to docs index: `docs/README.md`

Maintenance note:

- This document owns pipeline behavior and run artifact contract.
- Canonical CLI flag definitions/defaults live in `docs/SETUP.md`.

## Pipeline Overview

`discord-session-archive` uses one primary pipeline script:

- `src/discord_session_archive.py`

Flow:

1. Select input folder (or use `--input` to provide paths manually), then discover audio files.
2. Parse Craig `info.txt` (if available) for metadata, run naming, and Craig notes.
3. Split each track into overlapping chunks.
4. Transcribe chunks with OpenAI `whisper-1`.
5. Merge segments, apply quality filtering, and dedupe overlap artifacts.
6. Apply the selected legacy or campaign-profile name map to speaker labels, transcript text, and Craig metadata.
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

These outputs are local by design.
Depending on available Craig metadata, transcript frontmatter may include `guild`, `channel`, `requester`, `tracks`, `craig_notes`, `source_info_file` basename, and `start_time`.
When `--label` is omitted, `run_id` may derive from Craig metadata, and the run log may contain local filesystem paths used for troubleshooting.
Git guardrails reduce commit risk for these files, but they do not sanitize artifact contents.

## Replacement Map Contract

The replacement mode and optional profile select exactly one local source:

- `replace` without `--name-map-profile` uses `_local/config/name_replace_map.json`.
- `replace --name-map-profile PROFILE` uses `_local/config/name_maps/PROFILE.json`.
- `none` performs no replacement and cannot be combined with a profile.

Profile slugs must match `^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$`. This prevents extensions, separators, traversal, uppercase names, and other path selection.

Selected profiles use the existing JSON alias schema. Missing files, malformed JSON, non-string or empty entries, and conflicting normalized aliases fail before the API client is built. A selected profile never falls back to the legacy map.

The run log records only the profile slug and loaded-entry count. It never records map contents or the profile path, and transcript frontmatter does not record profile selection.

## Testing Surface

Primary tests:

- `tests/test_discord_session_archive.py`

Run:

```powershell
python -m pytest -q
```
