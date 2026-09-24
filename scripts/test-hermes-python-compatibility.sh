#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
installer="$repo_dir/scripts/install-hermes-artifact.sh"
grep -q "python3.11" "$repo_dir/scripts/prepare-hades-host.sh" || {
  echo 'FAIL Rocky host preparation does not install a compatible Python runtime'
  exit 1
}
grep -q "sys.version_info >= (3, 11)" "$installer" || {
  echo 'FAIL Hermes installer does not enforce its Python floor'
  exit 1
}
grep -q "requires Python 3.11 or newer" "$installer" || {
  echo 'FAIL Hermes installer has no actionable Python compatibility error'
  exit 1
}
grep -q 'HERMES_NIX_BUILD=1' "$installer" || {
  echo 'FAIL Hermes installer does not use the upstream-supported package build path'
  exit 1
}
echo 'PASS Hermes Python compatibility is explicit and enforced'
