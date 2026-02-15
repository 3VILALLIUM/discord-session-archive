# discord-session-archive

Turnkey Craig -> whisper-1 -> transcript pipeline.

This tool accepts a Craig export folder (or direct audio files) and writes local transcripts.
It is source-agnostic and domain-agnostic.

## Big Thanks to Craig

Huge thanks to the Craig project for making Discord recording workflows possible:
- https://craig.chat/
- https://discord.bots.gg/bots/272937604339466240
- https://www.patreon.com/CraigRec

## Quickstart (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
git config core.hooksPath .githooks
Copy-Item .env.example .env
# Edit .env and set OPENAI_API_KEY
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --clean --json --notebooklm
```

Outputs are written to `_local\runs\<run_id>\` by default.

Optional picker mode:

```powershell
python .\src\discord_session_archive.py --pick-folder --clean
```

## Bootstrap Script

```powershell
.\scripts\bootstrap.ps1
```

This creates/updates `.venv`, installs requirements, sets hooks, and runs the privacy guard.

## Local Config Bootstrap

```powershell
.\scripts\init_local_config.ps1
```

This creates local-only config templates if missing:
- `.env` (copied from `.env.example`)
- `_local/config/handle_map.json`
- `_local/config/realname_map.json`

## Name Mapping Modes

Speaker label mapping is optional and never modifies transcript text content.

Use handle mapping:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --name-map-mode handle --clean --json
```

Use real-name mapping:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --name-map-mode real --clean --json
```

## Preflight Checks

Run this before real transcription runs:

```powershell
.\scripts\preflight.ps1
```

## Privacy Boundary

Do not commit audio, transcripts, logs, or secrets.

You are responsible for understanding and complying with all applicable laws and regulations related to audio recording, consent, and transcription in your jurisdiction. This project does not provide legal advice.

Guardrails are enforced by:
- `.gitignore`
- `.githooks/pre-commit`
- `scripts/privacy_guard_check.ps1`
- `.github/workflows/guard-raw-transcripts.yml`

Details are in `docs/PRIVACY.md`.

## Project Policy

This repository is provided as-is.
Pull requests, issues, discussions, and suggestions are not accepted; see `docs/POLICY.md` for the full policy.
For security, vulnerability, or legal concerns, email `reap.change_0x@icloud.com`.

## License

Free to use, copy, and modify for noncommercial use only.
See `LICENSE`.
