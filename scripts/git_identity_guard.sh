#!/usr/bin/env bash
set -euo pipefail

APPROVED_GIT_NAME="3VILALLIUM"
APPROVED_GIT_EMAIL="128642648+3VILALLIUM@users.noreply.github.com"
APPROVED_HOOKS_PATH=".githooks"

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
  if [[ "${use_config_only,,}" != "true" ]]; then
    fail_identity_policy
  fi
  if [[ "$hooks_path" != "$APPROVED_HOOKS_PATH" ]]; then
    fail_hook_policy
  fi
}

check_commit_identities() {
  local rev author_name author_email committer_name committer_email

  for rev in "$@"; do
    [[ -z "$rev" ]] && continue
    author_name="$(git show -s --format=%an "$rev")"
    author_email="$(git show -s --format=%ae "$rev")"
    committer_name="$(git show -s --format=%cn "$rev")"
    committer_email="$(git show -s --format=%ce "$rev")"

    if [[ "$author_name" != "$APPROVED_GIT_NAME" ]]; then
      fail_identity_policy
    fi
    if [[ "$author_email" != "$APPROVED_GIT_EMAIL" ]]; then
      fail_identity_policy
    fi
    if [[ "$committer_name" != "$APPROVED_GIT_NAME" ]]; then
      fail_identity_policy
    fi
    if [[ "$committer_email" != "$APPROVED_GIT_EMAIL" ]]; then
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
    mapfile -t revisions < <(git rev-list --reverse "$range_spec")
    if [[ ${#revisions[@]} -gt 0 ]]; then
      check_commit_identities "${revisions[@]}"
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
