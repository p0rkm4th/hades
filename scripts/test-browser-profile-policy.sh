#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$repo_dir" <<'PY'
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("browser_policy", sys.argv[1] + "/integrations/browser-access/policy.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)

assert policy.select_profile("household") == {"allowed": True, "profile": "anonymous"}
assert policy.select_profile("household", "owner", owner_authorized=True)["allowed"] is False
assert policy.select_profile("owner", "owner")["allowed"] is False
assert policy.select_profile("owner", "owner", owner_authorized=True) == {"allowed": True, "profile": "owner"}
assert policy.select_profile("owner", "scotty-browser")["allowed"] is False
print("PASS anonymous browser profile is available to household scope")
print("PASS owner browser profile requires trusted explicit authorization")
print("PASS prompt-selected unknown profiles are rejected")
PY
