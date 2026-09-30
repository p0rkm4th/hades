#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
script="$repo_dir/scripts/check-production-cutover-authorization.sh"

[[ -x "$script" ]] || { echo 'FAIL cutover authorization gate is not executable'; exit 1; }
for marker in \
  'HADES_CUTOVER_AUTHORIZED=1' \
  'validate-destination-owner-acceptance.sh' \
  'production-cutover-preflight.sh' \
  'no cutover is authorized'; do
  grep -Fq -- "$marker" "$script" || { echo "FAIL authorization gate missing: $marker"; exit 1; }
done
if grep -En 'docker (rm|stop|down)|systemctl (disable|stop)|rm -rf|curl .* -X (POST|PUT|DELETE)|resolv|dnsmasq|iptables' "$script"; then
  echo 'FAIL authorization gate contains a mutating or routing operation'
  exit 1
fi
echo 'PASS production cutover authorization is explicit, fail-closed, and read-only'
