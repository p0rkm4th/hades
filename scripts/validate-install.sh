#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
inputs=''; root=/; test_mode=0
while (($#)); do
  case "$1" in
    --inputs) inputs=${2:?--inputs needs a file}; shift 2 ;;
    --root) root=${2:?--root needs a directory}; shift 2 ;;
    --test-mode) test_mode=1; shift ;;
    -h|--help) echo 'usage: validate-install.sh [--inputs FILE] [--root DIR] [--test-mode]'; exit 0 ;;
    *) echo "FAIL unknown option: $1"; exit 2 ;;
  esac
done
[[ -f "$repo_dir/config/versions.env" ]] || { echo 'FAIL version manifest missing'; exit 1; }
source "$repo_dir/config/versions.env"
if [[ -n "$inputs" && -f "$inputs" ]]; then source "$inputs"; fi
state="${root%/}${HADES_STATE_ROOT:-/var/lib/hades}/install-contract"
[[ -f "$state" ]] || { echo 'FAIL installer contract marker missing'; exit 1; }
grep -q '^manifest=' "$state" || { echo 'FAIL installer marker is malformed'; exit 1; }
if (( ! test_mode )) && command -v docker >/dev/null 2>&1; then
  for f in deploy/*.compose.yaml; do docker compose -f "$f" config --quiet || { echo "FAIL compose $(basename "$f")"; exit 1; }; done
fi
if ((test_mode)); then
  echo 'PASS synthetic authenticated-path placeholder contract'
  echo 'PASS synthetic validation: production credentials and fixture state were not created'
else
  echo 'WARN full conversation, identity, memory, Grocy, search, and operator checks require live private inputs'
fi
echo 'PASS install validation contract'
