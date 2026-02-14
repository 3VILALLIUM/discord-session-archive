# Privacy

Back to docs index: `docs/README.md`

## Forbidden to Track

Do not commit any of the following:

- Audio files and video files (`.mp3`, `.wav`, `.m4a`, `.aac`, `.flac`, `.mp4`).
- Transcript chunks and merged artifacts (`.json`, raw merged markdown outputs, recap outputs).
- Session output directories (`dotmm_output`, `dotmm_transcripts`, `dotmm_session_output_overviews`, `dotmm_sessions`, logs/chunks/raw_audio/merged trees).
- Real handle/real-name map source files (for example `handle_map.csv`, `realname_map.csv`).
- Secrets (`.env`, keys, PEM material).

Allowed exceptions include:

- `requirements.txt`
- `.env.example`
- `campaigns/dungeon_of_the_mad_mage/dotmm_scripts/handle_map.example.csv`
- `campaigns/dungeon_of_the_mad_mage/dotmm_scripts/realname_map.example.csv`

## Guardrails

- `.gitignore` blocks generated artifacts and sensitive file classes.
- `.githooks/pre-commit` blocks forbidden staged paths before commit.
- `.github/workflows/guard-raw-transcripts.yml` fails PRs/pushes if forbidden tracked files exist.

## Pre-Release Audit Commands

Run from repo root:

```powershell
git status --short
git ls-files -- "campaigns/**/dotmm_output/**" "campaigns/**/dotmm_transcripts/**" "campaigns/**/dotmm_session_output_overviews/**" "campaigns/**/dotmm_sessions/**" "*.mp3" "*.wav" "*.m4a" "*.aac" "*.flac" "*.mp4" "*.json" "*.log"
git check-ignore -v campaigns/dungeon_of_the_mad_mage/dotmm_output/session_001_transcript/session_001_annotated_recap_v2.md
```

Optional grep-based review for sensitive patterns in tracked docs/code:

```powershell
rg -n -i "transcript|recap|session_output|raw_audio|chunk|handle_map|realname_map" README.md docs campaigns .github .githooks tests
```

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

If sensitive files were pushed:

1. Remove tracking immediately in a follow-up commit.
2. Rotate any exposed credentials.
3. Plan a history rewrite if policy/legal needs require full purge.
4. Re-run privacy audit commands before reopening the repository.
