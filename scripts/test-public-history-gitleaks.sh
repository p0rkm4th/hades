#!/usr/bin/env bash
set -euo pipefail
command -v gitleaks >/dev/null 2>&1 || { echo 'FAIL gitleaks is required for the publication gate' >&2; exit 1; }
gitleaks git --no-banner --redact --log-opts='HEAD' --exit-code 1
echo 'PASS gitleaks reachable public history scan'
