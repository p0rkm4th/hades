#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
doctor="$repo_dir/scripts/hades-doctor.sh"
grep -q 'doctor_fail=0' "$doctor" || { echo 'FAIL doctor failure accumulator is missing'; exit 1; }
grep -q 'doctor_fail=1' "$doctor" || { echo 'FAIL doctor does not record runtime failures'; exit 1; }
grep -q '(( doctor_fail == 0 )) || exit 1' "$doctor" || { echo 'FAIL doctor failure status is not propagated'; exit 1; }
grep -q "PASS live container and service checks completed; no host changes were made" "$doctor" || { echo 'FAIL doctor does not report completed live checks truthfully'; exit 1; }
grep -Fq 'if [[ -n "${HADES_HINDSIGHT_COMPOSE_FILE:-}" ]]; then' "$doctor" || { echo 'FAIL doctor does not validate Hindsight worker identity when a Compose record is configured'; exit 1; }
grep -Fq 'WARN Hindsight worker identity is not checked without a Compose record' "$doctor" || { echo 'FAIL doctor does not explain when Hindsight worker identity cannot be checked'; exit 1; }
grep -Fq 'FAIL public-research privacy policy is missing from the Hermes integration root' "$doctor" || { echo 'FAIL doctor does not detect a missing runtime public-research privacy policy'; exit 1; }
grep -Fq 'openai.api_configs' "$doctor" && grep -Fq 'hades-user-{{USER_ID}}' "$doctor" || { echo 'FAIL doctor does not verify Open WebUI forwards the authenticated subject to Hermes'; exit 1; }
grep -Fq 'FAIL Open WebUI Hermes connection is missing the authenticated stable-subject header' "$doctor" || { echo 'FAIL doctor does not fail clearly when the HADES session header is absent'; exit 1; }
echo 'PASS doctor exits nonzero for failed runtime checks'
