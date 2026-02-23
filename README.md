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

Use canonical runtime docs to avoid drift:
- `docs/SETUP.md` for setup, CLI flags/defaults, output contract, and naming rules.
- `docs/TROUBLESHOOTING.md` for symptom-to-fix guidance.

Maintenance note:
- When CLI behavior changes, update `docs/SETUP.md` first.
- Then update `docs/TROUBLESHOOTING.md` for user-facing troubleshooting changes.
- Keep this README high-level and link-based.

## Transcript Accuracy Notes

`whisper-1` can misidentify background noise as words.
Mumbling, cross-talk, low speaking volume, clipped audio, and poor microphone quality can all reduce transcript accuracy.

For tabletop sessions, short numeric lines can be legitimate (for example dice rolls, counting, damage totals), so cleanup is intentionally conservative and may leave some noisy number-only lines.

## Privacy Boundary

Do not commit audio, transcripts, logs, or secrets.

You are responsible for understanding and complying with all applicable laws and regulations related to audio recording, consent, and transcription in your jurisdiction. This project does not provide legal advice.

Guardrails are enforced by:
- `.gitignore`
- `.githooks/pre-commit`
- `.githooks/pre-push`
- `scripts/privacy_guard_check.ps1`
- `scripts/privacy_guard_check.sh`
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
