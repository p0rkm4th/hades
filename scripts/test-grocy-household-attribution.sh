#!/usr/bin/env bash
set -eu

# Dependency-free contract for the Gamma shared-Grocy attribution boundary.
# It exercises the same overlay helper with an isolated audit file; no live
# Grocy state or production credential is touched.
python - <<'PY'
import importlib.util
import json
import os
import tempfile
import threading
import urllib.request
from pathlib import Path

spec = importlib.util.spec_from_file_location("hades_overlay_grocy_gamma", "hermes/sitecustomize.py")
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)

with tempfile.TemporaryDirectory(prefix="hades-grocy-audit-") as root:
    audit = Path(root) / "runtime" / "grocy-mutations.jsonl"
    os.environ["HADES_GROCY_AUDIT_FILE"] = str(audit)
    os.environ["HADES_OWNER_SUBJECT_IDS"] = "acceptance-owner"

    assert overlay._hades_record_grocy_mutation(
        "acceptance-household-a", "shopping_list_add", "product:17", "requested"
    )
    assert overlay._hades_record_grocy_mutation(
        "acceptance-household-a", "shopping_list_add", "product:17", "applied"
    )
    assert overlay._hades_record_grocy_mutation(
        "acceptance-owner", "shopping_list_add", "product:17", "already_present"
    )
    assert not overlay._hades_record_grocy_mutation(
        "bad subject", "shopping_list_add", "product:17", "requested"
    )

    rows = [json.loads(line) for line in audit.read_text().splitlines()]
    assert len(rows) == 3
    assert rows[0]["actor_subject"] == "acceptance-household-a"
    assert rows[0]["scope"] == "household"
    assert rows[2]["scope"] == "owner"
    assert rows[1]["outcome"] == "applied"
    assert all(set(row) == {
        "timestamp", "actor_subject", "scope", "resource", "operation", "target", "outcome"
    } for row in rows)
    assert audit.stat().st_mode & 0o077 == 0

    os.environ.pop("HADES_GROCY_AUDIT_FILE")
    os.environ.pop("HADES_STATE_ROOT", None)
    os.environ["HERMES_HOME"] = str(Path(root) / "profile")
    assert overlay._hades_grocy_audit_path().endswith(
        "/profile/runtime/grocy-mutations.jsonl"
    )

    class Response:
        def __init__(self, value): self.value = value
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return json.dumps(self.value).encode()

    class GrocyMock:
        def __init__(self): self.shopping = []
        def __call__(self, request, timeout=5):
            path = request.full_url.split("7003", 1)[-1]
            if path == "/api/objects/products":
                return Response([{"id": 17, "name": "Gamma Test Milk"}])
            if path == "/api/objects/shopping_list":
                if request.method == "POST":
                    self.shopping.append({"id": len(self.shopping) + 1, "product_id": 17, "done": False})
                    return Response({"created_object_id": self.shopping[-1]["id"]})
                return Response(list(self.shopping))
            raise AssertionError(path)

    mock = GrocyMock()
    previous_urlopen = urllib.request.urlopen
    urllib.request.urlopen = mock
    try:
        os.environ["HADES_GROCY_AUDIT_FILE"] = str(Path(root) / "concurrent" / "audit.jsonl")
        os.environ["GROCY_API_KEY"] = "synthetic"
        os.environ["GROCY_URL"] = "http://127.0.0.1:7003"
        results = []
        threads = [threading.Thread(
            target=lambda subject: results.append(
                overlay._hades_direct_household_grocy_mutation(
                    "add Gamma Test Milk to the shopping list", subject
                )
            ), args=(subject,)) for subject in ("acceptance-household-a", "acceptance-owner")]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        assert len(mock.shopping) == 1, mock.shopping
        assert sum("verified" in result.lower() for result in results) == 1, results
        assert sum("already" in result.lower() for result in results) == 1, results
    finally:
        urllib.request.urlopen = previous_urlopen

print("PASS shared Grocy actor attribution audit contract")
print("PASS invalid subject fails closed")
print("PASS concurrent shared Grocy add is folded to one canonical row")
assert overlay._HADES_ORDINARY_CHAT_INTENT.search("actually just say hello")
print("PASS ordinary follow-up overrides stale Grocy context")
PY
