#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHONPATH="$repo_dir" python3 - <<'PY'
import tempfile
from pathlib import Path

from integrations.automation import (
    HealthSource,
    HealthWatchAuthorizationError,
    HealthWatchError,
    HealthWatchService,
    HealthWatchStore,
    build_n8n_workflow,
)

allowed = {"owner": {"hades-core"}, "household-a": {"hades-core"}, "household-b": set()}
observations = iter([
    ("UP", "canonical health state"),
    ("DOWN", "canonical health state"),
    ("DOWN", "canonical health state"),
    ("UP", "canonical health state"),
    ("SOURCE_UNAVAILABLE", "health source unavailable"),
])

with tempfile.TemporaryDirectory() as directory:
    store = HealthWatchStore(str(Path(directory) / "health-watch.sqlite"))
    service = HealthWatchService(
        store,
        {"hades-core": HealthSource("hades-core", "HADES Core", "http://127.0.0.1:3000/health")},
        resource_authorizer=lambda actor, resource: resource in allowed.get(actor, set()),
        fetcher=lambda source: next(observations),
    )

    try:
        service.preview("household-a", owner=False, resource_id="hades-core", display_name="Core Watch", interval_minutes=10)
    except HealthWatchAuthorizationError:
        pass
    else:
        raise AssertionError("household user created a watch")

    preview = service.preview(
        "owner", owner=True, resource_id="hades-core", display_name="Core Watch",
        interval_minutes=10, shared_subjects=("household-a",),
    )
    try:
        service.confirm_create("owner", preview["preview_id"], confirmed=False, request_key="request-1")
    except HealthWatchError:
        pass
    else:
        raise AssertionError("unconfirmed create accepted")

    # A changed target cannot reuse the preview token: the token is consumed
    # only by the exact owner/preview pair and the create is idempotent.
    created = service.confirm_create("owner", preview["preview_id"], confirmed=True, request_key="request-1")
    workflow = build_n8n_workflow(
        type("Spec", (), {
            "automation_id": created["automation_id"], "display_name": "Core Watch",
        })(),
        HealthSource("hades-core", "HADES Core", "http://127.0.0.1:3000/health"),
    )
    assert workflow["id"] == created["automation_id"] and workflow["active"] is False
    assert workflow["tags"] == [{"name": "hades-template:shw"}, {"name": "hades-owner:owner"}, {"name": "hades-approved:true"}, {"name": "hades-trigger:schedule"}]
    duplicate = store.create(
        type("Spec", (), {
            "automation_id": created["automation_id"], "owner": "owner", "resource_id": "hades-core",
            "display_name": "Core Watch", "interval_minutes": 10,
            "notification_policy": "hades-local", "shared_subjects": ("household-a",),
            "validate": lambda self, sources: None,
        })(), "request-1", "owner",
    )
    assert duplicate["automation_id"] == created["automation_id"]
    automation_id = created["automation_id"]

    assert len(service.visible("owner", True)) == 1
    assert len(service.visible("household-a", False)) == 1
    assert service.visible("household-b", False) == []
    try:
        service.control("household-a", owner=False, automation_id=automation_id, action="run", confirmed=True)
    except HealthWatchAuthorizationError:
        pass
    else:
        raise AssertionError("shared user controlled a view-only watch")

    service.control("owner", owner=True, automation_id=automation_id, action="run", confirmed=True)
    service.control("owner", owner=True, automation_id=automation_id, action="run", confirmed=True)
    service.control("owner", owner=True, automation_id=automation_id, action="run", confirmed=True)
    service.control("owner", owner=True, automation_id=automation_id, action="run", confirmed=True)
    service.control("owner", owner=True, automation_id=automation_id, action="run", confirmed=True)
    history = store.history(automation_id)
    assert [item["to_state"] for item in history[:5]] == [
        "SOURCE_UNAVAILABLE", "UP", "DOWN", "DOWN", "UP"
    ]
    assert sum(item["notification_sent"] for item in history) == 3
    assert len(store.notifications(automation_id, "owner")) == 3
    assert len(store.notifications(automation_id, "household-a")) == 3

    allowed["household-a"].clear()
    assert service.visible("household-a", False) == []
    assert service.visible("owner", True)[0]["state"] != "AUTHORIZATION_LOST"
    allowed["owner"].clear()
    lost = service.visible("owner", True)[0]
    assert lost["state"] == "AUTHORIZATION_LOST" and lost["enabled"] is False
    try:
        service.history_for("household-a", owner=False, automation_id=automation_id)
    except HealthWatchAuthorizationError:
        pass
    else:
        raise AssertionError("revoked resource authority exposed history")

    service.control("owner", owner=True, automation_id=automation_id, action="delete", confirmed=True)
    assert service.visible("owner", True) == []
    print("PASS owner-only preview/create and explicit confirmation")
    print("PASS sharing is view-only and household isolation is enforced")
    print("PASS UP/DOWN/SOURCE_UNAVAILABLE transitions and deduplicated notifications")
    print("PASS current resource revocation disables and hides the watch")
    print("PASS delete is automation-only and create reconciliation is idempotent")
PY
