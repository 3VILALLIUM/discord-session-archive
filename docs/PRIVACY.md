# Privacy

Back to docs index: `docs/README.md`

## Baseline Risk Model

This workflow has baseline privacy risk:
- Audio is captured by Craig.
- Audio is sent to OpenAI for transcription (`whisper-1`).

Use only data you are allowed to process and share.

## Never Track These Artifacts

Do not commit:
- Local runtime outputs under `_local/`.
- Audio/video files (`.mp3`, `.wav`, `.m4a`, `.aac`, `.flac`, `.mp4`).
- Logs (`.log`).
- Secrets (`.env`, `*.key`, `*.pem`).
- Generated transcript files outside docs/code paths.

## Guardrails

- `.gitignore` blocks local outputs and sensitive file classes.
- `.githooks/pre-commit` runs privacy checks before commit.
- `scripts/privacy_guard_check.ps1` / `scripts/privacy_guard_check.sh` scan tracked files.
- `.github/workflows/guard-raw-transcripts.yml` enforces the same rules in CI.

## Audit Commands

Run from repo root:

```powershell
git status --short
git ls-files
.\scripts\privacy_guard_check.ps1
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
