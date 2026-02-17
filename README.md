# discord-session-archive

Turnkey Craig -> whisper-1 -> transcript pipeline.

This tool accepts a Craig export folder (or direct audio files) and writes local transcripts.
It is source-agnostic and domain-agnostic.

## Big Thanks to Craig

Huge thanks to the Craig project for making Discord recording workflows possible:
- https://craig.chat/
- https://discord.bots.gg/bots/272937604339466240
- https://www.patreon.com/CraigRec

## Setup

Do not run scripts you do not understand. Review repository code and setup scripts before execution, especially when cloning unfamiliar repositories.

All setup instructions are canonical in `docs/SETUP.md`, including:
- script review commands
- automated bootstrap (`scripts/bootstrap.ps1` and `scripts/bootstrap.sh`)
- manual no-bootstrap setup
- dependency detection and optional installer mode
- first-run command and verification checklist

Use `docs/SETUP.md` for all setup and first-run steps to avoid documentation drift.
Current runtime behavior is one-pass with two saved run artifacts:
- `<run_id>_transcript.md`
- `<run_id>_log.md`
Default CLI behavior is newbie-first: run with no input args and it opens the folder picker.
If Craig `info.txt` contains notes, they are included in transcript frontmatter (`craig_notes`).
Do not put personal/sensitive data in Craig notes unless you want it in transcript outputs.

## Privacy Boundary

Do not commit audio, transcripts, logs, or secrets.

You are responsible for understanding and complying with all applicable laws and regulations related to audio recording, consent, and transcription in your jurisdiction. This project does not provide legal advice.

Guardrails are enforced by:
- `.gitignore`
- `.githooks/pre-commit`
- `scripts/privacy_guard_check.ps1`
- `.github/workflows/guard-raw-transcripts.yml`

Details are in `docs/PRIVACY.md`.

## Documentation

Start with `docs/README.md`.

## Project Policy

This repository is provided as-is.
Pull requests, issues, discussions, and suggestions are not accepted; see `docs/POLICY.md` for the full policy.
For security, vulnerability, or legal concerns, email `reap.change_0x@icloud.com`.

## License

Free to use, copy, and modify for noncommercial use only.
See `LICENSE`.
