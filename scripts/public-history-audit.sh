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
  local matches
  matches="$(for commit in $(git rev-list "$branch"); do
    git grep -I -n -E "$pattern" "$commit" -- 2>/dev/null || true
  done)"
  if [ -n "$matches" ]; then
    printf 'FAIL %s\n' "$label"
    printf '%s\n' "$matches" | head -20
    fail=1
  else
    printf 'PASS %s\n' "$label"
  fi
}

# `/home/hindsight` is a container-internal service path, not an owner host
# path. Keep the owner workstation path explicit so the audit does not reject
# accurate container mount documentation.
check_history '/home/scootz/|/Users/[[:alnum:]_.-]+/|[[:space:]]192\.168\.|[[:space:]]10\.|[[:space:]]172\.(1[6-9]|2[0-9]|3[01])\.' \
  'local paths and private-network addresses absent'
check_history 'tail[a-z0-9-]+\.ts\.net' 'tailnet hostnames absent'

if git rev-list --objects "$branch" | rg -i '(\.env$|\.sqlite$|\.db$|\.pem$|\.p12$|\.key$|credentials|secrets)' >/dev/null; then
  printf 'FAIL credential-like tracked artifact paths present\n'
  git rev-list --objects "$branch" | rg -i '(\.env$|\.sqlite$|\.db$|\.pem$|\.p12$|\.key$|credentials|secrets)' | head -20
  fail=1
else
  printf 'PASS credential-like tracked artifact paths absent\n'
fi

printf 'SUMMARY branch=%s fail=%d\n' "$branch" "$fail"
exit "$fail"
