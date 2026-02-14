# LoreBot

LoreBot is a local-first transcription and cleanup pipeline for tabletop RPG sessions.

## What Is Public vs Local-Only

Public in this repo:
- Pipeline scripts
- Tests
- Documentation
- Guardrails (`.gitignore`, hooks, CI)

Local-only (must never be committed):
- Audio files
- Transcript JSON/chunks/logs
- Session output artifacts
- Name mapping CSV files

## Quickstart

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run stages:

```powershell
cd campaigns\dungeon_of_the_mad_mage\dotmm_scripts
python .\stage1_transcribe_dotmm_v6.py --session session_016_audio
python .\stage2_merge_dotmm_transcripts_v6.py --session session_016_transcript --scene-gap 10 --window 6 --max-repeats 5 --force
python .\stage3_clean_names_v3.py "C:\Users\Brigh\LoreBot\campaigns\dungeon_of_the_mad_mage\dotmm_output\session_016_transcript\_raw" .\handle_map.csv .\realname_map.csv --force
```

## Docs

See `docs/README.md` for the full docs index and reading order.

## Security/Privacy Boundary

This repository is designed so generated session artifacts remain local. Privacy guardrails are documented in `docs/PRIVACY.md`.
