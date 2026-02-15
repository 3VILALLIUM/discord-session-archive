#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

mapfile -t tracked < <(git ls-files)
violations=()

for path in "${tracked[@]}"; do
  lower="${path,,}"

  if [[ "$path" == ".env" ]]; then
    violations+=("$path [secret env file]")
    continue
  fi

  if [[ "$path" == _local/* ]] || [[ "$path" == */_local/* ]]; then
    violations+=("$path [local runtime output]")
    continue
  fi

  if [[ "$lower" =~ \.(aac|flac|m4a|mp3|wav|mp4|log|key|pem)$ ]]; then
    violations+=("$path [forbidden extension]")
    continue
  fi

  if [[ "$lower" =~ (^|/)transcript(\.cleaned)?\.md$ ]] || \
     [[ "$lower" =~ (^|/)transcript\.json$ ]] || \
     [[ "$lower" =~ (^|/)notebooklm\.md$ ]]; then
    violations+=("$path [generated transcript artifact]")
    continue
  fi
done

if (( ${#violations[@]} > 0 )); then
  echo "ERROR: privacy guard blocked due to forbidden tracked files:"
  printf ' - %s\n' "${violations[@]}"
  exit 1
fi

echo "Privacy guard check passed: no forbidden tracked paths found."
