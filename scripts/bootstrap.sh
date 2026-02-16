#!/usr/bin/env bash
set -euo pipefail

EXIT_MISSING_DEPS=2
EXIT_NO_PACKAGE_MANAGER=3
EXIT_DEP_INSTALL_FAILED=4

PLAN=false
INSTALL_MISSING=false
ASSUME_YES=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --plan)
      PLAN=true
      shift
      ;;
    --install-missing-dependencies)
      INSTALL_MISSING=true
      shift
      ;;
    --yes)
      ASSUME_YES=true
      shift
      ;;
    -h|--help)
      cat <<'HELP'
Usage: scripts/bootstrap.sh [--plan] [--install-missing-dependencies] [--yes]

Options:
  --plan                          Print planned actions and exit without changes.
  --install-missing-dependencies  Attempt to install missing python/ffmpeg/git.
  --yes                           Skip install confirmation prompt.
HELP
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

PY_BOOTSTRAP_CMD=()
INSTALL_CMD=()

format_cmd() {
  local out=""
  local token
  for token in "$@"; do
    if [[ -z "$out" ]]; then
      out="$(printf '%q' "$token")"
    else
      out="$out $(printf '%q' "$token")"
    fi
  done
  echo "$out"
}

run_step() {
  local title="$1"
  shift
  echo "== $title =="
  echo "   $(format_cmd "$@")"
  "$@"
}

os_family() {
  local uname_s
  uname_s="$(uname -s 2>/dev/null || echo unknown)"
  case "${uname_s,,}" in
    linux*) echo "linux" ;;
    darwin*) echo "macos" ;;
    msys*|mingw*|cygwin*) echo "windows" ;;
    *) echo "unknown" ;;
  esac
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

detect_python_bootstrap_cmd() {
  if command_exists python; then
    PY_BOOTSTRAP_CMD=(python)
    return 0
  fi
  if command_exists python3; then
    PY_BOOTSTRAP_CMD=(python3)
    return 0
  fi
  if command_exists py; then
    PY_BOOTSTRAP_CMD=(py -3)
    return 0
  fi
  PY_BOOTSTRAP_CMD=()
  return 1
}

test_dependency() {
  local dep="$1"
  case "$dep" in
    python) detect_python_bootstrap_cmd >/dev/null ;;
    ffmpeg) command_exists ffmpeg ;;
    git) command_exists git ;;
    *)
      return 1
      ;;
  esac
}

get_missing_dependencies() {
  local dep
  local missing=()
  for dep in python ffmpeg git; do
    if ! test_dependency "$dep"; then
      missing+=("$dep")
    fi
  done
  echo "${missing[*]:-}"
}

package_manager_chain() {
  local os="$1"
  case "$os" in
    windows) echo "winget choco scoop" ;;
    macos) echo "brew port" ;;
    linux) echo "apt-get dnf yum pacman zypper" ;;
    *) echo "" ;;
  esac
}

