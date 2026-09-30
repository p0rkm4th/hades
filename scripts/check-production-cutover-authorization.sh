#!/usr/bin/env bash
set -Eeuo pipefail

# Final, read-only authorization gate. This does not switch DNS, stop the
# laptop, or delete anything. It only permits a later operator action to begin
# when both real owner acceptance and the final infrastructure preflight pass.

record=${1:?usage: check-production-cutover-authorization.sh ACCEPTANCE_RECORD}
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
validator="$repo_dir/scripts/validate-destination-owner-acceptance.sh"
preflight="$repo_dir/scripts/production-cutover-preflight.sh"

[[ "${HADES_CUTOVER_AUTHORIZED:-}" == 1 ]] || {
  echo 'FAIL explicit HADES_CUTOVER_AUTHORIZED=1 is required'
  exit 1
}
[[ -x "$validator" && -x "$preflight" ]] || {
  echo 'FAIL cutover gate dependencies are not executable'
  exit 1
}

"$validator" "$record"

preflight_output=$(mktemp)
trap 'rm -f "$preflight_output"' EXIT
if ! "$preflight" >"$preflight_output" 2>&1; then
  cat "$preflight_output"
  echo 'FAIL infrastructure preflight did not pass; no cutover is authorized'
  exit 1
fi
cat "$preflight_output"
echo 'PASS owner acceptance and infrastructure preflight authorize the next explicit cutover step'
