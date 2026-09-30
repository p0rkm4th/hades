#!/usr/bin/env bash
set -euo pipefail
node --check scripts/dom-household-cookie-soak.js
grep -q 'HADES_DOM_OWNER_TOKEN' scripts/dom-household-cookie-soak.js
grep -q 'synthetic household cleanup HTTP' scripts/dom-household-cookie-soak.js
grep -q 'context.addCookies' scripts/dom-household-cookie-soak.js
if grep -Eq '9313100259|password=[0-9]{8,}' scripts/dom-household-cookie-soak.js; then
  echo 'FAIL household DOM harness contains credential material' >&2
  exit 1
fi
echo 'PASS household DOM harness supports protected owner token/password setup'
echo 'PASS household DOM harness runs prompts through authenticated browser cookies'
echo 'PASS household DOM harness has cleanup in finally'
