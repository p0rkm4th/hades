#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
installer="$repo_dir/scripts/install-hades.sh"
runtime_line=$(grep -n '^validate_started_runtime()' "$installer" | cut -d: -f1)
call_line=$(grep -n '^validate_started_runtime$' "$installer" | cut -d: -f1)
marker_line=$(grep -n "printf 'phase=deployed" "$installer" | cut -d: -f1)
[[ -n "$runtime_line" && -n "$call_line" && -n "$marker_line" ]] || {
  echo 'FAIL runtime health markers are missing'; exit 1;
}
[[ "$call_line" -lt "$marker_line" ]] || {
  echo 'FAIL deployment marker is written before runtime validation'; exit 1;
}
grep -q 'for container in hades-lldap hades-grocy hades-agent-zero' "$installer" || {
  echo 'FAIL runtime validation omits one or more tracked containers'; exit 1;
}
grep -q 'deployed container is not running: $container' "$installer" || {
  echo 'FAIL runtime validation has no tracked-container failure'; exit 1;
}
grep -q 'private deployment has no running service: $record' "$installer" || {
  echo 'FAIL runtime validation has no private-record failure'; exit 1;
}
grep -q "deployed Hermes service is not active" "$installer" || {
  echo 'FAIL runtime validation omits Hermes'; exit 1;
}
echo 'PASS installer validates tracked runtime before declaring deployment'
