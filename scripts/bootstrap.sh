#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ ! -f ".venv/Scripts/python.exe" && ! -f ".venv/bin/python" ]]; then
  python -m venv .venv
fi

if [[ -f ".venv/Scripts/python.exe" ]]; then
  py=".venv/Scripts/python.exe"
elif [[ -f ".venv/bin/python" ]]; then
  py=".venv/bin/python"
else
  echo "ERROR: Python executable not found in .venv." >&2
  exit 1
fi

"$py" -m pip install --upgrade pip
"$py" -m pip install -r requirements.txt
git config core.hooksPath .githooks
git config --get core.hooksPath
"$py" -c "import sys; print(sys.version)"
bash scripts/privacy_guard_check.sh
