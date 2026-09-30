#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
script="$repo_dir/scripts/inventory-laptop-decommission.sh"

[[ -x "$script" ]] || { echo 'FAIL decommission inventory is not executable'; exit 1; }
grep -q 'does not stop, remove, prune, or alter' "$script" || { echo 'FAIL read-only contract missing'; exit 1; }
grep -q 'hades-open-webui' "$script" || { echo 'FAIL production container allowlist missing'; exit 1; }
grep -q 'repo_dir=' "$script" || { echo 'FAIL checkout preservation path derivation missing'; exit 1; }
grep -q 'infra_repo_dir=' "$script" || { echo 'FAIL infrastructure checkout preservation missing'; exit 1; }
grep -q 'phase=.*before' "$script" || { echo 'FAIL before/after phase marker missing'; exit 1; }
grep -q 'phase\\t' "$script" || { echo 'FAIL phase output missing'; exit 1; }
grep -q 'review-required' "$script" || { echo 'FAIL ambiguity classification missing'; exit 1; }
if grep -Eq 'docker (rm|rmi|system prune|volume rm)|systemctl .* (stop|disable)|rm -rf|shutdown|reboot' "$script"; then
  echo 'FAIL destructive operation found in decommission inventory'
  exit 1
fi

echo 'PASS laptop decommission inventory is read-only and bounded'
