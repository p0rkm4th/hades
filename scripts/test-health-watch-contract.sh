#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHONPATH="$repo_dir" python3 - "$repo_dir" <<'PY'
import tempfile
import sqlite3
import ast
import os
import re
import secrets
import time
import logging
import sys
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

    # Persisted confirmation previews are scoped to the server conversation,
    # so another chat for the same actor cannot consume or clear them.
    alpha_preview = service.preview(
        "owner", owner=True, resource_id="hades-core", display_name="Alpha Watch",
        interval_minutes=10, conversation_id="chat-alpha",
    )
    beta_preview = service.preview(
        "owner", owner=True, resource_id="hades-core", display_name="Beta Watch",
        interval_minutes=10, conversation_id="chat-beta",
    )
    assert store.latest_preview("owner", conversation_id="chat-alpha")["preview_id"] == alpha_preview["preview_id"]
    assert store.latest_preview("owner", conversation_id="chat-beta")["preview_id"] == beta_preview["preview_id"]
    assert store.latest_preview("owner", conversation_id="chat-gamma") is None
    assert store.has_preview_for_other_conversation("owner", "chat-gamma")
    store.clear_previews("owner", conversation_id="chat-beta")
    assert store.latest_preview("owner", conversation_id="chat-alpha")["preview_id"] == alpha_preview["preview_id"]
    assert store.latest_preview("owner", conversation_id="chat-beta") is None
    store.clear_previews("owner", conversation_id="chat-alpha")

    # Exercise the actual overlay route: another chat fails closed, while the
    # originating chat still finds its persisted preview after worker change.
    overlay = (Path(sys.argv[1]) / "hermes/sitecustomize.py").read_text()
    tree = ast.parse(overlay)
    route_functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"_hades_health_watch_intent", "_hades_health_watch_response"}
    ]
    route_namespace = {
        "re": re,
        "os": os,
        "secrets": secrets,
        "time": time,
        "_HADES_PENDING_HEALTH_WATCH": {},
        "_hades_health_watch_state_path": lambda: str(store.path),
        "_hades_health_watch_service": lambda _subject, owner=False: (service, service.sources),
        "_hades_health_watch_runner": lambda: None,
        "_hades_health_watch_reconcile": lambda *_args: None,
        "_hades_health_watch_target": lambda _text, _sources: "hades-core",
        "_hades_self_service_share_subjects": lambda: {"household-a": "household-a"},
        "_hades_logger": logging.getLogger("hades.health-watch-test"),
    }
    exec(compile(ast.Module(body=route_functions, type_ignores=[]), "sitecustomize.py", "exec"), route_namespace)
    route_preview = service.preview(
        "owner", owner=True, resource_id="hades-core", display_name="Route Watch",
        interval_minutes=10, conversation_id="conversation-alpha",
    )
    route = route_namespace["_hades_health_watch_response"]
    cross_chat = route("yes", "owner", "owner", "conversation-beta")
    assert "couldn't match that confirmation" in cross_chat.lower()
    assert store.latest_preview("owner", conversation_id="conversation-alpha")["preview_id"] == route_preview["preview_id"]
    missing_chat = route("yes", "owner", "owner", "")
    assert "couldn't securely match" in missing_chat.lower()
    missing_chat_create = route("watch if the server goes offline every morning", "owner", "owner", "")
    assert "couldn't securely tie" in missing_chat_create.lower()
    assert store.latest_preview("owner", conversation_id="conversation-alpha")["preview_id"] == route_preview["preview_id"]
    same_chat = route("yes", "owner", "owner", "conversation-alpha")
    assert "nothing was changed" in same_chat.lower() and "runner" in same_chat.lower()
    assert store.latest_preview("owner", conversation_id="conversation-alpha")["preview_id"] == route_preview["preview_id"]

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

    # A second Hermes worker may retain an old process-local create preview
    # while a newer share action is persisted for the same conversation.
    # The persisted current action must win when the user answers "yes".
    race_conversation = "conversation-cross-worker-race"
    race_key = f"session:owner:{race_conversation}"
    stale_create = service.preview(
        "owner", owner=True, resource_id="hades-core", display_name="Stale Watch",
        interval_minutes=10, conversation_id=race_conversation,
    )
    store.store_preview(
        "newer-share-preview", "owner",
        {"kind": "action", "automation_id": automation_id, "action": "share",
         "grantee": "household-a", "grantee_label": "household-a"},
        int(time.time()) + 600, conversation_id=race_conversation,
    )
    route_namespace["_HADES_PENDING_HEALTH_WATCH"][race_key] = {
        "preview_id": stale_create["preview_id"],
        "request_key": "create:" + stale_create["preview_id"],
    }
    raced_confirmation = route("yes", "owner", "owner", race_conversation)
    assert "Updated sharing" in raced_confirmation, raced_confirmation
    assert len(service.visible("owner", True)) == 1, "stale create preview created a duplicate watch"
    assert len(service.visible("household-a", False)) == 1, "newer share action was not applied"
    assert store.latest_preview("owner", conversation_id=race_conversation) is None

    # The inverse race also honors the persisted create preview instead of a
    # stale worker-local share action. With the runner absent, it must leave
    # that preview untouched and perform no sharing change.
    current_create = service.preview(
        "owner", owner=True, resource_id="hades-core", display_name="Current Watch",
        interval_minutes=10, conversation_id=race_conversation,
    )
    route_namespace["_HADES_PENDING_HEALTH_WATCH"][race_key] = {
        "automation_id": automation_id, "action": "unshare",
        "grantee": "household-a", "grantee_label": "household-a",
    }
    inverse_race = route("yes", "owner", "owner", race_conversation)
    assert "runner is not available" in inverse_race.lower(), inverse_race
    assert len(service.visible("household-a", False)) == 1, "stale share action overrode current create preview"
    assert store.latest_preview("owner", conversation_id=race_conversation)["preview_id"] == current_create["preview_id"]

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
    print("PASS Health Watch route rejects a different chat and recovers its own preview")

with tempfile.TemporaryDirectory() as directory:
    legacy_path = Path(directory) / "legacy-health-watch.sqlite"
    with sqlite3.connect(legacy_path) as db:
        db.execute("CREATE TABLE pending_previews (preview_id TEXT PRIMARY KEY, actor TEXT NOT NULL, payload TEXT NOT NULL, expires_at INTEGER NOT NULL)")
    legacy_path.chmod(0o600)
    migrated = HealthWatchStore(str(legacy_path))
    migrated.store_preview("preview-a", "owner", {"kind": "create"}, 4_000_000_000, conversation_id="chat-alpha")
    assert migrated.latest_preview("owner", conversation_id="chat-alpha")["preview_id"] == "preview-a"
    assert migrated.latest_preview("owner", conversation_id="chat-beta") is None
    print("PASS existing preview databases migrate to conversation-scoped confirmation")
PY
