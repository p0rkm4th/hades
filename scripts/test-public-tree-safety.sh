#!/usr/bin/env bash
set -euo pipefail

# Fast current-tree guard. The history audit remains the authoritative check
# for every reachable commit; this catches new leaks before that slower scan.
matches="$(git grep -I -n -E '/home/(scootz|scotty)/|/Users/[[:alnum:]_.-]+/|(^|[^0-9])(192\.168|10|172\.(1[6-9]|2[0-9]|3[01]))\.[0-9]{1,3}\.[0-9]{1,3}([^0-9]|$)|tail[a-z0-9-]+\.ts\.net' HEAD -- . ':(exclude)scripts/public-history-audit.sh' ':(exclude)scripts/test-public-tree-safety.sh' | grep -vF '172.17.0.1' | grep -vF '172.18.0.1' || true)"
fail=0
if [ -n "$matches" ]; then
  match_count="$(printf '%s\n' "$matches" | awk 'END { print NR }')"
  printf 'FAIL private path, address, or tailnet hostname in current tree (findings=%s; values and paths redacted)\n' "$match_count" >&2
  fail=1
else
  printf 'PASS private paths, addresses, and tailnet hostnames absent\n'
fi
credential_paths="$(git ls-files | grep -Ei '(^|/)(\.env|.*\.(sqlite|db|pem|p12|key)|credentials|secrets)(\.|$|/)' || true)"
if [ -n "$credential_paths" ]; then
  credential_path_count="$(printf '%s\n' "$credential_paths" | awk 'END { print NR }')"
  printf 'FAIL credential-like tracked artifact path in current tree (findings=%s; paths redacted)\n' "$credential_path_count" >&2
  fail=1
else
  printf 'PASS credential-like tracked artifact paths absent\n'
fi
if (( fail == 0 )); then
  printf 'PASS current public tree safety\n'
  exit 0
fi
exit 1
