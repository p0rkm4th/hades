#!/usr/bin/env bash
set -Eeuo pipefail
mapfile -t compose_files < <(find deploy -type f -name '*.compose.yaml' -print | sort)
[[ ${#compose_files[@]} -gt 0 ]] || { echo 'FAIL no tracked Compose files found'; exit 1; }
for f in "${compose_files[@]}"; do
  grep -Eq '127\.0\.0\.1:' "$f" || { echo "FAIL $f has no loopback-only published port"; exit 1; }
  if grep -Eq '0\.0\.0\.0:|privileged:[[:space:]]*true|/var/run/docker\.sock' "$f"; then
    echo "FAIL unsafe exposure or privilege in $f"; exit 1
  fi
done
echo 'PASS tracked component exposure is private by default'
