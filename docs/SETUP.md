# Setup

Back to docs index: `docs/README.md`

## Before You Run Scripts

Do not run scripts you are unfamiliar with. Review setup scripts before execution, especially in newly cloned repositories.

Audit-first commands (PowerShell):

```powershell
git status --short
cmd /c findstr /n ".*" scripts\bootstrap.ps1
cmd /c findstr /n ".*" scripts\init_local_config.ps1
cmd /c findstr /n ".*" scripts\privacy_guard_check.ps1
cmd /c findstr /n ".*" .githooks\pre-commit
cmd /c findstr /n ".*" .githooks\pre-push
```

Audit-first commands (bash):

```bash
git status --short
cat -n scripts/bootstrap.sh
cat -n scripts/init_local_config.sh
cat -n scripts/privacy_guard_check.sh
cat -n .githooks/pre-commit
cat -n .githooks/pre-push
```

## Setup Modes

- Automated setup (recommended): `scripts/bootstrap.ps1` (Windows PowerShell) or `scripts/bootstrap.sh` (bash).
- Manual setup: explicit commands with no bootstrap script execution.

After setup completes, the repo is ready to run after you set `OPENAI_API_KEY` in `.env`.

## Automated Setup (Bootstrap)

PowerShell plan mode:

```powershell
.\scripts\bootstrap.ps1 -Plan
```

bash plan mode:

```bash
bash ./scripts/bootstrap.sh --plan
```

PowerShell default run:

```powershell
.\scripts\bootstrap.ps1
```

bash default run:

```bash
bash ./scripts/bootstrap.sh
```

Default mode checks dependencies and exits with code `2` if `python`, `ffmpeg`, or `git` are missing.

Opt-in dependency install:

```powershell
.\scripts\bootstrap.ps1 -InstallMissingDependencies
.\scripts\bootstrap.ps1 -InstallMissingDependencies -Yes
```

```bash
bash ./scripts/bootstrap.sh --install-missing-dependencies
bash ./scripts/bootstrap.sh --install-missing-dependencies --yes
```

Bootstrap exit codes:

- `0`: success
- `2`: missing dependencies and install mode disabled/declined
- `3`: no supported package manager found
- `4`: dependency install attempted but failed

Bootstrap done state:

- `.venv` exists and requirements installed
- `core.hooksPath` is `.githooks`
- `.env` exists
- `_local/config/name_replace_map.json` exists

## Manual Setup (No Bootstrap)

### 1. Install dependencies

Install:

- Python 3.10+
- ffmpeg (on `PATH`)
- Git

Examples (Windows):

```powershell
winget install --id Python.Python.3 -e --source winget
winget install --id Gyan.FFmpeg -e --source winget
winget install --id Git.Git -e --source winget
```

### 2. Create venv and install requirements

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure hooks

```powershell
git config core.hooksPath .githooks
git config --get core.hooksPath
```

Expected value: `.githooks`

### 4. Initialize local templates

```powershell
.\scripts\init_local_config.ps1
```

```bash
bash ./scripts/init_local_config.sh
```

This creates local-only files if missing:

- `.env`
- `_local/config/name_replace_map.json`

### 5. Set API key

Edit `.env`:

```env
OPENAI_API_KEY=your_real_key_here
```

## Name Replacement Map

Use one unified map file:

- `_local/config/name_replace_map.json`

The same map handles:

- Discord handle aliases
- spoken-name aliases

The default mode is `--name-map-mode replace`.
Use `--name-map-mode none` to disable replacements.

## Running the CLI

Default newbie run (no args, opens folder picker):

```powershell
python .\src\discord_session_archive.py
```

Manual path mode (optional customization):

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport"
```

Useful runtime flags:

- `--input <path>` bypass picker and use explicit path(s)
- `--pick-folder` explicitly force picker mode
- `--language auto|<code>` default `auto`
- `--quality-filter balanced|strict|off` default `balanced`
- `--track-workers 4` track-level parallelism
- `--api-workers 4` global paid API concurrency cap
- `--max-workers <n>` per-track chunk worker pool
- `--name-map-mode none` disables replacement map
- `--force` overwrite existing run directory

Example (faster + force English):

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --language en --track-workers 4 --api-workers 4
```

## Output Contract

Run directory:

```text
_local/runs/<run_id>/
```

Saved artifacts per run:

```text
_local/runs/<run_id>/<run_id>_transcript.md
_local/runs/<run_id>/<run_id>_log.md
```

No JSON and no NotebookLM file are generated.

Run ID precedence:

1. `--label` (highest precedence)
2. Craig `info.txt` (`<Guild_Name>_<StartTimeISOWithColonsReplacedByDash>`)
3. UTC timestamp fallback

Discord-style long numeric guild IDs found in `Guild` are stripped from filename naming.

If `info.txt` contains Craig notes (including timestamped note lines), they are included in transcript frontmatter under `craig_notes`.
Do not put personal or sensitive information in Craig notes unless you want it to appear in the transcript output.

## Done State Checklist

You are ready when:

- `python --version` works
- `ffmpeg -version` works
- `git --version` works
- `.venv` exists
- `pip install -r requirements.txt` completed
- `git config --get core.hooksPath` returns `.githooks`
- `.env` has real `OPENAI_API_KEY`
- `_local/config/name_replace_map.json` exists
