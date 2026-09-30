#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$repo_dir" <<'PY'
import importlib.util
import sys

spec = importlib.util.spec_from_file_location(
    "operator_policy", sys.argv[1] + "/integrations/operator-access/policy.py"
)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)

secret = "fixture-only-proxy-secret"
assert policy.authorize({}, proxy_secret=secret)["allowed"] is False
assert policy.authorize({"X-Hades-Proxy-Secret": secret, "X-Hades-Authenticated-User": "beta", "X-Hades-Authenticated-Groups": "hades-household"}, proxy_secret=secret)["allowed"] is False
owner = policy.authorize({"X-Hades-Proxy-Secret": secret, "X-Hades-Authenticated-User": "alpha", "X-Hades-Authenticated-Groups": "hades-owner,hades-household"}, proxy_secret=secret)
assert owner == {"allowed": True, "user": "alpha"}
assert policy.authorize({"X-Hades-Proxy-Secret": "wrong", "X-Hades-Authenticated-User": "alpha", "X-Hades-Authenticated-Groups": "hades-owner"}, proxy_secret=secret)["allowed"] is False
assert policy.validate_path("/operator/") == "/operator/"
assert policy.validate_path("/operator/chat/alpha%20notes?tab=1") == "/operator/chat/alpha%20notes?tab=1"
for bad in (
    "//operator",
    "operator",
    "/operator\r\nX: bad",
    "/operator/../admin",
    "/operator/%2e%2e/admin",
    "/operator/%252e%252e/admin",
    "/operator/%2f%2fevil",
    "/operator/%5c..%5cadmin",
    "/operator/%00",
    "/operator/%ZZ",
    "https://operator.example/",
    "/operator/#fragment",
):
    try:
        policy.validate_path(bad)
    except ValueError:
        pass
    else:
        raise AssertionError(bad)
print("PASS Operator trusted-proxy and owner-group policy")
print("PASS household direct-route denial policy")
print("PASS Operator path validation")
PY
python3 "$repo_dir/scripts/test-operator-session-auth.py"
