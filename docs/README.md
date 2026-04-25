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

- `AGENTS.md`: coding-agent operating rules, including PR review and merge gates.
- `docs/SETUP.md`: canonical setup source (automated bootstrap + manual path + default picker run).
- `docs/ARCHITECTURE.md`: single-run architecture and run artifact contract.
- `docs/PRIVACY.md`: privacy model, guardrails, and audit commands.
- `SECURITY.md`: private reporting channel for security, vulnerability, and legal concerns.
- `docs/TROUBLESHOOTING.md`: common failures and fixes.
- `docs/POLICY.md`: no-community-input and support policy.

## Doc ownership

- `docs/SETUP.md` owns CLI flag definitions and defaults.
- `docs/ARCHITECTURE.md` owns the run artifact/output contract and run ID naming behavior.
- `docs/TROUBLESHOOTING.md` owns symptom-to-fix recipes.
- `AGENTS.md` owns coding-agent PR review and merge behavior.
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

## Cost Quick Estimate

Start with a small prepaid budget while validating your setup.

| Item | Estimate |
| --- | --- |
| Whisper-1 list rate (as of February 23, 2026) | $0.006/min |
| Billed audio for a 1-hour track with defaults (`120s` chunk, `5s` overlap) | `~62.58` minutes |
| Cost per 1-hour track | `~$0.38` |

Quick multiplier: total cost is approximately `0.38 x number_of_1_hour_tracks`.

Examples:

| 1-hour tracks | Estimated total |
| --- | --- |
| `1` | `~$0.38` |
| `3` | `~$1.13` |
| `6` | `~$2.25` |

Reference: https://developers.openai.com/api/docs/models/whisper-1
