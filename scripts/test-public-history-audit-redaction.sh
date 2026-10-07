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
safe_base=$(git -C "$tmp" rev-parse HEAD)

mkdir -p "$tmp/fixtures"
synthetic_address=$(printf '%s.%s.%s.%s' 192 168 77 23)
synthetic_stage_root=$(printf '/%s/%s/%s' mnt shared synthetic-stage)
printf 'synthetic address %s staging root %s\n' "$synthetic_address" "$synthetic_stage_root" >"$tmp/fixtures/private.txt"
mkdir -p "$tmp/operator"
printf '%s\n' 'synthetic credential path fixture' >"$tmp/operator/example.credentials.json"
git -C "$tmp" add fixtures/private.txt operator/example.credentials.json
git -C "$tmp" commit -qm 'synthetic private findings'
private_commit=$(git -C "$tmp" rev-parse HEAD)

set +e
output=$(cd "$tmp" && bash "$audit" HEAD 2>&1)
status=$?
set -e

if (( status != 1 )); then
  echo 'FAIL audit did not reject synthetic private history' >&2
  exit 1
fi
if grep -Fq "$synthetic_address" <<<"$output" || grep -Fq "$synthetic_stage_root" <<<"$output" || grep -Eq 'fixtures/private\.txt|example\.credentials\.json' <<<"$output"; then
  echo 'FAIL audit output disclosed a synthetic matched value or path' >&2
  exit 1
fi
grep -Fq 'findings=' <<<"$output" || { echo 'FAIL audit omitted redacted finding counts' >&2; exit 1; }
grep -Fq 'paths redacted' <<<"$output" || { echo 'FAIL credential path finding was not marked redacted' >&2; exit 1; }

set +e
range_output=$(cd "$tmp" && bash "$audit" "$safe_base..$private_commit" 2>&1)
range_status=$?
set -e
if (( range_status != 1 )); then
  echo 'FAIL range audit did not reject newly introduced synthetic findings' >&2
  exit 1
fi
if grep -Fq "$synthetic_address" <<<"$range_output" || grep -Fq "$synthetic_stage_root" <<<"$range_output" || grep -Eq 'fixtures/private\.txt|example\.credentials\.json' <<<"$range_output"; then
  echo 'FAIL range audit disclosed a synthetic matched value or path' >&2
  exit 1
fi

set +e
clean_tree_output=$(cd "$tmp" && bash "$repo_dir/scripts/test-public-tree-safety.sh" "$safe_base" 2>&1)
clean_tree_status=$?
set -e
if (( clean_tree_status != 0 )) || ! grep -Fq 'PASS current public tree safety' <<<"$clean_tree_output"; then
  echo 'FAIL current-tree guard rejected the selected clean commit' >&2
  exit 1
fi

set +e
tree_output=$(cd "$tmp" && bash "$repo_dir/scripts/test-public-tree-safety.sh" 2>&1)
tree_status=$?
set -e
if (( tree_status != 1 )); then
  echo 'FAIL current-tree guard did not reject synthetic private content' >&2
  exit 1
fi
if grep -Fq "$synthetic_address" <<<"$tree_output" || grep -Fq "$synthetic_stage_root" <<<"$tree_output" || grep -Eq 'fixtures/private\.txt|example\.credentials\.json' <<<"$tree_output"; then
  echo 'FAIL current-tree guard disclosed a synthetic matched value or path' >&2
  exit 1
fi
grep -Fq 'values and paths redacted' <<<"$tree_output" || { echo 'FAIL current-tree address finding was not marked redacted' >&2; exit 1; }

# A previously audited base may contain legacy findings. The delta scan must
# inspect only new commits after that base, while the tree guard checks the
# cleaned result.
git -C "$tmp" rm -q fixtures/private.txt operator/example.credentials.json
printf '%s\n' 'synthetic findings removed from current tree' >>"$tmp/README.md"
git -C "$tmp" add README.md
git -C "$tmp" commit -qm 'remove synthetic findings from current tree'
clean_range_output=$(cd "$tmp" && bash "$audit" "$private_commit..HEAD" 2>&1)
grep -Fq 'SUMMARY ref=' <<<"$clean_range_output" || { echo 'FAIL range audit omitted its summary' >&2; exit 1; }
grep -Fq 'fail=0' <<<"$clean_range_output" || { echo 'FAIL range audit treated excluded legacy findings as new' >&2; exit 1; }
cleaned_tree_output=$(cd "$tmp" && bash "$repo_dir/scripts/test-public-tree-safety.sh" HEAD 2>&1)
grep -Fq 'PASS current public tree safety' <<<"$cleaned_tree_output" || { echo 'FAIL public-tree guard rejected the cleaned range tip' >&2; exit 1; }
echo 'PASS public history audit scans new ranges, preserves legacy baseline, and redacts synthetic findings'
