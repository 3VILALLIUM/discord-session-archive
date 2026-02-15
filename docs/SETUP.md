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

## One-Command Happy Path

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --clean --json --notebooklm
```

Picker alternative:

```powershell
python .\src\discord_session_archive.py --pick-folder --clean
```

## Optional Bootstrap

```powershell
.\scripts\bootstrap.ps1
```

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
