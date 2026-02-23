# Docs Index

Canonical docs for `discord-session-archive`.

## Big Thanks to Craig

Huge thanks to the Craig project for making Discord recording workflows possible:
- https://craig.chat/
- https://discord.bots.gg/bots/272937604339466240
- https://www.patreon.com/CraigRec

## Reading Order

1. `docs/SETUP.md`
2. `docs/ARCHITECTURE.md`
3. `docs/PRIVACY.md`
4. `SECURITY.md`
5. `docs/TROUBLESHOOTING.md`
6. `docs/POLICY.md`

## Docs Map

- `docs/SETUP.md`: canonical setup source (automated bootstrap + manual path + default picker run).
- `docs/ARCHITECTURE.md`: single-run architecture and run artifact contract.
- `docs/PRIVACY.md`: privacy model, guardrails, and audit commands.
- `SECURITY.md`: private reporting channel for security, vulnerability, and legal concerns.
- `docs/TROUBLESHOOTING.md`: common failures and fixes.
- `docs/POLICY.md`: no-community-input and support policy.

## Doc ownership

- `docs/SETUP.md` owns CLI flag definitions and defaults.
- `docs/TROUBLESHOOTING.md` owns symptom-to-fix recipes.
- `README.md` keeps only high-level summary and links.

Maintenance note:

- When CLI behavior changes, update `docs/SETUP.md` first.
- Then update `docs/TROUBLESHOOTING.md` for affected symptoms.
- Keep `README.md` limited to pointers into canonical docs.

## Transcript Quality Note

`whisper-1` frequently misidentifies background noise as words and will try to transcribe them.
This project corrects for that with post-processing heuristics that suppress repeated low-information artifacts (for example repetitive `you`, `okay`, or `thank you` bursts), remove overlap duplicates, and keep higher-signal lines.
Accuracy still depends on source audio quality: mumbling, low speaking volume, cross-talk, clipped audio, and poor microphones can all reduce results.
For tabletop sessions, number-only lines can be real speech (for example dice rolls and totals), so filtering is intentionally conservative and may keep some numeric artifacts.
