# Setup

Back to docs index: `docs/README.md`

## Prerequisites

- Windows with PowerShell.
- Python 3.10+.
- `ffmpeg` installed and available in `PATH`.
- A valid `OPENAI_API_KEY`.

## Environment Setup

From repo root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Configure API Key

Create local environment file:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set:

```env
OPENAI_API_KEY=your_real_key_here
```

`.env` is local-only and must never be committed.

## Prepare Name Maps

Create local map files from examples:

```powershell
Copy-Item campaigns\dungeon_of_the_mad_mage\dotmm_scripts\handle_map.example.csv campaigns\dungeon_of_the_mad_mage\dotmm_scripts\handle_map.csv
Copy-Item campaigns\dungeon_of_the_mad_mage\dotmm_scripts\realname_map.example.csv campaigns\dungeon_of_the_mad_mage\dotmm_scripts\realname_map.csv
```

Map format is `source;replacement` (semicolon-delimited).

## First Successful Run Checklist

1. Run Stage 1:

```powershell
cd campaigns\dungeon_of_the_mad_mage\dotmm_scripts
python .\stage1_transcribe_dotmm_v6.py --session session_001_audio
```

2. Run Stage 2:

```powershell
python .\stage2_merge_dotmm_transcripts_v6.py --session session_001_transcript --scene-gap 10 --window 6 --max-repeats 5 --force
```

3. Run Stage 3:

```powershell
python .\stage3_clean_names_v3.py ..\dotmm_output\session_001_transcript\_raw .\handle_map.csv .\realname_map.csv --force
```

4. Confirm outputs exist locally and are ignored by Git:

```powershell
git check-ignore -v ..\dotmm_output\session_001_transcript\session_001_annotated_recap_v2.md
```
