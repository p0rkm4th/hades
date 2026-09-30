#!/usr/bin/env bash
set -euo pipefail
node --check scripts/dom-shell-viewport-check.js
grep -q '320, height: 568' scripts/dom-shell-viewport-check.js
grep -q '390, height: 844' scripts/dom-shell-viewport-check.js
grep -q '768, height: 1024' scripts/dom-shell-viewport-check.js
grep -q 'globalFinance' scripts/dom-shell-viewport-check.js
grep -q 'globalReceipt' scripts/dom-shell-viewport-check.js
echo 'PASS responsive shell DOM check covers narrow, mobile, and tablet viewports'
