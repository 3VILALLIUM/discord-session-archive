#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
agents_path="$repo_root/AGENTS.md"

if [[ ! -f "$agents_path" ]]; then
  echo "ERROR: AGENTS.md is required for repository PR action policy." >&2
  exit 1
fi

section="$(
  awk '
    BEGIN { in_section = 0 }
    /^## PR Review Gate[[:space:]]*$/ { in_section = 1; next }
    /^## / && in_section { exit }
    in_section { print }
  ' "$agents_path" | tr -d '\r'
)"

if [[ -z "$section" ]]; then
  echo "ERROR: AGENTS.md is missing the PR Review Gate section." >&2
  exit 1
fi

required_lines=(
  '- Closing and merging pull requests are separate, explicit user-authorized actions, never routine cleanup.'
  '- Do not close a pull request unless the user gives an explicit close instruction for that pull request.'
  '- Do not merge a pull request unless the user gives an explicit instruction containing the standalone word `MERGE` for that pull request.'
  '- Do not infer close or merge permission from phrases like "ship it", "looks good", "approved", "done", "superseded", "replace it", "clean up", or "go ahead".'
  '- Do not get clever about this rule. If the exact close or `MERGE` instruction is missing, stop and ask.'
  '- Before inspecting PR details, reviewing comments, changing labels or branches, closing, merging, or otherwise acting on a pull request, first verify GitHub Copilot code review has completed and has been checked.'
  '- The only permitted pre-review action is checking whether GitHub Copilot code review has completed.'
  '- Even with explicit close or `MERGE` instruction, do not close or merge pull requests until GitHub Copilot code review has completed and has been checked.'
  '- If Copilot review is pending, missing, incomplete, or unchecked, do not act on the pull request; wait for review completion and ask the user to proceed once it is complete and checked.'
  '- Before merging, read every pull request conversation, review thread, and comment after GitHub Copilot code review has completed.'
  '- Before merging, address every actionable comment with code, docs, tests, or a documented no-change rationale.'
  '- Before merging, reply to every actionable comment with what was done or why no change was made, then resolve the thread only after it has been addressed and replied to.'
  '- Do not merge while any pull request conversation is unread, unaddressed, unreplied, or unresolved.'
  '- GitHub may auto-close superseded PRs independently, but agents must not proactively close superseded PRs before Copilot review has completed and been checked.'
)

allowed_lines=(
  "${required_lines[@]}"
  'This section is enforced by:'
  '- `scripts/pr_action_policy_check.ps1`'
  '- `scripts/pr_action_policy_check.sh`'
  '- `.githooks/pre-commit`'
  '- `.githooks/pre-push`'
  '- `.github/workflows/guard-raw-transcripts.yml`'
  '- `tests/test_pr_action_policy.py`'
)

missing=()
for required_line in "${required_lines[@]}"; do
  if ! grep -Fqx -- "$required_line" <<< "$section"; then
    missing+=("$required_line")
  fi
done

forbidden=()
while IFS= read -r line; do
  [[ -n "$line" ]] || continue
  if [[ "$line" == *"unless the user explicitly instructs otherwise"* ]] || \
     [[ "$line" == *"has had a chance"* ]] || \
     [[ "$line" == *"had a chance to appear"* ]] || \
     [[ "$line" == *"Do not close or merge pull requests until"* && "$line" == *"unless"* ]]; then
    forbidden+=("$line")
  fi
done <<< "$section"

unexpected=()
while IFS= read -r line; do
  [[ -n "$line" ]] || continue

  found=false
  for allowed_line in "${allowed_lines[@]}"; do
    if [[ "$line" == "$allowed_line" ]]; then
      found=true
      break
    fi
  done

  if [[ "$found" != true ]]; then
    unexpected+=("$line")
  fi
done <<< "$section"

if (( ${#missing[@]} > 0 || ${#forbidden[@]} > 0 || ${#unexpected[@]} > 0 )); then
  echo "ERROR: PR action policy guard failed." >&2
  echo "AGENTS.md must keep the hard completed-review, conversation, and close/MERGE gates in the PR Review Gate section." >&2

  if (( ${#missing[@]} > 0 )); then
    echo "Missing required lines:" >&2
    printf ' - %s\n' "${missing[@]}" >&2
  fi

  if (( ${#forbidden[@]} > 0 )); then
    echo "Forbidden soft-gate lines:" >&2
    printf ' - %s\n' "${forbidden[@]}" >&2
  fi

  if (( ${#unexpected[@]} > 0 )); then
    echo "Unexpected PR Review Gate lines:" >&2
    printf ' - %s\n' "${unexpected[@]}" >&2
  fi

  exit 1
fi

echo "PR action policy check passed: completed-review, conversation, and close/MERGE gates are present."
