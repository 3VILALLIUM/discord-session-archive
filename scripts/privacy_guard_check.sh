#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

violations=()

to_lower() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

while IFS= read -r path; do
  lower="$(to_lower "$path")"

  if [[ "$lower" =~ (^|/)\.env[^/]*$ ]] && [[ ! "$lower" =~ (^|/)\.env\.example$ ]]; then
    violations+=("$path [secret env file variant]")
    continue
  fi

  if [[ "$path" == _local/* ]] || [[ "$path" == */_local/* ]]; then
    violations+=("$path [local runtime output]")
    continue
  fi

  if [[ "$lower" =~ \.(aac|flac|m4a|mp3|wav|mp4|ogg|opus|webm|log|key|pem)$ ]]; then
    violations+=("$path [forbidden extension]")
    continue
  fi

  if [[ "$lower" =~ (^|/)transcript(\.cleaned)?\.md$ ]] || \
     [[ "$lower" =~ (^|/)transcript\.json$ ]] || \
     [[ "$lower" =~ (^|/)notebooklm\.md$ ]] || \
     [[ "$lower" =~ (^|/)[^/]+_(transcript|log)\.md$ ]]; then
    violations+=("$path [generated transcript artifact]")
    continue
  fi
done < <(git ls-files)

secret_patterns=(
  'sk-[A-Za-z0-9]{20,}'
  'gh[pousr]_[A-Za-z0-9]{20,}'
  'AKIA[0-9A-Z]{16}'
  'ASIA[0-9A-Z]{16}'
  'xox[baprs]-[A-Za-z0-9-]{10,}'
  '-----BEGIN (RSA|DSA|EC|OPENSSH|PGP) PRIVATE KEY-----'
)

for pattern in "${secret_patterns[@]}"; do
  set +e
  grep_output="$(git grep -nI -E -- "$pattern")"
  status=$?
  set -e

  if (( status == 0 )); then
    while IFS= read -r hit; do
      [[ -n "$hit" ]] || continue
      violations+=("$hit [possible secret content]")
    done <<< "$grep_output"
    continue
  fi

  if (( status != 1 )); then
    echo "ERROR: git grep failed for pattern '$pattern' with exit code $status." >&2
    exit "$status"
  fi
done

if (( ${#violations[@]} > 0 )); then
  echo "ERROR: privacy guard blocked due to forbidden tracked files:"
  printf '%s\n' "${violations[@]}" | sort -u | sed 's/^/ - /'
  exit 1
fi

echo "Privacy guard check passed: no forbidden tracked paths found."
