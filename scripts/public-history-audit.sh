#!/usr/bin/env bash
set -u

# Secret-free release guard for public history. A single ref scans its full
# reachable history. A BASE..HEAD range scans each newly introduced commit so
# legacy findings on an already-published base do not hide new leaks.
history_ref="${1:-HEAD}"
commits=''
fail=0

if [[ "$history_ref" == *..* ]]; then
  if [[ "$history_ref" == *...* ]]; then
    printf 'FAIL history range must use BASE..HEAD (details redacted)\n'
    exit 2
  fi
  base_ref="${history_ref%%..*}"
  head_ref="${history_ref#*..}"
  if [[ -z "$base_ref" || -z "$head_ref" || "$head_ref" == *..* ]] ||
    ! git rev-parse --verify "$base_ref^{commit}" >/dev/null 2>&1 ||
    ! git rev-parse --verify "$head_ref^{commit}" >/dev/null 2>&1; then
    printf 'FAIL invalid history range (details redacted)\n'
    exit 2
  fi
  if ! commits="$(git rev-list "$history_ref")"; then
    printf 'FAIL unable to enumerate history range (details redacted)\n'
    exit 2
  fi
else
  if ! git rev-parse --verify "$history_ref^{commit}" >/dev/null 2>&1; then
    printf 'FAIL unknown history ref (details redacted)\n'
    exit 2
  fi
  if ! commits="$(git rev-list "$history_ref")"; then
    printf 'FAIL unable to enumerate history (details redacted)\n'
    exit 2
  fi
fi

check_history() {
  local pattern="$1"
  local label="$2"
  local safe_synthetic_address="${3:-}"
  local second_safe_synthetic_address="${4:-}"
  local matches
  matches="$(for commit in $commits; do
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
  # These are container-internal application data paths from upstream images,
  # not host checkout or operator home directories. Match the narrow exception
  # also used by the current-tree safety guard.
  matches="$(printf '%s\n' "$matches" | grep -vE '/home/[[:alnum:]_.-]+/\.(pg0|n8n|cache)(/|[^[:alnum:]_-]|$)' || true)"
  # Python's threading.local() is a common false positive for the FQDN check.
  matches="$(printf '%s\n' "$matches" | grep -vF 'threading.local' | grep -vF 'self.local' || true)"
  if [ -n "$matches" ]; then
    local match_count
    match_count="$(printf '%s\n' "$matches" | awk 'END { print NR }')"
    printf 'FAIL %s (findings=%s; matched values and paths redacted)\n' "$label" "$match_count"
    fail=1
  else
    printf 'PASS %s\n' "$label"
  fi
}

# Docker bridge addresses used by disposable synthetic fixtures are not owner
# network addresses. Keep these exceptions narrow and explicit; all other
# private addresses remain findings.
check_history '/home/[[:alnum:]_.-]+/|/Users/[[:alnum:]_.-]+/|/mnt/shared/[[:alnum:]_.-]+|/var/tmp/hades-[[:alnum:]_.-]+|(^|[^0-9])(192\.168\.[0-9]{1,3}\.[0-9]{1,3}|10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|172\.(1[6-9]|2[0-9]|3[01])\.[0-9]{1,3}\.[0-9]{1,3})([^0-9]|$)' \
  'local paths and private-network addresses absent' '172.17.0.1' '172.18.0.1'
check_history 'tail[a-z0-9-]+\.ts\.net' 'tailnet hostnames absent'
check_history '(^|[^[:alnum:]_.-])([[:alnum:]-]+\.)+local([^[:alnum:]_.-]|$)|(^|[^[:alnum:]])([[:xdigit:]]{2}:){5}[[:xdigit:]]{2}([^[:alnum:]]|$)' \
  'private local-domain names and hardware addresses absent'

credential_paths="$(git rev-list --objects "$history_ref" | awk '$2 != "config/versions.env" && tolower($2) ~ /(\.env$|\.sqlite$|\.db$|\.pem$|\.p12$|\.key$|credentials|secrets)/ {print}')"
if [ -n "$credential_paths" ]; then
  credential_path_count="$(printf '%s\n' "$credential_paths" | awk 'END { print NR }')"
  printf 'FAIL credential-like tracked artifact paths present (findings=%s; paths redacted)\n' "$credential_path_count"
  fail=1
else
  printf 'PASS credential-like tracked artifact paths absent\n'
fi

printf 'SUMMARY ref=%s fail=%d\n' "$history_ref" "$fail"
exit "$fail"
