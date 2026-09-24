#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
output="$tmp/fresh-hades"

plan=$("$repo_dir/scripts/hades" setup --test-mode \
  --output "$output" \
  --profile cpu-only \
  --exposure lan \
  --owner-id owner1 \
  --model-endpoint http://127.0.0.1:11434/v1)

grep -q '^PLAN profile=cpu-only exposure=lan owner=owner1 model_endpoint=configured$' <<<"$plan"
grep -q '^PLAN generate fresh identity, build pinned artifacts, render records, and invoke the bounded installer$' <<<"$plan"
[[ ! -e "$output" ]] || { echo 'FAIL setup test mode created output state'; exit 1; }
! grep -Eq '[A-Fa-f0-9]{48,}|password|token|secret' <<<"$plan" || {
  echo 'FAIL setup test mode exposed credential-like output'; exit 1;
}

python3 -m py_compile "$repo_dir/scripts/setup-hades.py"
echo 'PASS product setup CLI is non-mutating, bounded, and secret-free in test mode'
