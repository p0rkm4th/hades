#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
installer="$repo_dir/scripts/install-hades.sh"

preflight_line=$(grep -n '^preflight()' "$installer" | cut -d: -f1)
preflight_exit_line=$(grep -n '^if ((preflight_only)); then exit 0; fi$' "$installer" | cut -d: -f1)
record_validation_line=$(grep -n 'validate_private_records$' "$installer" | tail -1 | cut -d: -f1)

[[ -n "$preflight_line" && -n "$preflight_exit_line" && -n "$record_validation_line" ]] || {
  echo 'FAIL installer preflight markers are missing'; exit 1;
}
grep -q 'curl --silent --show-error --connect-timeout 5 --max-time 10 --output /dev/null "\$HADES_HERMES_MODEL_ENDPOINT"' "$installer" || {
  echo 'FAIL preflight omits bounded model-endpoint reachability'; exit 1;
}
grep -q 'configured model endpoint is not reachable; verify the private endpoint' "$installer" || {
  echo 'FAIL preflight endpoint failure is not actionable'; exit 1;
}
if grep -q 'not reachable: \$HADES_HERMES_MODEL_ENDPOINT' "$installer"; then
  echo 'FAIL preflight leaks the configured endpoint'; exit 1
fi
(( record_validation_line > preflight_line && record_validation_line < preflight_exit_line )) || {
  echo 'FAIL private deployment records are not validated before --preflight exits'; exit 1;
}
echo 'PASS private deployment records are validated before mutation and --preflight exit'
