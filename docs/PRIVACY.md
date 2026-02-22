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
- Generated transcript files outside docs/code paths.

## Guardrails

- `.gitignore` blocks local outputs and sensitive file classes.
- `.githooks/pre-commit` runs privacy checks before commit.
- `.githooks/pre-push` runs privacy checks and tests before push, and blocks direct pushes to `origin/main`.
- `scripts/privacy_guard_check.ps1` / `scripts/privacy_guard_check.sh` scan tracked files.
- `.github/workflows/guard-raw-transcripts.yml` enforces the same rules in CI.

## Audit Commands

Run from repo root:

```powershell
git status --short
git ls-files
.\scripts\privacy_guard_check.ps1
.\scripts\preflight.ps1
# Requires ripgrep (rg). Alternatively: grep -rn -i "OPENAI_API_KEY\|_local\|transcript\|craig\|whisper" README.md docs scripts .githooks .github src tests
rg -n -i "OPENAI_API_KEY|_local|transcript|craig|whisper" README.md docs scripts .githooks .github src tests
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
