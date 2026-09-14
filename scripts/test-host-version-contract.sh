#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
installer="$repo_dir/scripts/install-hades.sh"
grep -q 'fedora).*VERSION_ID.*44' "$installer" || { echo 'FAIL Fedora 44 is not enforced'; exit 1; }
grep -q 'rocky).*VERSION_ID.*9|10' "$installer" || { echo 'FAIL Rocky 9/10 is not enforced'; exit 1; }
grep -q 'Fedora Server 44 or Rocky Linux 9/10' "$installer" || { echo 'FAIL unsupported-version guidance is incomplete'; exit 1; }
grep -q 'Fedora Server 44' "$repo_dir/docs/host-contract.md" && grep -q 'Rocky' "$repo_dir/docs/host-contract.md" || { echo 'FAIL host contract omits supported versions'; exit 1; }
echo 'PASS supported host versions are explicit and enforced'
