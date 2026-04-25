#!/usr/bin/env bash
set -euo pipefail

APPROVED_GIT_NAME="3VILALLIUM"
APPROVED_GIT_EMAIL="128642648+3VILALLIUM@users.noreply.github.com"
APPROVED_HOOKS_PATH=".githooks"
APPROVED_GITHUB_COMMITTER_NAME="GitHub"
APPROVED_GITHUB_COMMITTER_EMAIL="noreply@github.com"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

print_identity_fix() {
  cat <<'EOF' >&2
Fix:
  git config --local user.name "3VILALLIUM"
  git config --local user.email "128642648+3VILALLIUM@users.noreply.github.com"
  git config --local user.useConfigOnly true
  git config --local core.hooksPath .githooks
EOF
}

fail_identity_policy() {
  echo "ERROR: git identity does not match repo policy." >&2
  print_identity_fix
  exit 1
}

fail_hook_policy() {
  echo "ERROR: git hooks are not configured for this repository." >&2
  print_identity_fix
  exit 1
}

get_local_config() {
  local key="$1"
  git config --local --get "$key" 2>/dev/null || true
}

to_lower() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

committer_matches_policy() {
  local committer_name="$1"
  local committer_email="$2"

  if [[ "$committer_name" == "$APPROVED_GIT_NAME" && "$committer_email" == "$APPROVED_GIT_EMAIL" ]]; then
    return 0
  fi

  if [[ "$committer_name" == "$APPROVED_GITHUB_COMMITTER_NAME" \
    && "$committer_email" == "$APPROVED_GITHUB_COMMITTER_EMAIL" ]]; then
    return 0
  fi

  return 1
}

check_repo_config() {
  local user_name user_email use_config_only hooks_path

  user_name="$(get_local_config user.name)"
  user_email="$(get_local_config user.email)"
  use_config_only="$(git config --local --type=bool --get user.useConfigOnly 2>/dev/null || true)"
  hooks_path="$(get_local_config core.hooksPath)"

  if [[ "$user_name" != "$APPROVED_GIT_NAME" ]]; then
    fail_identity_policy
  fi
  if [[ "$user_email" != "$APPROVED_GIT_EMAIL" ]]; then
    fail_identity_policy
  fi
  if [[ "$(to_lower "$use_config_only")" != "true" ]]; then
    fail_identity_policy
  fi
  if [[ "$hooks_path" != "$APPROVED_HOOKS_PATH" ]]; then
    fail_hook_policy
  fi
}

check_commit_identities() {
  local rev author_name author_email committer_name committer_email
  local -a identity_fields

  for rev in "$@"; do
    [[ -z "$rev" ]] && continue
    identity_fields=()
    while IFS= read -r identity_field; do
      identity_fields+=("$identity_field")
    done < <(git show -s --format='%an%n%ae%n%cn%n%ce' "$rev")
    author_name="${identity_fields[0]:-}"
    author_email="${identity_fields[1]:-}"
    committer_name="${identity_fields[2]:-}"
    committer_email="${identity_fields[3]:-}"

    if [[ "$author_name" != "$APPROVED_GIT_NAME" ]]; then
      fail_identity_policy
    fi
    if [[ "$author_email" != "$APPROVED_GIT_EMAIL" ]]; then
      fail_identity_policy
    fi
    if ! committer_matches_policy "$committer_name" "$committer_email"; then
      fail_identity_policy
    fi
  done
}

usage() {
  cat <<'EOF' >&2
Usage:
  bash scripts/git_identity_guard.sh config
  bash scripts/git_identity_guard.sh range <rev-range>
  bash scripts/git_identity_guard.sh commits <rev> [<rev> ...]
EOF
  exit 1
}

mode="${1:-config}"
case "$mode" in
  config)
    check_repo_config
    ;;
  range)
    range_spec="${2:-}"
    [[ -z "$range_spec" ]] && usage
    if [[ "$range_spec" == *".."* ]]; then
      revisions=()
      while IFS= read -r revision; do
        [[ -n "$revision" ]] && revisions+=("$revision")
      done < <(git rev-list --reverse "$range_spec")
      if [[ ${#revisions[@]} -gt 0 ]]; then
        check_commit_identities "${revisions[@]}"
      fi
    else
      check_commit_identities "$range_spec"
    fi
    ;;
  commits)
    shift
    if [[ $# -gt 0 ]]; then
      check_commit_identities "$@"
    fi
    ;;
  *)
    usage
    ;;
esac
