#!/usr/bin/env bash
set -euo pipefail

# Fast current-tree guard. The history audit remains the authoritative check
# for every reachable commit; this catches new leaks before that slower scan.
matches="$(git grep -I -n -E '/home/(scootz|scotty)/|/Users/[[:alnum:]_.-]+/|(^|[^0-9])(192\.168|10|172\.(1[6-9]|2[0-9]|3[01]))\.[0-9]{1,3}\.[0-9]{1,3}([^0-9]|$)|tail[a-z0-9-]+\.ts\.net' HEAD -- . ':(exclude)scripts/public-history-audit.sh' ':(exclude)scripts/test-public-tree-safety.sh' | grep -vF '172.17.0.1' | grep -vF '172.18.0.1' || true)"
if [ -n "$matches" ]; then
  printf 'FAIL private path, address, or tailnet hostname in current tree\n' >&2
  printf '%s\n' "$matches" >&2
  exit 1
fi
if git ls-files | grep -Eqi '(^|/)(\.env|.*\.(sqlite|db|pem|p12|key)|credentials|secrets)(\.|$|/)'; then
  printf 'FAIL credential-like tracked artifact path in current tree\n' >&2
  exit 1
fi
printf 'PASS current public tree safety\n'
