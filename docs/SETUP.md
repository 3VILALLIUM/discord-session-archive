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

Both paths keep local runtime outputs under `_local/` and never require committing those files.

## Automated Setup (Bootstrap)

After successful bootstrap, your local environment is ready for first run:
- `.venv` is created/updated
- Python requirements are installed
- git hooks path is configured
- local templates are initialized (`.env`, `_local/config/handle_map.json`, `_local/config/realname_map.json`)
- privacy guard is run

You still must set a real `OPENAI_API_KEY` in `.env`.

### 1. Preview Planned Actions (No Changes)

PowerShell:

```powershell
.\scripts\bootstrap.ps1 -Plan
```

bash:

```bash
bash ./scripts/bootstrap.sh --plan
```

`-Plan` / `--plan` prints actions and exits without modifying files.

### 2. Default Run (Check-Only for Missing Dependencies)

PowerShell:

```powershell
.\scripts\bootstrap.ps1
```

bash:

```bash
bash ./scripts/bootstrap.sh
```

Default mode detects missing external dependencies (`python`, `ffmpeg`, `git`) and exits with code `2` with remediation instructions.

### 3. Opt-In Install Missing Dependencies

PowerShell:

```powershell
.\scripts\bootstrap.ps1 -InstallMissingDependencies
```

PowerShell (non-interactive confirmation):

```powershell
.\scripts\bootstrap.ps1 -InstallMissingDependencies -Yes
```

bash:

```bash
bash ./scripts/bootstrap.sh --install-missing-dependencies
```

bash (non-interactive confirmation):

```bash
bash ./scripts/bootstrap.sh --install-missing-dependencies --yes
```

Install mode is explicit opt-in only. Scripts print the exact install command before execution.

### Bootstrap Exit Codes

- `0`: success
- `2`: missing dependencies and install mode disabled (or user declined install)
- `3`: no supported package manager found for dependency install mode
- `4`: dependency installation was attempted but failed

### Bootstrap Action Table

| Step | Why it runs | Side effects | Network |
|---|---|---|---|
| Detect external dependencies (`python`, `ffmpeg`, `git`) | Prevent partial setup/fail-late behavior | None | No |
| Optional dependency install (`-InstallMissingDependencies` / `--install-missing-dependencies`) | White-glove setup for beginners | System package installs | Yes |
| Create `.venv` if missing | Isolate Python dependencies locally | May create `.venv/` | No |
| Install/upgrade Python packages | Ensure runtime requirements are present | Updates venv site-packages | Yes |
| Configure git hooks path | Enforce local privacy guard hook | Updates local git config (`core.hooksPath`) | No |
| Initialize local config templates | Make repo runnable with local-only defaults | May create `.env` and `_local/config/*.json` | No |
| Print Python version | Confirm runtime path and version | None | No |
| Run privacy guard | Catch forbidden tracked files early | None | No |
| Print next steps | Keep first run explicit | None | No |

### Dependency Installer Fallback Chains

- Windows: `winget` -> `choco` -> `scoop`
- macOS: `brew` -> `port`
- Linux: `apt-get` -> `dnf` -> `yum` -> `pacman` -> `zypper`

Managed dependencies in install mode:
- Python
- ffmpeg
- Git

## Manual Setup (No Bootstrap)

Use this path if you prefer explicit step-by-step control.

### 1. Install External Dependencies

Install all three:
- Python 3.10+
- ffmpeg (on `PATH`)
- Git

Windows examples (choose one manager):

```powershell
winget install --id Python.Python.3 -e --source winget
winget install --id Gyan.FFmpeg -e --source winget
winget install --id Git.Git -e --source winget
```

```powershell
choco install -y python ffmpeg git
```

```powershell
scoop install python ffmpeg git
```

macOS examples:

```bash
brew install python ffmpeg git
```

```bash
sudo port install python311 ffmpeg git
```

Linux examples:

```bash
sudo apt-get install -y python3 python3-venv ffmpeg git
```

```bash
sudo dnf install -y python3 ffmpeg git
```

### 2. Create Virtual Environment and Install Requirements

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

bash:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Hooks

```powershell
git config core.hooksPath .githooks
git config --get core.hooksPath
```

Expected value: `.githooks`

### 4. Initialize Local Config Templates

PowerShell:

```powershell
.\scripts\init_local_config.ps1
```

bash:

```bash
bash ./scripts/init_local_config.sh
```

This creates local-only templates if missing:
- `.env`
- `_local/config/handle_map.json`
- `_local/config/realname_map.json`

### 5. Set API Key

If `.env` does not exist yet:

```powershell
Copy-Item .env.example .env
```

Then edit `.env`:

```env
OPENAI_API_KEY=your_real_key_here
```

`.env` is local-only and must never be committed.

### 6. First Run

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --clean --json --notebooklm
```

Optional folder picker:

```powershell
python .\src\discord_session_archive.py --pick-folder --clean
```

No repository-level `inputs/` folder is required. Use `--input` with any audio file/folder path.

## Name Mapping Modes (Optional)

Speaker label mapping is optional and does not modify transcript body text.

Handle map mode:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --name-map-mode handle --clean --json
```

Real-name map mode:

```powershell
python .\src\discord_session_archive.py --input "C:\path\to\CraigExport" --name-map-mode real --clean --json
```

Map files:
- `_local/config/handle_map.json`
- `_local/config/realname_map.json`

Lookup is case-insensitive after trimming and treats `_` and `-` as spaces.
Reserved keys beginning with `__comment` are ignored.

## Preflight

Run preflight before real transcription runs:

```powershell
.\scripts\preflight.ps1
```

## Done State Checklist

You are ready to run when all items below are true:
- `python --version` (or `py -3 --version`) works
- `ffmpeg -version` works
- `git --version` works
- `.venv` exists
- `pip install -r requirements.txt` completed
- `git config --get core.hooksPath` returns `.githooks`
- `.env` exists with real `OPENAI_API_KEY`
- `_local/config/handle_map.json` exists
- `_local/config/realname_map.json` exists

## Output Location

By default, outputs are written under:

```text
_local/runs/<run_id>/
```

Typical files:
- `transcript.md`
- `transcript.cleaned.md` (if `--clean`)
- `transcript.json` (if `--json`)
- `notebooklm.md` (if `--notebooklm`)
- `run.log`
