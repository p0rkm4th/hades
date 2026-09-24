#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
runbook="$repo_dir/docs/upgrade-decommission.md"
[[ -f "$runbook" ]] || { echo 'FAIL upgrade/decommission runbook missing'; exit 1; }
for phrase in \
  'Change exactly one component' \
  'component-specific backup' \
  'hades-doctor.sh' \
  'validate-install.sh' \
  'Reconstructable component' \
  'State-bearing migration' \
  'Authority-bearing migration' \
  'preserve `/var/lib/hades`' \
  'latest' \
  'active migration record' \
  'production-migration-20260916.md'; do
  grep -Fq "$phrase" "$runbook" || { echo "FAIL runbook omits: $phrase"; exit 1; }
done
if grep -En 'rm -rf|destroy-everything|docker compose .* down -v|docker volume prune' "$runbook"; then
  echo 'FAIL decommission runbook contains destructive cleanup'; exit 1
fi
echo 'PASS bounded upgrade and preservation-first decommission contract'
