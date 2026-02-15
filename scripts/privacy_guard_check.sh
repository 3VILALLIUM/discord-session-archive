#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

mapfile -t tracked < <(git ls-files)
violations=()

for path in "${tracked[@]}"; do
  lower="${path,,}"

  if [[ "$path" == ".env" ]]; then
    violations+=("$path")
    continue
  fi

  if [[ "$lower" =~ \.(log|aac|flac|m4a|mp3|wav)$ ]]; then
    violations+=("$path")
    continue
  fi

  if [[ "$path" == dotmm_output/* ]] || [[ "$path" == */dotmm_output/* ]] || \
     [[ "$path" == dotmm_transcripts/* ]] || [[ "$path" == */dotmm_transcripts/* ]] || \
     [[ "$path" == dotmm_sessions/* ]] || [[ "$path" == */dotmm_sessions/* ]] || \
     [[ "$path" == dotmm_session_output_overviews/* ]] || [[ "$path" == */dotmm_session_output_overviews/* ]]; then
    violations+=("$path")
    continue
  fi
done

if (( ${#violations[@]} > 0 )); then
  printf '%s\n' "${violations[@]}"
  exit 1
fi

echo "Privacy guard check passed: no forbidden tracked paths found."
