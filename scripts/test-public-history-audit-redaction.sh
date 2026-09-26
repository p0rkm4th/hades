#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
audit="$repo_dir/scripts/public-history-audit.sh"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

git -C "$tmp" init -q
git -C "$tmp" config user.name 'Synthetic Audit'
git -C "$tmp" config user.email 'audit@example.invalid'
printf '%s\n' 'synthetic private fixture' >"$tmp/README.md"
git -C "$tmp" add README.md
git -C "$tmp" commit -qm 'safe baseline'

mkdir -p "$tmp/fixtures"
synthetic_address=$(printf '%s.%s.%s.%s' 192 168 77 23)
printf 'synthetic address %s\n' "$synthetic_address" >"$tmp/fixtures/private.txt"
mkdir -p "$tmp/operator"
printf '%s\n' 'synthetic credential path fixture' >"$tmp/operator/example.credentials.json"
git -C "$tmp" add fixtures/private.txt operator/example.credentials.json
git -C "$tmp" commit -qm 'synthetic private findings'

set +e
output=$(cd "$tmp" && bash "$audit" HEAD 2>&1)
status=$?
set -e

if (( status != 1 )); then
  echo 'FAIL audit did not reject synthetic private history' >&2
  exit 1
fi
if grep -Fq "$synthetic_address" <<<"$output" || grep -Eq 'fixtures/private\.txt|example\.credentials\.json' <<<"$output"; then
  echo 'FAIL audit output disclosed a synthetic matched value or path' >&2
  exit 1
fi
grep -Fq 'findings=' <<<"$output" || { echo 'FAIL audit omitted redacted finding counts' >&2; exit 1; }
grep -Fq 'paths redacted' <<<"$output" || { echo 'FAIL credential path finding was not marked redacted' >&2; exit 1; }

set +e
tree_output=$(cd "$tmp" && bash "$repo_dir/scripts/test-public-tree-safety.sh" 2>&1)
tree_status=$?
set -e
if (( tree_status != 1 )); then
  echo 'FAIL current-tree guard did not reject synthetic private content' >&2
  exit 1
fi
if grep -Fq "$synthetic_address" <<<"$tree_output" || grep -Eq 'fixtures/private\.txt|example\.credentials\.json' <<<"$tree_output"; then
  echo 'FAIL current-tree guard disclosed a synthetic matched value or path' >&2
  exit 1
fi
grep -Fq 'values and paths redacted' <<<"$tree_output" || { echo 'FAIL current-tree address finding was not marked redacted' >&2; exit 1; }
echo 'PASS public history audit detects synthetic findings without printing matched values or paths'
