#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
trap 'find "$fixture" -depth -mindepth 1 -delete; rmdir "$fixture" 2>/dev/null || true' EXIT
printf 'not a Hermes release\n' > "$fixture/artifact"
chmod 600 "$fixture/artifact"
test -n "$(bash "$repo_dir/scripts/install-hermes-artifact.sh" --help)"
if bash "$repo_dir/scripts/install-hermes-artifact.sh" --prefix "$fixture/prefix" \
  --artifact "$fixture/artifact" --sha256 0000000000000000000000000000000000000000000000000000000000000000 \
  >/tmp/hades-hermes-artifact-contract.out 2>&1; then
  echo 'FAIL checksum mismatch was accepted'; exit 1
fi
grep -q 'checksum mismatch' /tmp/hades-hermes-artifact-contract.out
test ! -e "$fixture/prefix"
grep -q 'python3 -m venv' "$repo_dir/scripts/install-hermes-artifact.sh"
! grep -qE 'cp .*venv|copy.*venv' "$repo_dir/scripts/install-hermes-artifact.sh"
echo 'PASS Hermes artifact checksum and fresh-venv contract'
