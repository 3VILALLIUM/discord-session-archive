# Setup

Back to docs index: `docs/README.md`

## Prerequisites

- Windows with PowerShell.
- Python 3.10+.
- `ffmpeg` installed and available in `PATH`.
- Valid `OPENAI_API_KEY`.

## Environment Setup

From repo root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
git config core.hooksPath .githooks
git config --get core.hooksPath
```

## Configure API Key

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set:

```env
OPENAI_API_KEY=your_real_key_here
```

`.env` is local-only and must never be committed.

## Initialize Local Config Templates

```powershell
.\scripts\init_local_config.ps1
```

This creates if missing:
- `.env`
- `_local/config/handle_map.json`
- `_local/config/realname_map.json`

Map files are optional and used only when `--name-map-mode handle` or `--name-map-mode real` is selected.
Map format is JSON object key/value pairs, for example:

```json
{
  "speaker one": "Example Person One",
  "speaker two": "Example Person Two"
}
```

## One-Command Happy Path

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --clean --json --notebooklm
```

No repository-level `inputs/` folder is required. Pass any folder/file path with `--input`, or use the picker mode below.

Picker alternative:

```powershell
python .\src\discord_session_archive.py --pick-folder --clean
```

Handle map mode:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --name-map-mode handle --clean --json
```

Real-name map mode:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --name-map-mode real --clean --json
```

## Name Map Reliability (Aliases)

Name map lookup is case-insensitive after trimming, and treats `_` and `-` as spaces. Add multiple alias keys per person so label replacement remains stable across formatting differences.

Checklist:
- Add variants with and without leading `@`.
- Add punctuation variants (hyphen, underscore, dots, spaces).
- Add spacing variants (`Mary-Jane`, `Mary Jane`, `MaryJane`).
- Add common nickname and misspelling variants.
- Map all alias keys to one canonical output label.

Example (placeholder data):

```json
{
  "example-name": "Example Name",
  "example_name": "Example Name",
  "example name": "Example Name",
  "@example-name": "Example Name",
  "examplename": "Example Name",
  "exampel name": "Example Name"
}
```

Use AI to generate many alias variants for each person, but do it locally and do NOT paste transcripts or private identifiers into public tools. Give the AI only the canonical name + handle you already know, ask for variants, then review and paste into your local gitignored map.

## Optional Bootstrap

```powershell
.\scripts\bootstrap.ps1
```

Bootstrap also initializes local config templates if missing (`.env`, `_local/config/handle_map.json`, `_local/config/realname_map.json`).

## Preflight

Run the local preflight before real runs:

```powershell
.\scripts\preflight.ps1
```

## Output Location

By default, outputs are written under:

```text
_local/runs/<run_id>/
```

Typical files:
- `transcript.md`
- `transcript.cleaned.md` (if `--clean`)
- `transcript.json` (if `--json`)
- `notebooklm.md` (if `--notebooklm`)
- `run.log`
