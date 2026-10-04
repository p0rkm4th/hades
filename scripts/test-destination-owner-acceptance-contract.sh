#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
validator="$repo_dir/scripts/validate-destination-owner-acceptance.sh"
template="$repo_dir/acceptance/destination-owner-acceptance-template.txt"

[[ -x "$validator" ]] || { echo 'FAIL destination acceptance validator is not executable'; exit 1; }
[[ -f "$template" ]] || { echo 'FAIL destination acceptance template missing'; exit 1; }
if HADES_DESTINATION_HOSTNAME=synthetic-destination "$validator" "$template" >/tmp/hades-destination-acceptance-contract.out 2>&1; then
  echo 'FAIL untouched acceptance template was accepted'
  exit 1
fi
grep -q 'owner_login=NOT RUN' "$template" || { echo 'FAIL template must remain pending'; exit 1; }
grep -q 'destination=DESTINATION_HOSTNAME' "$template" && grep -q 'REAL_DESTINATION' "$template" || { echo 'FAIL real-destination marker missing'; exit 1; }
grep -q 'operator_notes=REQUIRED' "$template" || { echo 'FAIL operator notes placeholder missing'; exit 1; }
grep -q 'operator_notes must contain a non-placeholder human record' "$validator" || { echo 'FAIL operator notes guard missing'; exit 1; }
grep -q 'duplicate acceptance field' "$validator" || { echo 'FAIL duplicate-field guard missing'; exit 1; }
grep -q 'unknown acceptance field' "$validator" || { echo 'FAIL unknown-field guard missing'; exit 1; }
echo 'PASS destination owner-acceptance contract fails closed before owner session'
