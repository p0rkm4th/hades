#!/usr/bin/env bash
set -euo pipefail
script=scripts/deploy-hermes-runtime-overlay.sh
rollback=scripts/rollback-hermes-runtime-overlay.sh
bash -n "$script" "$rollback"
for required in \
  'expected-current-sha256' \
  'expected-candidate-sha256' \
  'verify-config' \
  'trap on_exit EXIT' \
  'deployment_started=1' \
  'cp -a -- "$target" "$rollback_dir/sitecustomize.py"' \
  'mv -Tf -- "$current_tmp" "$destination"' \
  'chcon "$context" "$current_tmp"' \
  'systemctl restart "$service"' \
  'for attempt in {1..30}; do' \
  'sleep 2' \
  'runtime identity failed' \
  'verify-live' \
  'if rollback; then'; do
  grep -Fq -- "$required" "$script" || { printf 'FAIL missing deployment guarantee: %s\n' "$required" >&2; exit 1; }
done
for required in \
  'expected-current-sha256' \
  'expected-rollback-sha256' \
  'cp -a -- "$rollback_dir/sitecustomize.py" "$temporary"' \
  'mv -Tf -- "$temporary" "$target"' \
  'systemctl restart "$service"' \
  'wait_for_health "$service" "$health_url"' \
  'verify-live'; do
  grep -Fq -- "$required" "$rollback" || { printf 'FAIL missing rollback guarantee: %s\n' "$required" >&2; exit 1; }
done
if grep -Eq 'NOPASSWD:[[:space:]]*ALL|sudoers|sshd_config' "$script"; then
  echo 'FAIL deployment script contains a broad privilege change' >&2
  exit 1
fi
echo 'PASS checksum-guarded atomic deploy and rollback contract'
