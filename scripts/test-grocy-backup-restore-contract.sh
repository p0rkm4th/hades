#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
helper="$repo_dir/scripts/test-grocy-backup-restore.sh"
grep -Fq -- '--network none' "$helper" || { echo 'FAIL restored Grocy target is not network isolated'; exit 1; }
grep -Fq 'docker image inspect "$image"' "$helper" || { echo 'FAIL restore rehearsal does not require the pinned image locally'; exit 1; }
grep -Fq 'shopping_list' "$helper" && grep -Fq 'HADES Synthetic Milk' "$helper" || {
  echo 'FAIL restore rehearsal does not verify a canonical Grocy marker'; exit 1;
}
grep -Fq 'docker volume rm "$volume"' "$helper" && grep -Fq 'docker rm -f "$container"' "$helper" || {
  echo 'FAIL restore rehearsal does not clean only its isolated resources'; exit 1;
}
if grep -Eq 'docker run[^\n]* -p ' "$helper"; then
  echo 'FAIL restore rehearsal publishes a network port'; exit 1
fi
echo 'PASS Grocy backup restore rehearsal is pinned, isolated, and self-cleaning'
