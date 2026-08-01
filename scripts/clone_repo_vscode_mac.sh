#!/usr/bin/env bash
set -euo pipefail

DEFAULT_REPO_URL="https://github.com/3VILALLIUM/discord-audio-transcription.git"
DEFAULT_PARENT_DIR="$HOME"

usage() {
  cat <<'HELP'
Usage: bash ./scripts/clone_repo_vscode_mac.sh [--repo-url URL] [--parent-dir DIR]

Clones a repo to a user-selected location on macOS and opens it in VS Code.
If flags are omitted, the script prompts interactively.

Options:
  --repo-url URL    Git repository URL.
  --parent-dir DIR  Folder where the repo folder will be created.
  -h, --help        Show this help message.
HELP
}

repo_url="$DEFAULT_REPO_URL"
parent_dir="$DEFAULT_PARENT_DIR"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-url)
      repo_url="$2"
      shift 2
      ;;
    --parent-dir)
      parent_dir="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument '$1'" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ "${OSTYPE:-}" != darwin* ]]; then
  echo "ERROR: this script is intended for macOS." >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git is required but not found on PATH." >&2
  exit 1
fi

read -r -p "Repository URL [$repo_url]: " input_repo_url
if [[ -n "$input_repo_url" ]]; then
  repo_url="$input_repo_url"
fi

read -r -p "Save under which folder? [$parent_dir]: " input_parent_dir
if [[ -n "$input_parent_dir" ]]; then
  parent_dir="$input_parent_dir"
fi

mkdir -p "$parent_dir"

repo_name="$(basename "$repo_url")"
repo_name="${repo_name%.git}"
repo_dir="$parent_dir/$repo_name"

if [[ -e "$repo_dir" ]]; then
  echo "ERROR: target already exists: $repo_dir" >&2
  exit 1
fi

echo "Cloning $repo_url into $repo_dir"
git clone "$repo_url" "$repo_dir"

if command -v code >/dev/null 2>&1; then
  echo "Opening in VS Code..."
  code "$repo_dir"
else
  echo "VS Code 'code' command was not found."
  echo "Open VS Code, then run:"
  echo "  Command Palette -> 'Shell Command: Install \'code\' command in PATH'"
  echo "After that, you can open this repo with:"
  echo "  code '$repo_dir'"
fi

echo "Done."
