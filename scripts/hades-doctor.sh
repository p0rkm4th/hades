#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
inputs=''; root=/; test_mode=0
while (($#)); do
  case "$1" in
    --inputs) inputs=${2:?--inputs needs a file}; shift 2 ;;
    --root) root=${2:?--root needs a directory}; shift 2 ;;
    --test-mode) test_mode=1; shift ;;
    -h|--help) echo 'usage: hades-doctor.sh [--inputs FILE] [--root DIR] [--test-mode]'; exit 0 ;;
    *) echo "FAIL unknown option: $1"; exit 2 ;;
  esac
done
[[ -f "$repo_dir/config/versions.env" ]] || { echo 'FAIL version manifest missing'; exit 1; }
[[ -f "$repo_dir/docs/component-manifest.md" ]] || { echo 'FAIL component manifest missing'; exit 1; }
source "$repo_dir/config/versions.env"
if [[ -n "$inputs" && -f "$inputs" ]]; then source "$inputs"; fi
state="${root%/}${HADES_STATE_ROOT:-/var/lib/hades}/install-contract"
[[ -f "$state" ]] && echo 'PASS installation marker' || echo 'WARN installation marker missing'
if [[ -n "$inputs" && -f "$inputs" ]]; then
  perms=$(stat -c '%a' "$inputs")
  [[ "$perms" == 600 || "$perms" == 640 ]] && echo 'PASS operator-input permissions' || echo "WARN operator-input permissions: $perms"
else echo 'WARN operator-input file not supplied'; fi
if ((test_mode)); then echo 'PASS read-only synthetic doctor'; exit 0; fi
command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 && echo 'PASS container runtime available' || echo 'WARN container runtime unavailable'
if command -v docker >/dev/null 2>&1; then
  for container in hades-lldap hades-grocy hades-agent-zero; do
    status=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null || true)
    [[ "$status" == running ]] && echo "PASS container $container" || echo "FAIL container $container state=${status:-missing}"
  done
  health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' hades-lldap 2>/dev/null || true)
  [[ "$health" == healthy ]] && echo 'PASS LLDAP health' || echo "WARN LLDAP health=${health:-not-configured}"
fi
for f in deploy/*.compose.yaml; do
  if command -v docker >/dev/null 2>&1; then docker compose -f "$f" config --quiet && echo "PASS compose $(basename "$f")" || echo "FAIL compose $(basename "$f")"; fi
done
echo 'WARN live health and exposure checks require the target runtime; no repair was performed'
