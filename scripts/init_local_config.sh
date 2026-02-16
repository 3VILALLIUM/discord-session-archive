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

handle_map_path="_local/config/handle_map.json"
if [[ ! -f "$handle_map_path" ]]; then
  cat > "$handle_map_path" <<'JSON'
{
  "__comment_1": "Handle map: replace Discord handles/labels with your preferred names.",
  "__comment_2": "Keys are aliases; values are the preferred output speaker labels.",
  "__comment_3": "Add variants (with/without @, hyphen, underscore, spacing) for reliability.",
  "speaker one": "Example Preferred Name One",
  "@speaker-one": "Example Preferred Name One",
  "speaker two": "Example Preferred Name Two"
}
JSON
  echo "Created $handle_map_path"
else
  echo "$handle_map_path already exists; leaving unchanged"
fi

realname_map_path="_local/config/realname_map.json"
if [[ ! -f "$realname_map_path" ]]; then
  cat > "$realname_map_path" <<'JSON'
{
  "__comment_1": "Real-name map: optionally replace spoken-name labels with preferred real names.",
  "__comment_2": "Keys are aliases; values are canonical output speaker labels.",
  "__comment_3": "Transcript text is unchanged; only speaker labels are remapped.",
  "speaker one": "Example Person One",
  "example person one": "Example Person One",
  "speaker two": "Example Person Two"
}
JSON
  echo "Created $realname_map_path"
else
  echo "$realname_map_path already exists; leaving unchanged"
fi

echo
echo "Next steps:"
echo "1. Edit .env and set OPENAI_API_KEY"
echo "2. Edit _local/config/handle_map.json and _local/config/realname_map.json"
echo "3. Choose map mode per run with --name-map-mode none|handle|real"
