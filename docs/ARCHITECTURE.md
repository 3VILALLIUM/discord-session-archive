# Architecture

Back to docs index: `docs/README.md`

## Pipeline Overview

LoreBot is a local-first three-stage transcript pipeline:

1. Stage 1 transcribes audio into structured transcript chunks.
2. Stage 2 merges chunks into a raw markdown transcript.
3. Stage 3 replaces handles and real names to produce cleaned markdown.

## Data Flow

`dotmm_sessions/raw_audio` -> `dotmm_transcripts` -> `dotmm_output/<session>/_raw` -> `dotmm_output/<session>/*_cleaned.md`

Generated artifacts remain local-only by policy and guardrails.

## Script to Stage Mapping

| Stage | Script | Main Input | Main Output |
| --- | --- | --- | --- |
| 1 | `campaigns/dungeon_of_the_mad_mage/dotmm_scripts/stage1_transcribe_dotmm_v6.py` | `dotmm_sessions/raw_audio/session_*_audio` | `dotmm_transcripts/session_*_transcript/**/*.json` |
| 2 | `campaigns/dungeon_of_the_mad_mage/dotmm_scripts/stage2_merge_dotmm_transcripts_v6.py` | `dotmm_transcripts/session_*_transcript` | `dotmm_output/session_*_transcript/_raw/*_merged_raw_v*.md` |
| 3 | `campaigns/dungeon_of_the_mad_mage/dotmm_scripts/stage3_clean_names_v3.py` | Raw merged markdown + map CSVs | `dotmm_output/session_*_transcript/*_cleaned.md` |
| Alternative CLI | `campaigns/dungeon_of_the_mad_mage/dotmm_scripts/ttrpg_transcribe.py` | Audio file(s) or folder(s) | Transcript JSON + logs |

## Privacy Boundary

- Public repo surface is scripts, tests, docs, and guardrails.
- Output folders and generated artifacts are local-only.
- Real map CSVs are local-only; only `*.example.csv` files are trackable.

## Testing Surface

Current automated tests target the alternative transcription CLI:

- `tests/test_ttrpg_transcribe.py`

Run:

```powershell
python -m pytest -q
```
