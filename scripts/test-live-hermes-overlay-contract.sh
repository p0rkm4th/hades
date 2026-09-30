#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tmp_root=${TMPDIR:-/tmp}/hades-overlay-contract.$$
mkdir -p "$tmp_root"
trap 'find "$tmp_root" -depth -type f -delete; find "$tmp_root" -depth -type d -empty -delete' EXIT
cp "$repo_dir/hermes/sitecustomize.py" "$tmp_root/sitecustomize.py"
bash "$repo_dir/scripts/verify-live-hermes-overlay.sh" "$tmp_root/sitecustomize.py" >/dev/null
printf '\n# drift fixture\n' >> "$tmp_root/sitecustomize.py"
if bash "$repo_dir/scripts/verify-live-hermes-overlay.sh" "$tmp_root/sitecustomize.py" >/dev/null 2>&1; then
  printf 'FAIL overlay drift was accepted\n' >&2
  exit 1
fi
printf 'PASS live Hermes overlay drift contract\n'
