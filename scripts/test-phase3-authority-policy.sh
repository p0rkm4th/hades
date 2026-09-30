#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import json
import tempfile
from pathlib import Path

from integrations.automation.phase3_authority_policy import Phase3AuthorityPolicy
from integrations.automation.phase3_self_service import (
    Phase3Authority,
    Phase3AuthorizationError,
    Phase3Catalog,
    Phase3Runner,
    Phase3Service,
    Phase3Store,
)

owner = Phase3Authority("owner-subject", "owner", frozenset({"grocy.household"}))
with tempfile.TemporaryDirectory(prefix="hades-phase3-authority-") as tmp:
    path = Path(tmp) / "policy.json"

    def write_policy(*, active=True, resources=None, mode=0o600):
        value = {
            "schema": 1,
            "subjects": {
                owner.subject: {
                    "active": active,
                    "role": "owner",
                    "resources": resources if resources is not None else ["grocy.household"],
                },
            },
        }
        path.write_text(json.dumps(value), encoding="utf-8")
        path.chmod(mode)

    write_policy()
    policy = Phase3AuthorityPolicy(path)
    assert policy(owner.subject) == owner
    assert not policy("unknown-subject").active

    # Exercise the same policy hook used by the Hermes Phase 3 surface.
    import ast
    import os
    from integrations.automation.phase3_authority_policy import Phase3AuthorityPolicy
    overlay = ast.parse(Path("hermes/sitecustomize.py").read_text(encoding="utf-8"))
    function = next(node for node in overlay.body if isinstance(node, ast.FunctionDef) and node.name == "_hades_phase3_authority")
    namespace = {"os": os, "Phase3AuthorityPolicy": Phase3AuthorityPolicy}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "sitecustomize.py", "exec"), namespace)
    prior_policy = os.environ.get("HADES_EPSILON_PHASE3_AUTHORITY_POLICY_FILE")
    os.environ["HADES_EPSILON_PHASE3_AUTHORITY_POLICY_FILE"] = str(path)
    try:
        assert namespace["_hades_phase3_authority"](owner.subject, "household") == owner
    finally:
        if prior_policy is None:
            os.environ.pop("HADES_EPSILON_PHASE3_AUTHORITY_POLICY_FILE", None)
        else:
            os.environ["HADES_EPSILON_PHASE3_AUTHORITY_POLICY_FILE"] = prior_policy

    # Every lookup reopens the file, so a grant change between reservation and
    # dispatch blocks the source read without restarting the process.
    store = Phase3Store(str(Path(tmp) / "phase3.sqlite"))
    service = Phase3Service(store, Phase3Catalog())
    preview = service.preview(owner, "low-inventory-summary", {})
    record = service.confirm(owner, preview["preview_id"], preview["preview_hash"], "policy-fixture")
    source_reads = []
    lookups = {"count": 0}

    def revoke_after_claim(subject):
        lookups["count"] += 1
        authority = policy(subject)
        if lookups["count"] == 1:
            write_policy(active=False)
        return authority

    runner = Phase3Runner(store, revoke_after_claim, {
        "low-inventory-summary": lambda _payload: source_reads.append(True) or {"state": "READY"},
    })
    result = runner.run(record["automation_id"], "policy-revoked-before-read")
    assert result["status"] == "FAILED" and not source_reads, result
    assert not policy(owner.subject).active

    # Invalid or unsafe policy inputs fail closed instead of falling back to
    # process environment or a cached last-good value.
    write_policy(mode=0o644)
    try:
        policy(owner.subject)
    except Phase3AuthorizationError:
        pass
    else:
        raise AssertionError("world-readable authority policy was accepted")

    write_policy()
    symlink = Path(tmp) / "policy-link.json"
    symlink.symlink_to(path)
    try:
        Phase3AuthorityPolicy(symlink)(owner.subject)
    except Phase3AuthorizationError:
        pass
    else:
        raise AssertionError("symlink authority policy was accepted")

    write_policy(resources=["unapproved.resource"])
    try:
        policy(owner.subject)
    except Phase3AuthorizationError:
        pass
    else:
        raise AssertionError("unapproved resource was accepted")

print("PASS reloadable Phase 3 grant source: immediate revocation, strict owner/mode/path/schema, and fail-closed invalid policy")
PY
