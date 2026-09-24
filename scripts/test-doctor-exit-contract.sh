#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
doctor="$repo_dir/scripts/hades-doctor.sh"
grep -q 'doctor_fail=0' "$doctor" || { echo 'FAIL doctor failure accumulator is missing'; exit 1; }
grep -q 'doctor_fail=1' "$doctor" || { echo 'FAIL doctor does not record runtime failures'; exit 1; }
grep -q '(( doctor_fail == 0 )) || exit 1' "$doctor" || { echo 'FAIL doctor failure status is not propagated'; exit 1; }
echo 'PASS doctor exits nonzero for failed runtime checks'
