#!/usr/bin/env bash
set -u

# Secret-free release guard for the public branch. It checks every commit
# reachable from the selected branch, not only the current working tree.
branch="${1:-HEAD}"
fail=0

if ! git rev-parse --verify "$branch^{commit}" >/dev/null 2>&1; then
  printf 'FAIL unknown branch: %s\n' "$branch"
  exit 2
fi

check_history() {
  local pattern="$1"
  local label="$2"
  local safe_synthetic_address="${3:-}"
  local second_safe_synthetic_address="${4:-}"
  local matches
  matches="$(for commit in $(git rev-list "$branch"); do
    # Do not match the literal detector pattern in this verifier itself.
    git grep -I -n -E "$pattern" "$commit" -- . \
      ':(exclude)scripts/public-history-audit.sh' \
      ':(exclude)scripts/test-public-tree-safety.sh' 2>/dev/null || true
  done)"
  if [ -n "$safe_synthetic_address" ]; then
    # This exact Docker bridge address is a documented disposable Ollama
    # fixture, not an owner network address. Keep the exception narrow.
    matches="$(printf '%s\n' "$matches" | grep -vF "$safe_synthetic_address" || true)"
  fi
  if [ -n "$second_safe_synthetic_address" ]; then
    matches="$(printf '%s\n' "$matches" | grep -vF "$second_safe_synthetic_address" || true)"
  fi
  if [ -n "$matches" ]; then
    printf 'FAIL %s\n' "$label"
    printf '%s\n' "$matches" | head -20
    fail=1
  else
    printf 'PASS %s\n' "$label"
  fi
}

# Docker bridge addresses used by disposable synthetic fixtures are not owner
# network addresses. Keep these exceptions narrow and explicit; all other
# private addresses remain findings.
check_history '/home/(scootz|scotty)/|/Users/[[:alnum:]_.-]+/|(^|[^0-9])(192\.168|10|172\.(1[6-9]|2[0-9]|3[01]))\.[0-9]{1,3}\.[0-9]{1,3}([^0-9]|$)' \
  'local paths and private-network addresses absent' '172.17.0.1' '172.18.0.1'
check_history 'tail[a-z0-9-]+\.ts\.net' 'tailnet hostnames absent'

credential_paths="$(git rev-list --objects "$branch" | awk '$2 != "config/versions.env" && tolower($2) ~ /(\.env$|\.sqlite$|\.db$|\.pem$|\.p12$|\.key$|credentials|secrets)/ {print}')"
if [ -n "$credential_paths" ]; then
  printf 'FAIL credential-like tracked artifact paths present\n'
  printf '%s\n' "$credential_paths" | head -20
  fail=1
else
  printf 'PASS credential-like tracked artifact paths absent\n'
fi

printf 'SUMMARY branch=%s fail=%d\n' "$branch" "$fail"
exit "$fail"
