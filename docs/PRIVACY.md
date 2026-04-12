# Privacy

Back to docs index: `docs/README.md`

## Baseline Risk Model

This workflow has baseline privacy risk:
- Audio is captured by Craig.
- Audio is sent to OpenAI for transcription (`whisper-1`).

Use only data you are allowed to process and share.

Craig `info.txt` notes are copied into transcript frontmatter (`craig_notes`) when present.
Do not enter personal or sensitive information in Craig notes unless you intend to include it in transcript artifacts.

## Legal Compliance

Recording, consent, and transcription laws vary by jurisdiction and use case.
You must obtain any notice and consent required by the laws and regulations that apply to your location and participants.
You are solely responsible for legal compliance when using this repository and any generated artifacts.
This repository does not provide legal advice.

## Never Track These Artifacts

Do not commit:
- Local runtime outputs under `_local/`.
- Audio/video files (`.mp3`, `.wav`, `.m4a`, `.aac`, `.flac`, `.mp4`, `.ogg`, `.opus`, `.webm`).
- Logs (`.log`).
- Secrets (`.env`, `*.key`, `*.pem`).
- Local identity mapping files (for example `_local/config/name_replace_map.json`).
- Generated run artifacts (`<run_id>_transcript.md`, `<run_id>_log.md`) anywhere outside `_local/`.

## Guardrails

- `.gitignore` blocks `_local/`, `.env`, and sensitive file classes/extensions.
- `.githooks/pre-commit` runs privacy checks before commit.
- `.githooks/pre-push` runs privacy checks and tests before push, and blocks direct pushes to `origin/main`.
- `scripts/privacy_guard_check.ps1` / `scripts/privacy_guard_check.sh` block tracked `.env`, `_local/**`, forbidden extensions, exact generated filenames (`transcript.md`, `transcript.cleaned.md`, `transcript.json`, `notebooklm.md`), and run-style generated markdown names (`*_transcript.md`, `*_log.md`).
- `.github/workflows/guard-raw-transcripts.yml` enforces the same script checks in CI.

## Artifact Disclosure Surface

Runtime transcript and log artifacts are local by design and are not meant to be committed.
The git guardrails above reduce the risk of tracking these files, but they do not sanitize artifact contents.

Generated transcript artifacts may still disclose Craig-derived session metadata, including:
- `guild`
- `channel`
- `requester`
- `tracks`
- `craig_notes`
- `source_info_file` basename
- `start_time`

When `--label` is not provided, `run_id` may derive from Craig metadata.
Run logs may also contain local filesystem paths used for troubleshooting.

Treat generated transcript and log files as local-sensitive outputs.
Do not assume they are safe to share manually just because git guardrails are working correctly.

## Audit Commands

Run from repo root:

```powershell
git status --short
git ls-files
.\scripts\privacy_guard_check.ps1
.\scripts\preflight.ps1
# Requires ripgrep (rg). Alternatively: grep -rn -i -E "OPENAI_API_KEY|_local|transcript|craig|whisper" README.md docs scripts .githooks .github src tests
rg -n -i "OPENAI_API_KEY|_local|transcript|craig|whisper" README.md docs scripts .githooks .github src tests
# Optional targeted check for generated run markdown artifact names
git ls-files | rg -n "_(transcript|log)\.md$"
```

## API Key Handling

- Keep real keys only in `.env` or environment variables.
- Track only `.env.example`.
- Never print keys in logs, commits, issues, or screenshots.

## Incident Response

If sensitive files are staged:

```powershell
git restore --staged <path>
```

If sensitive files were committed but not pushed:

```powershell
git rm --cached <path>
git commit -m "Remove sensitive artifact from tracking"
```
