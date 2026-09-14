#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
for script in scripts/hades-doctor.sh scripts/validate-install.sh; do
  grep -q 'export HADES_IDENTITY_SECRETS_DIR' "$repo_dir/$script" || {
    echo "FAIL $script does not export Compose secret interpolation input"; exit 1;
  }
  grep -q '"\$repo_dir"/deploy/\*.compose.yaml' "$repo_dir/$script" || {
    echo "FAIL $script resolves deployment files relative to its repository"; exit 1;
  }
done
echo 'PASS reconstruction tools are independent of caller working directory'
