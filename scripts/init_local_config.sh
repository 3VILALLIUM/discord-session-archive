#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ ! -f ".env" ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
else
  echo ".env already exists; leaving unchanged"
fi

if [[ ! -d "_local/config" ]]; then
  mkdir -p _local/config
  echo "Created _local/config"
fi

name_replace_map_path="_local/config/name_replace_map.json"
if [[ ! -f "$name_replace_map_path" ]]; then
  cat > "$name_replace_map_path" <<'JSON'
{
  "__comment_1": "Unified replacement map for handle aliases and spoken-name aliases.",
  "__comment_2": "Keys are aliases; values are canonical output speaker labels.",
  "__comment_3": "Add variants (with/without @, hyphen, underscore, spacing) for reliability.",
  "@speaker-one": "Example Preferred Name One",
  "speaker one": "Example Preferred Name One",
  "example person one": "Example Preferred Name One",
  "speaker two": "Example Preferred Name Two"
}
JSON
  echo "Created $name_replace_map_path"
else
  echo "$name_replace_map_path already exists; leaving unchanged"
fi

echo
echo "Next steps:"
echo "1. Edit .env and set OPENAI_API_KEY"
echo "2. Edit _local/config/name_replace_map.json"
echo "3. Run with --name-map-mode replace (default) or --name-map-mode none"
