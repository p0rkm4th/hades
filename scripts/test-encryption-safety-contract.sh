#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
wrapper="$repo_dir/scripts/encrypt-recovery-artifacts.sh"
for phrase in 'recovery root must not be a symlink' 'recovery tree contains a symlink' 'FAIL recovery source permissions'; do
  grep -q "$phrase" "$wrapper" || { echo "FAIL encryption wrapper omits safety check: $phrase"; exit 1; }
done
grep -q 'root_mode' "$wrapper" || { echo 'FAIL encryption wrapper omits root permission check'; exit 1; }
echo 'PASS encrypted recovery source safety contract'
