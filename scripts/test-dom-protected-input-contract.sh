#!/usr/bin/env bash
set -euo pipefail

node --check scripts/dom-protected-input.js
node --check scripts/dom-daily-use-soak.js
node --check scripts/dom-receipt-rotation.js

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
printf 'example@example.invalid\n' > "$tmp/email"
chmod 600 "$tmp/email"
value=$(HADES_DOM_EMAIL_FILE="$tmp/email" node -e "process.stdout.write(require('./scripts/dom-protected-input').protectedInput('HADES_DOM_EMAIL'))")
test "$value" = 'example@example.invalid'
chmod 644 "$tmp/email"
if HADES_DOM_EMAIL_FILE="$tmp/email" node -e "require('./scripts/dom-protected-input').protectedInput('HADES_DOM_EMAIL')" 2>/dev/null; then
  echo 'FAIL unprotected DOM input file was accepted' >&2
  exit 1
fi
echo 'PASS DOM harness supports protected mode-0600 input files'
echo 'PASS DOM harness rejects group/world-readable credential files'