build_install_cmd() {
  local manager="$1"
  local dep="$2"
  INSTALL_CMD=()

  case "$manager" in
    winget)
      case "$dep" in
        python) INSTALL_CMD=(winget install --id Python.Python.3 -e --source winget) ;;
        ffmpeg) INSTALL_CMD=(winget install --id Gyan.FFmpeg -e --source winget) ;;
        git) INSTALL_CMD=(winget install --id Git.Git -e --source winget) ;;
      esac
      ;;
    choco)
      case "$dep" in
        python) INSTALL_CMD=(choco install -y python) ;;
        ffmpeg) INSTALL_CMD=(choco install -y ffmpeg) ;;
        git) INSTALL_CMD=(choco install -y git) ;;
      esac
      ;;
    scoop)
      case "$dep" in
        python) INSTALL_CMD=(scoop install python) ;;
        ffmpeg) INSTALL_CMD=(scoop install ffmpeg) ;;
        git) INSTALL_CMD=(scoop install git) ;;
      esac
      ;;
    brew)
      case "$dep" in
        python) INSTALL_CMD=(brew install python) ;;
        ffmpeg) INSTALL_CMD=(brew install ffmpeg) ;;
        git) INSTALL_CMD=(brew install git) ;;
      esac
      ;;
    port)
      case "$dep" in
        python) INSTALL_CMD=(sudo port install python311) ;;
        ffmpeg) INSTALL_CMD=(sudo port install ffmpeg) ;;
        git) INSTALL_CMD=(sudo port install git) ;;
      esac
      ;;
    apt-get)
      case "$dep" in
        python) INSTALL_CMD=(sudo apt-get install -y python3 python3-venv) ;;
        ffmpeg) INSTALL_CMD=(sudo apt-get install -y ffmpeg) ;;
        git) INSTALL_CMD=(sudo apt-get install -y git) ;;
      esac
      ;;
    dnf)
      case "$dep" in
        python) INSTALL_CMD=(sudo dnf install -y python3) ;;
        ffmpeg) INSTALL_CMD=(sudo dnf install -y ffmpeg) ;;
        git) INSTALL_CMD=(sudo dnf install -y git) ;;
      esac
      ;;
    yum)
      case "$dep" in
        python) INSTALL_CMD=(sudo yum install -y python3) ;;
        ffmpeg) INSTALL_CMD=(sudo yum install -y ffmpeg) ;;
        git) INSTALL_CMD=(sudo yum install -y git) ;;
      esac
      ;;
    pacman)
      case "$dep" in
        python) INSTALL_CMD=(sudo pacman -S --noconfirm python) ;;
        ffmpeg) INSTALL_CMD=(sudo pacman -S --noconfirm ffmpeg) ;;
        git) INSTALL_CMD=(sudo pacman -S --noconfirm git) ;;
      esac
      ;;
    zypper)
      case "$dep" in
        python) INSTALL_CMD=(sudo zypper install -y python3) ;;
        ffmpeg) INSTALL_CMD=(sudo zypper install -y ffmpeg) ;;
        git) INSTALL_CMD=(sudo zypper install -y git) ;;
      esac
      ;;
  esac

  [[ ${#INSTALL_CMD[@]} -gt 0 ]]
}

show_bootstrap_plan() {
  local os="$1"
  local missing="$2"

  echo "Bootstrap plan summary"
  echo "- Repo root: $repo_root"
  echo "- OS family: $os"
  echo "- Plan mode: $PLAN"
  echo "- Install missing deps mode: $INSTALL_MISSING"
  echo "- Non-interactive confirmation: $ASSUME_YES"
  echo
  echo "Steps:"
  echo "1. Detect required external dependencies: python, ffmpeg, git"
  echo "2. Optionally install missing dependencies (explicit opt-in only)"
  echo "3. Create .venv if missing"
  echo "4. Install pip requirements into .venv"
  echo "5. Set git hooks path to .githooks"
  echo "6. Initialize local templates (.env + _local/config/*.json)"
  echo "7. Print Python version"
  echo "8. Run privacy guard"
  echo
  echo "Network actions:"
  echo "- pip install --upgrade pip"
  echo "- pip install -r requirements.txt"
  echo "- optional package-manager installs for python/ffmpeg/git"
  echo
  echo "Possible side effects:"
  echo "- create or update .venv/"
  echo "- local git config update: core.hooksPath"
  echo "- create .env if missing"
  echo "- create _local/config/handle_map.json if missing"
  echo "- create _local/config/realname_map.json if missing"
  echo
  if [[ -z "$missing" ]]; then
    echo "Dependency status: all required external dependencies are present."
  else
    echo "Dependency status: missing -> $missing"
  fi
  echo
}

show_remediation_hints() {
  local os="$1"
  shift
  local missing=("$@")
  local dep manager
  local chain=()

  if [[ ${#missing[@]} -eq 0 ]]; then
    return
  fi

  read -r -a chain <<< "$(package_manager_chain "$os")"
  echo "Missing required dependencies: ${missing[*]}"
  echo "Re-run with --install-missing-dependencies to let bootstrap attempt installation."
  echo "Manual command examples:"
  for dep in "${missing[@]}"; do
    echo "- $dep"
    for manager in "${chain[@]}"; do
      if build_install_cmd "$manager" "$dep"; then
        echo "  $(format_cmd "${INSTALL_CMD[@]}")"
      fi
    done
  done
  echo
}

install_missing_dependencies() {
  local os="$1"
  shift
  local missing=("$@")
  local chain=()
  local available=()
  local failed=()
  local dep manager
  local installed

  read -r -a chain <<< "$(package_manager_chain "$os")"
  for manager in "${chain[@]}"; do
    if command_exists "$manager"; then
      available+=("$manager")
    fi
  done

  if [[ ${#available[@]} -eq 0 ]]; then
    return $EXIT_NO_PACKAGE_MANAGER
  fi

  echo "Available package managers: ${available[*]}"

  for dep in "${missing[@]}"; do
    if test_dependency "$dep"; then
      continue
    fi

    installed=false
    for manager in "${available[@]}"; do
      if ! build_install_cmd "$manager" "$dep"; then
        continue
      fi

      if run_step "Install $dep via $manager" "${INSTALL_CMD[@]}"; then
        if test_dependency "$dep"; then
          installed=true
          break
        fi
        echo "WARNING: $dep still appears missing after running $manager command." >&2
      else
        echo "WARNING: install via $manager failed for $dep." >&2
      fi
    done

    if [[ "$installed" != true ]]; then
      failed+=("$dep")
    fi
  done

  if [[ ${#failed[@]} -gt 0 ]]; then
    echo "Dependency install attempts failed for: ${failed[*]}" >&2
    return $EXIT_DEP_INSTALL_FAILED
  fi

  return 0
}

OS_FAMILY="$(os_family)"
MISSING_RAW="$(get_missing_dependencies)"
MISSING=()
if [[ -n "$MISSING_RAW" ]]; then
  read -r -a MISSING <<< "$MISSING_RAW"
fi

show_bootstrap_plan "$OS_FAMILY" "$MISSING_RAW"

if [[ "$PLAN" == true ]]; then
  if [[ ${#MISSING[@]} -gt 0 ]]; then
    show_remediation_hints "$OS_FAMILY" "${MISSING[@]}"
  fi
  echo "Plan mode enabled; no commands were executed."
  exit 0
fi

if [[ ${#MISSING[@]} -gt 0 ]]; then
  if [[ "$INSTALL_MISSING" != true ]]; then
    show_remediation_hints "$OS_FAMILY" "${MISSING[@]}"
    exit $EXIT_MISSING_DEPS
  fi

  if [[ "$ASSUME_YES" != true ]]; then
    read -r -p "Install missing dependencies now? [y/N] " answer
    case "${answer,,}" in
      y|yes)
        ;;
      *)
        show_remediation_hints "$OS_FAMILY" "${MISSING[@]}"
        exit $EXIT_MISSING_DEPS
        ;;
    esac
  fi

  if install_missing_dependencies "$OS_FAMILY" "${MISSING[@]}"; then
    :
  else
    rc=$?
    if [[ $rc -eq $EXIT_NO_PACKAGE_MANAGER ]]; then
      echo "No supported package manager was found for $OS_FAMILY." >&2
      show_remediation_hints "$OS_FAMILY" "${MISSING[@]}"
      exit $EXIT_NO_PACKAGE_MANAGER
    fi
    show_remediation_hints "$OS_FAMILY" "${MISSING[@]}"
    exit $EXIT_DEP_INSTALL_FAILED
  fi

  MISSING_RAW="$(get_missing_dependencies)"
  MISSING=()
  if [[ -n "$MISSING_RAW" ]]; then
    read -r -a MISSING <<< "$MISSING_RAW"
  fi
  if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo "Dependencies are still missing after install attempts: ${MISSING[*]}" >&2
    show_remediation_hints "$OS_FAMILY" "${MISSING[@]}"
    exit $EXIT_DEP_INSTALL_FAILED
  fi
fi

if ! detect_python_bootstrap_cmd; then
  echo "ERROR: Python is required for bootstrap but was not found." >&2
  exit $EXIT_MISSING_DEPS
fi

if [[ ! -f ".venv/Scripts/python.exe" && ! -f ".venv/bin/python" ]]; then
  run_step "Create virtual environment" "${PY_BOOTSTRAP_CMD[@]}" -m venv .venv
else
  echo "== Virtual environment =="
  echo "   .venv already exists; leaving unchanged"
fi

if [[ -f ".venv/Scripts/python.exe" ]]; then
  py=".venv/Scripts/python.exe"
elif [[ -f ".venv/bin/python" ]]; then
  py=".venv/bin/python"
else
  echo "ERROR: Python executable not found in .venv." >&2
  exit 1
fi

run_step "Upgrade pip" "$py" -m pip install --upgrade pip
run_step "Install requirements" "$py" -m pip install -r requirements.txt
run_step "Set git hooks path" git config core.hooksPath .githooks
run_step "Show git hooks path" git config --get core.hooksPath
run_step "Initialize local config templates" bash ./scripts/init_local_config.sh
run_step "Show Python version" "$py" -c "import sys; print(sys.version)"
run_step "Privacy guard check" bash ./scripts/privacy_guard_check.sh

echo
echo "Bootstrap completed."
echo "Next steps:"
echo "1. Edit .env and set OPENAI_API_KEY"
echo "2. Run: python ./src/discord_session_archive.py --input /path/to/CraigExport --clean --json --notebooklm"
