#!/usr/bin/env bash
set -Eeuo pipefail
for f in deploy/*.compose.yaml; do
  grep -Eq '127\.0\.0\.1:' "$f" || { echo "FAIL $f has no loopback-only published port"; exit 1; }
  if grep -Eq '0\.0\.0\.0:|privileged:[[:space:]]*true|/var/run/docker\.sock' "$f"; then
    echo "FAIL unsafe exposure or privilege in $f"; exit 1
  fi
done
echo 'PASS tracked component exposure is private by default'
