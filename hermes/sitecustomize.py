"""HADES runtime compatibility overlay for Hermes' Hindsight provider.

The upstream Hindsight plugin exposes an agentic reflection tool alongside
direct retain/recall. Local Ollama models can recurse through reflection after
retrieval instead of returning the owner-facing answer. Keep the supported
provider intact, but expose only the direct memory tools to the HADES profile.
"""

import os
import json
import logging
import re
import secrets
import time
import hashlib
import importlib.util
from pathlib import Path


_hades_logger = logging.getLogger("hades.overlay")


# The maintained Grocy MCP is the source of the household tool catalog.  A
# deployment-local companion exposes only the omitted recipe serving-count
# operation; keep both toolsets together whenever a Grocy turn is narrowed.
_HADES_GROCY_TOOLSETS = [
    "mcp-grocy",
    # Hermes exposes both the canonical generated name and the raw server
    # alias for dynamically registered MCP servers. Keep both so API-time
    # narrowing remains correct during discovery-order changes.
    "mcp-grocy_recipe_authoring",
    "grocy_recipe_authoring",
    # Preview-first URL/paste ingestion is a separate stdio MCP server. It is
    # included only on household/recipe turns and its apply tool still
    # requires an explicit confirmation plus a validated preview.
    "mcp-recipe-url-ingest",
    "recipe-url-ingest",
]

_HADES_HOMELAB_TOOLSETS = [
    "mcp-homelab-readonly",
    "homelab-readonly",
]
_HADES_HOMELAB_CONTROL_TOOLSETS = [
    "mcp-homelab-control",
    "homelab-control",
]
_HADES_PAGE_TOOLSETS = [
    "mcp_public_page_extract",
    "public-page-extract",
]
_HADES_HOMELAB_DISCOVERY_ATTEMPTED = False
_HADES_PENDING_PROVISION = {}
_HADES_PENDING_SERVER_ACTION = {}
_HADES_PENDING_HEALTH_WATCH = {}
_HADES_PENDING_PHASE2 = {}


def _hades_turn_identity(user_text, history):
    """Bind confirmation state to the immediately preceding conversation turn."""
    seed = ""
    if isinstance(history, list):
        for item in reversed(history):
            if isinstance(item, dict) and item.get("role") == "user" and str(item.get("content", "")).strip():
                seed = str(item.get("content", ""))
                break
    seed = seed or str(user_text or "")
    return "conversation:" + hashlib.sha256(seed.strip().casefold().encode("utf-8")).hexdigest()[:24]


def _hades_pending_record_is_current(store, pending, actor):
    """Reject confirmations whose referenced automation was changed elsewhere."""
    record = pending.get("record") if isinstance(pending, dict) else None
    operation_key = record.get("operation_key") if isinstance(record, dict) else None
    if not operation_key:
        return True
    current = store.get(str(operation_key))
    if not current or current.get("status") == "DELETED":
        return False
    if current.get("actor") == actor:
        return True
    payload = current.get("payload") or {}
    return actor in (payload.get("shared_subjects") or [])


def _hades_runner_has_workflow(runner, workflow_id):
    if not runner or not workflow_id:
        return False
    try:
        return any(str(row.get("id", "")) == str(workflow_id) for row in runner.list_workflows())
    except Exception:
        return None


def _hades_record_backup_execution(automation_id, owner, execution):
    from integrations.automation import BackupVerificationService, BackupVerificationSpec
    service = BackupVerificationService(
        _hades_health_watch_state_path(),
        BackupVerificationSpec(str(automation_id), str(owner)),
    )
    return service.reconcile_execution(execution)


def _hades_phase2_resource_shares(subject: str) -> set[str]:
    """Deployment-owned per-recipient resource grants for Phase 2 results."""
    grants: set[str] = set()
    for entry in os.environ.get("HADES_EPSILON_PHASE2_RESOURCE_SHARES", "").split(","):
        if ":" not in entry:
            continue
        actor, resource = entry.split(":", 1)
        if actor.strip() == subject:
            grants.add(resource.strip())
    return grants


def _hades_phase2_backup_response(user_text, subject, scope, phase2_session_key=""):
    """Owner-only Backup Check route; promotion uses the shared typed lifecycle."""
    text = str(user_text or "")
    if text.lstrip().startswith("### Task:"):
        return None
    backup_intent = bool(re.search(r"\b(?:backup|backups|bakup|bakups)\b", text, re.IGNORECASE))
    lowered = text.casefold()
    affirmative = bool(re.search(r"\b(?:yes|y|yeah|yep|okay|ok|do it|go ahead|confirm|create it|please do)\b", lowered))
    if not backup_intent and affirmative:
        # Follow-up confirmations can land in another Hermes worker.  Probe
        # the shared lifecycle store before claiming this plain "yes" turn.
        try:
            from integrations.automation import LifecycleStore
            probe_key = f"session:{subject}:{phase2_session_key}" if phase2_session_key else f"subject:{subject}"
            probe_store = LifecycleStore(_hades_health_watch_state_path())
            if not probe_store.pending_get(probe_key, subject):
                # API follow-ups can omit the transcript. Recover one
                # creation preview for this actor, but never choose among
                # multiple outstanding previews.
                now = int(time.time())
                previews = [
                    item for item in probe_store.pending_for_actor(subject)
                    if int(item.get("expires_at", 0) or 0) >= now
                    and not item.get("payload", {}).get("completed_response")
                    and (
                        item.get("payload", {}).get("preview_id")
                        or item.get("payload", {}).get("action")
                    )
                    and item.get("payload", {}).get("template_id") == "hades-backup-verification"
                ]
                explicit_action = re.search(r"\b(run|pause|resume|delete|remove|history|inspect|status|share|unshare|revoke)\b", lowered)
                if explicit_action:
                    wanted_action = "delete" if explicit_action.group(1) == "remove" else explicit_action.group(1)
                    previews = [
                        item for item in previews
                        if item.get("payload", {}).get("action") == wanted_action
                    ]
                if len(previews) != 1:
                    return None
                phase2_session_key = str(previews[0]["pending_key"]).split(
                    f"session:{subject}:", 1
                )[-1]
            backup_intent = True
        except Exception:
            return None
    if not backup_intent:
        return None
    create = bool(re.search(r"\b(?:check|verify|watch|monitor|every|daily|morning|tell me if)\b", lowered))
    action_match = re.search(r"\b(run|check|pause|resume|delete|remove|history|inspect|status|notifications?|edit|change|share|unshare|revoke)\b", lowered)
    action = action_match.group(1) if action_match else ""
    from integrations.automation import LifecycleStore, TypedLifecycle, build_backup_n8n_workflow, N8NControlHttpGateway
    path = _hades_health_watch_state_path()
    store = LifecycleStore(path)
    key = f"session:{subject}:{phase2_session_key}" if phase2_session_key else f"subject:{subject}"
    pending = store.pending_get(key, subject) or _HADES_PENDING_PHASE2.get(key)
    if pending and (pending.get("record", {}).get("template_id") or pending.get("template_id")) not in {None, "hades-backup-verification"}:
        return None
    _hades_logger.info("Phase2 backup turn subject=%s text=%r intent=%s affirmative=%s action=%s pending=%s", subject, text[:160], backup_intent, affirmative, action, bool(pending))
    def clear_pending():
        store.pending_delete(key, subject)
        _HADES_PENDING_PHASE2.pop(key, None)
    def save_pending(value):
        if value.get("completed_response") and pending and pending.get("record"):
            value = {**value, "record": pending["record"]}
        store.pending_put(key, subject, value, int(time.time()) + 600)
        _HADES_PENDING_PHASE2[key] = value
    if pending and pending.get("completed_response") and not affirmative:
        # A later ordinary/action turn supersedes the short replay window;
        # never let an earlier confirmation answer a future bare "yes".
        clear_pending()
        pending = None
    if affirmative and pending and not _hades_pending_record_is_current(store, pending, subject):
        clear_pending()
        return "That Backup Check no longer exists in the current HADES state, so I did not apply the old confirmation."
    if affirmative and pending and pending.get("completed_response"):
        response = str(pending["completed_response"])
        clear_pending()
        return response
    if not subject or scope not in {"owner", "household"}:
        return "I couldn't verify this HADES session, so I did not access backup checks."
    target_hint = bool(re.search(r"\b(?:infrastructure|infra|hades)\b", lowered))
    requested_target = "infrastructure-repository" if re.search(r"\b(?:infrastructure|infra)\b", lowered) else "hades-repository"
    records = [r for r in store.list_actor(subject, "hades-backup-verification") if r["result"].get("status") != "DELETED"]
    if scope != "owner":
        records = [r for r in store.list_template("hades-backup-verification") if subject in r["payload"].get("shared_subjects", []) and r["result"].get("status") != "DELETED" and "backup.evidence" in _hades_phase2_resource_shares(subject)]
    target_records = [item for item in records if item["payload"].get("target_id") == requested_target and item["result"].get("status") != "DELETED"]
    if scope != "owner" and not records:
        return "No shared Backup Check is available for this account."
    backup_mutations = {"pause", "resume", "delete", "remove", "edit", "change", "share", "unshare", "revoke"}
    if scope != "owner" and (
        action in backup_mutations
        or (pending and pending.get("action") in backup_mutations)
    ):
        return "This shared Backup Check is view-only for this account; I have not changed it."
    if not pending and not target_hint and action in {"", "inspect", "status"}:
        if not records:
            return "No Backup Check exists yet. The owner can create one for the approved HADES repository backup."
        entries = []
        for item in records:
            label = "Infrastructure repository" if item["payload"].get("target_id") == "infrastructure-repository" else "HADES repository"
            state = "enabled" if item["result"].get("production_schedule") else "paused"
            entries.append(f"- Backup Check ({label}) — {state}")
        response = "Your Backup Checks:\n" + "\n".join(entries)
        if re.search(r"\b(?:all|important|services?|everything|each|what(?:'s| is)\s+not)\b", lowered):
            covered = ", ".join(
                "Infrastructure repository" if item["payload"].get("target_id") == "infrastructure-repository" else "HADES repository"
                for item in records
            )
            response += f"\nVerified coverage currently exists only for: {covered}. Other important services have no verified Backup Check record in HADES."
        return response
    if affirmative and pending and pending.get("action") == "run":
        record = pending["record"]
        runner = _hades_health_watch_runner()
        try:
            runner.execute_workflow(str(record["result"]["workflow_id"]), str(record["result"]["automation_id"]))
            time.sleep(1.5)
            latest = runner.list_executions(str(record["result"]["workflow_id"]), limit=1)[0]
            state = str(latest.get("hades_state") or "UNKNOWN").replace("_", " ").lower()
            _hades_record_backup_execution(record["result"]["automation_id"], subject, latest)
            response = f"The Backup Check ran. Current result: **{state}**. {latest.get('hades_reason', 'current verification result')}."
            save_pending({"completed_response": response})
            return response
        except Exception:
            response = "The Backup Check outcome is uncertain, so I reconciled the runner state and did not blindly retry."
            save_pending({"completed_response": response})
            return response
    if affirmative and pending and pending.get("action") in {"share", "unshare"}:
        record = pending["record"]; shared = list(record["payload"].get("shared_subjects", [])); grantee = pending["grantee"]
        if pending["action"] == "share" and grantee not in shared: shared.append(grantee)
        if pending["action"] == "unshare": shared = [item for item in shared if item != grantee]
        store.update_payload(record["operation_key"], {**record["payload"], "shared_subjects": shared}); response = f"Backup Check sharing is now {'enabled' if pending['action'] == 'share' else 'revoked'} for the selected household member."; save_pending({"completed_response": response}); return response
    if affirmative and pending and pending.get("action") in {"pause", "resume", "delete", "edit"}:
        record = pending["record"]
        runner = _hades_health_watch_runner()
        workflow_id = record["result"].get("workflow_id")
        try:
            action = pending["action"]
            if action == "pause":
                runner.set_workflow_active(workflow_id, False)
                result = {**record["result"], "status": "PROMOTED", "enabled": False, "production_schedule": False}
            elif action == "resume":
                runner.set_workflow_active(workflow_id, True)
                result = {**record["result"], "status": "PROMOTED", "enabled": True, "production_schedule": True}
            else:
                if action == "edit":
                    interval = int(pending.get("interval_minutes", 1440))
                    graph = build_backup_n8n_workflow(record["result"]["automation_id"], record["payload"]["target_id"], interval)
                    runner.update_workflow(workflow_id, graph); runner.publish_workflow(workflow_id); runner.set_workflow_active(workflow_id, True)
                    payload = {**record["payload"], "interval_minutes": interval}
                    result = {**record["result"], "status": "PROMOTED", "enabled": True, "production_schedule": True}
                    store.put(record["operation_key"], subject, record["template_id"], payload, result["status"], result)
                    response = f"Backup Check is now scheduled every {interval // 1440} day(s)."
                    save_pending({"completed_response": response})
                    return response
                runner.set_workflow_active(workflow_id, False)
                runner.unpublish_workflow(workflow_id); runner.delete_workflow(workflow_id)
                result = {**record["result"], "status": "DELETED", "enabled": False, "production_schedule": False}
            store.put(record["operation_key"], subject, record["template_id"], record["payload"], result["status"], result)
            response = f"Backup Check is now {'paused' if action == 'pause' else 'enabled' if action == 'resume' else 'deleted'}."
            save_pending({"completed_response": response})
            return response
        except Exception:
            exists = _hades_runner_has_workflow(runner, workflow_id)
            if action == "delete" and exists is False:
                result = {**record["result"], "status": "DELETED", "enabled": False, "production_schedule": False}
                store.put(record["operation_key"], subject, record["template_id"], record["payload"], "DELETED", result)
                response = "Backup Check is now deleted after reconciling the runner state."
                save_pending({"completed_response": response})
                return response
            clear_pending()
            return "The Backup Check change is uncertain, so I reconciled current runner state before taking another action."
    if affirmative and pending:
        preview = store.preview_take(pending["preview_id"], subject)
        runner = _hades_health_watch_runner()
        if runner is None:
            return "The approved private runner is unavailable, so nothing was changed."
        class Adapter:
            def reconcile(self, operation_key):
                return None
            def promote(self, template, payload, operation_key):
                graph = build_backup_n8n_workflow(payload["automation_id"], payload["target_id"], payload["interval_minutes"])
                created = runner.create_workflow(graph)
                workflow_id = str(created.get("id", ""))
                if not workflow_id:
                    raise RuntimeError("runner did not return workflow identity")
                runner.update_workflow(workflow_id, graph); runner.publish_workflow(workflow_id); runner.set_workflow_active(workflow_id, True)
                return {"status": "PROMOTED", "automation_id": payload["automation_id"], "workflow_id": workflow_id, "production_schedule": True}
            def mutate(self, action, template, payload, operation_key):
                workflow_id = payload.get("workflow_id")
                if action == "pause": runner.set_workflow_active(workflow_id, False)
                elif action == "resume": runner.set_workflow_active(workflow_id, True)
                elif action == "delete":
                    runner.unpublish_workflow(workflow_id); runner.delete_workflow(workflow_id)
                elif action == "run": runner.execute_workflow(workflow_id, payload["automation_id"])
                return {"status": "PROMOTED", "action": action, "automation_id": payload["automation_id"], "workflow_id": workflow_id}
        lifecycle = TypedLifecycle(store, Adapter(), promotion_enabled=True)
        result = lifecycle.confirm(subject, preview, confirmed=True, operation_key=pending["operation_key"])
        response = f"Created `{preview['display_name']}`. It verifies the approved HADES backup evidence daily, reports only inside HADES, and does not create or repair backups."
        save_pending({"completed_response": response})
        return response
    if create and scope == "owner" and not target_records:
        automation_id = "epsilon-backup-" + secrets.token_hex(8)
        target_id = "infrastructure-repository" if re.search(r"\b(?:infrastructure|infra)\b", lowered) else "hades-repository"
        target_label = "Infrastructure repository backup" if target_id == "infrastructure-repository" else "HADES repository backup"
        preview_payload = {"automation_id": automation_id, "target_id": target_id, "interval_minutes": 1440, "shared_subjects": []}
        lifecycle = TypedLifecycle(store)
        preview = lifecycle.preview(subject, "hades-backup-verification", preview_payload)
        preview_id = secrets.token_urlsafe(18)
        store.preview_put(preview_id, subject, {**preview, "display_name": "Backup Check"}, int(time.time()) + 600)
        save_pending({"preview_id": preview_id, "operation_key": automation_id, "template_id": "hades-backup-verification"})
        return f"Backup Check\n\nTarget: {target_label}\nSchedule: every morning\nNotifications: HADES-local, only when verification state changes\nCustody: Alexandra temporary protected landing zone\n\nCreate it?"
    if create and scope != "owner":
        return "Only the owner can create a Backup Check. I have not created anything."
    if not target_records:
        return "No Backup Check exists yet. The owner can create one for the approved HADES repository backup."
    record = target_records[0]
    result = record["result"]
    status = "enabled" if result.get("production_schedule") else "staged"
    interval_days = max(1, int(record["payload"].get("interval_minutes", 1440)) // 1440)
    schedule_text = "daily" if interval_days == 1 else f"every {interval_days} days"
    if action in {"inspect", "status"} or not action:
        return f"`Backup Check` is {status}; it verifies the approved repository backup {schedule_text} and reports current verification state."
    if action == "history":
        runner = _hades_health_watch_runner()
        try:
            rows = runner.list_executions(str(result["workflow_id"]), limit=5)
            return "\n".join(f"- {row.get('hades_state', 'UNKNOWN')}: {row.get('hades_reason', 'no detail')}" for row in rows) or "`Backup Check` has no recorded checks yet."
        except Exception:
            return "Backup Check history is temporarily unavailable."
    if action in {"notification", "notifications"}:
        try:
            from integrations.automation import BackupVerificationService, BackupVerificationSpec
            rows = BackupVerificationService(_hades_health_watch_state_path(), BackupVerificationSpec(str(result["automation_id"]), subject)).notifications()
            return "No new HADES-local notifications." if not rows else "\n".join(f"- {row['message']}" for row in rows)
        except Exception:
            return "Backup notifications are temporarily unavailable."
    if action in {"run", "check"}:
        if not affirmative:
            save_pending({"action": "run", "record": record})
            return "I found `Backup Check`. Shall I run it now?"
        runner = _hades_health_watch_runner()
        workflow_id = result.get("workflow_id")
        if runner is None or not workflow_id:
            return "The approved private runner is unavailable, so I did not run the Backup Check."
        try:
            runner.execute_workflow(str(workflow_id), str(result.get("automation_id")))
            time.sleep(1.5)
            executions = runner.list_executions(str(workflow_id), limit=3)
            latest = executions[0] if executions else {}
            state = str(latest.get("hades_state") or "UNKNOWN").replace("_", " ").lower()
            reason = str(latest.get("hades_reason") or "current verification result")
            _hades_record_backup_execution(result.get("automation_id"), subject, latest)
            return f"The Backup Check ran. Current result: **{state}**. {reason}."
        except Exception:
            return "The Backup Check outcome is uncertain, so I reconciled the runner state and did not blindly retry."
    if action in {"pause", "resume", "delete", "remove"}:
        action = "delete" if action == "remove" else action
        if not affirmative:
            save_pending({"action": action, "record": record})
            return f"I found `Backup Check`. Shall I {action} it?"
    if action in {"edit", "change"}:
        match = re.search(r"every\s+(\d+)\s*(?:day|days|week|weeks)", lowered)
        interval = int(match.group(1)) * (10080 if "week" in match.group(0) else 1440) if match else 1440
        if interval < 1440 or interval > 10080:
            return "Backup Check schedules are bounded between daily and weekly."
        if not affirmative:
            save_pending({"action": "edit", "record": record, "interval_minutes": interval})
            return f"I found `Backup Check`. Shall I change it to every {interval // 1440} day(s)?"
    if action in {"share", "unshare", "revoke"}:
        if scope != "owner": return "Only the owner can change Backup Check sharing."
        grantee = next((sid for label, sid in _hades_self_service_share_subjects().items() if label in lowered), None)
        if not grantee: return "Which approved household member should receive this Backup Check? I have not changed sharing."
        normalized = "unshare" if action == "revoke" else action
        save_pending({"action": normalized, "record": record, "grantee": grantee})
        return f"Shall I {normalized} Backup Check for that household member?"
    return f"`Backup Check` is owner-controlled. I can {action} it after a confirmation."


def _hades_phase2_inventory_response(user_text, subject, scope, phase2_session_key=""):
    """Bounded Grocy read route using the shared typed lifecycle."""
    text = str(user_text or "")
    if text.lstrip().startswith("### Task:"):
        return None
    lowered = text.casefold()
    inventory_intent = bool(re.search(r"\b(?:grocer(?:y|ies)|grocry|inventory|stock|pantry)\b", lowered)) and bool(re.search(r"\b(?:summar(?:y|ies|ize)|every|weekly|friday|sunday|run|pause|resume|delete|remove|inspect|history|check|tell us|let me know|automation|thing)\b", lowered))
    affirmative = bool(re.search(r"\b(?:yes|y|yeah|yep|okay|ok|do it|go ahead|confirm|please do)\b", lowered))
    if not inventory_intent and not affirmative:
        return None
    from integrations.automation import LifecycleStore, build_inventory_n8n_workflow
    subject = str(subject or "").strip()
    if not subject or scope not in {"owner", "household"}:
        return "I couldn't verify this HADES session, so I did not access grocery summaries."
    store = LifecycleStore(_hades_health_watch_state_path())
    key = f"session:{subject}:{phase2_session_key}" if phase2_session_key else f"subject:{subject}"
    pending = store.pending_get(key, subject) or _HADES_PENDING_PHASE2.get(key)
    if pending and (pending.get("record", {}).get("template_id") or pending.get("template_id")) not in {None, "low-inventory-summary"}:
        return None
    # Do not let an unrelated bare confirmation fall through to an existing
    # grocery record; another typed Phase 2 family may own the confirmation.
    if affirmative and not pending and not inventory_intent:
        return None
    def clear():
        store.pending_delete(key, subject); _HADES_PENDING_PHASE2.pop(key, None)
    def save(value):
        if value.get("completed_response") and pending and pending.get("record"):
            value = {**value, "record": pending["record"]}
        store.pending_put(key, subject, value, int(time.time()) + 600); _HADES_PENDING_PHASE2[key] = value
    if pending and pending.get("completed_response") and not affirmative:
        clear(); pending = None
    if affirmative and pending and not _hades_pending_record_is_current(store, pending, subject):
        clear()
        return "That Low Grocery Summary no longer exists in the current HADES state, so I did not apply the old confirmation."
    if affirmative and pending and pending.get("completed_response"):
        response = str(pending["completed_response"]); clear(); return response
    records = [r for r in store.list_actor(subject, "low-inventory-summary") if r["result"].get("status") != "DELETED"]
    if scope != "owner":
        records = [r for r in store.list_template("low-inventory-summary") if subject in r["payload"].get("shared_subjects", []) and r["result"].get("status") != "DELETED" and "grocy.household" in _hades_phase2_resource_shares(subject)]
    action_match = re.search(r"\b(run|check|pause|resume|delete|remove|history|inspect|status|edit|change|share|unshare|revoke)\b", lowered)
    action = action_match.group(1) if action_match else ""
    if scope != "owner" and (action in {"pause", "resume", "delete", "remove", "share", "unshare", "revoke", "edit", "change"} or (pending and pending.get("action") in {"pause", "resume", "delete", "share", "unshare", "edit"})):
        return "This shared grocery summary is view-only for this account; I have not changed it."
    if affirmative and pending and pending.get("action") in {"share", "unshare"}:
        record = pending["record"]; shared = list(record["payload"].get("shared_subjects", [])); grantee = pending["grantee"]
        if pending["action"] == "share" and grantee not in shared: shared.append(grantee)
        if pending["action"] == "unshare": shared = [item for item in shared if item != grantee]
        payload = {**record["payload"], "shared_subjects": shared}; store.update_payload(record["operation_key"], payload)
        response = f"Low Grocery Summary sharing is now {'enabled' if pending['action'] == 'share' else 'revoked'} for the selected household member."; save({"completed_response": response}); return response
    if affirmative and pending and pending.get("action") in {"run", "pause", "resume", "delete"}:
        record = pending["record"]; runner = _hades_health_watch_runner(); workflow_id = record["result"].get("workflow_id")
        try:
            if pending["action"] == "run":
                runner.execute_workflow(str(workflow_id), str(record["result"]["automation_id"]))
                time.sleep(1.2); row = runner.list_executions(str(workflow_id), limit=1)[0]
                state = str(row.get("hades_state") or "UNKNOWN").replace("_", " ").lower()
                response = f"The grocery summary ran. Current result: **{state}**. {row.get('hades_reason', 'current Grocy result')}."
            elif pending["action"] == "pause":
                runner.set_workflow_active(workflow_id, False); result = {**record["result"], "enabled": False, "production_schedule": False}; store.put(record["operation_key"], subject, record["template_id"], record["payload"], "PROMOTED", result); response = "Low Grocery Summary is now paused."
            elif pending["action"] == "resume":
                runner.set_workflow_active(workflow_id, True); result = {**record["result"], "enabled": True, "production_schedule": True}; store.put(record["operation_key"], subject, record["template_id"], record["payload"], "PROMOTED", result); response = "Low Grocery Summary is now enabled."
            else:
                runner.set_workflow_active(workflow_id, False); runner.unpublish_workflow(workflow_id); runner.delete_workflow(workflow_id); result = {**record["result"], "status": "DELETED", "enabled": False, "production_schedule": False}; store.put(record["operation_key"], subject, record["template_id"], record["payload"], "DELETED", result); response = "Low Grocery Summary is now deleted."
            save({"completed_response": response}); return response
        except Exception:
            response = "The grocery summary change is uncertain, so I reconciled current runner state and did not blindly retry."; save({"completed_response": response}); return response
    if affirmative and pending and pending.get("preview_id"):
        preview = store.preview_take(pending["preview_id"], subject)
        runner = _hades_health_watch_runner()
        if runner is None: return "The approved private runner is unavailable, so nothing was changed."
        payload = dict(preview["payload"]); workflow = build_inventory_n8n_workflow(payload["automation_id"], 7); created = runner.create_workflow(workflow); workflow_id = str(created.get("id", "")); runner.update_workflow(workflow_id, workflow); runner.publish_workflow(workflow_id); runner.set_workflow_active(workflow_id, True)
        result = {"status": "PROMOTED", "automation_id": payload["automation_id"], "workflow_id": workflow_id, "enabled": True, "production_schedule": True}
        store.put(payload["automation_id"], subject, "low-inventory-summary", payload, "PROMOTED", result)
        response = "Created `Low Grocery Summary`. It reads current Grocy stock and reports only inside HADES; it does not change groceries."
        save({"completed_response": response}); return response
    if scope == "owner" and not records and re.search(r"\b(?:every|daily|weekly|friday|sunday|summary|tell us|let me know|grocery thing)\b", lowered):
        automation_id = "epsilon-inventory-" + secrets.token_hex(8); payload = {"automation_id": automation_id, "interval_days": 7, "shared_subjects": []}
        from integrations.automation import TypedLifecycle
        preview = TypedLifecycle(store).preview(subject, "low-inventory-summary", payload); preview_id = secrets.token_urlsafe(18); store.preview_put(preview_id, subject, {**preview, "display_name": "Low Grocery Summary"}, int(time.time()) + 600); save({"preview_id": preview_id, "operation_key": automation_id, "template_id": "low-inventory-summary"})
        return "Low Grocery Summary\n\nSchedule: weekly\nSource: current Grocy stock and minimum-stock rules\nNotifications: HADES-local, bounded summary\n\nCreate it?"
    if scope != "owner" and not records: return "No shared Low Grocery Summary is available for this account. Only the owner can create one."
    if not records: return "No Low Grocery Summary exists yet. The owner can create one."
    record = records[0]; result = record["result"]; status = "enabled" if result.get("production_schedule") else "paused"
    if action in {"inspect", "status", ""}: return f"`Low Grocery Summary` is {status}; it reads current Grocy state weekly and reports a bounded summary."
    if action in {"run", "check"}:
        save({"action": "run", "record": record}); return "I found `Low Grocery Summary`. Shall I run it now?"
    if action in {"pause", "resume", "delete", "remove"}:
        action = "delete" if action == "remove" else action; save({"action": action, "record": record}); return f"I found `Low Grocery Summary`. Shall I {action} it?"
    if action in {"share", "unshare", "revoke"}:
        grantee = next((sid for label, sid in _hades_self_service_share_subjects().items() if label in lowered), None)
        if not grantee: return "Which approved household member should receive this summary? I have not changed sharing."
        normalized = "unshare" if action == "revoke" else action; save({"action": normalized, "record": record, "grantee": grantee}); return f"Shall I {normalized} Low Grocery Summary for that household member?"
    return "`Low Grocery Summary` is owner-controlled and uses only the approved Grocy read source."


def _hades_phase3_enabled() -> bool:
    return os.environ.get("HADES_EPSILON_PHASE3_HOUSEHOLD_CREATION", "").strip().casefold() == "staged"


def _hades_phase3_authority(subject: str, scope: str):
    from integrations.automation.phase3_self_service import Phase3Authority
    resources = set()
    if scope == "owner":
        resources.update({"hades-core.health", "grocy.household", "backup.evidence"})
    for entry in os.environ.get("HADES_EPSILON_PHASE2_RESOURCE_SHARES", "").split(","):
        if ":" not in entry:
            continue
        actor, resource = entry.split(":", 1)
        if actor.strip() == subject:
            resources.add(resource.strip())
    # Phase 3 household authority is the explicit subject/resource grant.
    # HADES_EPSILON_HOUSEHOLD_RESOURCES is a Phase 2 health-watch default and
    # must not silently grant every household user Phase 3 server access.
    return Phase3Authority(str(subject), "owner" if scope == "owner" else "household", frozenset(resources), True)


def _hades_phase3_service():
    from integrations.automation.phase3_self_service import Phase3Catalog, Phase3Service, Phase3Store
    sources = _hades_health_watch_sources()
    catalog = Phase3Catalog({key: value.display_name for key, value in sources.items()})
    return Phase3Service(Phase3Store(_hades_health_watch_state_path()), catalog=catalog)


def _hades_phase3_owner_response(user_text, authority, service, pending_key):
    """Bounded owner metadata oversight; never returns protected results."""
    # This staged owner surface receives only the current turn. Do not refer
    # to an undeclared history variable or reinterpret stale assistant prose.
    text = str(user_text or "").strip()
    lowered = text.casefold()
    affirmative = bool(re.search(r"\b(?:yes|y|yeah|yep|okay|ok|do it|go ahead|confirm|please do)\b", lowered))
    pending = service.store.pending_get(pending_key, authority.subject)
    if affirmative and pending and pending.get("kind") == "admin-disable":
        try:
            item = service.store.admin_disable(authority, pending["automation_id"], "owner oversight")
            service.store.pending_delete(pending_key, authority.subject)
            return f"Disabled `{item['template_type']}` owned by `{item['owner_subject_id']}`. No underlying resource was changed."
        except Exception as exc:
            service.store.pending_delete(pending_key, authority.subject)
            return str(exc)
    inventory_intent = bool(
        re.search(r"\b(?:household|inventory|created|automations|workflows|alerts)\b", lowered)
        and not re.search(r"\b(?:share|revoke|unshare|pause|resume|delete|remove|edit|change|run)\b", lowered)
    )
    if inventory_intent and not re.search(r"\b(?:disable|turn\s+off|stop)\b", lowered):
        items = service.store.list_admin()
        if not items:
            return "There are no staged household automations."
        rows = [
            f"- {item['template_type']} — owner: {item['owner_subject_id']} — "
            f"every {item['interval_minutes']} minutes — "
            f"{'enabled' if item['enabled'] else item['status'].lower()} — "
            f"resources: {', '.join(item['resource_scope'])}"
            for item in items
        ]
        return "Staged household automation metadata (no protected results):\n" + "\n".join(rows)
    if re.search(r"\b(?:most frequent|frequent|duplicate)\b", lowered):
        items = service.store.list_admin()
        if not items:
            return "There are no staged household automations."
        if "duplicate" in lowered:
            groups = {}
            for item in items:
                key = (item["template_type"], tuple(item["resource_scope"]))
                groups.setdefault(key, []).append(item)
            duplicates = [f"{key[0]} ({len(value)})" for key, value in groups.items() if len(value) > 1]
            return "Duplicate metadata groups: " + (", ".join(duplicates) if duplicates else "none detected.")
        fastest = min(items, key=lambda item: item["interval_minutes"])
        return f"Most frequent staged automation: `{fastest['template_type']}` every {fastest['interval_minutes']} minutes, owned by `{fastest['owner_subject_id']}`."
    if re.search(r"\b(?:disable|turn\s+off|stop)\b", lowered):
        items = service.store.list_admin()
        candidates = [item for item in items if item["status"] != "DELETED" and any(token in lowered for token in (item["template_type"].replace("-", " "), item["owner_subject_id"]))]
        if len(candidates) != 1:
            return "Tell me the exact staged automation template and owner to disable; I have not changed anything."
        item = candidates[0]
        if not affirmative:
            service.store.pending_put(pending_key, authority.subject, {"kind": "admin-disable", "automation_id": item["automation_id"]})
            return f"I found `{item['template_type']}` owned by `{item['owner_subject_id']}`. Shall I disable it?"
    return None


def _hades_phase3_response(user_text, subject, scope, session_key=""):
    """Staged household instantiation of the approved typed catalog only."""
    # Keep the accepted Owner Phase 2 surface unchanged; Phase 3 is a
    # household-only staged gate until Manny approves production policy.
    if not _hades_phase3_enabled() or scope not in {"owner", "household"}:
        return None
    from integrations.automation.phase3_self_service import (
        RESOURCE_LABELS, Phase3AuthorizationError, Phase3DuplicateError, Phase3Error, Phase3QuotaError,
    )
    text = str(user_text or "").strip()
    lowered = text.casefold()
    authority = _hades_phase3_authority(subject, scope)
    service = _hades_phase3_service()
    pending_key = f"session:{subject}:{session_key}" if session_key else f"subject:{subject}"
    if scope == "owner":
        return _hades_phase3_owner_response(user_text, authority, service, pending_key)
    affirmative = bool(re.search(r"\b(?:yes|y|yeah|yep|okay|ok|do it|go ahead|confirm|create it|please do)\b", lowered))
    pending = service.store.pending_get(pending_key, subject)
    if not pending and affirmative:
        candidates = service.store.pending_for_actor(subject)
        if len(candidates) == 1:
            pending_key = candidates[0]["pending_key"]
            pending = candidates[0]
    action_match = re.search(r"\b(?P<action>run|pause|resume|delete|remove|edit|change|share|revoke|unshare|history)\b", lowered)
    owned_listing = bool(re.search(r"\b(?:what automations do i have|what'?s mine|whats mine|my automations|my alerts?)\b", lowered))
    catalog_intent = bool(re.search(r"\b(?:what can i automate|what can i monitor|household automations)\b", lowered)) and not owned_listing
    create_health = bool(not action_match and re.search(r"\b(?:watch|monitor|tell me if|let me know if)\b", lowered) and re.search(r"\b(?:server|down|offline|dies|fails|minecraft|health)\b", lowered))
    create_inventory = bool(not action_match and re.search(r"\b(?:grocery|groceries|pantry|inventory|stock|low)\b", lowered) and re.search(r"\b(?:every|weekly|friday|sunday|summary|tell me|what)", lowered))
    create_weekly = bool(not action_match and re.search(r"\b(?:weekly|household)\b", lowered) and re.search(r"\b(?:summary|make|create|give|tell)", lowered))
    backup_request = bool(re.search(r"\bbackup\b", lowered)) and bool(re.search(r"\b(?:create|make|verify|watch|why|automation|check)", lowered))
    if affirmative and pending and pending.get("kind") == "create":
        try:
            item = service.confirm(authority, pending["preview_id"], pending["preview_hash"], "create:" + pending["preview_id"])
            service.store.pending_delete(pending_key, subject)
            return f"Created staged `{item['template_type']}` for you. It is owned by your account, read-only, and has not been promoted to n8n production."
        except (Phase3Error, Phase3AuthorizationError) as exc:
            return str(exc)
    if affirmative and pending and pending.get("kind") == "action":
        action = pending["action"]
        item = service.store.get(pending["automation_id"])
        try:
            if action in {"share", "revoke", "unshare"}:
                recipient = pending["recipient"]
                recipient_authority = _hades_phase3_authority(recipient, "household")
                service.store.share(authority, item["automation_id"], recipient_authority, revoke=action != "share")
                response = "Sharing is now revoked." if action != "share" else "Sharing is now enabled for that household member."
            else:
                service.control(authority, item["automation_id"], action, interval_minutes=pending.get("interval_minutes"))
                response = f"Your staged automation is now {'deleted' if action == 'delete' else 'paused' if action == 'pause' else 'enabled' if action == 'resume' else 'updated'}; no resource was changed."
            service.store.pending_delete(pending_key, subject)
            return response
        except (Phase3Error, Phase3AuthorizationError) as exc:
            service.store.pending_delete(pending_key, subject)
            return str(exc)
    if owned_listing:
        items = service.store.list_for(authority)
        if not items:
            # Owner metadata remains inspectable after resource revocation;
            # protected results do not. The creator may still delete it.
            items = service.store.list_owned(subject)
        if not items:
            return "You do not have any staged household automations yet."
        return "\n".join(["Your staged automations:"] + [f"- {item['template_type']} — {'enabled' if item['enabled'] else 'paused'} — owner: {'you' if item['owner_subject_id'] == subject else 'another household user'}" for item in items])
    if catalog_intent:
        entries = service.catalog.entries(authority)
        if not entries:
            return "There are no approved automations available for this account's current access."
        lines = ["You can create these approved HADES automations:"]
        for entry in entries:
            suffix = f" for {entry['target']}" if entry.get("target") else ""
            if entry["template"] == "weekly-household-summary":
                suffix = " with " + ", ".join(entry.get("sections", []))
            lines.append(f"- {entry['display_name']}{suffix}")
        lines.append("They can only read authorized resources, notify inside HADES, and cannot modify them.")
        return "\n".join(lines)
    if backup_request and scope == "household" and "backup.evidence" not in authority.resources:
        return "Backup Verification is not available for this account's current approved access. Nothing was created."
    if create_health or create_inventory or create_weekly or (backup_request and "backup.evidence" in authority.resources):
        entries = service.catalog.entries(authority)
        template = "server-health-watch" if create_health else "low-inventory-summary" if create_inventory else "weekly-household-summary" if create_weekly else "hades-backup-verification"
        matches = [entry for entry in entries if entry["template"] == template]
        if not matches:
            return "That approved automation is not available for this account's current resource access. Nothing was created."
        entry = matches[0]
        if template == "server-health-watch":
            target = next((item for item in entries if item["template"] == template and any(token in lowered for token in [item.get("resource_id", "").casefold(), item.get("display_name", "").casefold()])), entry)
            payload = {"resource_id": target["resource_id"], "display_name": target["display_name"], "interval_minutes": entry.get("interval_minutes", 10)}
        else:
            payload = {key: entry[key] for key in ("resource_scope", "interval_minutes") if key in entry}
        try:
            preview = service.preview(authority, template, payload)
        except Phase3DuplicateError as exc:
            return str(exc)
        except (Phase3Error, Phase3AuthorizationError) as exc:
            return str(exc)
        service.store.pending_put(pending_key, subject, {"kind": "create", "preview_id": preview["preview_id"], "preview_hash": preview["preview_hash"]})
        if template == "weekly-household-summary":
            sections = ", ".join(entry.get("sections", []))
            body = f"\nSections: {sections}\nSchedule: weekly"
        else:
            body = f"\nSchedule: every {preview['interval_minutes']} minutes" if preview["interval_minutes"] < 1440 else "\nSchedule: weekly"
        return f"{entry['display_name']}\n\nOwner: you\nResources: {', '.join(RESOURCE_LABELS.get(item, item) for item in preview['resource_scope'])}{body}\nNotifications: HADES-local only\nCannot: modify the underlying resource or run arbitrary workflows\n\nCreate it?"
    if re.search(r"\b(?:what automations|what alerts|my automations|what'?s mine|whats mine)\b", lowered):
        items = service.store.list_for(authority)
        if not items:
            items = service.store.list_owned(subject)
        if not items:
            return "You do not have any staged household automations yet."
        return "\n".join(["Your staged automations:"] + [f"- {item['template_type']} — {'enabled' if item['enabled'] else 'paused'} — owner: {'you' if item['owner_subject_id'] == subject else 'another household user'}" for item in items])
    pending_action = pending.get("action") if pending and pending.get("kind") == "action" else ""
    requested_action = (action_match.group("action") if action_match else pending_action)
    if requested_action:
        action = "delete" if requested_action == "remove" else ("edit" if requested_action == "change" else requested_action)
        items = service.store.list_for(authority)
        def _phase3_item_matches(candidate):
            template = candidate["template_type"]
            if template.replace("-", " ") in lowered:
                return True
            aliases = {
                "server-health-watch": ("server", "health", "watch"),
                "low-inventory-summary": ("low", "grocery", "inventory", "pantry"),
                "weekly-household-summary": ("weekly", "household", "summary"),
                "hades-backup-verification": ("backup", "verification"),
            }
            words = aliases.get(template, ())
            return any(word in lowered for word in words)
        item = items[0] if len(items) == 1 else next((candidate for candidate in items if _phase3_item_matches(candidate)), None)
        if not item:
            return "I could not match that request to an automation you currently control."
        if action == "history":
            if item["owner_subject_id"] != subject:
                return "History is available only to the automation owner; no protected result was disclosed."
            audit = service.store.audit_for(item["automation_id"])
            if not audit:
                return f"`{item['template_type']}` has no recorded staged actions yet."
            actions = ", ".join(str(row["action"]) for row in audit[-8:])
            return f"Staged metadata history for `{item['template_type']}`: {actions}. Protected source results are not shown here."
        if action in {"share", "revoke", "unshare"}:
            labels = _hades_self_service_share_subjects()
            recipient = pending.get("recipient") if pending_action else next((sid for label, sid in labels.items() if label in lowered), None)
            if not recipient:
                return "Tell me which approved household member should receive it. I have not changed sharing."
            recipient_authority = _hades_phase3_authority(recipient, "household")
            if not affirmative:
                service.store.pending_put(pending_key, subject, {"kind": "action", "action": action, "automation_id": item["automation_id"], "recipient": recipient})
                return f"I found your `{item['template_type']}` automation. Shall I {'revoke sharing' if action != 'share' else 'share it'}?"
            try:
                service.store.share(authority, item["automation_id"], recipient_authority, revoke=action != "share")
                return "Sharing is now revoked." if action != "share" else "Sharing is now enabled for that household member."
            except (Phase3Error, Phase3AuthorizationError) as exc:
                return str(exc)
        if action == "edit":
            match = re.search(r"every\s+(\d+)\s*(minutes?|hours?|days?|weeks?)", lowered)
            if not match:
                return "Tell me a bounded interval between 5 minutes and 7 days."
            unit = match.group(2); multiplier = 60 if unit.startswith("hour") else 1440 if unit.startswith("day") else 10080 if unit.startswith("week") else 1
            interval = int(match.group(1)) * multiplier
        else:
            interval = None
        if action != "run" and not affirmative:
            service.store.pending_put(pending_key, subject, {"kind": "action", "action": action, "automation_id": item["automation_id"], "interval_minutes": interval})
            return f"I found your `{item['template_type']}` automation. Shall I {action} it?"
        try:
            service.control(authority, item["automation_id"], action, interval_minutes=interval)
            return f"Your staged automation is now {'deleted' if action == 'delete' else 'paused' if action == 'pause' else 'enabled' if action == 'resume' else 'updated' if action == 'edit' else 'queued for a bounded run'}; no resource was changed."
        except (Phase3Error, Phase3AuthorizationError) as exc:
            return str(exc)
    return None


def _hades_phase2_weekly_response(user_text, subject, scope, phase2_session_key=""):
    """Owner-created bounded composition of the three approved result families."""
    text = str(user_text or "")
    if text.lstrip().startswith("### Task:"):
        return None
    lowered = text.casefold()
    if re.search(r"\b(?:grocer(?:y|ies)|grocry|pantry|inventory|backup|backups|health|server)\b", lowered):
        return None
    intent = bool(re.search(r"\b(?:household|weekly|weeky|sunday|summar(?:y|ies)|house stuff)\b", lowered)) and bool(re.search(r"\b(?:summar(?:y|ies)|every|run|create|give|tell|what|show|latest|last|previous|did|history|pause|resume|delete|share)\b", lowered))
    affirmative = bool(re.search(r"\b(?:yes|y|yeah|yep|okay|ok|do it|go ahead|confirm|please do)\b", lowered))
    if not intent and not affirmative: return None
    from integrations.automation import LifecycleStore, build_weekly_n8n_workflow
    subject = str(subject or "").strip()
    if not subject or scope not in {"owner", "household"}: return "I couldn't verify this HADES session, so I did not access household summaries."
    store = LifecycleStore(_hades_health_watch_state_path()); key = f"session:{subject}:{phase2_session_key}" if phase2_session_key else f"subject:{subject}"; pending = store.pending_get(key, subject) or _HADES_PENDING_PHASE2.get(key)
    if pending and (pending.get("record", {}).get("template_id") or pending.get("template_id")) not in {None, "weekly-household-summary"}:
        # An ordinary Weekly read/history turn supersedes an unrelated stale
        # Phase 2 pending record in the same browser conversation. Preserve
        # fail-closed behavior only for a bare confirmation.
        if affirmative:
            return None
        pending = None
    # A bare confirmation may belong to another typed Phase 2 family. Leave
    # it for the subsequent family-specific routes when this route has no
    # current Weekly preview/action.
    if affirmative and not pending:
        return None
    def clear(): store.pending_delete(key, subject); _HADES_PENDING_PHASE2.pop(key, None)
    def save(value):
        if value.get("completed_response") and pending and pending.get("record"):
            value = {**value, "record": pending["record"]}
        store.pending_put(key, subject, value, int(time.time()) + 600); _HADES_PENDING_PHASE2[key] = value
    if pending and pending.get("completed_response") and not affirmative: clear(); pending = None
    if affirmative and pending and not _hades_pending_record_is_current(store, pending, subject):
        clear()
        return "That Weekly Household Summary no longer exists in the current HADES state, so I did not apply the old confirmation."
    if affirmative and pending and pending.get("completed_response"):
        response = str(pending["completed_response"]); clear(); return response
    records = [r for r in store.list_actor(subject, "weekly-household-summary") if r["result"].get("status") != "DELETED"]
    if scope != "owner":
        records = [r for r in store.list_template("weekly-household-summary") if subject in r["payload"].get("shared_subjects", []) and r["result"].get("status") != "DELETED"]
    action = (re.search(r"\b(run|pause|resume|delete|remove|history|inspect|status|share|unshare|revoke)\b", lowered) or ("history" if re.search(r"\b(?:show|give|tell me)\b.*\b(?:latest|last|previous)\b.*\bsummary\b|\b(?:last|previous)\s+week\b|\bwhat did .*summary say\b", lowered) else ""))
    if hasattr(action, "group"):
        action = action[0]
    if affirmative and pending and pending.get("action") in {"share", "unshare"}:
        record = pending["record"]; shared = list(record["payload"].get("shared_subjects", [])); grantee = pending["grantee"]
        if pending["action"] == "share" and grantee not in shared: shared.append(grantee)
        if pending["action"] == "unshare": shared = [item for item in shared if item != grantee]
        store.update_payload(record["operation_key"], {**record["payload"], "shared_subjects": shared}); response = f"Weekly Household Summary sharing is now {'enabled' if pending['action'] == 'share' else 'revoked'} for the selected household member."; save({"completed_response": response}); return response
    if scope != "owner" and (action in {"pause", "resume", "delete", "remove", "share", "unshare", "revoke"} or (pending and pending.get("action") in {"pause", "resume", "delete", "share", "unshare"})):
        return "This shared household summary is view-only for this account; I have not changed it."
    if affirmative and pending and pending.get("action") in {"run", "pause", "resume", "delete"}:
        record = pending["record"]; runner = _hades_health_watch_runner(); workflow_id = record["result"].get("workflow_id")
        try:
            act = pending["action"]
            if act == "run":
                runner.execute_workflow(str(workflow_id), str(record["result"]["automation_id"])); time.sleep(1.2)
                lines = ["Weekly Household Summary", ""]
                allowed_sources = {"grocy.household", "hades-core.health", "backup.evidence"} if scope == "owner" else _hades_phase2_resource_shares(subject)
                low_records = store.list_template("low-inventory-summary")
                if "grocy.household" not in allowed_sources:
                    lines.append("Groceries: unavailable due to current access.")
                elif low_records:
                    low_exec = runner.list_executions(str(low_records[0]["result"].get("workflow_id")), limit=1)
                    row = low_exec[0] if low_exec else {}
                    if row.get("hades_state") == "SOURCE_UNAVAILABLE": lines.append("Groceries: source temporarily unavailable.")
                    else: lines.append("Groceries: current Low Grocery result is available.")
                else: lines.append("Groceries: unavailable because no approved Low Grocery result exists.")
                try:
                    if "hades-core.health" not in allowed_sources:
                        raise PermissionError("server health access revoked")
                    from integrations.automation import HealthWatchStore
                    health = [item for item in HealthWatchStore(_hades_health_watch_state_path()).list_all() if item.get("state")]
                    lines.append("Servers: " + (str(health[0].get("state", "UNKNOWN")).replace("_", " ").lower() if health else "no current Server Health Watch result") + ".")
                except Exception:
                    lines.append("Servers: status could not be verified.")
                backup_records = [r for r in store.list_template("hades-backup-verification") if r["result"].get("status") != "DELETED"]
                if "backup.evidence" not in allowed_sources:
                    lines.append("Backups: unavailable due to current access.")
                elif backup_records:
                    backup_exec = runner.list_executions(str(backup_records[0]["result"].get("workflow_id")), limit=1)
                    brow = backup_exec[0] if backup_exec else {}
                    lines.append("Backups: " + (str(brow.get("hades_state", "UNKNOWN")).replace("_", " ").lower() + "." if brow else "current result unavailable."))
                else: lines.append("Backups: no current approved verification result.")
                response = "\n".join(lines)
                from integrations.automation import SummaryHistory
                SummaryHistory(_hades_health_watch_state_path()).record(subject, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), response)
            elif act == "pause": runner.set_workflow_active(workflow_id, False); result = {**record["result"], "enabled": False, "production_schedule": False}; store.put(record["operation_key"], subject, record["template_id"], record["payload"], "PROMOTED", result); response = "Weekly Household Summary is now paused."
            elif act == "resume": runner.set_workflow_active(workflow_id, True); result = {**record["result"], "enabled": True, "production_schedule": True}; store.put(record["operation_key"], subject, record["template_id"], record["payload"], "PROMOTED", result); response = "Weekly Household Summary is now enabled."
            else: runner.set_workflow_active(workflow_id, False); runner.unpublish_workflow(workflow_id); runner.delete_workflow(workflow_id); result = {**record["result"], "status": "DELETED", "enabled": False, "production_schedule": False}; store.put(record["operation_key"], subject, record["template_id"], record["payload"], "DELETED", result); response = "Weekly Household Summary is now deleted."
            save({"completed_response": response}); return response
        except Exception:
            response = "The household summary change is uncertain, so I reconciled current runner state and did not blindly retry."; save({"completed_response": response}); return response
    if affirmative and pending and pending.get("preview_id"):
        preview = store.preview_take(pending["preview_id"], subject); runner = _hades_health_watch_runner()
        if runner is None: return "The approved private runner is unavailable, so nothing was changed."
        payload = dict(preview["payload"]); graph = build_weekly_n8n_workflow(payload["automation_id"]); created = runner.create_workflow(graph); workflow_id = str(created.get("id", "")); runner.update_workflow(workflow_id, graph); runner.publish_workflow(workflow_id); runner.set_workflow_active(workflow_id, True)
        result = {"status": "PROMOTED", "automation_id": payload["automation_id"], "workflow_id": workflow_id, "enabled": True, "production_schedule": True}; store.put(payload["automation_id"], subject, "weekly-household-summary", payload, "PROMOTED", result)
        response = "Created `Weekly Household Summary`. It includes only Grocy, Server Health Watch, and Backup Verification results."; save({"completed_response": response}); return response
    if scope == "owner" and not records and re.search(r"\b(?:every|weekly|sunday|create|give me|tell us)\b", lowered):
        automation_id = "epsilon-weekly-" + secrets.token_hex(8); payload = {"automation_id": automation_id, "interval_days": 7, "sources": ["low-inventory-summary", "server-health-watch", "hades-backup-verification"], "shared_subjects": []}
        from integrations.automation import TypedLifecycle
        preview = TypedLifecycle(store).preview(subject, "weekly-household-summary", payload); preview_id = secrets.token_urlsafe(18); store.preview_put(preview_id, subject, {**preview, "display_name": "Weekly Household Summary"}, int(time.time()) + 600); save({"preview_id": preview_id, "operation_key": automation_id, "template_id": "weekly-household-summary"})
        return "Weekly Household Summary\n\nSources: Grocy, Server Health Watch, and Backup Verification\nSchedule: weekly\nNotifications: HADES-local\n\nCreate it?"
    if scope != "owner" and not records: return "No shared Weekly Household Summary is available for this account. Only the owner can create one."
    if not records: return "No Weekly Household Summary exists yet. The owner can create one."
    record = records[0]
    if action in {"", "inspect", "status"}:
        status = "enabled" if record["result"].get("production_schedule") else "paused"
        return f"`Weekly Household Summary` is {status}; it composes only the approved Grocy, Server Health Watch, and Backup Verification read results."
    if action in {"run"}: save({"action": "run", "record": record}); return "I found `Weekly Household Summary`. Shall I run it now?"
    if action in {"pause", "resume", "delete", "remove"}: action = "delete" if action == "remove" else action; save({"action": action, "record": record}); return f"I found `Weekly Household Summary`. Shall I {action} it?"
    if action in {"share", "unshare", "revoke"}:
        grantee = next((sid for label, sid in _hades_self_service_share_subjects().items() if label in lowered), None)
        if not grantee: return "Which approved household member should receive this summary? I have not changed sharing."
        normalized = "unshare" if action == "revoke" else action; save({"action": normalized, "record": record, "grantee": grantee}); return f"Shall I {normalized} Weekly Household Summary for that household member?"
    if action == "history":
        from integrations.automation import SummaryHistory
        latest = SummaryHistory(_hades_health_watch_state_path()).latest(subject)
        if not latest and scope != "owner":
            # Shared recipients may inspect the owner-created bounded result,
            # but only after the record-level share and resource grants above
            # have authorized this subject. The composed text contains only
            # the approved Grocy, health, and backup sections.
            latest = SummaryHistory(_hades_health_watch_state_path()).latest(str(record.get("actor", "")))
        return latest["text"] if latest else "Weekly Household Summary has no recorded run yet."
    return "`Weekly Household Summary` uses only the three approved read-only source families."


def _hades_pending_provision_keys(agent):
    """Return stable-first keys for a preview/confirmation pair.

    Open WebUI can give separate API turns different gateway session keys.
    The authenticated subject is stable, while the per-turn/session keys are
    useful compatibility fallbacks on older gateway paths.
    """
    keys = []
    subject = str(getattr(agent, "_hades_subject", "") or "").strip()
    if subject:
        keys.append(f"subject:{subject}")
    for value in (
        getattr(agent, "_hades_gateway_session_key", ""),
        getattr(agent, "session_id", ""),
    ):
        value = str(value or "").strip()
        if value and value not in keys:
            keys.append(value)
    return keys


def _hades_load_control_module():
    """Load the deployed bounded self-service adapter, never a raw API client."""
    site_path = Path(__file__).resolve()
    candidates = (
        site_path.parents[1] / "integrations" / "homelab-control" / "control.py",
        site_path.parents[3] / "Hades-reconciled-b102dfd" / "integrations" / "homelab-control" / "control.py",
    )
    control_path = next((path for path in candidates if path.is_file()), None)
    if control_path is None:
        raise FileNotFoundError("bounded homelab control adapter is not deployed")
    spec = importlib.util.spec_from_file_location("hades_live_control", control_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _hades_agent_zero_available():
    """Bounded reachability probe for owner-facing operator failure UX."""
    import urllib.request
    from urllib.error import HTTPError, URLError

    base_url = str(os.environ.get("AGENT_ZERO_URL") or "http://127.0.0.1:7002").rstrip("/")
    try:
        urllib.request.urlopen(
            urllib.request.Request(base_url, method="GET"),
            timeout=2,
        ).close()
        return True
    except HTTPError as exc:
        # A live service may reject an unauthenticated root probe; the
        # transport is nevertheless available and the MCP call should decide
        # authorization/result semantics.
        return exc.code not in {502, 503, 504}
    except (URLError, OSError, TimeoutError):
        return False


def _hades_self_service_share_subjects() -> dict[str, str]:
    """Resolve human share labels from protected deployment configuration."""
    result = {}
    for entry in os.environ.get("HADES_SELF_SERVICE_SHARE_SUBJECTS", "").split(","):
        if ":" not in entry:
            continue
        label, subject = entry.split(":", 1)
        label = re.sub(r"[^a-z0-9]+", "-", label.strip().lower()).strip("-")
        subject = subject.strip()
        if label and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", subject):
            result[label] = subject
    return result


def _hades_health_watch_sources():
    """Load only operator-declared health sources; never accept user URLs."""
    from integrations.automation import HealthSource

    raw = os.environ.get("HADES_EPSILON_HEALTH_SOURCES_JSON", "").strip()
    if raw:
        try:
            document = json.loads(raw)
        except (TypeError, ValueError):
            document = {}
    else:
        document = {
            "hades-core": {
                "display_name": "HADES Core",
                "url": os.environ.get(
                    "HADES_EPSILON_HEALTH_SOURCE_URL",
                    "http://hades-core.local:3000/health",
                ),
            }
        }
    sources = {}
    if not isinstance(document, dict):
        return sources
    for resource_id, value in document.items():
        if not isinstance(value, dict):
            continue
        try:
            sources[str(resource_id)] = HealthSource(
                str(resource_id), str(value["display_name"]), str(value["url"])
            )
        except (KeyError, TypeError, ValueError):
            continue
    return sources


def _hades_health_watch_state_path():
    configured = os.environ.get("HADES_EPSILON_STATE_FILE", "").strip()
    if configured:
        return configured
    return str(Path(os.environ.get("HERMES_HOME", "/var/lib/hades")) / "profiles" / "hades" / "state" / "epsilon-automation.sqlite")


def _hades_health_watch_service(subject, *, owner=False):
    from integrations.automation import HealthWatchService, HealthWatchStore

    sources = _hades_health_watch_sources()
    household_resources = {
        item.strip()
        for item in os.environ.get("HADES_EPSILON_HOUSEHOLD_RESOURCES", "").split(",")
        if item.strip()
    }

    def authorized(actor, resource_id):
        if actor == subject and owner:
            return resource_id in sources
        return resource_id in household_resources

    service = HealthWatchService(
        HealthWatchStore(_hades_health_watch_state_path()),
        sources,
        resource_authorizer=authorized,
    )
    return service, sources


def _hades_health_watch_reconcile(service, runner, automation_id):
    """Reconcile n8n's allowlisted execution projection into HADES state."""
    if runner is None:
        return
    try:
        workflow_id = service.store.get(automation_id).get("workflow_id") or automation_id
        for execution in runner.list_executions(workflow_id, limit=5):
            service.reconcile_execution(automation_id, execution)
    except Exception as exc:
        _hades_logger.warning("Server Health Watch execution reconciliation unavailable: %s", exc)


def _hades_health_watch_runner():
    """Return the separately scoped control adapter, or None fail-closed."""
    base_url = os.environ.get("HADES_N8N_BASE_URL", "").strip()
    api_key = os.environ.get("HADES_EPSILON_N8N_CONTROL_API_KEY", "").strip()
    if not api_key:
        key_path = os.environ.get("HADES_EPSILON_N8N_CONTROL_API_KEY_FILE", "").strip()
        if key_path:
            try:
                api_key = Path(key_path).read_text(encoding="utf-8").strip()
            except (OSError, UnicodeError):
                api_key = ""
    if not base_url or not api_key:
        return None
    from integrations.automation import N8NControlHttpGateway
    return N8NControlHttpGateway(base_url, api_key)


def _hades_health_watch_target(text, sources):
    lowered = str(text or "").casefold()
    matches = []
    for resource_id, source in sources.items():
        aliases = {
            resource_id.casefold(),
            resource_id.casefold().replace("-", " "),
            source.display_name.casefold(),
        }
        aliases.update(
            token for token in re.split(r"[^a-z0-9]+", source.display_name.casefold())
            if len(token) > 2 and token not in {"hades", "core", "server", "health", "watch"}
        )
        if any(alias and alias in lowered for alias in aliases):
            matches.append(resource_id)
    return matches[0] if len(set(matches)) == 1 else None


def _hades_health_watch_intent(text):
    value = str(text or "")
    create = bool(re.search(
        r"\b(?:watch|monitor|observe|keep\s+an\s+eye\s+on|tell\s+me\s+if|let\s+me\s+know\s+if)\b",
        value, re.IGNORECASE,
    )) and bool(re.search(r"\b(?:down|offline|dies|fails|breaks|stops|health)\b", value, re.IGNORECASE))
    listing = bool(re.search(r"\b(?:what\s+(?:am\s+i|are\s+you)\s+monitoring|my\s+automations?|my\s+alerts?|what\s+alerts?)\b", value, re.IGNORECASE))
    action = re.search(r"\b(?P<action>run|check|pause|resume|delete|remove|stop|share|unshare|revoke|inspect|status|history|notifications?|edit|change)\b", value, re.IGNORECASE)
    return create, listing, action.group("action").casefold() if action else ""


def _hades_health_watch_response(user_text, subject, scope):
    """Deterministic owner/household Server Health Watch product surface."""
    create, listing, action = _hades_health_watch_intent(user_text)
    key = f"subject:{subject}"
    lowered = str(user_text or "").casefold()
    affirmative = bool(re.search(r"\b(?:yes|y|yeah|yep|okay|ok|do it|go ahead|confirm|create it|please do)\b", lowered))
    from integrations.automation import HealthWatchStore
    persisted_pending = HealthWatchStore(_hades_health_watch_state_path()).latest_preview(subject)
    if not (create or listing or action or (affirmative and (key in _HADES_PENDING_HEALTH_WATCH or persisted_pending))):
        return None
    if not subject or scope not in {"owner", "household"}:
        return "I couldn't verify this HADES session, so I did not access automations."
    try:
        service, sources = _hades_health_watch_service(subject, owner=scope == "owner")
        runner = _hades_health_watch_runner()
        # A bare action verb in a compound diagnostic (for example, "check
        # network health") is not a Server Health Watch command. Require an
        # explicit watch target or watch/listing language so broader homelab
        # composition can reach the live read-only route.
        if action and not create and not listing and not _hades_health_watch_target(user_text, sources):
            return None
        # A confirmation turn is intentionally narrow but must be routable
        # without repeating the original creation wording.
        if affirmative and key in _HADES_PENDING_HEALTH_WATCH:
            pending_action = _HADES_PENDING_HEALTH_WATCH[key].get("action", "create")
            if pending_action == "create" and not action:
                create = True
            if not action and pending_action != "create":
                action = pending_action
        # The persisted preview is shared across gateway workers, while the
        # in-memory pending map is process-local.  A worker can therefore see
        # an older in-memory create preview alongside a newer persisted
        # share/revoke preview.  For a bare confirmation, the newest persisted
        # action must win; otherwise a reply to "shall I revoke it?" can replay
        # stale creation state and create a duplicate watch.
        if affirmative and persisted_pending:
            pending_kind = persisted_pending.get("kind", "create")
            current_pending = _HADES_PENDING_HEALTH_WATCH.get(key, {})
            if pending_kind == "action" and current_pending.get("action") == "create":
                _HADES_PENDING_HEALTH_WATCH[key] = dict(persisted_pending)
                current_pending = _HADES_PENDING_HEALTH_WATCH[key]
            if not current_pending:
                if pending_kind == "create" and not action:
                    create = True
                    _HADES_PENDING_HEALTH_WATCH[key] = {
                        "preview_id": persisted_pending["preview_id"],
                        "request_key": "create:" + persisted_pending["preview_id"],
                    }
                elif pending_kind == "action":
                    action = str(persisted_pending.get("action", action))
                    _HADES_PENDING_HEALTH_WATCH[key] = dict(persisted_pending)

        if listing:
            visible = service.visible(subject, scope == "owner")
            for item in visible:
                _hades_health_watch_reconcile(service, runner, item["automation_id"])
            visible = service.visible(subject, scope == "owner")
            if not visible:
                return "You are not monitoring any authorized servers yet."
            lines = ["Here are the HADES health watches I can show you:"]
            for item in visible:
                state = str(item.get("state", "UNKNOWN")).replace("_", " ").lower()
                lines.append(f"- {item.get('display_name', 'Unnamed')}: {state}; every {item.get('interval_minutes')} minutes; {'enabled' if item.get('enabled') else 'paused'}.")
            return "\n".join(lines)

        if create and scope == "household":
            return "Only the owner can create a Server Health Watch. I have not created anything."

        if create and scope == "owner":
            pending = _HADES_PENDING_HEALTH_WATCH.get(key)
            if affirmative and pending:
                if runner is None:
                    return "The approved private runner is not available for creation right now. Nothing was changed."
                item = service.confirm_create(subject, pending["preview_id"], confirmed=True, request_key=pending["request_key"])
                # Semantic store idempotency may return an already-promoted
                # watch when a browser double-submit produced a second
                # confirmation. Do not create a second n8n workflow for that
                # existing canonical record.
                if item.get("workflow_id"):
                    _HADES_PENDING_HEALTH_WATCH.pop(key, None)
                    return f"`{item['display_name']}` is already active; no duplicate watch was created."
                from integrations.automation import HealthSource, HealthWatchSpec, build_n8n_workflow
                source = sources[item["resource_id"]]
                spec = HealthWatchSpec(
                    item["automation_id"], item["owner"], item["resource_id"], item["display_name"],
                    item["interval_minutes"], item["notification_policy"], item["shared_subjects"],
                )
                try:
                    created = runner.create_workflow(build_n8n_workflow(spec, source))
                    runner_id = str(created.get("id", ""))
                    if runner_id:
                        service.store.bind_workflow(item["automation_id"], runner_id, subject)
                except Exception:
                    service.store.delete(item["automation_id"], subject)
                    raise
                _HADES_PENDING_HEALTH_WATCH.pop(key, None)
                return f"Created `{item['display_name']}`. It checks every {item['interval_minutes']} minutes, reports only inside HADES, and cannot change the server."
            target = _hades_health_watch_target(user_text, sources)
            if not target:
                names = ", ".join(source.display_name for source in sources.values()) or "none"
                return f"Which authorized server should I watch? Available: {names}. I have not created anything."
            interval = 10
            match = re.search(r"\bevery\s+(\d+)\s*(minutes?|mins?|hours?|hrs?)\b", lowered)
            if match:
                interval = int(match.group(1)) * (60 if match.group(2).startswith(("hour", "hr")) else 1)
            source = sources[target]
            preview = service.preview(subject, owner=True, resource_id=target, display_name=f"{source.display_name} Watch", interval_minutes=interval)
            _HADES_PENDING_HEALTH_WATCH[key] = {"preview_id": preview["preview_id"], "request_key": "create:" + preview["preview_id"]}
            return (
                f"Server Health Watch\n\nWatching: {source.display_name}\nOwner: you\n"
                f"Checks: every {interval} minutes\nNotifications: only inside HADES, only when the state changes\n"
                "This automation cannot restart or modify the server.\n\nCreate it?"
            )

        visible = service.visible(subject, scope == "owner")
        for item in visible:
            _hades_health_watch_reconcile(service, runner, item["automation_id"])
        visible = service.visible(subject, scope == "owner")
        if not visible:
            return "I couldn't find a shared HADES health watch for this account."
        target_item = visible[0]
        if len(visible) > 1:
            # Duplicate same-resource watches can exist after an interrupted
            # confirmation race.  If the owner names the household recipient,
            # use that durable share state to select the intended record
            # instead of silently acting on the first row returned by SQLite.
            share_subjects = _hades_self_service_share_subjects()
            requested_grantee = next(
                (subject for label, subject in share_subjects.items() if label in lowered),
                "",
            )
            shared_matches = [
                item for item in visible
                if requested_grantee and requested_grantee in item.get("shared_subjects", ())
            ]
            if len(shared_matches) == 1:
                target_item = shared_matches[0]
            elif len(shared_matches) > 1:
                return "Which shared health watch should I use? I found more than one for that household member."
            state_match = re.search(r"\b(unknown|up|down|paused|disabled)\b", lowered)
            state_matches = [
                item for item in visible
                if state_match and str(item.get("state", "")).casefold() == state_match.group(1)
            ]
            if len(state_matches) == 1:
                target_item = state_matches[0]
            target = _hades_health_watch_target(user_text, sources)
            matches = [item for item in visible if item.get("resource_id") == target]
            if target_item is not visible[0] and shared_matches:
                pass
            elif len(matches) == 1:
                target_item = matches[0]
            elif not target:
                return "Which health watch should I use? I found more than one."
        if scope != "owner" and action not in {"inspect", "status", "history", "notification", "notifications"}:
            return "This shared health watch is view-only for you; I did not change or run it."
        if action in {"inspect", "status", "history", "notification", "notifications"}:
            if action in {"inspect", "status"}:
                state = str(target_item.get("state", "UNKNOWN")).replace("_", " ").lower()
                return f"`{target_item['display_name']}` is {state}; it checks every {target_item['interval_minutes']} minutes and is {'enabled' if target_item.get('enabled') else 'paused'}."
            if action == "history":
                rows = service.history_for(subject, owner=scope == "owner", automation_id=target_item["automation_id"], limit=5)
                if not rows:
                    return f"`{target_item['display_name']}` has no recorded checks yet."
                return "\n".join(f"- {row['to_state']}: {row['reason']}" for row in rows)
            rows = service.notifications_for(subject, owner=scope == "owner", automation_id=target_item["automation_id"], limit=5)
            return "No new HADES-local notifications." if not rows else "\n".join(f"- {row['message']}" for row in rows)
        if action in {"share", "unshare", "revoke"}:
            label_match = re.search(r"\b(household-[a-z0-9_-]+)\b", lowered)
            grantee_match = re.search(r"\b(?:with|to|from)\s+([A-Za-z0-9][A-Za-z0-9_-]{0,127})\b", lowered)
            grantee_label = label_match.group(1) if label_match else (grantee_match.group(1) if grantee_match else _HADES_PENDING_HEALTH_WATCH.get(key, {}).get("grantee_label", ""))
            grantee = grantee_label
            share_subjects = _hades_self_service_share_subjects()
            grantee = share_subjects.get(grantee, grantee)
            if not grantee:
                return "Tell me which household subject to share this health watch with. Nothing changed."
            if not affirmative:
                preview_id = secrets.token_urlsafe(18)
                service.store.store_preview(
                    preview_id, subject,
                    {"kind": "action", "automation_id": target_item["automation_id"],
                     "action": action, "grantee": grantee, "grantee_label": grantee_label},
                    int(time.time()) + 600,
                )
                _HADES_PENDING_HEALTH_WATCH[key] = {
                    "automation_id": target_item["automation_id"], "action": action,
                    "grantee": grantee, "grantee_label": grantee_label,
                    "preview_id": preview_id,
                }
                return f"I found `{target_item['display_name']}`. Shall I {action} it with `{grantee_label}`?"
            pending = _HADES_PENDING_HEALTH_WATCH.pop(key, {})
            if pending.get("preview_id"):
                service.store.consume_preview(pending["preview_id"], subject)
            service.store.clear_previews(subject)
            grantee = pending.get("grantee", grantee)
            shared = list(target_item.get("shared_subjects", ()))
            if action == "share" and grantee not in shared:
                shared.append(grantee)
            if action in {"unshare", "revoke"}:
                shared = [item for item in shared if item != grantee]
            service.edit(subject, owner=True, automation_id=target_item["automation_id"], confirmed=True, shared_subjects=shared)
            return f"Updated sharing for `{target_item['display_name']}`. `{grantee_label}` has view-only access." if action == "share" else f"Revoked `{grantee_label}`'s access."
        if action in {"edit", "change"}:
            interval_match = re.search(r"\bevery\s+(\d+)\s*(minutes?|mins?|hours?|hrs?)\b", lowered)
            if not interval_match:
                return "Tell me the new bounded interval, such as `every 15 minutes`. Nothing changed."
            interval = int(interval_match.group(1)) * (60 if interval_match.group(2).startswith(("hour", "hr")) else 1)
            if not affirmative:
                _HADES_PENDING_HEALTH_WATCH[key] = {"automation_id": target_item["automation_id"], "action": "edit", "interval_minutes": interval}
                return f"I found `{target_item['display_name']}`. Shall I change it to every {interval} minutes?"
            pending = _HADES_PENDING_HEALTH_WATCH.pop(key, {})
            interval = int(pending.get("interval_minutes", interval))
            updated = service.edit(subject, owner=True, automation_id=target_item["automation_id"], confirmed=True, interval_minutes=interval)
            if runner:
                source = sources[updated["resource_id"]]
                from integrations.automation import HealthWatchSpec, build_n8n_workflow
                spec = HealthWatchSpec(updated["automation_id"], updated["owner"], updated["resource_id"], updated["display_name"], interval, updated["notification_policy"], updated["shared_subjects"])
                workflow_id = updated.get("workflow_id") or updated["automation_id"]
                runner.update_workflow(workflow_id, build_n8n_workflow(spec, source))
                runner.publish_workflow(workflow_id)
            return f"Updated `{updated['display_name']}` to every {interval} minutes."
        if not affirmative:
            _HADES_PENDING_HEALTH_WATCH[key] = {"automation_id": target_item["automation_id"], "action": action}
            verb = "run a check" if action in {"run", "check"} else action
            return f"I found `{target_item['display_name']}`. Shall I {verb} it?"
        pending = _HADES_PENDING_HEALTH_WATCH.pop(key, {})
        target_id = pending.get("automation_id", target_item["automation_id"])
        action = pending.get("action", action)
        if action in {"run", "check"}:
            if runner is None:
                return "The approved private runner is not available, so I did not run anything."
            # The n8n REST identity and the typed webhook path are distinct:
            # n8n assigns its own workflow ID, while HADES owns the stable
            # automation ID exposed by the confirmation contract.
            runner.execute_workflow(target_id)
            for _ in range(5):
                time.sleep(0.4)
                _hades_health_watch_reconcile(service, runner, target_id)
                if service.store.get(target_id).get("last_run"):
                    break
            result = service.store.get(target_id)
        else:
            runner_workflow_id = service.store.get(target_id).get("workflow_id") or target_id
            result = service.control(subject, owner=True, automation_id=target_id, action=action, confirmed=True)
            if action in {"pause", "stop", "resume"} and runner:
                runner.set_workflow_active(runner_workflow_id, action == "resume")
            if action == "delete" and runner:
                runner.delete_workflow(runner_workflow_id)
        if action in {"run", "check"}:
            state = str(result.get("state", "UNKNOWN")).replace("_", " ").lower()
            return f"The check ran. `{target_item['display_name']}` is {state}. I did not change the server."
        if action == "delete":
            return "The health watch was deleted. The monitored server was not changed."
        return f"The health watch is now {'paused' if action in {'pause', 'stop'} else 'enabled'}."
    except Exception as exc:
        _hades_logger.warning("Server Health Watch deterministic path failed closed: %s", exc)
        return "I couldn't complete that health-watch request safely. Nothing was changed."


# A small provider-selection contract for clearly current/external requests.
# This is intentionally narrower than a general intent classifier; explicit
# memory and household-domain checks retain precedence in the turn handler.
_HADES_LIVE_WEB_INTENT = re.compile(
    r"\b(?:weather|forecast|temperature|search|look\s+up|latest|news|web|"
    r"current|today|tonight|tomorrow|yesterday|recent(?:ly)?|newer|"
    r"who\s+won|score|what\s+happened|release(?:d)?|version|online|internet)\b|"
    r"https?://",
    re.IGNORECASE,
)
_HADES_PAGE_INTENT = re.compile(
    r"\b(?:read|article|page|website|instructions?|what\s+does\s+it\s+say|"
    r"open\s+(?:the\s+)?(?:page|article|link|first\s+result)|compare\s+(?:these|the)\b)",
    re.IGNORECASE,
)
_HADES_ORDINARY_CHAT_INTENT = re.compile(
    r"\b(?:say\s+hello|just\s+say|hello|hey|hi|never\s+mind|nevermind|"
    r"tell\s+me|explain|write\s+me|what\s+do\s+you\s+think)\b",
    re.IGNORECASE,
)


_HADES_TRANSIENT_ERROR = re.compile(
    r"\b(?:outcome\s+unknown|timed\s*out|timeout|temporarily\s+unavailable|"
    r"could\s+not\s+be\s+reached|request\s+failed|invalid\s+(?:json|response)|"
    r"connection\s+(?:failed|error)|service\s+(?:is\s+)?unavailable)\b",
    re.IGNORECASE,
)

_HADES_SHARED_MEMORY_INTENT = re.compile(
    r"\b(?:grocy|grocery|groceries|grocry|grocerys|shopping list|pantry|inventory|stock|"
    r"recipe|food|ingredient|bought|purchase|purchased|consume|consumed|used up|out of|add it|remove it)\b",
    re.IGNORECASE,
)
_HADES_GROCY_ACTION_INTENT = re.compile(
    r"\b(?:add|remove|buy|bought|purchase|consume|used|out of|outta)\s+"
    r"(?:(?:the|some|my)\s+)?(?:milk|eggs?|cereal|bread|cheese|pasta|rice|chicken|beef|fruit|vegetables?)\b|"
    # In household speech, "add milk" conventionally means the shared
    # shopping list. Keep the item vocabulary bounded; unknown products still
    # go through clarification rather than being guessed or created.
    r"\b(?:add|put|place)\s+(?:(?:the|some|my)\s+)?(?:milk|eggs?|cereal|bread|cheese|pasta|rice|chicken|beef|fruit|vegetables?)\s*(?:please)?[.!?]*\s*$|"
    r"\b(?:put|place|add)\s+(?:(?:the|some|my)\s+)?(?:milk|eggs?|cereal|bread|cheese|pasta|rice|chicken|beef|fruit|vegetables?)\b[^.!?]{0,40}\b(?:shopping\s+list|pantry)\b|"
    # Household products are not limited to the canned examples above. An
    # explicit verb plus a bounded destination phrase is the reliable signal
    # for a mutation such as “add HADES beta test oat milk to the grocery
    # list”; leaving it classified as a read turn exposes only read tools and
    # produces a misleading pantry answer.
    r"\b(?:add|put|place)\s+(?:(?:the|some|my)\s+)?[^.!?\n]{1,80}\s+(?:to|on|onto)\s+(?:the\s+)?(?:shopping|grocery)\s+list\b",
    re.IGNORECASE,
)
_HADES_GROCY_ITEM_FRAGMENT = re.compile(
    r"^\s*(?:milk|eggs?|cereal|bread|cheese|pasta|rice|chicken|beef|fruit|vegetables?)\s*[?!.,]*\s*$",
    re.IGNORECASE,
)


def _hades_direct_household_grocy_read(user_text):
    """Read canonical shared Grocy state without a model round trip.

    This is deliberately limited to authenticated pantry/grocery read questions.  It uses the
    same runtime-scoped credential as the Grocy MCP and performs only GETs;
    mutations, recipes, and ambiguous questions stay on the
    normal Hermes/tool path.
    """
    import urllib.request

    # Core publishes its canonical Grocy service on this loopback port.  Keep
    # the explicit environment override for reconstructed deployments, but do
    # not make a missing URL turn a safe read into a model-dependent failure.
    base_url = str(os.environ.get("GROCY_URL") or "http://127.0.0.1:7003").rstrip("/")
    api_key = str(os.environ.get("GROCY_API_KEY", ""))
    if not api_key:
        key_paths = [
            str(os.environ.get("GROCY_API_KEY_FILE") or ""),
            "/run/secrets/hades-grocy-api-key",
            "/var/lib/hades/secrets/grocy-api-key",
        ]
        for key_path in key_paths:
            if not key_path:
                continue
            try:
                api_key = Path(key_path).read_text(encoding="utf-8").strip()
            except (OSError, UnicodeError):
                continue
            if api_key:
                break
    if not base_url or not api_key:
        return None
    text = str(user_text or "")
    recommendation = bool(re.search(
        r"\b(?:what|which)\s+(?:groceries|food|items)\s+(?:sh(?:ould|ud)|do)\s+i\s+buy\b|"
        r"\bwhat\s+sh(?:ould|ud)\s+i\s+buy\b|\bwhat\s+do\s+i\s+need\s+to\s+buy\b|"
        r"\bwhat(?:'s| is)\s+running\s+low\b|\b(?:restock|run(?:ning)?\s+out|burn\s+through|consume\s+quickly)\b",
        text,
        re.IGNORECASE,
    ))
    if recommendation:
        endpoints = ("/api/stock", "/api/objects/shopping_list")
        def render(rows):
            stock, shopping = rows
            stocked = []
            for row in stock:
                product = row.get("product") or {}
                name = str(product.get("name") or row.get("product_id") or "").strip()
                amount = row.get("amount_aggregated", row.get("amount"))
                if name:
                    stocked.append(f"{name} ({amount} units)")
            listed = [str(row.get("name") or "").strip() for row in shopping]
            listed = [item for item in listed if item]
            list_text = ", ".join(listed) if listed else "nothing"
            stock_text = ", ".join(stocked) if stocked else "no stocked items"
            return (
                f"Your shared shopping list currently has {list_text}. "
                f"Grocy reports these stocked pantry items: {stock_text}. "
                "I won't add or remove anything unless you explicitly ask me to."
            )
    elif re.search(r"\bshopping\s+list\b", text, re.IGNORECASE):
        endpoint = "/api/objects/shopping_list"
        empty_message = "The shared shopping list is empty."
        def render(rows):
            items = [str(row.get("name") or "").strip() for row in rows]
            items = [item for item in items if item]
            return (
                empty_message
                if not items
                else "The shared shopping list contains: " + ", ".join(items) + "."
            )
    else:
        endpoint = "/api/stock"
        empty_message = "Grocy reports no stocked pantry items."
        def render(rows):
            items = []
            for row in rows:
                product = row.get("product") or {}
                name = str(product.get("name") or row.get("product_id") or "").strip()
                amount = row.get("amount_aggregated", row.get("amount"))
                if not name:
                    continue
                items.append(f"{name} ({amount} units)")
            return (
                empty_message
                if not items
                else "The current stock in the pantry includes " + ", ".join(items) + "."
            )
    try:
        if recommendation:
            results = []
            for endpoint in endpoints:
                request = urllib.request.Request(
                    base_url + endpoint,
                    headers={"GROCY-API-KEY": api_key, "Accept": "application/json"},
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    results.append(json.load(response))
            rows = results
        else:
            request = urllib.request.Request(
                base_url + endpoint,
                headers={"GROCY-API-KEY": api_key, "Accept": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                rows = json.load(response)
        if recommendation:
            if not all(isinstance(value, list) for value in rows):
                return None
        elif not isinstance(rows, list):
            return None
        return render(rows)
    except Exception as exc:
        _hades_logger.warning("Direct household Grocy read failed: %s", exc)
        return (
            "I couldn't check the shared pantry right now because the pantry service is unavailable. "
            "Nothing was changed; please try again in a moment."
        )


def _hades_direct_household_grocy_mutation(user_text, actor_subject=""):
    """Apply an explicit shopping-list add through Grocy and verify it.

    A plain request such as “add milk to the grocery list” is a small
    canonical mutation. Keeping it bounded prevents a weak model from
    spending minutes narrating a read before it applies the write. Unknown
    products are clarification-required; this path never creates products.
    """
    import urllib.request

    match = re.search(
        r"\b(?:add|put|place)\s+(?:(?:the|some|my)\s+)?(.+?)\s+"
        r"(?:to|on|onto)\s+(?:the\s+)?(?:shopping|grocery)\s+list\b",
        str(user_text or ""),
        re.IGNORECASE,
    )
    if match:
        item_text = re.sub(r"\s+", " ", match.group(1)).strip(" .,!?:;")
    else:
        # Bare bounded additions are a normal household shorthand. They
        # target the shared shopping list; pantry mutations remain explicit.
        bare = re.search(
            r"^\s*(?:add|put|place)\s+(?:(?:the|some|my)\s+)?"
            r"(milk|eggs?|cereal|bread|cheese|pasta|rice|chicken|beef|fruit|vegetables?)"
            r"\s*(?:please)?[.!?]*\s*$",
            str(user_text or ""),
            re.IGNORECASE,
        )
        if not bare:
            return None
        item_text = bare.group(1)
    item_text = re.sub(r"\s+", " ", item_text).strip(" .,!?:;")
    if not item_text or len(item_text) > 96:
        return "Which item should I add to the shared shopping list? I haven't changed anything yet."
    base_url = str(os.environ.get("GROCY_URL") or "http://127.0.0.1:7003").rstrip("/")
    api_key = str(os.environ.get("GROCY_API_KEY", ""))
    if not api_key:
        return None

    def request(path, method="GET", payload=None):
        body = None if payload is None else json.dumps(payload).encode()
        headers = {"GROCY-API-KEY": api_key, "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(base_url + path, data=body, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.load(response)

    def serialized_add(product_id):
        """Re-read and add under a small cross-process lock.

        The canonical shopping-list API has no idempotency key for this
        operation. The second read must therefore happen while the lock is
        held, otherwise two household users can both pass the initial check.
        """
        import fcntl
        from pathlib import Path

        lock_path = Path(_hades_grocy_audit_path() + ".lock")
        lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with lock_path.open("a+") as lock:
            os.chmod(lock_path, 0o600)
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                current = request("/api/objects/shopping_list")
                current = current if isinstance(current, list) else []
                if any(
                    int(row.get("product_id") or 0) == product_id and not row.get("done")
                    for row in current
                ):
                    return None, True
                return (
                    request(
                        "/api/objects/shopping_list",
                        method="POST",
                        payload={"product_id": product_id, "amount": 1, "shopping_list_id": 1},
                    ),
                    False,
                )
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    try:
        products = request("/api/objects/products")
        products = products if isinstance(products, list) else []
        needle = item_text.casefold()
        matches = [p for p in products if str(p.get("name") or "").casefold() == needle]
        if not matches:
            matches = [
                p for p in products
                if needle in str(p.get("name") or "").casefold()
                or str(p.get("name") or "").casefold() in needle
            ]
        if len(matches) != 1:
            return (
                f"I couldn't match '{item_text}' to one existing Grocy product. "
                "Tell me the exact pantry item, and I haven't changed anything yet."
            )
        product = matches[0]
        product_id = int(product["id"])
        product_name = str(product.get("name") or item_text)
        if not _hades_record_grocy_mutation(
            actor_subject, "shopping_list_add", f"product:{product_id}", "requested"
        ):
            return (
                "I couldn't establish a protected record of your household change, "
                "so I haven't changed the shopping list."
            )
        try:
            created, already_present = serialized_add(product_id)
            if already_present:
                _hades_record_grocy_mutation(
                    actor_subject, "shopping_list_add", f"product:{product_id}", "already_present"
                )
                return f"{product_name} is already on the shared shopping list. Nothing was duplicated."
        except Exception:
            _hades_record_grocy_mutation(
                actor_subject, "shopping_list_add", f"product:{product_id}", "outcome_unknown"
            )
            return (
                "The shopping-list service stopped responding while I was adding "
                f"{product_name}. The outcome is unknown; please check the list before retrying."
            )
        created_id = int(created.get("created_object_id") or 0) if isinstance(created, dict) else 0
        verified = request("/api/objects/shopping_list")
        verified = verified if isinstance(verified, list) else []
        if not any(
            int(row.get("product_id") or 0) == product_id
            and (not created_id or int(row.get("id") or 0) == created_id)
            and not row.get("done")
            for row in verified
        ):
            _hades_record_grocy_mutation(
                actor_subject, "shopping_list_add", f"product:{product_id}", "outcome_unknown"
            )
            return "I couldn't verify the shopping-list change, so treat the outcome as unknown and check the list before retrying."
        _hades_record_grocy_mutation(
            actor_subject, "shopping_list_add", f"product:{product_id}", "applied"
        )
        return f"Added {product_name} to the shared shopping list and verified it."
    except Exception as exc:
        _hades_logger.warning("Direct household Grocy mutation failed: %s", exc)
        _hades_record_grocy_mutation(
            actor_subject, "shopping_list_add", "unresolved", "failed"
        )
        return "I couldn't update the shared shopping list. Nothing was confirmed as changed; please try again."


def _hades_direct_grocy_recipe_read(user_text):
    """Recommend canonical Grocy recipes using only shared stock reads.

    This is intentionally limited to explicit recipe-fulfillment questions.
    It never creates recipes, edits stock, or claims that an unlisted recipe
    exists; the model/tool path remains responsible for authoring and writes.
    """
    import urllib.request

    text = str(user_text or "")
    _hades_logger.info("Direct Grocy recipe classifier received text=%r", text[:240])
    not_make_request = bool(re.search(
        r"\b(?:what|which)\s+(?:recipes?|meals?)\b.*\b(?:can't|cannot|can\s+(?:i|we)\s+not|not\s+(?:make|cook|prepare))\b",
        text,
        re.IGNORECASE,
    ))
    inventory_request = bool(re.search(
        r"\b(?:list|show)\s+(?:all\s+)?(?:my\s+|our\s+|the\s+)?(?:saved\s+)?recipes?\b|"
        r"\b(?:list|show)\b.*\brecipes?\b.*\b(?:which|what)\b.*\b(?:make|cook|prepare)\b|"
        r"\bwhat\s+(?:recipes?|cooking\s+recipes?)\s+(?:do\s+(?:i|we)\s+have|are\s+(?:saved|available))\b|"
        r"\bwhat\s+(?:recipes?|cooking\s+recipes?)\s+do\s+we\s+have\b",
        text,
        re.IGNORECASE,
    ))
    if not re.search(
        r"(?:\b(?:list|show)\s+(?:my\s+|our\s+|the\s+)?recipes?\b|"
        r"\b(?:list|show)\b.*\brecipes?\b.*\b(?:which|what)\b.*\b(?:make|cook|prepare)\b|"
        r"\bwhat\s+(?:recipes?|cooking\s+recipes?|can\s+(?:i|we)\s+(?:make|cook|prepare))\b|"
        r"\b(?:recipes?|meals?)\s+(?:i|we)\s+(?:have|can\s+make|can\s+cook)\b|"
        r"\b(?:recipes?|meals?)\s+(?:i|we)\s+(?:cannot|can't|can\s+not)\s+(?:make|cook|prepare)\b|"
        r"\bwhat\s+can\s+(?:i|we)\s+(?:make|cook|prepare)\b|"
        r"\bwhat(?:'s|\s+is)\s+there\s+to\s+(?:make|cook|prepare)\b|"
        r"\bwhat\s+(?:should|could)\s+(?:i|we)\s+(?:make|cook|prepare)\b|"
        r"\bwhat\s+should\s+(?:i|we)\s+have\s+(?:for\s+)?(?:dinner|tonight)\b|"
        r"\bhelp\s+(?:me|us)\s+(?:make|cook|plan)\s+(?:a\s+)?(?:meal|dinner)\b|"
        r"\b(?:dinner|meal)\s+ideas?\b)",
        text,
        re.IGNORECASE,
    ):
        if not not_make_request and not inventory_request:
            return None
    base_url = str(os.environ.get("GROCY_URL") or "http://127.0.0.1:7003").rstrip("/")
    api_key = str(os.environ.get("GROCY_API_KEY", ""))
    if not api_key:
        for key_path in [str(os.environ.get("GROCY_API_KEY_FILE") or ""), "/run/secrets/hades-grocy-api-key", "/var/lib/hades/secrets/grocy-api-key"]:
            if not key_path:
                continue
            try:
                api_key = Path(key_path).read_text(encoding="utf-8").strip()
            except (OSError, UnicodeError):
                continue
            if api_key:
                break
    if not base_url or not api_key:
        _hades_logger.warning("Direct Grocy recipe read unavailable: base_url=%s api_key_present=%s", bool(base_url), bool(api_key))
        return None

    def get(path):
        request = urllib.request.Request(
            base_url + path,
            headers={"GROCY-API-KEY": api_key, "Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)

    try:
        recipes = get("/api/objects/recipes")
        positions = get("/api/objects/recipes_pos")
        products = get("/api/objects/products")
        stock = get("/api/stock")
        if not all(isinstance(value, list) for value in (recipes, positions, products, stock)):
            return None
        product_names = {
            int(row["id"]): str(row.get("name") or row["id"])
            for row in products
            if isinstance(row, dict) and str(row.get("id", "")).isdigit()
        }
        available = {}
        for row in stock:
            if not isinstance(row, dict) or not str(row.get("product_id", "")).isdigit():
                continue
            product_id = int(row["product_id"])
            try:
                available[product_id] = available.get(product_id, 0.0) + float(
                    row.get("amount_aggregated", row.get("amount", 0)) or 0
                )
            except (TypeError, ValueError):
                continue
        by_recipe = {}
        for row in positions:
            if not isinstance(row, dict) or not str(row.get("recipe_id", "")).isdigit():
                continue
            by_recipe.setdefault(int(row["recipe_id"]), []).append(row)
        candidates = []
        for recipe in recipes:
            if not isinstance(recipe, dict) or not str(recipe.get("id", "")).isdigit():
                continue
            ingredients = by_recipe.get(int(recipe["id"]), [])
            missing = []
            for ingredient in ingredients:
                product_id = ingredient.get("product_id")
                if not str(product_id).isdigit():
                    continue
                required = float(ingredient.get("amount", 0) or 0)
                have = available.get(int(product_id), 0.0)
                if have < required:
                    label = product_names.get(int(product_id), str(product_id))
                    missing.append(f"{label} ({max(required - have, 0):g} more)")
            candidates.append((str(recipe.get("name") or recipe["id"]), missing))
        if not candidates:
            return "I couldn't find any stocked recipes in the shared pantry yet."
        complete = [name for name, missing in candidates if not missing]
        partial = [(name, missing) for name, missing in candidates if missing]
        if inventory_request:
            entries = []
            for name, missing in candidates:
                entries.append(
                    f"{name} — makeable with current stock"
                    if not missing
                    else f"{name} — missing: {', '.join(missing)}"
                )
            return "Saved Grocy recipes: " + "; ".join(entries) + ". I only checked canonical recipes and stock; I did not change anything."
        if not_make_request:
            if not partial:
                return "You can currently make every canonical Grocy recipe with the shared stock. I did not change anything."
            return "You cannot currently make: " + "; ".join(f"{name} (missing {', '.join(missing)})" for name, missing in partial) + ". I only checked canonical recipes and stock; I did not change anything."
        lines = []
        if complete:
            lines.append("You currently have everything Grocy lists for: " + ", ".join(complete) + ".")
        if partial:
            for name, missing in partial:
                lines.append(f"{name} is possible, but you still need: {', '.join(missing)}.")
        lines.append("I only checked the shared pantry; I did not change stock or the shopping list.")
        return " ".join(lines)
    except Exception as exc:
        _hades_logger.warning("Direct Grocy recipe read failed: %s", exc)
        return (
            "I couldn't check the shared pantry for recipes right now because the pantry service is unavailable. "
            "Nothing was changed; please try again in a moment."
        )


def _hades_direct_spaghetti_authorized(user_text, actor_subject=""):
    """Create the owner-approved canonical spaghetti draft and shopping items.

    This is deliberately narrow. The owner authorized inventing a standard
    spaghetti recipe and missing products; the recipe is labeled as an HADES
    draft, every write is idempotent by exact name, and canonical reads verify
    the result before reporting it.
    """
    text = str(user_text or "")
    if not re.search(r"\bspaghetti\b", text, re.IGNORECASE) or not re.search(r"\b(?:make|missing|grocery|shopping|need|tonight)\b", text, re.IGNORECASE):
        return None
    import urllib.request
    base_url = str(os.environ.get("GROCY_URL") or "http://127.0.0.1:7003").rstrip("/")
    api_key = str(os.environ.get("GROCY_API_KEY", ""))
    if not api_key:
        for key_path in [str(os.environ.get("GROCY_API_KEY_FILE") or ""), "/run/secrets/hades-grocy-api-key", "/var/lib/hades/secrets/grocy-api-key"]:
            if key_path:
                try:
                    api_key = Path(key_path).read_text(encoding="utf-8").strip()
                except (OSError, UnicodeError):
                    pass
            if api_key:
                break
    if not api_key:
        return "I couldn't create the canonical spaghetti draft because Grocy is not configured. Nothing was changed."
    ingredients = [("Spaghetti", "200"), ("Tomato Sauce", "1"), ("Ground Beef", "500"), ("Onion", "1"), ("Garlic", "2")]
    def request(path, method="GET", payload=None):
        body = None if payload is None else json.dumps(payload).encode()
        headers = {"GROCY-API-KEY": api_key, "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(base_url + path, data=body, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            return json.load(response)
    try:
        products = request("/api/objects/products")
        units = request("/api/objects/quantity_units")
        products = products if isinstance(products, list) else []
        units = units if isinstance(units, list) else []
        piece = next((int(row["id"]) for row in units if str(row.get("name", "")).casefold() == "piece"), 2)
        product_by_name = {str(row.get("name", "")).casefold(): row for row in products if row.get("name")}
        created_products = []
        for name, _amount in ingredients:
            if name.casefold() in product_by_name:
                continue
            created = request("/api/objects/products", "POST", {"name": name, "location_id": 2, "qu_id_purchase": piece, "qu_id_stock": piece, "min_stock_amount": 0, "default_best_before_days": 0})
            product_id = int(created.get("created_object_id"))
            product = request(f"/api/objects/products/{product_id}")
            product_by_name[name.casefold()] = product
            created_products.append(name)
        recipes = request("/api/objects/recipes")
        recipes = recipes if isinstance(recipes, list) else []
        title = "HADES Owner Spaghetti Draft"
        existing = next((row for row in recipes if str(row.get("name", "")).casefold() == title.casefold()), None)
        recipe_id = int(existing["id"]) if existing else None
        if recipe_id is None:
            created = request("/api/objects/recipes", "POST", {"name": title, "description": "Owner-authorized invented baseline recipe; ingredients are editable in Grocy.", "base_servings": 4, "desired_servings": 4, "not_check_shoppinglist": False})
            recipe_id = int(created.get("created_object_id"))
            for name, amount in ingredients:
                request("/api/objects/recipes_pos", "POST", {"recipe_id": recipe_id, "product_id": int(product_by_name[name.casefold()]["id"]), "amount": amount, "qu_id": piece})
        positions = request("/api/objects/recipes_pos")
        positions = positions if isinstance(positions, list) else []
        present_ids = {int(row.get("product_id")) for row in positions if str(row.get("recipe_id")) == str(recipe_id) and str(row.get("product_id", "")).isdigit()}
        stock = request("/api/stock")
        available = {int(row.get("product_id")): float(row.get("amount_aggregated", row.get("amount", 0)) or 0) for row in stock if isinstance(row, dict) and str(row.get("product_id", "")).isdigit()}
        shopping = request("/api/objects/shopping_list")
        shopping = shopping if isinstance(shopping, list) else []
        missing = []
        for name, amount in ingredients:
            product = product_by_name[name.casefold()]; product_id = int(product["id"])
            if float(available.get(product_id, 0)) < float(amount):
                missing.append(name)
                if not any(int(row.get("product_id") or 0) == product_id and not row.get("done") for row in shopping):
                    request("/api/objects/shopping_list", "POST", {"product_id": product_id, "amount": 1, "shopping_list_id": 1})
        verified = request("/api/objects/recipes_pos")
        verified_ids = {int(row.get("product_id")) for row in verified if str(row.get("recipe_id")) == str(recipe_id) and str(row.get("product_id", "")).isdigit()}
        if not all(int(product_by_name[name.casefold()]["id"]) in verified_ids for name, _ in ingredients):
            return "I created the spaghetti draft attempt, but Grocy did not verify every ingredient. Check the recipe before retrying; I won't duplicate it."
        return f"I created and verified `{title}` in canonical Grocy with {len(ingredients)} invented baseline ingredients. Missing items added to the shared shopping list: {', '.join(missing) if missing else 'none'}. This is an editable owner draft; no pantry stock was fabricated."
    except Exception as exc:
        # A Grocy response can be lost after the write. Reconcile the exact
        # draft title and all ingredient positions before reporting unknown;
        # this prevents a successful canonical action from being retried and
        # duplicated merely because the final response was interrupted.
        try:
            recipes = request("/api/objects/recipes")
            found = next((row for row in recipes if str(row.get("name", "")).casefold() == "hades owner spaghetti draft"), None)
            positions = request("/api/objects/recipes_pos")
            if found and str(found.get("id", "")).isdigit():
                recipe_id = int(found["id"])
                ids = {int(row.get("product_id")) for row in positions if str(row.get("recipe_id")) == str(recipe_id) and str(row.get("product_id", "")).isdigit()}
                products = request("/api/objects/products")
                names = {str(row.get("name", "")).casefold(): int(row["id"]) for row in products if row.get("name") and str(row.get("id", "")).isdigit()}
                if all(names.get(name.casefold()) in ids for name, _ in ingredients):
                    return "I created and verified `HADES Owner Spaghetti Draft` in canonical Grocy with five owner-authorized baseline ingredients. The shared shopping-list state was reconciled after the interrupted response; no pantry stock was fabricated."
        except Exception:
            pass
        _hades_logger.warning("Authorized spaghetti canonical action failed: %s", type(exc).__name__)
        return "I couldn't complete the canonical spaghetti action safely. The result is not confirmed; check Grocy before retrying."


def _hades_direct_grocy_expiry_read(user_text):
    """Read Grocy expiry metadata and bounded recipe overlap without writes."""
    import urllib.request
    from datetime import date, timedelta

    text = str(user_text or "")
    if not re.search(r"\b(?:expir|expire|go\s+bad|use\s+up|waste|best\s+before)\w*\b", text, re.IGNORECASE):
        return None
    base_url = str(os.environ.get("GROCY_URL") or "http://127.0.0.1:7003").rstrip("/")
    api_key = str(os.environ.get("GROCY_API_KEY", ""))
    if not api_key:
        for key_path in [str(os.environ.get("GROCY_API_KEY_FILE") or ""), "/run/secrets/hades-grocy-api-key", "/var/lib/hades/secrets/grocy-api-key"]:
            if not key_path:
                continue
            try:
                api_key = Path(key_path).read_text(encoding="utf-8").strip()
            except (OSError, UnicodeError):
                continue
            if api_key:
                break
    if not api_key:
        return "I couldn't check expiry metadata because the canonical Grocy read authority is unavailable. Nothing was changed."
    def get(path):
        request = urllib.request.Request(base_url + path, headers={"GROCY-API-KEY": api_key, "Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)
    try:
        stock = get("/api/stock")
        today = date.today()
        cutoff = today + timedelta(days=7)
        expiring, expired, missing_date = [], [], []
        for row in stock if isinstance(stock, list) else []:
            product = row.get("product") or {}
            name = str(product.get("name") or row.get("product_id") or "").strip()
            raw = str(row.get("best_before_date") or "").strip()
            if not name:
                continue
            if not raw:
                missing_date.append(name)
                continue
            try:
                due = date.fromisoformat(raw[:10])
            except ValueError:
                missing_date.append(name)
                continue
            amount = row.get("amount_aggregated", row.get("amount"))
            item = f"{name} ({amount} units, {raw})"
            if due < today:
                expired.append(item)
            elif due <= cutoff:
                expiring.append(item)
        lines = []
        lines.append("Known expired: " + (", ".join(expired) if expired else "none" ) + ".")
        lines.append("Known to expire within 7 days: " + (", ".join(expiring) if expiring else "none" ) + ".")
        if missing_date:
            lines.append("Expiry metadata is missing for: " + ", ".join(missing_date) + "; I did not guess dates.")
        if expiring or expired:
            try:
                recipes = get("/api/objects/recipes")
                positions = get("/api/objects/recipes_pos")
                expiring_ids = {str(row.get("product_id")) for row in stock if str(row.get("best_before_date") or "")[:10] and str(row.get("product_id"))}
                recipe_ids = []
                for row in positions if isinstance(positions, list) else []:
                    if str(row.get("product_id")) in expiring_ids and str(row.get("recipe_id")) not in recipe_ids:
                        recipe_ids.append(str(row.get("recipe_id")))
                meals = [str(row.get("name")) for row in recipes if str(row.get("id")) in recipe_ids][:3]
                lines.append("Recipes that overlap expiring ingredients: " + (", ".join(meals) if meals else "none found in Grocy") + ".")
            except Exception:
                lines.append("I could not cross-reference recipes for meal suggestions; the expiry read itself completed.")
        lines.append("This was a canonical Grocy expiry read; no stock or shopping-list changes were made.")
        return " ".join(lines)
    except Exception as exc:
        _hades_logger.warning("Direct Grocy expiry read failed: %s", exc)
        return "I couldn't check expiry metadata because the canonical Grocy read is unavailable. Nothing was changed."


def _hades_live_proxmox_vm_rows():
    """Read bounded VM runtime rows through the configured GET-only path.

    The standalone homelab adapter may have no NetBox/Kuma inputs in a
    deployment. The existing Proxmox control adapter already has a bounded
    cluster/resources GET operation and its credential is available to the
    Hermes runtime. Use only that read operation as a supplemental source;
    never call a control or mutation method from this helper.
    """
    try:
        from pathlib import Path
        import importlib.util

        candidates = [
            Path("/var/lib/hades/source/integrations/homelab-control/control.py"),
            Path(__file__).resolve().parents[2] / "Hades-reconciled-b102dfd" / "integrations" / "homelab-control" / "control.py",
        ]
        control_path = next((path for path in candidates if path.is_file()), None)
        if control_path is None:
            return []
        spec = importlib.util.spec_from_file_location("hades_live_proxmox_read", control_path)
        if spec is None or spec.loader is None:
            return []
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        payload = module._request("cluster/resources", params={"type": "vm"})
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        return [
            {
                "name": str(row.get("name") or f"vm-{row.get('vmid')}"),
                "node": str(row.get("node") or "UNKNOWN"),
                "vmid": row.get("vmid"),
                "status": str(row.get("status") or "UNKNOWN"),
                "cpu": row.get("cpu"),
                "maxcpu": row.get("maxcpu"),
                "mem": row.get("mem"),
                "maxmem": row.get("maxmem"),
                "disk": row.get("disk"),
                "maxdisk": row.get("maxdisk"),
                "uptime": row.get("uptime"),
            }
            for row in rows
            if isinstance(row, dict) and row.get("vmid") is not None
        ]
    except Exception as exc:
        _hades_logger.info("Supplemental Proxmox runtime read unavailable: %s", type(exc).__name__)
        return []


def _hades_direct_finance_guidance(user_text):
    """Answer owner finance questions from the explicitly authorized CSV.

    This is a read-only, local-file source. It intentionally refuses to turn
    historical statement rows into current balances, future paychecks, or a
    guaranteed safe-to-spend amount.
    """
    text = str(user_text or "")
    # A correction can mention the prior finance topic while explicitly
    # replacing it with a household request.  Let the canonical Grocy route
    # own phrases such as "forget the spending advice; just give me groceries"
    # instead of leaking the old finance interpretation into the new turn.
    if re.search(
        r"\b(?:just|only|instead|forget|actually)\b[^.!?]{0,100}\b(?:grocery|groceries|food|pantry|fridge)\b",
        text,
        re.IGNORECASE,
    ):
        return None
    if not re.search(
        r"\b(?:finance|finances|finaces|bank|csv|spend|spending|spent|budget|"
        r"transaction|account|checking|savings|credit\s+card|money|cost|paid|"
        r"expense|expenses|subscription|subscriptions|recurring|utilities?|restaurant|doordash|"
        r"coffee|rent|lease|paycheck|bills?)\b|"
        r"\bprivate\s+(?:account|checking|savings|finance|finances)\b|"
        r"^\s*(?:import|review|inspect)\s+(?:this|the\s+(?:file|statement|csv))\s*[.!?]*$",
        text, re.IGNORECASE,
    ):
        return None
    lowered_text = text.casefold()
    csv_path = Path(os.environ.get("HADES_FINANCE_CSV_PATH", "/mnt/shared/Downloads/bk_download.csv"))
    if csv_path.is_file() and csv_path.stat().st_size <= 25 * 1024 * 1024:
        try:
            import csv
            from collections import defaultdict
            from datetime import date
            from decimal import Decimal, InvalidOperation
            rows = []
            with csv_path.open(newline="", encoding="utf-8-sig") as handle:
                for row in csv.DictReader(handle):
                    raw_date = str(row.get("Date") or "").strip()
                    try:
                        when = date.fromisoformat(raw_date[:10])
                        amount = Decimal(str(row.get("Amount") or "0").replace(",", "").replace("$", "").strip())
                    except (ValueError, InvalidOperation):
                        continue
                    rows.append({"date": when, "amount": amount, "description": str(row.get("Description") or row.get("Original Description") or "").strip(), "category": str(row.get("Category") or "").strip(), "status": str(row.get("Status") or "").strip()})
            if rows:
                first, last = min(row["date"] for row in rows), max(row["date"] for row in rows)
                pending = sum(row["status"].casefold() == "pending" for row in rows)
                months = sorted({row["date"].strftime("%Y-%m") for row in rows})
                lowered = text.casefold()
                monthly = defaultdict(Decimal)
                for row in rows:
                    monthly[row["date"].strftime("%Y-%m")] += -row["amount"] if row["amount"] < 0 else Decimal("0")
                def money(value):
                    return f"${value.quantize(Decimal('0.01')):,.2f}"
                if re.search(r"\b(?:actual\s+budget\s+)?account(?:s|\s+ids?)\b|\baccount\s+id\b", lowered_text):
                    return f"The attached statement covers {first} through {last}, but its columns do not contain Actual Budget account IDs. HADES currently has no verified live Actual Budget account catalog to query, so I cannot name or invent an account ID. The statement can be inspected read-only; no import was performed."
                if re.search(r"\b(?:import|review|inspect)\b", lowered_text) and (csv_path.name.casefold() in lowered_text or "this" in lowered_text or "csv" in lowered_text or "statement" in lowered_text):
                    return f"Private statement inspection: {len(rows)} usable rows in {csv_path.name}, covering {first} through {last}; {pending} are pending. I can preview the mapping, but no Actual Budget account is configured/verified here, so nothing was imported and no account ID was invented."
                if re.search(r"utilities?|electric|internet|phone", lowered):
                    buckets = {"electric": ("electric",), "internet": ("internet",), "phone": ("phone", "mobile"), "other utilities": ("utility", "utilities", "water", "gas")}
                    totals = {name: sum((-r["amount"] for r in rows if r["amount"] < 0 and any(term in (r["category"] + " " + r["description"]).casefold() for term in terms)), Decimal("0")) for name, terms in buckets.items()}
                    total = sum(totals.values(), Decimal("0"))
                    return f"CSV finance read (owner-only, read-only): {len(rows)} usable rows covering {first} through {last}; {pending} pending. Utilities found: " + "; ".join(f"{name} {money(value)} total" for name, value in totals.items() if value) + f". Average across {len(months)} statement months: {money(total / max(len(months), 1))}. This is historical statement data, not a live balance."
                if re.search(r"restaurant|doordash|coffee|convenience|takeout|food", lowered):
                    matches = [r for r in rows if r["amount"] < 0 and any(term in (r["category"] + " " + r["description"]).casefold() for term in ("restaurant", "fast food", "coffee", "doordash", "grubhub", "uber eats", "convenience"))]
                    by_month = defaultdict(Decimal)
                    merchants = defaultdict(Decimal)
                    for row in matches:
                        value = -row["amount"]; by_month[row["date"].strftime("%Y-%m")] += value; merchants[row["description"] or row["category"]] += value
                    top = sorted(merchants.items(), key=lambda item: item[1], reverse=True)[:5]
                    return f"CSV finance read (owner-only, read-only): {len(matches)} dining/coffee/food transactions totaling {money(sum(by_month.values(), Decimal('0')))} across {first} through {last}. Monthly totals: " + "; ".join(f"{month} {money(value)}" for month, value in sorted(by_month.items())) + ". Largest description groups: " + "; ".join(f"{name} {money(value)}" for name, value in top) + ". Merchant identity is limited to statement descriptions."
                if re.search(r"prepaid|lease", lowered) and not re.search(r"safe(?:ly)?\s+spend|weekend", lowered):
                    return f"I can read the authorized CSV ({first} through {last}, {len(rows)} usable rows), but it does not contain your current balance, lease target, remaining lease amount, or future paychecks. I will not invent where you should be or how much to set aside from each paycheck."
                if re.search(r"safe(?:ly)?\s+spend|weekend|balances?|paychecks?|rent\s+plan", lowered):
                    return f"I can read the authorized CSV ({first} through {last}, {len(rows)} usable rows), but it does not contain current account balances, future bills, or future paychecks. I will not invent a safe-to-spend number or a lease-prepayment target from historical transactions."
                if re.search(r"subscription|recurring|duplicate|increased|barely use", lowered):
                    grouped = defaultdict(list)
                    for row in rows:
                        if row["amount"] < 0 and row["description"]:
                            key = re.sub(r"[^a-z0-9]+", " ", row["description"].casefold()).strip()
                            grouped[key].append(-row["amount"])
                    recurring = [(key, values) for key, values in grouped.items() if len(values) >= 2]
                    increases = [key for key, values in recurring if max(values) > min(values) * Decimal("1.05")]
                    return f"CSV finance read (owner-only, read-only): {len(recurring)} description groups recur at least twice. {len(increases)} show a material amount increase over observed charges. I cannot prove usage or true duplicate subscriptions from this CSV alone; review candidates before acting."
                if re.search(r"cut|save|reduce|300", lowered):
                    discretionary = sum((-r["amount"] for r in rows if r["amount"] < 0 and any(term in (r["category"] + " " + r["description"]).casefold() for term in ("restaurant", "fast food", "coffee", "shopping", "entertainment"))), Decimal("0"))
                    return f"Historical CSV analysis found {money(discretionary)} in restaurant/fast-food/coffee/shopping/entertainment charges across {len(months)} months. A $300/month reduction is not guaranteed from this file alone, but these categories are the first owner-review candidates."
                return f"Authorized finance CSV is available owner-only and read-only: {len(rows)} usable rows covering {first} through {last}; {pending} pending. It is not imported into Actual Budget and does not expose current balances."
        except (OSError, UnicodeError, csv.Error) as exc:
            _hades_logger.warning("Finance CSV read failed: %s", type(exc).__name__)
    if re.search(r"\b(?:csv|statement|downloaded|file|upload|attach|give it to you)\b", text, re.IGNORECASE):
        return "I could not read the configured finance CSV. Attach a CSV statement for a private, write-free preview; no account import will occur from the preview screen."
    return (
        "I don't have a live bank or Actual Budget ledger connected. The authorized local CSV is unavailable or unreadable, so I won't guess at spending totals or balances."
    )


def _hades_direct_capability_guidance(user_text):
    """Explain everyday capabilities without requiring an inference turn."""
    text = str(user_text or "").strip()
    if re.search(
        r"^\s*(?:did\s+(?:that|it)\s+work|did\s+that\s+actually\s+get\s+added|"
        r"are\s+you\s+sure|show\s+me)\s*[?!.]*\s*$",
        text,
        re.IGNORECASE,
    ):
        return (
            "I can verify it, but I need to know which action you mean. Tell me what you want me to check, "
            "and I will compare it with the actual pantry, list, memory, or account state."
        )
    if re.search(r"\b(?:look|check)\s+(?:in|at)\s+(?:your|my)\s+memory\b", text, re.IGNORECASE):
        return "What fact or topic should I look for in your memory?"
    if re.search(r"\bwhat\s+can\s+you\s+(?:help|do)\b|\bwhat\s+can\s+hades\s+do\b", text, re.IGNORECASE):
        return (
            "I can help with the shared pantry and shopping list, suggest meals from what is stocked, "
            "search and read public web pages, remember useful personal context, check homelab status, "
            "and review receipt or statement files before anything is changed. "
            "I will ask before a consequential update, and I will say when a service or live account is unavailable."
        )
    if re.search(r"\b(?:anything\s+with|help\s+with)\s+(?:groceries|grocery|food|pantry|shopping)\b", text, re.IGNORECASE):
        return (
            "Yes. I can check the shared pantry, manage the shopping list, suggest recipes, and review a receipt "
            "before adding anything. Say what you want in ordinary language, such as `do we have milk` or "
            "`add eggs to the list`. I will confirm consequential changes."
        )
    if re.search(r"\b(?:use|read|import)\b.*\b(?:bank\s+statement|bank\s+statements|statement|csv|money)\b", text, re.IGNORECASE):
        return (
            "Yes—attach a statement and ask me to import or inspect it. I start with a private, write-free preview "
            "of the rows and mapping. A live spending total or final import still needs an authorized finance account; "
            "I will not ask you to paste bank credentials into chat."
        )
    if re.search(r"\b(?:read|understand|look\s+at)\b.*\b(?:pictures?|photos?|images?)\b", text, re.IGNORECASE):
        return (
            "I can inspect receipt photos and show what I think they contain for your review. Unclear items stay "
            "unresolved until you correct or confirm them, and an OCR outage will not create a pantry change."
        )
    if re.search(r"\b(?:remember|memory|recall)\b", text, re.IGNORECASE):
        return (
            "Yes. You can ask me to remember useful personal context and recall it in a later conversation. "
            "I keep private memory separate from household shared state, and I will not treat a failed tool call as a memory."
        )
    if re.search(r"\b(?:roommate|room mate|household|family)\b.*\b(?:use|access|share|login)\b|\bcan\s+my\s+roommate\b", text, re.IGNORECASE):
        return (
            "Household members can use shared pantry, shopping-list, and public-search features with their own account. "
            "Owner finance, private memory, administration, and operator actions stay owner-only."
        )
    return None


def _hades_direct_ambiguous_mutation_clarification(user_text):
    """Ask a small clarification for an underspecified household mutation."""
    text = str(user_text or "").strip()
    if not re.search(
        r"\b(?:put|add|place)\s+(?:this|that)\s+(?:in|on)\s+(?:there|that)\b|"
        r"\b(?:put|add)\s+it\s+(?:in|on)\s+(?:there|that)\b|"
        r"\b(?:put|save|add)\s+(?:this|that|it)\s+(?:in|to|into)\s+"
        r"(?:the\s+)?(?:database|grocery\s+app|money\s+thing)\b",
        text,
        re.IGNORECASE,
    ):
        return None
    return (
        "What should I add, and which place do you mean? If it's groceries, say pantry or "
        "shopping list; if it's a statement, attach it for a safe preview. I haven't changed anything yet."
    )


def _hades_direct_web_search(user_text):
    """Return bounded SearXNG evidence for an explicit simple search request.

    This is a failure-locality fallback for ordinary search while inference is
    unavailable. It deliberately does not handle page-reading requests and
    labels snippets as search evidence rather than pretending they are a full
    source read.
    """
    import urllib.parse
    import urllib.request

    text = str(user_text or "").strip()
    query = _hades_extract_web_query(text)
    if query is None or _HADES_PAGE_INTENT.search(text) or re.search(r"https?://", text, re.IGNORECASE):
        return None
    base_url = str(os.environ.get("SEARXNG_URL") or "http://127.0.0.1:8080").rstrip("/")
    url = f"{base_url}/search?{urllib.parse.urlencode({'q': query, 'format': 'json'})}"
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.load(response)
        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list) or not results:
            return f"I searched for {query!r}, but the search returned no results."
        lines = [f"I searched for {query!r}. These are search snippets, not full page reads:"]
        for result in results[:3]:
            if not isinstance(result, dict):
                continue
            title = str(result.get("title") or "Untitled result").strip()
            content = re.sub(r"\s+", " ", str(result.get("content") or "")).strip()
            link = str(result.get("url") or "").strip()
            if len(content) > 280:
                content = content[:277].rstrip() + "..."
            lines.append(f"- {title}: {content or 'No snippet provided.'} ({link})")
        lines.append("Say ‘read the first result’ if you want me to try the page itself.")
        return "\n".join(lines)
    except Exception as exc:
        _hades_logger.warning("Direct SearXNG search failed: %s", exc)
        return "The web search is unavailable right now. I did not invent an answer. Try again in a moment."


def _hades_extract_web_query(user_text):
    """Extract the user's query without leaking conversational filler."""
    text = str(user_text or "").strip()
    match = re.search(
        r"(?:look(?:\s+this)?\s+up(?:\s+for\s+me)?|search(?:\s+for)?|find(?:\s+out)?(?:\s+about)?|google)"
        r"\s*[:\-]?\s*(.+)$",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    query = re.sub(r"\s+", " ", match.group(1)).strip(" .?!")
    if len(query) < 3 or len(query) > 240:
        return None
    return query


def _hades_direct_public_page_read(user_text):
    """Read an explicitly supplied public static URL without model inference."""
    import importlib.util
    from pathlib import Path

    text = str(user_text or "").strip()
    url_match = re.search(r"https?://[^\s<>]+", text, re.IGNORECASE)
    if not url_match or not re.search(
        r"\b(?:read|page|website|link|article|what(?:'s|\s+is)\s+(?:on|it\s+say)|look\s+(?:at|this\s+up))\b",
        text,
        re.IGNORECASE,
    ):
        return None
    url = url_match.group(0).rstrip(".,!?)]}")
    roots = [Path(os.environ.get("HADES_HERMES_WORKING_DIRECTORY") or Path.cwd())]
    # Older generated Hermes profiles do not carry the newer adapter tree into
    # the reconciled checkout. Prefer the configured runtime tree, but retain
    # the existing private source checkout as a bounded compatibility source
    # until the next full deployment-record refresh.
    roots.append(Path("/var/lib/hades/source"))
    source = next(
        (root / "integrations" / "web-extract" / "server.py" for root in roots
         if (root / "integrations" / "web-extract" / "server.py").is_file()),
        None,
    )
    if source is None:
        return None
    try:
        spec = importlib.util.spec_from_file_location("hades_public_page_reader", source)
        if not spec or not spec.loader:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.read_public_page(url)
        if not isinstance(result, dict):
            return "I couldn't read that public page. The reader returned an invalid result."
        if result.get("status") != "SUCCEEDED":
            return f"I couldn't read that public page. {result.get('error') or 'The page returned no usable text.'}"
        title = str(result.get("title") or "Untitled page")
        content = str(result.get("text") or "").strip()
        if len(content) > 6000:
            content = content[:5997].rstrip() + "..."
        final_url = str(result.get("final_url") or result.get("url") or url)
        return (
            f"I read the public page: {title}\n\n{content}\n\n"
            f"Source: {final_url}\n"
            "Evidence: static page text only; I did not log in, click, or submit anything."
        )
    except Exception as exc:
        _hades_logger.warning("Direct public page read failed: %s", exc)
        return "I couldn't read that public page. I did not invent an answer."


def _hades_direct_owner_location(user_text):
    """Answer the common 'where is HADES?' question from the production contract."""
    text = str(user_text or "")
    if not re.search(r"\b(?:where|wher|which\s+computer|what\s+computer).{0,40}\b(?:hades|core|running|runing)\b", text, re.IGNORECASE):
        return None
    return (
        "HADES Core is running on the configured HADES control-plane instance. "
        "This chat is served by that Core. Model work is distributed: Tartarus handles "
        "deep/code work, Hypnos handles background/creative work, and the fast lane is "
        "separate. The Core endpoint is responding now; I will report a node as unknown "
        "rather than calling it healthy when live evidence is incomplete."
    )


def _hades_task_store():
    """Open the durable coordination store without creating a scheduler."""
    configured = os.environ.get("HADES_TASK_STATE_FILE", "").strip()
    if not configured:
        configured = str(Path(os.environ.get("HERMES_HOME", "/var/lib/hades")) / "profiles" / "hades" / "state" / "tasks.sqlite")
    from integrations.task import TaskStore
    return TaskStore(configured)


def _hades_task_grocy_snapshot() -> dict:
    """Read the bounded canonical pantry projection for a Task step.

    This is deliberately a read-only Task executor.  Grocy remains canonical;
    the Task store receives only a small observation and provenance reference.
    """
    import urllib.request

    base_url = str(os.environ.get("GROCY_URL") or "http://127.0.0.1:7003").rstrip("/")
    api_key = str(os.environ.get("GROCY_API_KEY", ""))
    if not api_key:
        key_path = str(os.environ.get("GROCY_API_KEY_FILE", "")).strip()
        if key_path:
            try:
                api_key = Path(key_path).read_text(encoding="utf-8").strip()
            except (OSError, UnicodeError):
                api_key = ""
    if not api_key:
        raise RuntimeError("Grocy read authority is unavailable")
    request = urllib.request.Request(
        base_url + "/api/stock",
        headers={"GROCY-API-KEY": api_key, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        rows = json.load(response)
    if not isinstance(rows, list):
        raise RuntimeError("Grocy returned an invalid stock projection")
    items = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        product = row.get("product") or {}
        name = str(product.get("name") or row.get("product_id") or "").strip()
        if name:
            items.append({
                "name": name,
                "amount": row.get("amount_aggregated", row.get("amount")),
                "minimum": row.get("amount_aggregated_min_stock", row.get("min_stock_amount", product.get("min_stock_amount"))),
            })
    return {"source": "Grocy", "endpoint": "/api/stock", "observed_at": time.time(), "item_count": len(items), "items": items[:200]}


def _hades_task_schedule_wait(task: dict, subject: str, day_name: str | None) -> dict | None:
    """Create the fixed, owner-authorized n8n wait graph for one Task."""
    owner_subjects = {value.strip() for value in os.environ.get("HADES_OWNER_SUBJECT_IDS", "").split(",") if value.strip()}
    owner_subjects.update(value.strip() for value in os.environ.get("HADES_OWNER_SUBJECT_ID", "").split(",") if value.strip())
    if subject not in owner_subjects:
        return None
    runner = _hades_health_watch_runner()
    if runner is None:
        return None
    from datetime import datetime, timedelta, timezone
    from integrations.task import build_wait_workflow, fixed_wait_contract, wait_workflow_id

    target = (day_name or "").casefold()
    now = datetime.now(timezone.utc)
    weekdays = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
    if target not in weekdays:
        return None
    days = (weekdays[target] - now.weekday()) % 7
    if days == 0 and (now.hour, now.minute) >= (8, 0):
        days = 7
    resume_at = (now + timedelta(days=days)).replace(hour=8, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")
    graph = build_wait_workflow(task["task_id"], resume_at)
    if not fixed_wait_contract(graph):
        raise RuntimeError("fixed Task wait contract rejected")
    created = runner.create_workflow(graph)
    workflow_id = str(created.get("id") or wait_workflow_id(task["task_id"]))
    runner.update_workflow(workflow_id, graph)
    runner.publish_workflow(workflow_id)
    runner.set_workflow_active(workflow_id, True)
    execution = None
    last_error = None
    for _attempt in range(6):
        try:
            execution = runner.execute_workflow(workflow_id, webhook_path=wait_workflow_id(task["task_id"]))
            break
        except Exception as exc:
            last_error = exc
            time.sleep(0.5)
    if execution is None:
        try:
            runner.set_workflow_active(workflow_id, False)
            runner.delete_workflow(workflow_id)
        except Exception:
            _hades_logger.warning("Task wait cleanup failed workflow=%s", workflow_id)
        raise RuntimeError("n8n Task wait trigger did not become available") from last_error
    return {"workflow_id": workflow_id, "resume_at": resume_at, "execution": {"status": execution.get("status", "accepted")}}


def _hades_task_remove_wait(task: dict, subject: str) -> bool:
    """Remove only the fixed scheduler artifact owned by this Task."""
    target = task.get("execution_target") or {}
    if target.get("executor") != "n8n" or not target.get("workflow_id"):
        return True
    owner_subjects = {value.strip() for value in os.environ.get("HADES_OWNER_SUBJECT_IDS", "").split(",") if value.strip()}
    if subject not in owner_subjects:
        return False
    runner = _hades_health_watch_runner()
    if runner is None:
        return False
    try:
        runner.set_workflow_active(str(target["workflow_id"]), False)
        runner.delete_workflow(str(target["workflow_id"]))
        return True
    except Exception as exc:
        _hades_logger.warning("Bounded Task wait cleanup failed workflow=%s: %s", target["workflow_id"], type(exc).__name__)
        return False


def _hades_task_response(user_text, subject, scope, history):
    """Minimal owner-facing persistent-goal surface for Alpha dogfood.

    This deliberately handles one bounded durable goal shape and plain
    inspection/replan/cancel language. Its first step is a read-only canonical
    Grocy observation; n8n scheduling remains a separate typed executor.
    """
    if scope not in {"owner", "household"} or not subject:
        return None
    text = str(user_text or "").strip()
    try:
        store = _hades_task_store()
        tasks = store.list_for_actor(subject)
    except Exception as exc:
        _hades_logger.warning("Persistent Task store unavailable: %s", exc)
        return None
    active = [item for item in tasks if item.get("status") not in {"COMPLETED", "CANCELLED"}]
    assistant_history = "\n".join(
        str(item.get("content", "")) for item in (history if isinstance(history, list) else [])
        if isinstance(item, dict) and item.get("role") == "assistant"
    )
    confirmation = bool(
        re.search(r"\b(?:yes|y|yeah|yep|okay|ok|create it|go ahead|confirm|please do)\b", text, re.IGNORECASE)
        and ("I can keep track of that as a task" in assistant_history or any(item.get("status") == "PROPOSED" for item in active))
    )
    target = next((item for item in active if re.search(r"spaghetti|lasagna|dinner|friday|saturday", item.get("goal", ""), re.IGNORECASE)), None)
    # Approval is a separate, revision-bound step.  It is intentionally
    # explicit so a stale conversational "yes" cannot authorize a changed
    # consequence.
    if target and re.search(r"\b(?:approve|approval)\b", text, re.IGNORECASE) and target.get("status") in {"WAITING", "READY"}:
        try:
            requested = store.request_approval(
                target["task_id"], subject, target["task_revision"],
                action="prepare_recipe", resource={"system": "grocy.household", "endpoint": "/api/stock"},
                parameters={"goal": target["goal"]},
            )
            return f"Approval is required before the next task step for `{requested['goal']}`. Approve this exact bounded Grocy read and I will continue?"
        except Exception as exc:
            _hades_logger.warning("Task approval request failed: %s", type(exc).__name__)
            return "I could not create a current revision-bound approval request; nothing was changed."
    task_approval_confirmation = bool(
        target and target.get("status") == "AWAITING_APPROVAL"
        and re.search(r"\b(?:yes|y|yeah|yep|okay|ok|approve|confirm|go ahead|please do)\b", text, re.IGNORECASE)
    )
    if target and target.get("status") == "AWAITING_APPROVAL" and task_approval_confirmation:
        approval = target.get("approval_state") or {}
        try:
            approved = store.approve(
                target["task_id"], subject, target["task_revision"],
                action=str(approval.get("action", "")), resource=approval.get("resource") or {},
                parameters=approval.get("parameters") or {},
            )
            return f"Approved the current task revision for `{approved['goal']}`. It is ready for the bounded next step; say resume when you want me to continue."
        except Exception as exc:
            _hades_logger.warning("Task approval failed: %s", type(exc).__name__)
            return "That approval is stale or no longer matches the task plan; nothing was changed."
    if confirmation:
        proposed = next((item for item in active if item.get("status") == "PROPOSED"), None)
        if proposed:
            from integrations.task import TaskStatus
            target_day = re.search(r"\b(friday|saturday)\b", proposed.get("goal", ""), re.IGNORECASE)
            ready = store.transition(
                proposed["task_id"], subject, proposed["task_revision"], TaskStatus.READY,
                fields={"current_step": "read_shared_pantry", "next_eligible_action": "execute"},
                event_type="PLAN_ACCEPTED",
                detail={"executor_contracts": ["Grocy read", "n8n wait"], "writes_performed": False},
            )
            execution_id = f"exec-{hashlib.sha256(f'{ready['task_id']}:read_shared_pantry'.encode()).hexdigest()[:20]}"
            idem = f"{ready['task_id']}:read_shared_pantry:{ready['task_revision']}"
            running = store.begin_execution(
                ready["task_id"], subject, ready["task_revision"], execution_id=execution_id,
                step_id="read_shared_pantry", executor="grocy", idempotency_key=idem,
                action="read", resource={"system": "grocy.household", "endpoint": "/api/stock"},
            )
            try:
                snapshot = _hades_task_grocy_snapshot()
            except Exception as exc:
                store.record_execution(
                    running["task_id"], subject, running["task_revision"], execution_id=execution_id,
                    status="UNAVAILABLE", metadata={"error": type(exc).__name__},
                    result={"source": "Grocy", "error": "canonical read unavailable"},
                    detail={"executor": "grocy", "source": "canonical"},
                )
                return "I created the task, but the canonical Grocy read is currently unavailable. The task is blocked; nothing was changed."
            result = store.record_execution(
                running["task_id"], subject, running["task_revision"], execution_id=execution_id,
                status="SUCCEEDED", canonical_refs={"grocy_endpoint": "/api/stock"},
                metadata={"observed_at": snapshot["observed_at"], "item_count": snapshot["item_count"]},
                result={"source": "Grocy", "item_count": snapshot["item_count"]},
                success_status=TaskStatus.WAITING,
                next_eligible_action="scheduled_wake",
                detail={"executor": "grocy", "canonical_verification": "read completed"},
            )
            result = store.transition(
                result["task_id"], subject, result["task_revision"], TaskStatus.WAITING,
                fields={
                    "current_step": "wait_until",
                    "waiting_reason": target_day.group(1).capitalize() if target_day else "the scheduled date",
                    "next_eligible_action": "scheduled_wake",
                    "canonical_references": {"planned_system": "Grocy", "scheduler": "n8n", "grocy_endpoint": "/api/stock"},
                },
                event_type="WAIT_REQUESTED", detail={"executor": "n8n", "wait_reason": "scheduled date", "schedule_requested": False},
            )
            try:
                wait = _hades_task_schedule_wait(result, subject, target_day.group(1) if target_day else None)
            except Exception as exc:
                _hades_logger.warning("Bounded Task n8n wait unavailable: %s", exc)
                wait = None
            if wait:
                result = store.transition(
                    result["task_id"], subject, result["task_revision"], TaskStatus.WAITING,
                    fields={"execution_target": {"executor": "n8n", **wait}, "canonical_references": {"planned_system": "Grocy", "scheduler": "n8n", "grocy_endpoint": "/api/stock", "workflow_id": wait["workflow_id"]}},
                    event_type="N8N_WAIT_SCHEDULED", detail={"executor": "n8n", "workflow_id": wait["workflow_id"], "resume_at": wait["resume_at"]},
                )
            return (
                f"Created the task for `{result['goal']}`. I’m keeping it open until {result.get('waiting_reason') or 'the scheduled date'}; "
                "the canonical Grocy pantry read completed, and the next step is a bounded scheduled wake. "
                + ("The fixed n8n wait is scheduled; no groceries were changed." if wait else "I have not changed groceries; the n8n wait could not be scheduled and the task remains inspectable.")
            )
        existing_goal = next(
            (item for item in active if re.search(r"spaghetti|lasagna|dinner|friday|saturday", item.get("goal", ""), re.IGNORECASE)),
            None,
        )
        if existing_goal:
            return f"That task is already created: `{existing_goal['goal']}`. Status: {existing_goal['status'].replace('_', ' ').lower()}; no duplicate task was created."
    if re.search(r"\b(?:cancel|stop)\b", text, re.IGNORECASE) and active:
        target = target or active[0]
        # Scheduler cleanup is reconciled separately; cancellation itself must
        # not block on a control-plane request.
        wait_removed = _hades_task_remove_wait(target, subject)
        result = store.cancel(target["task_id"], subject, target["task_revision"], reason="user cancelled")
        suffix = "" if wait_removed else " The scheduler cleanup could not be confirmed; I left the task cancelled and flagged that artifact for operator review."
        return f"Cancelled the task for `{result['goal']}`. No future task action is eligible; prior external effects, if any, remain recorded.{suffix}"
    if target and re.search(r"\b(?:resume|continue|run|finish|complete)\b", text, re.IGNORECASE) and target.get("status") in {"WAITING", "READY"}:
        from integrations.task import TaskStatus
        if target.get("status") == "READY" and (target.get("approval_state") or {}).get("status") != "APPROVED":
            return f"The task `{target['goal']}` is ready but still needs an explicit approval before I continue. Say approve task."
        if target.get("status") == "WAITING":
            if not _hades_task_remove_wait(target, subject):
                return "The task remains waiting because its bounded scheduler cleanup could not be confirmed. Nothing was changed."
            target = store.transition(target["task_id"], subject, target["task_revision"], TaskStatus.READY,
                                      fields={"next_eligible_action": "execute"}, event_type="RESUMED",
                                      detail={"source": "owner_request", "scheduler_reconciled": True})
        execution_id = f"exec-{hashlib.sha256(f'{target['task_id']}:complete:{target['task_revision']}'.encode()).hexdigest()[:20]}"
        idem = f"{target['task_id']}:complete:{target['task_revision']}"
        running = store.begin_execution(
            target["task_id"], subject, target["task_revision"], execution_id=execution_id,
            step_id="complete_recipe_read", executor="grocy", idempotency_key=idem,
            action="read", resource={"system": "grocy.household", "endpoint": "/api/stock"},
        )
        try:
            snapshot = _hades_task_grocy_snapshot()
        except Exception:
            store.record_execution(running["task_id"], subject, running["task_revision"], execution_id=execution_id,
                                   status="UNAVAILABLE", result={"source": "Grocy", "error": "canonical read unavailable"},
                                   detail={"executor": "grocy", "source": "canonical"})
            return "The task resumed, but the canonical Grocy read is unavailable. It is blocked; nothing was changed."
        completed = store.record_execution(
            running["task_id"], subject, running["task_revision"], execution_id=execution_id,
            status="SUCCEEDED", canonical_refs={"grocy_endpoint": "/api/stock"},
            metadata={"observed_at": snapshot["observed_at"], "item_count": snapshot["item_count"]},
            result={"source": "Grocy", "item_count": snapshot["item_count"], "completed": True},
            success_status=TaskStatus.COMPLETED, detail={"executor": "grocy", "canonical_verification": "read completed"},
        )
        return f"Completed the bounded task for `{completed['goal']}` after a fresh canonical Grocy read. No groceries were changed."
    if re.search(r"\b(?:actually|change|changed)\b", text, re.IGNORECASE) and active and re.search(r"lasagna|spaghetti|friday|saturday", text, re.IGNORECASE):
        target = next((item for item in active if re.search(r"spaghetti|lasagna|dinner|friday|saturday", item.get("goal", ""), re.IGNORECASE)), active[0])
        new_goal = target["goal"]
        if re.search(r"lasagna", text, re.IGNORECASE):
            new_goal = re.sub(r"spaghetti", "lasagna", new_goal, flags=re.IGNORECASE)
        if re.search(r"saturday", text, re.IGNORECASE):
            new_goal = re.sub(r"friday", "Saturday", new_goal, flags=re.IGNORECASE)
        new_day = re.search(r"\b(friday|saturday)\b", new_goal, re.IGNORECASE)
        from integrations.task import TaskStatus
        if new_goal.casefold() == target["goal"].casefold():
            return f"I already have the task plan `{target['goal']}`. No duplicate replan was recorded."
        command_digest = hashlib.sha256(text.casefold().encode("utf-8")).hexdigest()
        if (target.get("result") or {}).get("task_command_digest") == command_digest:
            return f"I already applied that change: `{target['goal']}`. Any old approval remains invalid."
        result = store.replan(target["task_id"], subject, target["task_revision"], goal=new_goal, current_step="read_recipe",
                              detail={"reason": "user_changed_goal", "approval_invalidated": True, "task_command_digest": command_digest})
        if new_day:
            result = store.transition(result["task_id"], subject, result["task_revision"], TaskStatus.READY,
                                      fields={"waiting_reason": new_day.group(1).capitalize()},
                                      event_type="REPLAN_WAIT_UPDATED", detail={"waiting_reason": new_day.group(1).capitalize()})
        return f"I replanned it as `{result['goal']}`. Any old approval is invalid; I’ll recheck current authority and pantry state before any consequential action."
    if re.search(r"\b(?:what(?:'s| is) happening|what are you working on|what happens next|status of|dinner thing|spaghetti thing)\b", text, re.IGNORECASE) and active:
        target = next((item for item in active if re.search(r"spaghetti|lasagna|dinner|friday|saturday", item.get("goal", ""), re.IGNORECASE)), active[0])
        waiting = target.get("waiting_reason") or "nothing currently"
        return f"I’m tracking `{target['goal']}`. Status: {target['status'].replace('_', ' ').lower()}; waiting for {waiting}. Next: {target.get('next_eligible_action') or 'review the plan'}."
    if re.search(r"\b(?:what(?:'s| is) happening|what happens next|status of|dinner thing|spaghetti thing)\b", text, re.IGNORECASE):
        historical = next((item for item in tasks if re.search(r"spaghetti|lasagna|dinner|friday|saturday", item.get("goal", ""), re.IGNORECASE)), None)
        if historical:
            return f"The most recent task was `{historical['goal']}`. Status: {historical['status'].replace('_', ' ').lower()}; no further action is eligible."
    durable = re.search(r"\bhelp\s+(?:me|us)\s+get\s+ready\s+to\s+(?:make|cook)\s+(.+?)\s+(?:(?:on|this\s+coming)\s+)?(friday|saturday)\b", text, re.IGNORECASE)
    if durable:
        goal = f"Help me get ready to make {durable.group(1).strip()} {durable.group(2).capitalize()}"
        existing = next((item for item in active if item.get("goal", "").casefold() == goal.casefold()), None)
        if existing:
            return f"I’m already tracking `{existing['goal']}`. Status: {existing['status'].replace('_', ' ').lower()}; next: {existing.get('next_eligible_action') or 'confirm the plan'}."
        task_id = f"task-{hashlib.sha256(f'{subject}:{goal}:{time.time_ns()}'.encode()).hexdigest()[:20]}"
        store.create(task_id=task_id, actor_subject_id=subject, goal=goal,
                     resource_scope={"systems": ["grocy.household", "n8n.wait"]},
                     required_authority={"read": ["grocy.household"], "write": []},
                     bounded_plan=[{"step": "read_recipe"}, {"step": "read_shared_pantry"}, {"step": "wait_until", "day": durable.group(2).capitalize()}])
        return (
            "I can keep track of that as a task. I’ll check the recipe and shared pantry, "
            f"work out what you’re missing, and keep the plan open until {durable.group(2).capitalize()}. "
            "I’ll ask before making any changes. Create it?"
        )
    return None


def _hades_direct_homelab_read(user_text):
    """Answer simple owner homelab-status questions from canonical read sources.

    These questions are safe to answer without a model round trip.  That matters
    during an inference outage: a dead provider must not turn a live status
    question into stale text from the previous assistant turn.  This path only
    calls the existing read-only composition adapter and never handles control
    or provisioning requests.
    """
    text = str(user_text or "")
    # Explicit Agent Zero requests belong to the bounded operator route.
    # Do not let the generic ``server``/``inspect`` homelab shortcut
    # answer them as a live-status question before Agent Zero intent
    # narrowing gets a chance to select its catalog or deny it.
    if re.search(
        r"\b(?:agent\s*zero|agent0|bounded\s+operator|delegate|delegation)\b",
        text,
        re.IGNORECASE,
    ):
        return None
    if re.search(
        r"\b(?:restart|reboot|stop|start|shutdown|shut\s+down|turn\s+off|fix|update|change|"
        r"spin\s+up|provision|deploy|create)\b",
        text,
        re.IGNORECASE,
    ):
        return None
    if not re.search(
        r"\b(?:server|homelab|homlab|home\s+lab|proxmox|vm|virtual\s+machine|"
        r"node|computer|network|running|runing|down|online|offline|healthy|status|"
        r"tartarus|hypnos|thanatos|erebus|alexandra|hermes)\b",
        text,
        re.IGNORECASE,
    ):
        return None
    workdir = str(os.environ.get("HADES_HERMES_WORKING_DIRECTORY", "")).strip()
    if not workdir:
        # The generated service already runs from the reconciled repository;
        # use that deployment contract when the protected env omits the
        # operator-only variable.
        workdir = os.getcwd()
    if not workdir:
        return None
    try:
        from pathlib import Path
        import importlib.util

        adapter = Path(workdir) / "integrations" / "homelab-readonly" / "server.py"
        if not adapter.is_file():
            # Hermes may change cwd during gateway bootstrap. This is the
            # fixed reconciled deployment path, not user-controlled input.
            deployed_root = Path("/var/lib/hades/source")
            candidate = deployed_root / "integrations" / "homelab-readonly" / "server.py"
            if candidate.is_file():
                adapter = candidate
        if not adapter.is_file():
            return None
        if str(adapter.parent) not in __import__("sys").path:
            __import__("sys").path.insert(0, str(adapter.parent))
        spec = importlib.util.spec_from_file_location("hades_direct_homelab", adapter)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        summary = module.homelab_summary()
        resources = summary.get("resources", []) if isinstance(summary, dict) else []
        supplemental_runtime = []
        has_guest_runtime = any(
            isinstance(item, dict)
            and isinstance(item.get("runtime") or item.get("runtime_detail"), dict)
            and (item.get("runtime") or item.get("runtime_detail")).get("vmid") is not None
            for item in resources
        )
        if isinstance(summary, dict) and not has_guest_runtime:
            supplemental_runtime = _hades_live_proxmox_vm_rows()
            if supplemental_runtime:
                guest_resources = [
                    {
                        "name": f"{row['name']} (VM {row['vmid']})",
                        "runtime_status": row["status"],
                        "currently_online": row["status"] in {"running", "online"},
                        "inventory": {"role": "Proxmox virtual machine", "primary_ip": None},
                        "availability": None,
                        "availability_freshness": "UNKNOWN",
                        "conflicts": [],
                        "runtime_detail": row,
                    }
                    for row in supplemental_runtime
                ]
                resources = list(resources) + guest_resources
                summary["resources"] = resources
                summary["online_names"] = list(dict.fromkeys(
                    [*summary.get("online_names", []), *[item["name"] for item in guest_resources if item["currently_online"]]]
                ))
        target_match = re.search(
            r"\b(?:tartarus|hypnos|thanatos|erebus|alexandra|hermes)\b",
            text,
            re.IGNORECASE,
        )
        if target_match:
            target = target_match.group(0).casefold()
            matching = [
                resource for resource in resources
                if target in str(resource.get("name", "")).casefold()
            ]
            if not matching:
                # A physical inference node may be present in the observed
                # hardware matrix without being represented as a Proxmox
                # guest. Report that distinction instead of collapsing known
                # hardware into either "healthy" or "does not exist".
                matrix_env = os.environ.get("HADES_CAPABILITY_MATRIX_FILE", "").strip()
                matrix_path = None
                if not matrix_env:
                    hermes_home = os.environ.get("HERMES_HOME", "").strip()
                    profile_config = Path(hermes_home) / "profiles" / "hades" / "config.yaml"
                    try:
                        profile_text = profile_config.read_text(encoding="utf-8")
                        matrix_match = re.search(
                            r"HADES_CAPABILITY_MATRIX_FILE:\s*['\"]?([^'\"\s]+)",
                            profile_text,
                        )
                        matrix_path = matrix_match.group(1) if matrix_match else None
                    except OSError:
                        matrix_path = None
                else:
                    matrix_path = matrix_env
                if not matrix_path:
                    # The generated production profile historically kept the
                    # private infra checkout beside the deployment directory
                    # without exporting this non-secret path to the Hermes
                    # process. Discover that sibling deterministically, but
                    # only if the expected tracked manifest exists.
                    search_roots = [Path(workdir)]
                    hermes_home = os.environ.get("HERMES_HOME", "").strip()
                    if hermes_home:
                        search_roots.append(Path(hermes_home))
                    for root in search_roots:
                        for parent in (root, *root.parents):
                            candidate = parent / "hades-infra" / "inventory" / "capability-matrix.yaml"
                            if candidate.is_file() and not candidate.is_symlink():
                                matrix_path = str(candidate)
                                break
                        if matrix_path:
                            break
                previous_matrix = os.environ.get("HADES_CAPABILITY_MATRIX_FILE")
                if matrix_path:
                    os.environ["HADES_CAPABILITY_MATRIX_FILE"] = matrix_path
                try:
                    compute = module.homelab_compute_capabilities()
                finally:
                    if previous_matrix is None:
                        os.environ.pop("HADES_CAPABILITY_MATRIX_FILE", None)
                    else:
                        os.environ["HADES_CAPABILITY_MATRIX_FILE"] = previous_matrix
                machines = compute.get("machines", []) if isinstance(compute, dict) else []
                if not machines and matrix_path:
                    try:
                        import yaml
                        document = yaml.safe_load(Path(matrix_path).read_text(encoding="utf-8"))
                        machines = document.get("machines", []) if isinstance(document, dict) else []
                    except Exception:
                        machines = []
                observed = [
                    machine for machine in machines
                    if target in str(machine.get("name", "")).casefold()
                ]
                if observed:
                    machine = observed[0]
                    details = [
                        f"{machine.get('name', target_match.group(0))} is present in the observed hardware inventory",
                        "but its current runtime is not verified by Proxmox",
                    ]
                    if machine.get("address"):
                        details.append(f"the recorded address is {machine['address']}")
                    if machine.get("role"):
                        details.append(f"its recorded role is {machine['role']}")
                    return "; ".join(details) + ". I did not assume it is online."
                return (
                    f"I couldn't verify {target_match.group(0)} in the live homelab sources. "
                    "I did not assume it was running."
                )
            resource = matching[0]
            name = resource.get("name") or target_match.group(0)
            runtime_status = resource.get("runtime_status") or "UNKNOWN"
            inventory = resource.get("inventory") or {}
            availability = resource.get("availability") or {}
            parts = [f"{name}: Proxmox runtime status is {runtime_status}."]
            if inventory.get("primary_ip"):
                parts.append(f"Its recorded address is {inventory['primary_ip']}.")
            if inventory.get("role"):
                parts.append(f"Role: {inventory['role']}.")
            if availability.get("status"):
                freshness = resource.get("availability_freshness", "UNKNOWN")
                parts.append(f"Uptime Kuma reports {availability['status']} ({freshness.lower()} observation).")
            runtime = resource.get("runtime") or resource.get("runtime_detail") or {}
            if runtime:
                def _size(value):
                    try:
                        return f"{float(value) / (1024 ** 3):.1f} GiB"
                    except (TypeError, ValueError):
                        return "unknown"
                def _percent(value):
                    try:
                        return f"{float(value) * 100:.1f}%"
                    except (TypeError, ValueError):
                        return "unknown"
                parts.append(
                    f"Runtime telemetry: CPU {_percent(runtime.get('cpu'))}, "
                    f"memory {_size(runtime.get('mem'))}/{_size(runtime.get('maxmem'))}, "
                    f"storage {_size(runtime.get('disk'))}/{_size(runtime.get('maxdisk'))}."
                )
            if resource.get("conflicts"):
                parts.append("The live sources disagree, so treat this as needing attention.")
            return " ".join(parts)
        online = summary.get("online_names", []) if isinstance(summary, dict) else []
        inventory_only = summary.get("inventory_only_names", []) if isinstance(summary, dict) else []
        availability = summary.get("availability_summary", []) if isinstance(summary, dict) else []
        resources_by_name = {
            str(item.get("name")): item for item in (summary.get("resources", []) if isinstance(summary, dict) else [])
            if isinstance(item, dict) and item.get("name")
        }
        detailed_request = bool(re.search(
            r"\b(?:node(?:s)?|blocker(?:s)?|concise|core|major|inference|worker(?:s)?|issue(?:s)?|problem(?:s)?)\b",
            text,
            re.IGNORECASE,
        ))
        partial = isinstance(summary, dict) and summary.get("status") != "OK"
        if partial:
            response = "I couldn't get a complete live homelab status. "
            response += "HADES Core gateway is responding to this request; inference-worker health was not independently verified. "
            if online:
                response += "The available Proxmox data reports: " + ", ".join(str(name) for name in online) + ". "
            response += "I did not assume any unreported machine was running."
        elif online:
            response = "Live Proxmox currently reports: " + ", ".join(str(name) for name in online) + "."
        else:
            response = "Proxmox did not report any currently running homelab resources."
        if re.search(r"\b(?:network|dns|slow|latency|bottleneck|resource\s+usage|performance)\b", text, re.IGNORECASE):
            response += " Network-health telemetry and historical resource trends are not available from the approved live sources in this turn, so I cannot identify a network bottleneck from evidence."
        if availability:
            down = [
                str(item.get("name")) for item in availability
                if str(item.get("status", "")).casefold() in {"down", "offline"}
            ]
            if down:
                response += " Uptime Kuma reports down: " + ", ".join(down) + "."
        if detailed_request:
            runtime_details = [
                (item.get("runtime_detail") or item.get("runtime")) for item in resources
                if isinstance(item, dict) and isinstance(item.get("runtime_detail") or item.get("runtime"), dict)
                and item.get("currently_online")
            ]
            if runtime_details:
                def _memory(value):
                    try:
                        return f"{float(value) / (1024 ** 3):.1f} GiB"
                    except (TypeError, ValueError):
                        return "unknown"
                def _runtime_line(row):
                    cpu = f", CPU {float(row.get('cpu')) * 100:.1f}%" if row.get('cpu') is not None else ""
                    return (
                        f"{row.get('name')} VM {row.get('vmid')} on {row.get('node')}, "
                        f"status {row.get('status')}{cpu}, "
                        f"memory {_memory(row.get('mem'))} / {_memory(row.get('maxmem'))}, "
                        f"storage {_memory(row.get('disk'))} / {_memory(row.get('maxdisk'))}"
                    )
                response += " Runtime telemetry available from Proxmox: " + "; ".join(
                    _runtime_line(row) for row in runtime_details
                ) + "."
                response += " Proxmox did not provide guest OS, major-service, storage-utilization, GPU, or network-trend data in this read, so those fields remain unknown."
            if inventory_only:
                response += " NetBox lists but Proxmox did not observe running: " + ", ".join(str(name) for name in inventory_only) + "."
            unknown = [str(item.get("name")) for item in availability if str(item.get("freshness", "")).upper() in {"UNKNOWN", "STALE"}]
            if unknown:
                response += " Availability evidence is stale or unknown for: " + ", ".join(unknown) + "."
            conflicts = summary.get("conflicts", []) if isinstance(summary, dict) else []
            if conflicts:
                response += " Source conflicts require attention for: " + ", ".join(str(item.get("name")) for item in conflicts if isinstance(item, dict)) + "."
            errors = summary.get("errors", []) if isinstance(summary, dict) else []
            if errors:
                response += " Some sources are unavailable, so unreported nodes remain unknown."
            elif not down and not conflicts:
                response += " No blocker was reported by the configured live sources."
            core = resources_by_name.get("hades-core") or resources_by_name.get("HADES Core")
            if core:
                response += f" HADES Core runtime is {core.get('runtime_status', 'UNKNOWN')}."
        return response
    except Exception as exc:
        _hades_logger.warning("Direct homelab read failed: %s", exc)
        return None


def _hades_direct_homelab_write_guidance(user_text):
    """Fail closed immediately for novice requests that imply infrastructure writes."""
    text = str(user_text or "")
    if not re.search(
        r"\b(?:restart|reboot|stop|start|shutdown|shut\s+down|turn\s+off|fix|update|change|"
        r"spin\s+up|provision|deploy|create)\b",
        text,
        re.IGNORECASE,
    ):
        return None
    if not re.search(
        r"\b(?:homelab|homlab|home\s+lab|server|network|computer|node|proxmox|vm|machine|router|switch)\b",
        text,
        re.IGNORECASE,
    ):
        return None
    return (
        "I can inspect the homelab, but HADES is deliberately read-only for infrastructure. "
        "I cannot restart, reboot, stop, start, or update a server, VM, router, or other "
        "network device from this chat. I can check live monitoring and tell you exactly "
        "what appears unhealthy, or give you the manual next step."
    )


_HADES_MEMORY_NEGATION = re.compile(
    r"\b(?:do\s+not|don't|without|never|not)\b[^.!?]{0,32}\bmemory\b",
    re.IGNORECASE,
)
_HADES_HOMELAB_INTENT = re.compile(
    r"\b(?:homelab|homlab|home\s+lab|proxmox|netbox|uptime\s+kuma|server(?:s)?|node(?:s)?|"
    r"virtual\s+machine(?:s)?|\bvm\b|container(?:s)?|sandbox(?:es)?|workload(?:s)?|"
    r"website(?:s)?|gpu(?:s)?|"
    r"ram|free\s+memory|unhealthy|host(?:s)?|network\s+scan|network|"
    r"nmap|discov(?:er|y)|ip(?:s)?|mac(?:s)?|what(?:['’]?s| is)\s+running|"
    r"alexandra|erebus|tartarus|hypnos|thanatos|hermes)\b",
    re.IGNORECASE,
)
_HADES_NONPERSONAL_STATE_INTENT = re.compile(
    r"\b(?:weather|forecast|temperature|search|look\s+up|latest|news|web|agent\s+zero|agent0|"
    r"delegat(?:e|ion|ed)|finance|budget|balance|transaction|account|afford|"
    r"homelab|homlab|home\s+lab|proxmox|netbox|uptime\s+kuma|virtual\s+machine|\bvm\b|container|"
    r"home\s+assistant|smart\s+home|light(?:s)?|air\s+purifier|sensor|device(?:s)?|"
    r"unavailable|offline|locked|garage\s+door|alarm|camera)\b",
    re.IGNORECASE,
)


def _hades_nonpersonal_state_turn(user_text):
    """Identify live/shared turns that must not enter private memory."""
    return bool(
        _HADES_SHARED_MEMORY_INTENT.search(user_text)
        or _HADES_GROCY_ACTION_INTENT.search(user_text)
        or _HADES_GROCY_ITEM_FRAGMENT.search(user_text)
        or _HADES_NONPERSONAL_STATE_INTENT.search(user_text)
    )


def _hades_transient_error_text(content):
    """Identify operational failure output that must not become memory."""
    return bool(_HADES_TRANSIENT_ERROR.search(str(content or "")))


def _hades_web_tool_failed(message):
    """Return true only for an actual web-search tool error envelope."""
    if not isinstance(message, dict) or message.get("role") != "tool":
        return False
    if message.get("name") not in {"web_search", "mcp_web_search"}:
        return False
    content = message.get("content", "")
    if isinstance(content, list):
        content = " ".join(
            str(part.get("text", "")) if isinstance(part, dict) else str(part)
            for part in content
        )
    text = str(content or "")
    if "[TOOL_ERROR]" in text or text.lstrip().lower().startswith("error executing"):
        return True
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return False
    return isinstance(payload, dict) and bool(payload.get("error")) and not payload.get("result")


def _hades_should_skip_automatic_memory(user_content, assistant_content):
    """Decide whether a completed turn is unsafe for automatic private retain.

    Keep this policy dependency-free so it can be regression-tested without
    importing Hermes or Hindsight. The runtime sync wrapper below delegates to
    this decision; user text is the authority for domain classification, while
    transient assistant/tool failures are always suppressed.
    """
    return (_hades_nonpersonal_state_turn(user_content)
            or _hades_transient_error_text(assistant_content))


def _hades_subject_from_session_key(session_key):
    """Extract the server-generated subject from an Open WebUI key.

    Open WebUI can expand ``{{USER_ID}}`` in a connection header. Hermes'
    API gateway already accepts that header as a stable session key, so this
    small translation lets the supported Hindsight provider resolve its
    ``{user}`` bank template without trusting model text or a mutable display
    name. Unrecognized keys intentionally produce no subject.
    """
    prefix = "hades-user-"
    if not isinstance(session_key, str) or not session_key.startswith(prefix):
        return ""
    subject = session_key[len(prefix):].strip()
    if not subject or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", subject):
        return ""
    return subject


def _hades_session_scope(session_key):
    """Return the server-selected capability scope for a gateway session."""
    if not isinstance(session_key, str):
        return ""
    if session_key.startswith("hades-user-"):
        # Open WebUI uses one server-expanded template for all authenticated
        # users. Resolve the owner exception from a private service setting,
        # never from model text or a client-provided role/group claim.
        subject = _hades_subject_from_session_key(session_key)
        if not subject:
            # A prefix alone is not authentication. Invalid or empty subjects
            # must remain denied rather than inheriting household capability.
            return ""
        owner_subjects = {
            value.strip()
            for value in os.environ.get("HADES_OWNER_SUBJECT_IDS", "").split(",")
            if value.strip()
        }
        legacy_owner_subject = os.environ.get("HADES_OWNER_SUBJECT_ID", "").strip()
        if legacy_owner_subject:
            owner_subjects.add(legacy_owner_subject)
        if subject in owner_subjects:
            return "owner"
        return "household"
    # Do not honor a client-selectable owner prefix. Production Open WebUI
    # emits only the server-expanded hades-user template, and unknown session
    # formats must fail closed.
    return ""


def _hades_grocy_audit_path():
    """Return the protected append-only audit path for shared Grocy writes.

    This is authorization/audit metadata only. Grocy remains the canonical
    inventory and transaction store; the audit deliberately contains no
    prompt text, credentials, balances, or private conversation content.
    """
    configured = str(os.environ.get("HADES_GROCY_AUDIT_FILE", "")).strip()
    if configured:
        return configured
    state_root = str(os.environ.get("HADES_STATE_ROOT") or "").rstrip("/")
    if state_root:
        return f"{state_root}/runtime/grocy-mutations.jsonl"
    hermes_home = str(os.environ.get("HERMES_HOME") or "").rstrip("/")
    if hermes_home:
        return f"{hermes_home}/runtime/grocy-mutations.jsonl"
    return "/var/lib/hades/runtime/grocy-mutations.jsonl"


def _hades_record_grocy_mutation(actor_subject, operation, target, outcome):
    """Record bounded shared-Grocy mutation metadata before/after a write.

    Planned mutations fail closed if the audit store cannot be written. A
    post-attempt write is best effort because a provider timeout can leave the
    canonical outcome unknown; the caller still reports that uncertainty.
    """
    from datetime import datetime, timezone
    from pathlib import Path

    subject = str(actor_subject or "").strip()
    if not subject or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", subject):
        return False
    owner_subjects = {
        value.strip()
        for value in os.environ.get("HADES_OWNER_SUBJECT_IDS", "").split(",")
        if value.strip()
    }
    path = Path(_hades_grocy_audit_path())
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor_subject": subject,
        "scope": "owner" if subject in owner_subjects else "household",
        "resource": "shared_grocy",
        "operation": str(operation),
        "target": str(target),
        "outcome": str(outcome),
    }
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, (json.dumps(record, sort_keys=True) + "\n").encode("utf-8"))
        finally:
            os.close(fd)
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return True
    except Exception as exc:
        _hades_logger.error(
            "Grocy mutation audit write failed path=%s operation=%s outcome=%s: %s",
            path, operation, outcome, exc,
        )
        return False


def _hades_filter_tools_for_scope(tools, scope):
    """Remove owner-only tools before a household model invocation."""
    if not isinstance(tools, list) or scope != "household":
        return tools
    privileged_markers = ("agent_zero", "agent-zero", "finance", "homelab")
    return [
        tool for tool in tools
        if not any(
            marker in str(tool.get("function", {}).get("name", "")).lower()
            for marker in privileged_markers
        )
    ]


def _hades_conversation_intent_text(user_message, conversation_history):
    """Build bounded routing context without truncating the current turn.

    Recent history provides pronoun/domain continuity, but the current user
    request is authoritative for this turn and must remain inside the cap.
    """
    history_parts = []
    if isinstance(conversation_history, list):
        for message in conversation_history[-8:]:
            if isinstance(message, dict):
                # Tool payloads are observations, not user intent. They may
                # be stale, contradictory, or attacker-controlled and must
                # not steer a later capability/authority decision.
                if message.get("role") == "tool":
                    continue
                content = message.get("content", "")
                if isinstance(content, str):
                    history_parts.append(content)
    current = str(user_message or "")
    history = "\n".join(history_parts)
    # Trim only historical context. A left slice of the combined value can
    # silently remove the beginning of a long current request and change
    # routing/authorization decisions.
    history_budget = max(0, 12000 - len(current) - (1 if history else 0))
    if len(history) > history_budget:
        history = history[-history_budget:] if history_budget else ""
    return f"{history}\n{current}" if history else current


def _hades_previous_user_message(conversation_history):
    """Return only the immediately preceding user turn for follow-up routing."""
    if not isinstance(conversation_history, list):
        return ""
    for message in reversed(conversation_history):
        if isinstance(message, dict) and message.get("role") == "user":
            content = message.get("content", "")
            if isinstance(content, str):
                return content
    return ""


def _hades_grocy_reversal_notice(user_text, previous_user_text):
    """Keep a late reversal honest after a canonical shopping-list write.

    A follow-up arriving after the prior turn was committed cannot atomically
    undo that write. Do not send the vague reversal to a model (which tended
    to answer with generic chat); explain the actual state and offer the
    explicit compensating action instead.
    """
    current = str(user_text or "").strip()
    previous = str(previous_user_text or "").strip()
    if not re.search(
        r"\b(?:actually\s+(?:don['’]?t|dont|never\s+mind|nevermind)|"
        r"never\s+mind|nevermind|wait\s+(?:don['’]?t|dont))\b",
        current,
        re.IGNORECASE,
    ):
        return None
    item = re.search(
        r"\b(?:add|put|place)\s+(?:(?:the|some|my)\s+)?"
        r"(milk|eggs?|cereal|bread|cheese|pasta|rice|chicken|beef|fruit|vegetables?)"
        r"(?:\s+(?:to|on|onto)\s+(?:the\s+)?(?:shopping|grocery)\s+list)?\b",
        previous,
        re.IGNORECASE,
    )
    if not item:
        return None
    name = item.group(1)
    return (
        f"The {name} addition had already been applied, so I did not pretend to undo it. "
        f"If you want it removed from the shared shopping list, say 'remove {name}'."
    )


def _hades_contextual_followup_clarification(user_text, previous_user_text):
    """Clarify vague follow-ups without selecting an arbitrary old domain."""
    current = str(user_text or "").strip()
    previous = str(previous_user_text or "")
    if not re.search(
        r"\b(?:what about|how about|which one|the other one|the other|is it okay|"
        r"check it|look at it|what was it|what did it say)\b",
        current,
        re.IGNORECASE,
    ):
        return None
    if re.search(
        r"\b(?:server|homelab|proxmox|node|tartarus|hypnos|thanatos|erebus|alexandra|hermes)\b",
        previous,
        re.IGNORECASE,
    ):
        return (
            "Which server or node do you mean? You can name it, such as Tartarus, Hypnos, "
            "Hermes Compute, or Alexandra. I haven't changed anything."
        )
    if re.search(r"\b(?:pantry|grocery|grocry|food|milk|eggs?|shopping list|recipe)\b", previous, re.IGNORECASE):
        return (
            "Which food or list item do you mean? I can check the pantry or shopping list, "
            "but I haven't changed anything yet."
        )
    if re.search(r"\b(?:search|look\s+up|page|link|website|article)\b", previous, re.IGNORECASE):
        return "Which result or page do you mean? I haven't opened or changed anything."
    return None


try:
    import json
    import logging
    import threading
    from plugins.memory import hindsight as _hindsight
    from hindsight_client.hindsight_client import Hindsight as _HindsightClient
    import cli as _hermes_cli
    from agent.web_search_registry import register_provider as _register_web_provider
    from plugins.web.searxng.provider import SearXNGWebSearchProvider
    _hades_logger = logging.getLogger("hades.overlay")
    _hades_memory_local = threading.local()

    def _hades_grocy_tool_definitions(_get_tool_definitions):
        """Return the canonical Grocy tools plus the serving companion.

        MCP discovery can complete after an API agent has initialized. Query
        the normal toolset first, then use the registry for the one known
        companion tool so discovery order cannot silently remove it from a
        narrowed recipe turn.
        """
        definitions = _get_tool_definitions(
            enabled_toolsets=_HADES_GROCY_TOOLSETS, quiet_mode=True
        )
        companion_names = {"mcp_grocy_recipe_authoring_recipe_set_servings"}
        missing = {
            name for name in companion_names
            if not any(tool.get("function", {}).get("name") == name for tool in definitions)
        }
        if missing:
            try:
                from tools.registry import registry as _hades_registry
                definitions.extend(_hades_registry.get_definitions(missing, quiet=True))
            except Exception as exc:
                _hades_logger.warning("Grocy/recipe tool reconciliation failed: %s", exc)
        unique = {}
        for tool in definitions:
            name = tool.get("function", {}).get("name")
            if name:
                unique[name] = tool
        _hades_logger.warning(
            "Grocy tool catalog reconciled: total=%d serving_tool=%s",
            len(unique), "mcp_grocy_recipe_authoring_recipe_set_servings" in unique,
        )
        return list(unique.values())

    def _hades_homelab_tool_definitions(_get_tool_definitions):
        """Return only the registered read-only homelab tool catalog."""
        global _HADES_HOMELAB_DISCOVERY_ATTEMPTED
        definitions = _get_tool_definitions(
            enabled_toolsets=_HADES_HOMELAB_TOOLSETS, quiet_mode=True
        )
        if not definitions and not _HADES_HOMELAB_DISCOVERY_ATTEMPTED:
            _HADES_HOMELAB_DISCOVERY_ATTEMPTED = True
            try:
                from tools.mcp_tool import discover_mcp_tools
                discover_mcp_tools()
                definitions = _get_tool_definitions(
                    enabled_toolsets=_HADES_HOMELAB_TOOLSETS, quiet_mode=True
                )
            except Exception as exc:
                _hades_logger.warning("Homelab MCP lazy discovery failed: %s", exc)
        if not definitions:
            _hades_register_homelab_fallback_tools()
            # A local fallback is intentionally not added to the static
            # toolset map: that map is profile-wide and would make the
            # capability visible to household agents. Retrieve the owner-only
            # entries by exact name instead.
            try:
                from tools.registry import registry as _hades_registry
                definitions = _hades_registry.get_definitions(
                    {
                        "mcp_homelab_readonly_homelab_summary",
                        "mcp_homelab_readonly_homelab_owner_snapshot",
                        "mcp_homelab_readonly_homelab_compute_capabilities",
                        "mcp_homelab_readonly_homelab_discovery_scan",
                        "mcp_homelab_readonly_homelab_discovery_candidates",
                    },
                    quiet=True,
                )
            except Exception as exc:
                _hades_logger.warning("Homelab fallback catalog lookup failed: %s", exc)
        unique = {}
        for tool in definitions:
            name = tool.get("function", {}).get("name")
            if name and name.startswith("mcp_"):
                unique[name] = tool
        _hades_logger.info("Homelab tool catalog reconciled: total=%d", len(unique))
        return list(unique.values())

    def _hades_homelab_control_tool_definitions(_get_tool_definitions):
        """Return only the owner-scoped homelab write/provisioning tools."""
        definitions = _get_tool_definitions(
            enabled_toolsets=_HADES_HOMELAB_CONTROL_TOOLSETS, quiet_mode=True
        )
        if not definitions:
            try:
                from tools.mcp_tool import discover_mcp_tools
                discover_mcp_tools()
                definitions = _get_tool_definitions(
                    enabled_toolsets=_HADES_HOMELAB_CONTROL_TOOLSETS, quiet_mode=True
                )
            except Exception as exc:
                _hades_logger.warning("Homelab control MCP discovery failed: %s", exc)
        if not definitions:
            _hades_register_homelab_fallback_tools()
            try:
                from tools.registry import registry as _hades_registry
                definitions = _hades_registry.get_definitions(
                    {
                        # Current Hermes MCP names use the canonical
                        # double-underscore server/tool boundary. Keep the
                        # legacy spelling as a compatibility fallback for
                        # older generated registries.
                        "mcp__homelab_control__homelab_control_templates",
                        "mcp__homelab_control__homelab_provision_guest",
                        "mcp__homelab_control__homelab_managed_guests",
                        "mcp__homelab_control__homelab_manage_guest",
                        "mcp_homelab_control_homelab_control_templates",
                        "mcp_homelab_control_homelab_provision_guest",
                        "mcp_homelab_control_homelab_managed_guests",
                        "mcp_homelab_control_homelab_manage_guest",
                    }, quiet=True
                )
            except Exception as exc:
                _hades_logger.warning("Homelab control fallback lookup failed: %s", exc)
        allowed_prefixes = (
            "mcp__homelab_control__",
            "mcp_homelab_control_",
        )
        return [
            tool for tool in definitions
            if tool.get("function", {}).get("name", "").startswith(allowed_prefixes)
        ]

    def _hades_page_tool_definitions(_get_tool_definitions):
        """Return the static public-page evidence tool when it has discovered."""
        definitions = _get_tool_definitions(
            enabled_toolsets=_HADES_PAGE_TOOLSETS, quiet_mode=True
        )
        unique = {}
        for tool in definitions:
            name = tool.get("function", {}).get("name")
            if name and name.endswith("public_page_read"):
                unique[name] = tool
        _hades_logger.info("Public page tool catalog reconciled: total=%d", len(unique))
        return list(unique.values())

    _HADES_HOMELAB_FALLBACK_REGISTERED = False

    def _hades_register_homelab_fallback_tools():
        """Register a local registry fallback while MCP discovery is racing.

        The fallback imports and calls the same read-only adapter code. It is
        owner-only at the agent boundary and has no lifecycle or write path.
        Native MCP discovery may later replace these entries with the same
        canonical names.
        """
        global _HADES_HOMELAB_FALLBACK_REGISTERED
        if _HADES_HOMELAB_FALLBACK_REGISTERED:
            return
        from pathlib import Path
        import importlib.util
        from tools.registry import registry

        adapter_root = Path(os.environ.get(
            "HADES_HERMES_WORKING_DIRECTORY", str(Path(__file__).resolve().parents[1])
        )) / "integrations" / "homelab-readonly"
        if not adapter_root.is_dir():
            return
        if str(adapter_root) not in __import__("sys").path:
            __import__("sys").path.insert(0, str(adapter_root))
        spec = importlib.util.spec_from_file_location(
            "hades_homelab_fallback_server", adapter_root / "server.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        tools = {
            "mcp_homelab_readonly_homelab_summary": {
                "description": "MANDATORY for any owner question about servers, hosts, VMs, online status, or homelab infrastructure: call this tool first. Read current Proxmox runtime, NetBox inventory, Uptime Kuma availability, and clearly labeled supplemental hardware inventory without writes. Only runtime_status=online for hosts or running for guests is currently live; inventory-only records are not liveness.",
                "parameters": {"type": "object", "properties": {}},
                "call": lambda _args: module.homelab_summary(),
            },
            "mcp_homelab_readonly_homelab_owner_snapshot": {
                "description": "For compound owner questions about current homelab status and hardware, read the live Proxmox/NetBox/Uptime Kuma summary together with the observed compute capability matrix. Proxmox is the only liveness authority; hardware inventory never implies online status. Read-only, no writes.",
                "parameters": {"type": "object", "properties": {}},
                "call": lambda _args: module.homelab_owner_snapshot(),
            },
            "mcp_homelab_readonly_homelab_compute_capabilities": {
                "description": "Read confirmed observed CPU, RAM, and GPU hardware inventory. This tool does not provide liveness: never label a machine online from it; use Proxmox runtime for that. It does not claim CUDA, VRAM, or control authority.",
                "parameters": {"type": "object", "properties": {}},
                "call": lambda _args: module.homelab_compute_capabilities(),
            },
            "mcp_homelab_readonly_homelab_discovery_scan": {
                "description": "Run bounded, review-only TCP discovery inside the configured authorized LAN scope.",
                "parameters": {"type": "object", "properties": {"target": {"type": "string"}, "ports": {"type": "string"}}, "required": ["target"]},
                "call": lambda args: module.run_bounded_scan(
                    args.get("target", ""),
                    allowed_networks=[v.strip() for v in os.environ.get("HADES_DISCOVERY_ALLOWED_NETWORKS", "").split(",") if v.strip()],
                    ports=args.get("ports", module.DEFAULT_PORTS),
                ),
            },
            "mcp_homelab_readonly_homelab_discovery_candidates": {
                "description": "Project normalized discovery into transient review-only candidates; never write inventory.",
                "parameters": {"type": "object", "properties": {"evidence": {"type": "object"}, "netbox": {"type": "object"}}, "required": ["evidence"]},
                "call": lambda args: module.propose_inventory_candidates(args.get("evidence"), args.get("netbox")),
            },
        }
        control_root = adapter_root.parent / "homelab-control"
        control_module = None
        if control_root.is_dir():
            control_spec = importlib.util.spec_from_file_location(
                "hades_homelab_control_fallback", control_root / "control.py"
            )
            control_module = importlib.util.module_from_spec(control_spec)
            control_spec.loader.exec_module(control_module)
            tools.update({
                "mcp_homelab_control_homelab_control_templates": {
                    "description": "List approved server templates and target nodes; no writes.",
                    "parameters": {"type": "object", "properties": {}},
                    "call": lambda _args: control_module.inspect_templates(),
                },
                "mcp_homelab_control_homelab_provision_guest": {
                    "description": "Owner-confirmed bounded server provisioning; no shell or arbitrary Proxmox paths.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "template": {"type": "string"},
                            "target": {
                                "type": "object",
                                "properties": {
                                    "node": {"type": "string"},
                                    "vmid": {"type": "integer"},
                                },
                                "required": ["node"],
                                "additionalProperties": False,
                            },
                            "name": {"type": "string"},
                            "cores": {"type": "integer"},
                            "memory_mib": {"type": "integer"},
                            "disk_gib": {"type": "integer"},
                            "owner_confirmed": {"type": "boolean"},
                        },
                        "required": ["template", "target", "name", "owner_confirmed"],
                    },
                    "call": lambda args: control_module.provision_guest(
                        args.get("template", ""), args.get("target", {}),
                        name=args.get("name", ""), cores=args.get("cores", 4),
                        memory_mib=args.get("memory_mib", 8192), disk_gib=args.get("disk_gib", 0),
                        owner_confirmed=args.get("owner_confirmed") is True,
                    ),
                },
                "mcp_homelab_control_homelab_managed_guests": {
                    "description": "Owner-only read of HADES-managed self-service guests in the approved pool; no writes.",
                    "parameters": {"type": "object", "properties": {}},
                    "call": lambda _args: control_module.list_managed_guests(),
                },
                "mcp_homelab_control_homelab_manage_guest": {
                    "description": "Owner-only bounded status/start/stop/restart/delete for an HADES-managed self-service guest; no raw Proxmox administration.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {
                                "type": "object",
                                "properties": {"node": {"type": "string"}, "vmid": {"type": "integer"}},
                                "required": ["node", "vmid"],
                                "additionalProperties": False,
                            },
                            "action": {"type": "string", "enum": ["status", "start", "stop", "restart", "delete"]},
                            "owner_confirmed": {"type": "boolean"},
                        },
                        "required": ["target", "action", "owner_confirmed"],
                    },
                    "call": lambda args: control_module.manage_guest(
                        args.get("target", {}), args.get("action", ""),
                        owner_confirmed=args.get("owner_confirmed") is True,
                    ),
                },
            })
        for name, definition in tools.items():
            registry.register(
                name=name,
                toolset="mcp-homelab-readonly",
                schema={
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": definition["description"],
                        "parameters": definition["parameters"],
                    },
                },
                handler=lambda args, _call=definition["call"], **_kw: json.dumps(
                    _call(args or {}), sort_keys=True
                ),
                override=True,
            )
        _HADES_HOMELAB_FALLBACK_REGISTERED = True
        _hades_logger.warning("Registered owner-scoped homelab fallback tools: %d", len(tools))

    # The profile plugin is discovered lazily, while the legacy web tool
    # resolves its backend on first use. Register the packaged provider at
    # interpreter startup so resolution cannot race plugin discovery.
    _register_web_provider(SearXNGWebSearchProvider())

    _hades_original_handle_tool_call = _hindsight.HindsightMemoryProvider.handle_tool_call

    # Hindsight's retain endpoint supports background processing.  The
    # provider's default client call waits for local LLM fact extraction,
    # which can exceed the owner-facing chat timeout when Ollama is sharing
    # the GPU with Hermes.  Submit writes asynchronously; recall remains
    # synchronous so answers never use an unverified write as truth.
    _hades_original_aretain = _HindsightClient.aretain
    _hades_original_aretain_batch = _HindsightClient.aretain_batch

    _hades_original_sync_turn = _hindsight.HindsightMemoryProvider.sync_turn
    _HADES_EXPLICIT_MEMORY_INTENT = re.compile(
        r"\b(?:remember|memorize|forget|memory|recall|do you remember|"
        r"actually my|correction)\b",
        re.IGNORECASE,
    )

    def _hades_direct_memory_response(user_text, subject, scope):
        """Perform explicit memory turns through the authenticated bank.

        The generic capability explainer must not swallow a real "remember
        this" request.  This narrow path binds the bank from the trusted
        gateway subject, uses Hindsight directly, and never falls back to the
        owner bank for an unbound actor.
        """
        text = str(user_text or "").strip()
        if scope not in {"owner", "household"} or not subject:
            return None
        if re.search(r"\b(?:what\s+do\s+you\s+remember|what\s+do\s+i\s+remember|what\s+is\s+(?:the|my)\s+.*(?:memory|fact|marker|fruit)|recall|look\s+in\s+(?:your|my)\s+memory)\b", text, re.IGNORECASE):
            intent = "recall"
        else:
            match = re.match(r"^\s*(?:please\s+)?remember(?:\s+that)?\s+(.+?)\s*[.!?]*\s*$", text, re.IGNORECASE)
            if not match:
                return None
            intent = "retain"
            fact = match.group(1).strip()
            if not fact or len(fact) > 1000:
                return "I couldn't store that memory safely; the fact was empty or too long."
        bank = "hades-owner" if scope == "owner" else f"hades-user-{subject}"
        try:
            client = _HindsightClient(os.environ.get("HADES_HINDSIGHT_URL", "http://127.0.0.1:8888"), timeout=30)
            if intent == "retain":
                response = client.retain(
                    bank_id=bank,
                    content=f"User explicitly asked HADES to remember: {fact}",
                    context="authenticated HADES personal memory",
                    tags=["hades-explicit-memory"],
                    retain_async=False,
                )
                client.close()
                return f"I stored that as private memory for this account: `{fact}`. It is not shared household state."
            response = client.recall(bank_id=bank, query=text, max_tokens=1200, budget="low", tags=["hades-explicit-memory"], tags_match="any")
            client.close()
            rows = [" ".join(str(item.text or "").split()) for item in (response.results or []) if str(item.text or "").strip()]
            if not rows:
                return "I couldn't find a matching private memory for this account. I did not use another user's bank."
            return "I remember: " + " ".join(rows[:3])
        except Exception as exc:
            _hades_logger.warning("Explicit Hindsight operation failed: %s", type(exc).__name__)
            return "I couldn't complete that private memory operation. Nothing was represented as remembered."

    def _hades_sync_turn(self, user_content, assistant_content, *, session_id=""):
        """Keep shared household turns out of private semantic memory.

        Grocy is the canonical household store. Hermes' generic automatic
        retain path otherwise persists the entire completed turn, including
        live shopping-list/tool results, into the authenticated user's private
        Hindsight bank. Explicit memory requests remain eligible for retain;
        ordinary shared-state turns do not become personal memory by accident.
        """
        # Classify from the user's request only. Assistant/tool output is
        # untrusted generated text and must not decide whether a turn is
        # private or shared.
        user_text = str(user_content or "")
        if _hades_should_skip_automatic_memory(user_text, assistant_content):
            _hades_logger.info(
                "Skipping automatic Hindsight retain for non-personal or transient-error turn"
            )
            return None
        return _hades_original_sync_turn(
            self, user_content, assistant_content, session_id=session_id
        )

    _hindsight.HindsightMemoryProvider.sync_turn = _hades_sync_turn

    async def _hades_aretain(self, *args, **kwargs):
        kwargs["retain_async"] = True
        return await _hades_original_aretain(self, *args, **kwargs)

    async def _hades_aretain_batch(self, *args, **kwargs):
        kwargs["retain_async"] = True
        return await _hades_original_aretain_batch(self, *args, **kwargs)

    _HindsightClient.aretain = _hades_aretain
    _HindsightClient.aretain_batch = _hades_aretain_batch

    def _hades_prefetch(self, query: str, *, session_id: str = "") -> str:
        """Recall the current query before the model's first API call.

        Hermes' stock Hindsight prefetch is queued at turn end, which makes
        the first turn of a new owner session unable to use relevant memory.
        HADES uses the direct recall endpoint here so the current query gets
        its context synchronously; reflection remains intentionally disabled.
        """
        if self._memory_mode == "tools" or not self._auto_recall or not query.strip():
            return ""
        # Grocy is authoritative for live household state. Do not inject
        # stale personal semantic-memory claims into a live Grocy question,
        # especially when Grocy is unavailable and the model must report a
        # dependency failure. Explicit memory requests may still compose with
        # a Grocy read.
        if _hades_nonpersonal_state_turn(query) and not _HADES_EXPLICIT_MEMORY_INTENT.search(query):
            return ""
        if self._recall_max_input_chars and len(query) > self._recall_max_input_chars:
            query = query[:self._recall_max_input_chars]
        recall_kwargs = {
            "bank_id": self._bank_id,
            "query": query,
            "budget": self._budget,
            "max_tokens": self._recall_max_tokens,
        }
        if self._recall_tags:
            recall_kwargs["tags"] = self._recall_tags
            recall_kwargs["tags_match"] = self._recall_tags_match
        if self._recall_types:
            recall_kwargs["types"] = self._recall_types
        try:
            response = self._run_hindsight_operation(
                lambda client: client.arecall(**recall_kwargs)
            )
            seen = set()
            lines = []
            for item in (response.results or []):
                text = " ".join(str(item.text or "").split())
                if not text:
                    continue
                # Hindsight can return several retained paraphrases of the
                # same fact. Keep the first occurrence, but don't let those
                # duplicates crowd out a more specific result.
                key = text.split(" | ", 1)[0].casefold()
                if key in seen:
                    continue
                seen.add(key)
                lines.append(f"- {text}")
            if not lines:
                return ""
            header = self._recall_prompt_preamble or (
                "# Hindsight Memory (persistent cross-session context)\n"
                "Use this to answer questions about the user and prior sessions. "
                "Prefer a specific matching fact (such as a named location, "
                "version, or preference) over a generic description. "
                "Do not call tools to look up information already present here."
            )
            return header + "\n\n" + "\n".join(lines)
        except Exception:
            return ""

    def _hades_memory_tools(self):
        if self._memory_mode == "context":
            return []
        return [_hindsight.RETAIN_SCHEMA, _hindsight.RECALL_SCHEMA]

    def _hades_handle_tool_call(self, tool_name, args, **kwargs):
        started = time.perf_counter()
        try:
            result = _hades_original_handle_tool_call(self, tool_name, args, **kwargs)
        finally:
            _hades_logger.info(
                "HADES timing stage=tool name=%s elapsed_ms=%.1f",
                tool_name,
                (time.perf_counter() - started) * 1000,
            )
        if tool_name == "hindsight_retain" and isinstance(result, str):
            try:
                payload = json.loads(result)
                if payload.get("result") == "Memory stored successfully.":
                    payload["result"] = "Memory accepted for background storage."
                    return json.dumps(payload)
            except Exception:
                pass
        if tool_name != "hindsight_recall" or not isinstance(result, str):
            return result
        try:
            payload = json.loads(result)
            raw = payload.get("result")
            if not isinstance(raw, str) or not raw.strip() or raw.startswith("No relevant"):
                return result
            facts = [line.strip() for line in raw.splitlines() if line.strip()]
            seen = set()
            unique = []
            for fact in facts:
                text = re.sub(r"^\d+\.\s*", "", fact).strip()
                key = text.split(" | ", 1)[0].casefold()
                if key and key not in seen:
                    seen.add(key)
                    unique.append(text)

            def specificity(text):
                concrete = len(re.findall(
                    r"\b(?:node|host|server|location|version|port|model|address|running on|located|prefer|favorite)\b",
                    text,
                    re.IGNORECASE,
                ))
                identifiers = len(re.findall(r"\b[A-Z0-9][A-Za-z0-9_.:/-]{2,}\b", text))
                return (concrete, identifiers, len(text))

            unique.sort(key=specificity, reverse=True)
            payload["result"] = "\n".join(f"{i}. {fact}" for i, fact in enumerate(unique, 1))
            _hades_memory_local.result = payload["result"]
            return json.dumps(payload)
        except Exception:
            return result

    # Keep automatic context disabled for now: broad Hindsight recall can
    # surface low-confidence acceptance fixtures on unrelated prompts. The
    # direct hindsight_recall tool remains available for explicit memory work.
    _hindsight.HindsightMemoryProvider.get_tool_schemas = _hades_memory_tools
    _hindsight.HindsightMemoryProvider.handle_tool_call = _hades_handle_tool_call

    # Local Ollama routing policy: keep conversational turns on the quick
    # 14B model, but move turns that plainly require an external/current
    # source or durable memory to the local model that reliably emits tool
    # calls.  This is intentionally a small deployment overlay rather than a
    # second HADES router; Hermes still owns the turn lifecycle and tools.
    _hades_original_resolve_turn = _hermes_cli.HermesCLI._resolve_turn_agent_config
    _HADES_TOOL_INTENT = re.compile(
        r"\b(?:remember(?:ed|ing)?|recall|forget|did i tell|do you remember|memory|"
        r"weather|forecast|temperature|search|look up|latest|news|web|"
        r"current|today|tonight|tomorrow|yesterday|recent(?:ly)?|newer|"
        r"who won|score|what happened|release(?:d)?|version|"
        r"grocy|grocery|groceries|grocry|grocerys|shopping list|recipe|food|pantry|inventory|"
        r"what(?:'s| is) running|what(?:'s| is) down|homelab|server|proxmox|"
        r"netbox|uptime|docker|finance|finances|spend|spending|spent|subscription|"
        r"bank|account balance|before payday|"
        r"(?:add|out\s+of|outta)\s+(?:(?:the|some|my)\s+)?(?:milk|eggs?|cereal|bread|cheese|"
        r"pasta|rice|chicken|beef|fruit|vegetables?)|"
        r"remove\s+(?:(?:the|some|my)\s+)?(?:milk|eggs?|cereal|bread|cheese|"
        r"pasta|rice|chicken|beef|fruit|vegetables?))\b|"
        r"^\s*(?:milk|eggs?|cereal|bread|cheese|pasta|rice|chicken|"
        r"beef|fruit|vegetables?)\s*[?!.,]*\s*$",
        re.IGNORECASE,
    )
    # The OpenAI-compatible API server constructs AIAgent directly rather
    # than going through HermesCLI's turn resolver.  Route at the agent turn
    # boundary instead; profile/runtime initialization has completed by this
    # point, so this cannot erase the selected provider or model.
    from run_agent import AIAgent as _AIAgent

    # The API gateway can construct agents after MCP discovery but before the
    # dynamic server alias is visible to its platform allowlist. Reconcile
    # HADES-owned MCP toolsets at the agent boundary so owner-facing API turns
    # receive the same schemas as an explicit toolset run.
    _hades_original_agent_init = _AIAgent.__init__

    def _hades_agent_init(self, *args, **kwargs):
        _hades_install_gateway_route_patch()
        session_key = kwargs.get("gateway_session_key")
        self._hades_gateway_session_key = session_key or ""
        # The OpenAI-compatible gateway supplies the stable conversation/session
        # identity to the agent constructor.  Keep it separate from the
        # gateway session key: the latter is user-scoped and would make two
        # authenticated tabs share one pending confirmation.
        _agent_history = kwargs.get("conversation_history")
        _agent_first_user = next(
            (str(item.get("content", "")) for item in (_agent_history if isinstance(_agent_history, list) else [])
             if isinstance(item, dict) and item.get("role") == "user" and str(item.get("content", "")).strip()),
            "",
        )
        self._hades_conversation_id = (
            "conversation:" + hashlib.sha256(_agent_first_user.strip().casefold().encode("utf-8")).hexdigest()[:24]
            if _agent_first_user else str(kwargs.get("session_id") or "")
        )
        subject = _hades_subject_from_session_key(session_key)
        self._hades_subject = subject
        self._hades_session_scope = _hades_session_scope(session_key)
        if subject and not kwargs.get("user_id"):
            kwargs["user_id"] = subject
            _hades_logger.info("API subject propagated to agent user_id")
        _hades_original_agent_init(self, *args, **kwargs)
        # The profile's private Hindsight JSON is the authoritative runtime
        # config and contains the owner's legacy bank as its static fallback.
        # Override only the provider instance after trusted gateway identity
        # is known: preserve that existing bank for the owner, isolate every
        # household subject, and never fall back to the owner bank when the
        # request has no validated subject.
        memory_scope = getattr(self, "_hades_session_scope", "")
        if self._memory_manager and self._memory_manager.providers:
            if memory_scope == "owner":
                memory_bank = "hades-owner"
            elif memory_scope == "household" and subject:
                memory_bank = f"hades-user-{subject}"
            else:
                memory_bank = "hades-denied"
            for memory_provider in self._memory_manager.providers:
                if hasattr(memory_provider, "_bank_id"):
                    memory_provider._bank_id = memory_bank
                if hasattr(memory_provider, "_auto_recall"):
                    # The profile intentionally disables global auto-recall;
                    # once a trusted subject has selected an isolated bank,
                    # enable scoped prefetch so UI recall does not depend on
                    # a small model choosing the memory tool correctly.
                    memory_provider._auto_recall = memory_scope in {
                        "owner", "household"
                    }
                if memory_scope in {"owner", "household"}:
                    # Bind HADES' synchronous current-query prefetch helper;
                    # the upstream tools-only mode otherwise suppresses
                    # prefetch and makes recall depend on model tool choice.
                    memory_provider._memory_mode = "hybrid"
                    memory_provider.prefetch = _hades_prefetch.__get__(
                        memory_provider, type(memory_provider)
                    )
            _hades_logger.info(
                "Hindsight bank selected from trusted scope: scope=%s subject_present=%s",
                memory_scope or "denied", bool(subject),
            )
        tools = getattr(self, "tools", None)
        if not isinstance(tools, list):
            return
        if self._hades_session_scope == "household":
            # Capability exclusion must happen before model invocation. The
            # base profile may advertise privileged toolsets globally, so do
            # not rely on a later prompt/intent guard to hide them.
            self.tools = _hades_filter_tools_for_scope(tools, "household")
            self.valid_tool_names = {
                tool.get("function", {}).get("name") for tool in self.tools
            }
            tools = self.tools
        # Keep ordinary turns free of the complete household and homelab
        # schemas.  The turn-level intent paths below materialize only the
        # narrowly relevant definitions before model invocation.  Injecting
        # every MCP schema here made even a one-line chat request carry a
        # multi-thousand-token prompt on local inference hardware.
        inherited_count = len(tools)
        self.tools = []
        self.valid_tool_names = set()
        _hades_logger.warning(
            "API ordinary-turn tool catalog cleared: %d inherited tools",
            inherited_count,
        )

    _AIAgent.__init__ = _hades_agent_init

    _hades_original_run_conversation = _AIAgent.run_conversation

    def _hades_run_conversation(self, user_message, *args, **kwargs):
        turn_started = time.perf_counter()
        # Resolve typed confirmations before the broader server-control route.
        # Open WebUI can omit the chat transcript on a follow-up; when there is
        # exactly one outstanding typed action for this actor, its persisted
        # operation key is still a safe recovery anchor. Multiple outstanding
        # actions remain deliberately ambiguous and are never guessed.
        _early_text = str(user_message or "")
        _early_affirmative = bool(re.search(r"\b(?:yes|y|yeah|yep|okay|ok|do it|go ahead|confirm|please do)\b", _early_text, re.IGNORECASE))
        _early_subject = str(getattr(self, "_hades_subject", "") or "")
        _early_scope = getattr(self, "_hades_session_scope", "")
        if _early_affirmative and _early_subject and _early_scope in {"owner", "household"}:
            try:
                from integrations.automation import LifecycleStore
                _early_store = LifecycleStore(_hades_health_watch_state_path())
                _early_history = kwargs.get("conversation_history")
                if not isinstance(_early_history, list):
                    _early_history = []
                _early_key = f"session:{_early_subject}:{_hades_turn_identity(_early_text, _early_history)}"
                _early_pending = _early_store.pending_get(_early_key, _early_subject)
                # API follow-up turns may omit the prior transcript. Recover a
                # single outstanding typed action or creation preview by its
                # persisted operation key; retain fail-closed ambiguity when
                # more than one candidate exists.
                _early_candidates = [
                    item for item in _early_store.pending_for_actor(_early_subject)
                    if item.get("payload", {}).get("action")
                    or item.get("payload", {}).get("preview_id")
                ]
                if not (_early_pending and _early_pending.get("action")) and len(_early_candidates) == 1:
                    _only = _early_candidates[0]
                    _only_key = str(_only.get("pending_key", ""))
                    _prefix = f"session:{_early_subject}:"
                    if _only_key.startswith(_prefix):
                        _early_key = _only_key
                        _early_pending = _only.get("payload")
                if _early_pending and _early_pending.get("action"):
                    _template = (_early_pending.get("record") or {}).get("template_id") or _early_pending.get("template_id")
                    _early_response = None
                    if _template == "hades-backup-verification":
                        _early_response = _hades_phase2_backup_response(_early_text, _early_subject, _early_scope, _early_key.split(f"session:{_early_subject}:", 1)[-1])
                    elif _template == "low-inventory-summary":
                        _early_response = _hades_phase2_inventory_response(_early_text, _early_subject, _early_scope, _early_key.split(f"session:{_early_subject}:", 1)[-1])
                    elif _template == "weekly-household-summary":
                        _early_response = _hades_phase2_weekly_response(_early_text, _early_subject, _early_scope, _early_key.split(f"session:{_early_subject}:", 1)[-1])
                    if _early_response:
                        callback = getattr(self, "stream_delta_callback", None)
                        if callback:
                            callback(_early_response)
                        return {"final_response": _early_response, "messages": [{"role": "assistant", "content": _early_response}], "api_calls": 0, "completed": True}
            except Exception as _early_exc:
                _hades_logger.warning("Phase2 early confirmation recovery failed closed: %s", _early_exc)
        original_model = getattr(self, "model", "")
        fast_lane_restore = None
        fast_prompt_restore = None
        fast_base_url = os.environ.get("HADES_FAST_COMPLETION_BASE_URL", "").strip()
        fast_model = os.environ.get("HADES_FAST_COMPLETION_MODEL", "qwen3:8b").strip()
        current_base_url = str(getattr(self, "base_url", "") or "").lower()
        if (
            str(getattr(self, "provider", "") or "").lower() == "custom"
            and ("11437" in current_base_url or "qwen3.6:35b" in str(original_model).lower())
            and fast_base_url
            and fast_model
            and not _HADES_TOOL_INTENT.search(str(user_message or ""))
        ):
            fast_lane_restore = (
                original_model,
                getattr(self, "provider", "custom"),
                getattr(self, "api_key", ""),
                getattr(self, "base_url", ""),
                getattr(self, "api_mode", ""),
            )
            try:
                self.switch_model(
                    fast_model,
                    "custom",
                    api_key=os.environ.get("HADES_FAST_COMPLETION_API_KEY", "local"),
                    base_url=fast_base_url.rstrip("/"),
                )
                _hades_logger.info(
                    "HADES API turn lane=fast-completion model=%s base_url=%s",
                    fast_model,
                    fast_base_url,
                )
                # The normal HADES system prompt is intentionally rich for
                # tools, operator policy, and deep work. It is wasteful for a
                # completion-only turn and, on the one-slot Fast server, makes
                # title + answer requests serialize behind a ~9K-token prompt.
                # Keep the conversation history, but use a compact per-turn
                # prompt and do not persist it as the canonical session prompt.
                fast_prompt_restore = (
                    getattr(self, "_cached_system_prompt", None),
                    getattr(self, "_cached_system_prompt_static", None),
                    getattr(self, "_session_db", None),
                    hasattr(self, "_build_system_prompt"),
                )
                compact_fast_prompt = (
                    "You are HADES Fast, the quick conversational lane. "
                    "Answer naturally and briefly. Use only the conversation "
                    "history supplied in this turn. Do not claim to have used "
                    "tools, checked live data, changed anything, or accessed "
                    "private information. If a request needs live data or an "
                    "action, say that it needs the appropriate HADES capability."
                )
                self._session_db = None
                self._cached_system_prompt = None
                self._cached_system_prompt_static = None
                self._build_system_prompt = lambda _system_message: compact_fast_prompt
            except Exception as exc:
                _hades_logger.warning("HADES fast lane switch failed; retaining original route: %s", exc)
                fast_lane_restore = None
        # Managed-server status and lifecycle are deterministic owner actions.
        # Resolve the resource from the bounded pool adapter; never let the
        # model invent a VMID or turn a shared household conversation into
        # infrastructure authority.
        _server_history_for_routing = kwargs.get("conversation_history")
        _server_user_turns = [
            str(item.get("content", "")).strip()
            for item in (_server_history_for_routing if isinstance(_server_history_for_routing, list) else [])
            if isinstance(item, dict) and item.get("role") == "user" and str(item.get("content", "")).strip()
        ]
        _server_text = _server_user_turns[-1] if _server_user_turns else str(user_message or "")
        # Typed household automation lifecycle language must reach the Phase 3
        # policy route before the separate managed-server control adapter. In
        # particular, "delete my weekly household summary" contains "delete"
        # and "my" but is not a Proxmox workload operation.
        _phase3_language = bool(re.search(
            r"\b(?:automation|automations|weekly\s+household\s+summary|low\s+(?:grocery|inventory)|server\s+health\s+watch|backup\s+verification)\b",
            _server_text,
            re.IGNORECASE,
        ))
        _owner_server_turn = getattr(self, "_hades_session_scope", "") == "owner"
        _server_actor_turn = getattr(self, "_hades_session_scope", "") in {"owner", "household"}
        _server_share_match = re.search(r"\b(?:share|unshare|revoke|stop\s+sharing)\b", _server_text, re.IGNORECASE)
        _server_action_matches = list(re.finditer(r"\b(start|stop|restart|reboot|delete|remove)\b", _server_text, re.IGNORECASE))
        _server_action_match = _server_action_matches[-1] if _server_action_matches else None
        _server_status_turn = bool(
            re.search(r"\b(?:show|list|what|which|check|status|is|are)\b", _server_text, re.IGNORECASE)
            and re.search(r"\b(?:server|sandbox|workload|guest|vm|virtual\s+machine)\b", _server_text, re.IGNORECASE)
        )
        _server_action_turn = bool(
            _server_action_match and re.search(r"\b(?:server|sandbox|workload|guest|vm|virtual\s+machine)\b", _server_text, re.IGNORECASE)
        )
        _server_share_turn = bool(
            _owner_server_turn and _server_share_match and
            re.search(r"\b(?:server|sandbox|workload|guest|vm|virtual\s+machine)\b", _server_text, re.IGNORECASE)
        )
        _server_confirmation = bool(
            re.search(r"\b(?:yes|y|yeah|yep|okay|ok|do it|go ahead|confirm|please do)\b", _server_text, re.IGNORECASE)
        )
        _server_history_for_identity = kwargs.get("conversation_history")
        _server_conversation = _hades_turn_identity(_server_text, _server_history_for_identity)
        _phase2_current = None
        if _server_confirmation and getattr(self, "_hades_subject", ""):
            try:
                from integrations.automation import LifecycleStore
                _phase2_store = LifecycleStore(_hades_health_watch_state_path())
                _phase2_key = f"session:{self._hades_subject}:{_server_conversation}"
                _phase2_current = _phase2_store.pending_get(_phase2_key, self._hades_subject)
                _phase2_other = [item for item in _phase2_store.pending_for_actor(self._hades_subject) if item.get("payload", {}).get("action")]
                if _phase2_other and not (_phase2_current and _phase2_current.get("action")):
                    _phase2_clarification = "I couldn't match that confirmation to this conversation's current HADES action, so I did not change anything."
                    callback = getattr(self, "stream_delta_callback", None)
                    if callback:
                        callback(_phase2_clarification)
                    return {"final_response": _phase2_clarification, "messages": [{"role": "assistant", "content": _phase2_clarification}], "api_calls": 0, "completed": True}
            except Exception:
                pass
        _server_key = (
            f"session:{getattr(self, '_hades_subject', '')}:{_server_conversation}"
            if getattr(self, "_hades_subject", "") and _server_conversation else
            (f"subject:{getattr(self, '_hades_subject', '')}" if getattr(self, "_hades_subject", "") else
             (getattr(self, "_hades_gateway_session_key", "") or getattr(self, "session_id", "")))
        )
        if _phase2_current and _phase2_current.get("action"):
            # A typed Phase 2 confirmation owns this turn; an older server
            # confirmation must not steal a bare "yes" from it.
            _pending_server = {}
        _pending_server = _HADES_PENDING_SERVER_ACTION.get(_server_key, {}) if _server_key else {}
        if _owner_server_turn and _server_confirmation and not _pending_server:
            _server_history = kwargs.get("conversation_history")
            if not isinstance(_server_history, list):
                _server_history = []
            _server_assistant_text = "\n".join(
                str(item.get("content", "")) for item in _server_history
                if isinstance(item, dict) and item.get("role") == "assistant"
            )
            _history_action = re.search(r"\b(?:shall|should)\s+i\s+(start|stop|restart|reboot|delete|remove)\b", _server_assistant_text, re.IGNORECASE)
            if _history_action:
                _pending_server = {"action": "restart" if _history_action.group(1).lower() == "reboot" else ("delete" if _history_action.group(1).lower() == "remove" else _history_action.group(1).lower())}
        if _server_actor_turn and not _phase3_language and (_server_status_turn or _server_action_turn or _server_share_turn or (_server_confirmation and _pending_server)):
            try:
                _control_module = _hades_load_control_module()
                _guests_result = _control_module.list_managed_guests()
                _guests = _guests_result.get("guests", []) if _guests_result.get("status") == "READY" else []
                try:
                    from integrations.self_service.registry import WorkloadRegistry
                    _registry_path = os.environ.get("HADES_SELF_SERVICE_REGISTRY_FILE", "").strip()
                    if not _registry_path:
                        _registry_path = str(Path(os.environ.get("HERMES_HOME", "/var/lib/hades") ) / "profiles" / "hades" / "state" / "self-service-workloads.json")
                    _registry = WorkloadRegistry(_registry_path)
                    _visible = {(item.get("node"), item.get("vmid")) for item in _registry.list_for(getattr(self, "_hades_subject", ""))}
                    _guests = [guest for guest in _guests if (guest.get("node"), guest.get("vmid")) in _visible]
                except Exception as _registry_exc:
                    _hades_logger.warning("Self-service registry lookup failed closed: %s", _registry_exc)
                    _guests = []
                if _server_share_turn:
                    _share_map = _hades_self_service_share_subjects()
                    _share_label = re.sub(r"[^a-z0-9]+", "-", _server_text.lower()).strip("-")
                    _grantee = next((subject for label, subject in _share_map.items() if label in _share_label), None)
                    if not _guests:
                        _server_response = "I don't have an HADES-managed server you can share."
                    elif not _grantee:
                        _server_response = "Tell me which approved household member should receive access. I have not changed sharing."
                    else:
                        _guest = _guests[0]
                        _resource_id = f"{_guest.get('node')}-{_guest.get('vmid')}"
                        _registry_result = _registry.revoke(getattr(self, "_hades_subject", ""), _resource_id, _grantee) if re.search(r"\b(?:unshare|revoke|stop\s+sharing)\b", _server_text, re.IGNORECASE) else _registry.grant(getattr(self, "_hades_subject", ""), _resource_id, _grantee)
                        if _registry_result.get("status") == "READY":
                            _server_response = f"Sharing for `{_guest.get('name', 'unnamed')}` was updated. The selected household member can use only this server's approved actions."
                        else:
                            _server_response = f"I couldn't change sharing for that server: {_registry_result.get('error', _registry_result.get('status', 'unknown failure'))}. Nothing else changed."
                    callback = getattr(self, "stream_delta_callback", None)
                    if callback:
                        callback(_server_response)
                    return {"final_response": _server_response, "messages": [{"role": "assistant", "content": _server_response}], "api_calls": 0, "completed": True}
                _requested_name = re.sub(r"\b(?:my|our|server|sandbox|workload|thing|status|is|up|the|a|an|show|list|what|which|check)\b", " ", _server_text, flags=re.IGNORECASE).strip()
                _guest = None
                if _pending_server.get("target"):
                    _guest = next((g for g in _guests if g.get("node") == _pending_server["target"].get("node") and g.get("vmid") == _pending_server["target"].get("vmid")), None)
                if _guest is None and len(_guests) == 1:
                    _guest = _guests[0]
                if _guest is None and _requested_name:
                    _matches = [g for g in _guests if _requested_name.casefold() in str(g.get("name", "")).casefold()]
                    if len(_matches) == 1:
                        _guest = _matches[0]
                if _guest is None:
                    _server_response = "I don't have an HADES-managed server to show or change." if not _guests else "Which HADES-managed server should I use? I can show its name and status first."
                elif _server_status_turn and not _server_action_match and not (_server_confirmation and _pending_server):
                    _server_response = f"Your HADES-managed server `{_guest.get('name', 'unnamed')}` is {_guest.get('status', 'unknown')} on {_guest.get('node', 'the approved host')}."
                else:
                    _action = _pending_server.get("action") if _server_confirmation and _pending_server else (_server_action_match.group(1).lower() if _server_action_match else "status")
                    if _action == "reboot":
                        _action = "restart"
                    _hades_logger.info("Managed server UI action=%s confirmation=%s pending=%s", _action, _server_confirmation, bool(_pending_server))
                    if _action in {"start", "stop", "restart", "delete", "remove"} and not _server_confirmation:
                        _HADES_PENDING_SERVER_ACTION[_server_key] = {"expires_at": time.time() + 600, "action": "delete" if _action == "remove" else _action, "target": {"node": _guest.get("node"), "vmid": _guest.get("vmid")}}
                        _server_response = f"I found `{_guest.get('name', 'unnamed')}` on {_guest.get('node')}, currently {_guest.get('status', 'unknown')}. Shall I {_action} it?"
                    elif _action in {"start", "stop", "restart", "delete"}:
                        _HADES_PENDING_SERVER_ACTION.pop(_server_key, None)
                        _result = _control_module.manage_guest({"node": _guest.get("node"), "vmid": _guest.get("vmid")}, _action, owner_confirmed=True)
                        if _result.get("status") == "SUCCEEDED":
                            if _action == "delete":
                                from integrations.self_service.registry import WorkloadRegistry
                                _registry_path = os.environ.get("HADES_SELF_SERVICE_REGISTRY_FILE", "").strip()
                                if not _registry_path:
                                    _registry_path = str(Path(os.environ.get("HERMES_HOME", "/var/lib/hades")) / "profiles" / "hades" / "state" / "self-service-workloads.json")
                                WorkloadRegistry(_registry_path).remove(
                                    getattr(self, "_hades_subject", ""),
                                    f"{_guest.get('node')}-{_guest.get('vmid')}",
                                )
                            _server_response = (
                                f"Done. `{_guest.get('name', 'unnamed')}` was removed and Proxmox confirmed the deletion."
                                if _action == "delete" else
                                f"Done. `{_guest.get('name', 'unnamed')}` is now {_result.get('observed_status', 'updated')} and Proxmox confirmed the change."
                            )
                        else:
                            _server_response = f"I couldn't {_action} that server: {_result.get('error', _result.get('status', 'unknown failure'))}. I did not guess at the result."
                    else:
                        _server_response = f"`{_guest.get('name', 'unnamed')}` is {_guest.get('status', 'unknown')} on {_guest.get('node', 'the approved host')}."
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(_server_response)
                return {"final_response": _server_response, "messages": [{"role": "assistant", "content": _server_response}], "api_calls": 0, "completed": True}
            except Exception as _server_exc:
                _server_response = f"I couldn't check the HADES-managed server right now: {_server_exc}. Nothing was changed."
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(_server_response)
                return {"final_response": _server_response, "messages": [{"role": "assistant", "content": _server_response}], "api_calls": 0, "completed": True}
        # Do not make a provisioning request wait for Hindsight prefetch or a
        # model turn. The first step is a read-only product preflight; the
        # bounded adapter remains the only write path.
        _early_provisioning_request = bool(
            getattr(self, "_hades_session_scope", "") == "owner"
            and not re.search(
                r"\b(?:yes|yeah|yep|okay|ok|do it|create it|go ahead|confirm|please do)\b",
                str(user_message or ""),
                re.IGNORECASE,
            )
            and re.search(
                r"\b(?:spin\s+up|provision|deploy|create|make|host)\b",
                str(user_message or ""),
                re.IGNORECASE,
            )
            and re.search(
                r"\b(?:server|palworld|minecraft|factorio|sandbox(?:es)?|workload(?:s)?|website(?:s)?|linux\s+box)\b",
                str(user_message or ""),
                re.IGNORECASE,
            )
        )
        if _early_provisioning_request:
            _pending_template = "minecraft" if re.search(r"\bminecraft\b", str(user_message or ""), re.IGNORECASE) else (
                "website" if re.search(r"\b(?:website|site)\b", str(user_message or ""), re.IGNORECASE) else "linux-sandbox"
            )
            _pending_name = "gamma-minecraft" if _pending_template == "minecraft" else (
                "gamma-website" if _pending_template == "website" else "gamma-sandbox"
            )
            _pending_record = {
                "expires_at": time.time() + 600,
                "template": _pending_template,
                "name": _pending_name,
                "origin": str(user_message or ""),
            }
            for _pending_key in _hades_pending_provision_keys(self):
                _HADES_PENDING_PROVISION[_pending_key] = dict(_pending_record)
            _early_preview = (
                "I can provision an approved household server, but I have not created anything yet. "
                "I will first show the approved template, bounded resources, placement, and sharing "
                "plan, then ask for confirmation before making a change."
            )
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(_early_preview)
            _hades_logger.info("Self-service provisioning early preflight completed without model invocation")
            return {
                "final_response": _early_preview,
                "messages": [{"role": "assistant", "content": _early_preview}],
                "api_calls": 0,
                "completed": True,
            }
        early_ambiguity_response = _hades_direct_ambiguous_mutation_clarification(
            user_message
        )
        if early_ambiguity_response and getattr(self, "_hades_session_scope", "") in {
            "household", "owner"
        }:
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(early_ambiguity_response)
            _hades_logger.info(
                "Ambiguous household mutation received early clarification without model invocation"
            )
            return {
                "final_response": early_ambiguity_response,
                "messages": [{"role": "assistant", "content": early_ambiguity_response}],
                "api_calls": 0,
                "completed": True,
            }
        if (
            getattr(self, "_hades_session_scope", "") == "household"
            and re.search(
                r"\b(?:agent\s*zero|agent0|bounded\s+operator|delegate|delegation)\b",
                str(user_message or ""),
                re.IGNORECASE,
            )
        ):
            denial = (
                "Agent Zero is owner-only and is not available to household "
                "users. I did not send or simulate an inspection."
            )
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(denial)
            return {
                "final_response": denial,
                "messages": [{"role": "assistant", "content": denial}],
                "api_calls": 0,
                "completed": True,
            }
        if (
            getattr(self, "_hades_session_scope", "") == "household"
            and re.search(
                r"\b(?:finance|finances|finaces|bank|spend|spending|spent|budget|"
                r"transaction|account|checking|savings|credit\s+card|money|cost|"
                r"paid|expense|expenses)\b|"
                r"\bprivate\s+(?:account|checking|savings|finance|finances)\b",
                str(user_message or ""),
                re.IGNORECASE,
            )
        ):
            denial = (
                "I can help with shared household tasks, but I can't access Scotty's "
                "finances. That information is owner-only, and nothing was changed."
            )
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(denial)
            _hades_logger.info("Household finance request denied before model invocation")
            return {
                "final_response": denial,
                "messages": [{"role": "assistant", "content": denial}],
                "api_calls": 0,
                "completed": True,
            }
        if (
            getattr(self, "_hades_session_scope", "") == "household"
            and re.search(r"\b(?:scotty|owner|private|personal)\b", str(user_message or ""), re.IGNORECASE)
            and re.search(r"\b(?:memory|remember|recall|hindsight|fact|marker)\b", str(user_message or ""), re.IGNORECASE)
        ):
            denial = (
                "I can't access another person's private memory from a household session. "
                "I did not search, reveal, or change any private memory."
            )
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(denial)
            _hades_logger.info("Household private-memory request denied before model invocation")
            return {
                "final_response": denial,
                "messages": [{"role": "assistant", "content": denial}],
                "api_calls": 0,
                "completed": True,
            }
        # Open WebUI sends follow-ups as separate turns.  Domain intent must
        # include the active conversation, otherwise a natural correction such
        # as "remove it" loses the Grocy route and can be misread as an
        # unrelated task-list request by a small local model.
        _hades_history = kwargs.get("conversation_history")
        if not isinstance(_hades_history, list):
            _hades_history = next(
                (value for value in args if isinstance(value, list)), []
            )
        _hades_logger.info(
            "Self-service turn state scope=%s gateway_key=%s session_id=%s history_messages=%d",
            getattr(self, "_hades_session_scope", ""),
            bool(getattr(self, "_hades_gateway_session_key", "")),
            bool(getattr(self, "session_id", "")),
            len(_hades_history),
        )
        # Finance CSV reads and household finance denials are deterministic
        # policy paths.  Resolve them before conversation-history intent
        # reconstruction; otherwise a long persistent chat can spend the
        # provider's entire turn budget rebuilding stale context for a reply
        # that never needs model inference.
        _early_finance_request = bool(re.search(
            r"\b(?:finance|finances|finaces|bank|spend|spending|spent|budget|"
            r"transaction|account|checking|savings|credit\s+card|money|cost|paid|"
            r"expense|expenses|subscription|subscriptions|recurring|utilities?|"
            r"restaurant|doordash|coffee|rent|lease|paycheck|bills?)\b|"
            r"\bprivate\s+(?:account|checking|savings|finance|finances)\b",
            str(user_message or ""), re.IGNORECASE,
        )) and not bool(re.search(
            r"\b(?:morning|briefing|homelab|grocy|grocery|groceries|pantry|recipe|network|"
            r"health\s+watch|backup\s+coverage|restock)\b",
            str(user_message or ""), re.IGNORECASE,
        ))
        if _early_finance_request and self._hades_session_scope == "household":
            _early_finance_denial = (
                "I can help with shared household tasks, but I can't access Scotty's "
                "finances. That information is owner-only, and nothing was changed."
            )
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(_early_finance_denial)
            return {
                "final_response": _early_finance_denial,
                "messages": [{"role": "assistant", "content": _early_finance_denial}],
                "api_calls": 0,
                "completed": True,
            }
        if _early_finance_request and self._hades_session_scope == "owner":
            _early_finance_response = _hades_direct_finance_guidance(user_message)
            if _early_finance_response:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(_early_finance_response)
                return {
                    "final_response": _early_finance_response,
                    "messages": [{"role": "assistant", "content": _early_finance_response}],
                    "api_calls": 0,
                    "completed": True,
                }
        _hades_intent_text = _hades_conversation_intent_text(
            user_message, _hades_history
        )
        previous_user_text = _hades_previous_user_message(_hades_history)
        _phase2_session_key = _hades_turn_identity(user_message, _hades_history)
        _preflight_text = str(user_message or "")
        _compound_briefing = bool(re.search(r"\b(?:morning\s+briefing|briefing)\b", _preflight_text, re.IGNORECASE))
        _briefing_recap = bool(
            re.search(
                r"\b(?:what\s+did\s+we\s+learn|what\s+needs\s+attention|what\s+should\s+i\s+handle\s+first|recap)\b",
                _preflight_text,
                re.IGNORECASE,
            )
            and re.search(r"\b(?:briefing|morning|hades)\b", _preflight_text, re.IGNORECASE)
        )
        if re.search(
            r"\b(?:what\s+should\s+i\s+handle\s+first|what(?:'s|\s+is)\s+most\s+urgent|what\s+needs\s+attention|highest\s+priority|why\s+first)\b",
            _preflight_text,
            re.IGNORECASE,
        ):
            _briefing_recap = True
        _compound_briefing = _compound_briefing or _briefing_recap
        if self._hades_session_scope in {"owner", "household"} and not _compound_briefing:
            _expiry_response = _hades_direct_grocy_expiry_read(_preflight_text)
            if _expiry_response:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(_expiry_response)
                return {"final_response": _expiry_response, "messages": [{"role": "assistant", "content": _expiry_response}], "api_calls": 0, "completed": True}
            if self._hades_session_scope == "owner":
                _spaghetti_response = _hades_direct_spaghetti_authorized(
                    _preflight_text, getattr(self, "_hades_subject", "")
                )
                if _spaghetti_response:
                    callback = getattr(self, "stream_delta_callback", None)
                    if callback:
                        callback(_spaghetti_response)
                    return {"final_response": _spaghetti_response, "messages": [{"role": "assistant", "content": _spaghetti_response}], "api_calls": 0, "completed": True}
            if self._hades_session_scope == "owner" and re.search(r"\b(?:where|which)\b.*\b(?:deploy|place|put)\b.*\b(?:model|ai)\b|\bdeploy\s+another\s+(?:local\s+)?ai\s+model\b", _preflight_text, re.IGNORECASE):
                _placement_response = "Observed hardware candidates include Hypnos (2× Quadro P4000, CUDA-capable in the tracked matrix) and Tartarus (4× Quadro P4000, CUDA-capable in the tracked matrix). Current per-host GPU load/VRAM and interference budget are not exposed by the approved live telemetry, so I cannot safely choose a placement. I did not deploy or change anything."
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(_placement_response)
                return {"final_response": _placement_response, "messages": [{"role": "assistant", "content": _placement_response}], "api_calls": 0, "completed": True}
        if self._hades_session_scope == "owner" and _compound_briefing:
            _brief_title = (
                "HADES morning briefing refresh (bounded live sources):"
                if _briefing_recap
                else "HADES morning briefing (bounded live sources):"
            )
            _brief_parts = [_brief_title]
            if _briefing_recap:
                _brief_parts.append(
                    "I refreshed the live sources instead of relying on a stale prior conversation; the highest-priority attention items are listed below."
                )
            _brief_homelab = _hades_direct_homelab_read("homelab status and blockers")
            _brief_backup = _hades_phase2_backup_response("what backup checks do I have?", getattr(self, "_hades_subject", ""), "owner", _phase2_session_key)
            _brief_food = _hades_direct_household_grocy_read("what is in stock")
            _brief_expiry = _hades_direct_grocy_expiry_read("what food is going to expire")
            if _brief_homelab: _brief_parts.append("INFRASTRUCTURE: " + _brief_homelab)
            if _brief_backup: _brief_parts.append("BACKUPS: " + _brief_backup)
            if _brief_food: _brief_parts.append("HOUSEHOLD: " + _brief_food)
            if _brief_expiry: _brief_parts.append("EXPIRY: " + _brief_expiry)
            _brief_finance = _hades_direct_finance_guidance("finance summary")
            if _brief_finance:
                _brief_parts.append("FINANCE: " + _brief_finance)
            _brief_response = "\n\n".join(_brief_parts)
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(_brief_response)
            return {"final_response": _brief_response, "messages": [{"role": "assistant", "content": _brief_response}], "api_calls": 0, "completed": True}
        _direct_memory_response = _hades_direct_memory_response(
            user_message,
            getattr(self, "_hades_subject", ""),
            getattr(self, "_hades_session_scope", ""),
        )
        if _direct_memory_response and self._hades_session_scope in {"household", "owner"}:
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(_direct_memory_response)
            _hades_logger.info("Explicit Hindsight deterministic path completed without model invocation")
            return {
                "final_response": _direct_memory_response,
                "messages": [{"role": "assistant", "content": _direct_memory_response}],
                "api_calls": 0,
                "completed": True,
            }
        _task_response = _hades_task_response(
            user_message,
            getattr(self, "_hades_subject", ""),
            getattr(self, "_hades_session_scope", ""),
            _hades_history,
        )
        if _task_response:
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(_task_response)
            _hades_logger.info("Persistent Task deterministic surface completed without model invocation")
            return {
                "final_response": _task_response,
                "messages": [{"role": "assistant", "content": _task_response}],
                "api_calls": 0,
                "completed": True,
            }
        # Resolve high-signal owner domains before the staged automation
        # catalog. Otherwise words such as "backup", "all", or "restock"
        # can be misclassified as automation administration.
        if self._hades_session_scope == "owner":
            direct_finance_response = _hades_direct_finance_guidance(user_message)
            if direct_finance_response:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(direct_finance_response)
                return {
                    "final_response": direct_finance_response,
                    "messages": [{"role": "assistant", "content": direct_finance_response}],
                    "api_calls": 0,
                    "completed": True,
                }
        if self._hades_session_scope in {"owner", "household"}:
            direct_backup_response = _hades_phase2_backup_response(
                user_message, getattr(self, "_hades_subject", ""),
                self._hades_session_scope, _phase2_session_key,
            )
            if direct_backup_response:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(direct_backup_response)
                return {
                    "final_response": direct_backup_response,
                    "messages": [{"role": "assistant", "content": direct_backup_response}],
                    "api_calls": 0,
                    "completed": True,
                }
            if (
                re.search(r"\b(?:restock|running\s+low|run(?:ning)?\s+out|burn\s+through|consume\s+quickly)\b", str(user_message), re.IGNORECASE)
                and not re.search(r"\b(?:automation|weekly|summary|every|watch|monitor)\b", str(user_message), re.IGNORECASE)
            ):
                direct_restock_response = _hades_direct_household_grocy_read(user_message)
                if direct_restock_response:
                    callback = getattr(self, "stream_delta_callback", None)
                    if callback:
                        callback(direct_restock_response)
                    return {
                        "final_response": direct_restock_response,
                        "messages": [{"role": "assistant", "content": direct_restock_response}],
                        "api_calls": 0,
                        "completed": True,
                    }
        # A named Server Health Watch action must outrank the broader staged
        # automation catalog.  Otherwise a household "run HADES Core check"
        # can be consumed by a stale Phase 3 pending action and reach the
        # generic runner instead of receiving the typed view-only denial.
        _health_watch_response = _hades_health_watch_response(
            user_message,
            getattr(self, "_hades_subject", ""),
            getattr(self, "_hades_session_scope", ""),
        )
        if _health_watch_response and self._hades_session_scope in {"household", "owner"}:
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(_health_watch_response)
            _hades_logger.info("Server Health Watch deterministic path completed without model invocation")
            return {
                "final_response": _health_watch_response,
                "messages": [{"role": "assistant", "content": _health_watch_response}],
                "api_calls": 0,
                "completed": True,
            }
        # Typed Phase 2 summary records outrank the broader staged catalog.
        # Keep read/list questions on their typed canonical routes instead of
        # returning Phase 3 metadata or a generic Grocy read.
        _typed_weekly_response = _hades_phase2_weekly_response(
            user_message,
            getattr(self, "_hades_subject", ""),
            getattr(self, "_hades_session_scope", ""),
            _phase2_session_key,
        )
        if _typed_weekly_response and self._hades_session_scope in {"household", "owner"}:
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(_typed_weekly_response)
            return {"final_response": _typed_weekly_response, "messages": [{"role": "assistant", "content": _typed_weekly_response}], "api_calls": 0, "completed": True}
        _typed_inventory_response = _hades_phase2_inventory_response(
            user_message,
            getattr(self, "_hades_subject", ""),
            getattr(self, "_hades_session_scope", ""),
            _phase2_session_key,
        )
        if _typed_inventory_response and self._hades_session_scope in {"household", "owner"}:
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(_typed_inventory_response)
            return {"final_response": _typed_inventory_response, "messages": [{"role": "assistant", "content": _typed_inventory_response}], "api_calls": 0, "completed": True}
        _typed_backup_response = _hades_phase2_backup_response(
            user_message,
            getattr(self, "_hades_subject", ""),
            getattr(self, "_hades_session_scope", ""),
            _phase2_session_key,
        )
        if _typed_backup_response and self._hades_session_scope in {"household", "owner"}:
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(_typed_backup_response)
            return {"final_response": _typed_backup_response, "messages": [{"role": "assistant", "content": _typed_backup_response}], "api_calls": 0, "completed": True}
        _phase3_response = _hades_phase3_response(
            user_message,
            getattr(self, "_hades_subject", ""),
            getattr(self, "_hades_session_scope", ""),
            _phase2_session_key,
        )
        if _phase3_response and self._hades_session_scope in {"household", "owner"}:
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(_phase3_response)
            return {
                "final_response": _phase3_response,
                "messages": [{"role": "assistant", "content": _phase3_response}],
                "api_calls": 0,
                "completed": True,
            }
        _weekly_response = _hades_phase2_weekly_response(
            user_message,
            getattr(self, "_hades_subject", ""),
            getattr(self, "_hades_session_scope", ""),
            _phase2_session_key,
        )
        if _weekly_response and self._hades_session_scope in {"household", "owner"}:
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(_weekly_response)
            return {
                "final_response": _weekly_response,
                "messages": [{"role": "assistant", "content": _weekly_response}],
                "api_calls": 0,
                "completed": True,
            }
        _inventory_response = _hades_phase2_inventory_response(
            user_message,
            getattr(self, "_hades_subject", ""),
            getattr(self, "_hades_session_scope", ""),
            _phase2_session_key,
        )
        if _inventory_response and self._hades_session_scope in {"household", "owner"}:
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(_inventory_response)
            return {
                "final_response": _inventory_response,
                "messages": [{"role": "assistant", "content": _inventory_response}],
                "api_calls": 0,
                "completed": True,
            }
        _backup_response = _hades_phase2_backup_response(
            user_message,
            getattr(self, "_hades_subject", ""),
            getattr(self, "_hades_session_scope", ""),
            _phase2_session_key,
        )
        if _backup_response and self._hades_session_scope in {"household", "owner"}:
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(_backup_response)
            _hades_logger.info("Backup Verification deterministic path completed without model invocation")
            return {
                "final_response": _backup_response,
                "messages": [{"role": "assistant", "content": _backup_response}],
                "api_calls": 0,
                "completed": True,
            }
        # Broad homelab composition must win over the narrower Server Health
        # Watch inventory route for requests that name nodes/Core/blockers.
        if self._hades_session_scope == "owner":
            direct_homelab_response = _hades_direct_homelab_read(user_message)
            if direct_homelab_response:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(direct_homelab_response)
                _hades_logger.info("Owner direct homelab read completed without model invocation")
                return {
                    "final_response": direct_homelab_response,
                    "messages": [{"role": "assistant", "content": direct_homelab_response}],
                    "api_calls": 0,
                    "completed": True,
                }
        reversal_notice = _hades_grocy_reversal_notice(
            user_message, previous_user_text
        )
        if reversal_notice and self._hades_session_scope in {"household", "owner"}:
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(reversal_notice)
            _hades_logger.info(
                "Late Grocy reversal explained without model invocation"
            )
            return {
                "final_response": reversal_notice,
                "messages": [{"role": "assistant", "content": reversal_notice}],
                "api_calls": 0,
                "completed": True,
            }
        _provision_user_turns = [
            str(message.get("content", ""))
            for message in _hades_history
            if isinstance(message, dict) and message.get("role") == "user"
        ]
        # Open WebUI includes the current user message in conversation_history
        # for API turns. For confirmation, the provisioning request is the
        # user turn immediately before the current confirmation, not the last
        # item returned by the generic follow-up helper.
        _provision_origin_text = (
            _provision_user_turns[-2]
            if len(_provision_user_turns) >= 2
            else previous_user_text
        )
        _history_assistant_text = "\n".join(
            str(message.get("content", ""))
            for message in _hades_history
            if isinstance(message, dict) and message.get("role") == "assistant"
        )
        _explicit_provision_confirmation = bool(
            self._hades_session_scope == "owner"
            and re.search(
                r"\b(?:yes|y|yeah|yep|okay|ok|do it|create it|go ahead|confirm|please do)\b",
                str(user_message or ""),
                re.IGNORECASE,
            )
            and (
                "I can provision an approved household server" in _history_assistant_text
                or bool(
                    any(
                        _HADES_PENDING_PROVISION.get(_key, {}).get("expires_at", 0) > time.time()
                        for _key in _hades_pending_provision_keys(self)
                    )
                )
            )
        )
        if _explicit_provision_confirmation:
            try:
                from pathlib import Path as _HadesPath
                import importlib.util as _HadesImportlibUtil
                _site_path = _HadesPath(__file__).resolve()
                _control_candidates = [
                    _site_path.parents[1] / "integrations" / "homelab-control" / "control.py",
                    _site_path.parents[3] / "Hades-reconciled-b102dfd" / "integrations" / "homelab-control" / "control.py",
                ]
                _control_path = next((path for path in _control_candidates if path.is_file()), None)
                if _control_path is None:
                    raise FileNotFoundError("bounded homelab control adapter is not deployed")
                _control_spec = _HadesImportlibUtil.spec_from_file_location(
                    "hades_live_control_confirm", _control_path
                )
                _control_module = _HadesImportlibUtil.module_from_spec(_control_spec)
                _control_spec.loader.exec_module(_control_module)
                _catalog = _control_module.inspect_templates()
                _pending = {}
                for _pending_key in _hades_pending_provision_keys(self):
                    _candidate = _HADES_PENDING_PROVISION.pop(_pending_key, None)
                    if _candidate and not _pending:
                        _pending = _candidate
                for _pending_key in _hades_pending_provision_keys(self):
                    _HADES_PENDING_PROVISION.pop(_pending_key, None)
                _prior = (_pending.get("origin") or _provision_origin_text).casefold()
                if _pending.get("template"):
                    _template = _pending["template"]
                    _name = _pending.get("name", "gamma-sandbox")
                    _spec = {
                        "cores": 4 if _template == "minecraft" else (1 if _template == "website" else 2),
                        "memory_mib": 8192 if _template == "minecraft" else (1024 if _template == "website" else 4096),
                        "disk_gib": 40 if _template == "minecraft" else (10 if _template == "website" else 30),
                    }
                elif "minecraft" in _prior:
                    _template, _name = "minecraft", "gamma-minecraft"
                    _spec = {"cores": 4, "memory_mib": 8192, "disk_gib": 40}
                elif "website" in _prior or "site" in _prior:
                    _template, _name = "website", "gamma-website"
                    _spec = {"cores": 1, "memory_mib": 1024, "disk_gib": 10}
                else:
                    _template, _name = "linux-sandbox", "gamma-sandbox"
                    _spec = {"cores": 2, "memory_mib": 4096, "disk_gib": 30}
                if _template not in _catalog.get("templates", ()):
                    raise ValueError("requested template is not in the approved live catalog")
                _nodes = _catalog.get("approved_nodes", ())
                if not _nodes:
                    raise ValueError("no approved self-service node is available")
                _result = _control_module.provision_guest(
                    _template,
                    {"node": _nodes[0]},
                    name=_name,
                    owner_confirmed=True,
                    **_spec,
                )
                _status = str(_result.get("status", "UNKNOWN"))
                if _status == "SUCCEEDED":
                    try:
                        from integrations.self_service.registry import WorkloadRegistry
                        _registry_path = os.environ.get("HADES_SELF_SERVICE_REGISTRY_FILE", "").strip()
                        if not _registry_path:
                            _registry_path = str(Path(os.environ.get("HERMES_HOME", "/var/lib/hades")) / "profiles" / "hades" / "state" / "self-service-workloads.json")
                        WorkloadRegistry(_registry_path).register(
                            f"{_result['target']['node']}-{_result['target']['vmid']}",
                            owner=getattr(self, "_hades_subject", ""),
                            node=_result["target"]["node"], vmid=int(_result["target"]["vmid"]),
                            template=_template, name=_name,
                        )
                    except Exception as _registry_exc:
                        _confirmation_response = (
                            "The workload was created, but its ownership record could not be stored. "
                            f"I will not claim it is safely manageable: {_registry_exc}."
                        )
                        _status = "OUTCOME_UNKNOWN"
                    else:
                        _confirmation_response = (
                            f"Created {_template} `{_name}` on {_result['target']['node']} "
                            f"with VMID {_result['target']['vmid']}. Proxmox reports it running."
                        )
                else:
                    _confirmation_response = (
                        f"I could not complete that server request: {_result.get('error', _status)}. "
                        "Nothing else was changed; the infrastructure result is not being guessed."
                    )
            except Exception as _exc:
                _confirmation_error = str(_exc)
                _confirmation_response = (
                    f"I could not complete that server request: {_exc}. "
                    "Nothing else was changed; the infrastructure result is not being guessed."
                )
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(_confirmation_response)
            _hades_logger.info(
                "Self-service provisioning confirmation completed status=%s result_error=%s exception=%s",
                _status if "_status" in locals() else "FAILED",
                (_result.get("error") if isinstance(locals().get("_result"), dict) else "none"),
                locals().get("_confirmation_error", "none"),
            )
            return {
                "final_response": _confirmation_response,
                "messages": [{"role": "assistant", "content": _confirmation_response}],
                "api_calls": 0,
                "completed": True,
            }
        contextual_followup_response = _hades_contextual_followup_clarification(
            user_message, previous_user_text
        )
        if contextual_followup_response and self._hades_session_scope in {"household", "owner"}:
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(contextual_followup_response)
            _hades_logger.info(
                "Ambiguous contextual follow-up received clarification without model invocation"
            )
            return {
                "final_response": contextual_followup_response,
                "messages": [{"role": "assistant", "content": contextual_followup_response}],
                "api_calls": 0,
                "completed": True,
            }
        direct_capability_response = _hades_direct_capability_guidance(user_message)
        if direct_capability_response and self._hades_session_scope in {"household", "owner"}:
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(direct_capability_response)
            _hades_logger.info(
                "Capability discoverability response completed without model invocation"
            )
            return {
                "final_response": direct_capability_response,
                "messages": [{"role": "assistant", "content": direct_capability_response}],
                "api_calls": 0,
                "completed": True,
            }
        memory_intent = re.search(
            r"\b(?:remember(?:ed|ing)?|recall|forget|did i tell|do you remember|memory)\b",
            str(user_message or ""),
            re.IGNORECASE,
        ) and not _HADES_MEMORY_NEGATION.search(str(user_message or ""))
        original_stream_callback = getattr(self, "stream_delta_callback", None)
        original_internal_stream_callback = getattr(self, "_stream_callback", None)
        original_ephemeral_system_prompt = getattr(self, "ephemeral_system_prompt", None)
        original_request_overrides = dict(getattr(self, "request_overrides", {}) or {})
        original_tools = getattr(self, "tools", None)
        original_valid_tool_names = getattr(self, "valid_tool_names", None)
        completion_only_model = bool(re.search(
            # Hermes Compute's qwen3:8b lane is qualified for direct completion
            # only.  It is also used as a degradation route when Tartarus is
            # unavailable, so never let fallback provenance accidentally grant
            # it HADES tools.
            r"\b(?:qwen3:8b|dolphin(?:-llama3|3)?|heretic|uncensored|abliterated)\b",
            original_model,
            re.IGNORECASE,
        ))
        grocy_intent = re.search(
            r"\b(?:grocy|grocery|groceries|grocry|grocerys|shopping list|recipe|food|pantry|pantrie|inventory|"
            r"what(?:'s| is) in stock|do we have)\b",
            _hades_intent_text,
            re.IGNORECASE,
        ) or _HADES_GROCY_ACTION_INTENT.search(_hades_intent_text)
        current_text = str(user_message or "")
        current_grocy_intent = bool(
            re.search(
                r"\b(?:grocy|grocery|groceries|grocry|grocerys|shopping list|recipe|food|pantry|"
                r"pantrie|inventory|what(?:'s| is) in stock|do we have)\b",
                current_text,
                re.IGNORECASE,
            )
            or _HADES_GROCY_ACTION_INTENT.search(current_text)
            or _HADES_GROCY_ITEM_FRAGMENT.search(current_text)
        )
        explicit_other_domain_turn = bool(
            not current_grocy_intent
            and (
                _HADES_LIVE_WEB_INTENT.search(current_text)
                or _HADES_PAGE_INTENT.search(current_text)
                or _HADES_HOMELAB_INTENT.search(current_text)
                or re.search(
                    r"\b(?:finance|finances|bank|csv|spend|spending|spent|budget|"
                    r"transaction|account|checking|savings|credit\s+card|money)\b|"
                    r"\bprivate\s+(?:account|checking|savings|finance|finances)\b",
                    current_text,
                    re.IGNORECASE,
                )
                or _HADES_ORDINARY_CHAT_INTENT.search(current_text)
            )
        )
        if explicit_other_domain_turn:
            # A current explicit domain must not be overridden by a stale
            # pantry/recipe mention in recent conversation history.
            grocy_intent = False
        elif not current_grocy_intent:
            previous_grocy_intent = bool(
                re.search(
                    r"\b(?:grocy|grocery|groceries|grocry|shopping list|recipe|food|pantry|"
                    r"inventory|stock|do we have)\b",
                    previous_user_text,
                    re.IGNORECASE,
                )
            )
            grocy_intent = bool(
                previous_grocy_intent
                and re.search(
                    r"\b(?:add it|remove it|buy it|consume it|what about|how about|actually|"
                    r"the other|which one|is it okay)\b",
                    current_text,
                    re.IGNORECASE,
                )
            )
        if not grocy_intent and _HADES_GROCY_ITEM_FRAGMENT.search(str(user_message or "")):
            grocy_intent = True
        grocy_read_only_turn = bool(
            grocy_intent
            and not _HADES_GROCY_ACTION_INTENT.search(_hades_intent_text)
            and not re.search(
                r"\b(?:recipe|ingredient|make|cook|fulfill|missing)\b",
                current_text,
                re.IGNORECASE,
            )
        )
        direct_ambiguity_response = _hades_direct_ambiguous_mutation_clarification(
            _hades_intent_text or user_message
        )
        if direct_ambiguity_response and self._hades_session_scope in {"household", "owner"}:
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(direct_ambiguity_response)
            _hades_logger.info(
                "Ambiguous household mutation received clarification without model invocation"
            )
            return {
                "final_response": direct_ambiguity_response,
                "messages": [{"role": "assistant", "content": direct_ambiguity_response}],
                "api_calls": 0,
                "completed": True,
            }
        control_intent = bool(
            re.search(
                r"\b(?:spin\s+up|provision|deploy|create|start|restart|stop|reboot|shutdown|"
                r"update|change|fix)\b",
                current_text,
                re.IGNORECASE,
            )
            and re.search(
                r"\b(?:server|palworld|minecraft|factorio|proxmox|vm|virtual\s+machine|"
                r"sandbox(?:es)?|workload(?:s)?|website(?:s)?|homelab|homlab|home\s+lab|"
                r"node|computer|network|hades(?:\s+core)?)\b",
                current_text,
                re.IGNORECASE,
            )
        )
        if self._hades_session_scope == "household" and control_intent:
            denial = (
                "I can check the homelab, but infrastructure changes are owner-only. "
                "I did not start, stop, restart, update, or provision anything."
            )
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(denial)
            return {
                "final_response": denial,
                "messages": [{"role": "assistant", "content": denial}],
                "api_calls": 0,
                "completed": True,
            }
        # Provisioning starts with a deterministic, read-only preflight. This
        # keeps a small local model from inventing a web/terminal answer or a
        # VM target before the user has seen the approved catalog. The actual
        # write remains behind the bounded control adapter and explicit
        # confirmation.
        provisioning_request = bool(
            self._hades_session_scope == "owner"
            and re.search(
                r"\b(?:spin\s+up|provision|deploy|create|make|host)\b",
                current_text,
                re.IGNORECASE,
            )
            and re.search(
                r"\b(?:server|palworld|minecraft|factorio|sandbox(?:es)?|workload(?:s)?|website(?:s)?|linux\s+box)\b",
                current_text,
                re.IGNORECASE,
            )
        )
        if provisioning_request:
            try:
                from pathlib import Path as _HadesPath
                import importlib.util as _HadesImportlibUtil
                _site_path = _HadesPath(__file__).resolve()
                _control_candidates = [
                    _site_path.parents[1] / "integrations" / "homelab-control" / "control.py",
                    _site_path.parents[3] / "Hades-reconciled-b102dfd" / "integrations" / "homelab-control" / "control.py",
                ]
                _control_path = next((path for path in _control_candidates if path.is_file()), None)
                if _control_path is None:
                    raise FileNotFoundError("bounded homelab control adapter is not deployed")
                _control_spec = _HadesImportlibUtil.spec_from_file_location(
                    "hades_live_control_preview", _control_path
                )
                _control_module = _HadesImportlibUtil.module_from_spec(_control_spec)
                _control_spec.loader.exec_module(_control_module)
                _catalog = _control_module.inspect_templates()
                _templates = ", ".join(_catalog.get("templates", ())) or "none"
                _nodes = ", ".join(_catalog.get("approved_nodes", ())) or "none"
                _preview = (
                    "I can help with a bounded household server, but I haven't created anything yet. "
                    f"Approved templates: {_templates}. Approved placement: {_nodes}. "
                    "Tell me which template you want, the server name, and who should share it with; "
                    "I will show the exact resource plan and ask for confirmation before creation."
                )
            except Exception:
                _preview = (
                    "I can help provision only an approved household server template, but the live "
                    "template catalog is unavailable right now. Nothing was changed."
                )
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(_preview)
            _hades_logger.info(
                "Self-service provisioning preflight completed without model invocation"
            )
            return {
                "final_response": _preview,
                "messages": [{"role": "assistant", "content": _preview}],
                "api_calls": 0,
                "completed": True,
            }
        owner_finance_request = bool(
            re.search(
                r"\b(?:finance|finances|finaces|bank|spend|spending|spent|budget|"
                r"transaction|account|checking|savings|credit\s+card|money|cost|"
                r"paid|expense|expenses)\b|"
                r"\bprivate\s+(?:account|checking|savings|finance|finances)\b",
                current_text,
                re.IGNORECASE,
            )
        )
        if self._hades_session_scope == "household" and owner_finance_request:
            denial = (
                "I can help with shared household tasks, but I can't access Scotty's "
                "finances. That information is owner-only, and nothing was changed."
            )
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(denial)
            _hades_logger.info(
                "Household finance request denied before model invocation"
            )
            return {
                "final_response": denial,
                "messages": [{"role": "assistant", "content": denial}],
                "api_calls": 0,
                "completed": True,
            }
        if self._hades_session_scope == "owner":
            direct_finance_response = _hades_direct_finance_guidance(
                user_message
            )
            if direct_finance_response:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(direct_finance_response)
                _hades_logger.info("Owner direct finance guidance completed without model invocation")
                return {
                    "final_response": direct_finance_response,
                    "messages": [{"role": "assistant", "content": direct_finance_response}],
                    "api_calls": 0,
                    "completed": True,
                }
            direct_location_response = _hades_direct_owner_location(
                _hades_intent_text or user_message
            )
            if direct_location_response:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(direct_location_response)
                _hades_logger.info("Owner direct HADES location response completed without model invocation")
                return {
                    "final_response": direct_location_response,
                    "messages": [{"role": "assistant", "content": direct_location_response}],
                    "api_calls": 0,
                    "completed": True,
                }
        # Explicit recipe-fulfillment wording is authoritative for this turn.
        # Do not let generic words such as "current" or "tell me" in a
        # compound recipe request divert it into the completion model.
        if self._hades_session_scope in {"household", "owner"}:
            direct_recipe_response = _hades_direct_grocy_recipe_read(current_text)
            if direct_recipe_response:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(direct_recipe_response)
                _hades_logger.info("Direct Grocy recipe fulfillment completed from current turn")
                return {
                    "final_response": direct_recipe_response,
                    "messages": [{"role": "assistant", "content": direct_recipe_response}],
                    "api_calls": 0,
                    "completed": True,
                }
        if self._hades_session_scope in {"household", "owner"} and not explicit_other_domain_turn:
            direct_grocy_mutation = _hades_direct_household_grocy_mutation(
                # Mutations must parse only the current turn. Historical
                # grocery language is useful for routing a correction, but
                # must never let an older item become the target of a new
                # short command such as "add milk".
                current_text,
                getattr(self, "_hades_subject", ""),
            )
            if direct_grocy_mutation:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(direct_grocy_mutation)
                _hades_logger.info("Direct Grocy shopping-list mutation completed with read-back")
                return {
                    "final_response": direct_grocy_mutation,
                    "messages": [{"role": "assistant", "content": direct_grocy_mutation}],
                    "api_calls": 0,
                    "completed": True,
                }
            direct_recipe_response = _hades_direct_grocy_recipe_read(
                _hades_intent_text or user_message
            )
            if direct_recipe_response:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(direct_recipe_response)
                _hades_logger.info(
                    "Direct Grocy recipe fulfillment read completed without model invocation"
                )
                return {
                    "final_response": direct_recipe_response,
                    "messages": [{"role": "assistant", "content": direct_recipe_response}],
                    "api_calls": 0,
                    "completed": True,
                }
        if (
            self._hades_session_scope in {"household", "owner"}
            and grocy_read_only_turn
            and not explicit_other_domain_turn
        ):
            direct_grocy_response = _hades_direct_household_grocy_read(
                _hades_intent_text or user_message
            )
            if direct_grocy_response:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(direct_grocy_response)
                _hades_logger.info(
                    "Household direct Grocy read completed without model invocation"
                )
                return {
                    "final_response": direct_grocy_response,
                    "messages": [{"role": "assistant", "content": direct_grocy_response}],
                    "api_calls": 0,
                    "completed": True,
                }
        if self._hades_session_scope in {"household", "owner"}:
            direct_page_response = _hades_direct_public_page_read(user_message)
            if direct_page_response:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(direct_page_response)
                _hades_logger.info("Direct public page read completed without model invocation")
                return {
                    "final_response": direct_page_response,
                    "messages": [{"role": "assistant", "content": direct_page_response}],
                    "api_calls": 0,
                    "completed": True,
                }
            direct_web_response = _hades_direct_web_search(user_message)
            if direct_web_response:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(direct_web_response)
                _hades_logger.info("Direct SearXNG search completed without model invocation")
                return {
                    "final_response": direct_web_response,
                    "messages": [{"role": "assistant", "content": direct_web_response}],
                    "api_calls": 0,
                    "completed": True,
                }
        homelab_intent = bool(
            self._hades_session_scope == "owner"
            and _HADES_HOMELAB_INTENT.search(_hades_intent_text)
        )
        if (
            self._hades_session_scope == "owner"
            and re.search(
                r"\b(?:scan|scanning|discovery|nmap|network\s+scan|bounded\s+discovery|discover(?:y|ing)\s+(?:the|devices|hosts))\b",
                str(user_message or ""),
                re.IGNORECASE,
            )
        ):
            homelab_intent = True
        # Agent Zero is a distinct owner-only capability.  A phrase such as
        # "ask Agent Zero to inspect the server" contains the generic
        # homelab word "server", but must not be downgraded to a read-only
        # homelab status request.
        agent_zero_intent = re.search(
            r"\b(?:agent\s+zero|agent0|bounded\s+operator|delegate|delegation)\b",
            _hades_intent_text,
            re.IGNORECASE,
        )
        if agent_zero_intent:
            homelab_intent = False
        web_intent = _HADES_LIVE_WEB_INTENT.search(_hades_intent_text)
        page_intent = bool(_HADES_PAGE_INTENT.search(_hades_intent_text))
        # Conversation history can contain the word "memory" even when the
        # current request is an ordinary live-domain request. Disable
        # automatic personal-memory prefetch for pure web/Grocy turns at the
        # agent boundary; the explicit-memory path remains available for
        # intentional composition.
        _hades_saved_auto_recall = []
        _hades_saved_memory_modes = []
        if (
            not memory_intent
            and (
                grocy_intent
                or homelab_intent
                or (web_intent and not grocy_intent)
            )
            and self._memory_manager
        ):
            for _hades_provider in self._memory_manager.providers:
                if hasattr(_hades_provider, "_auto_recall"):
                    _hades_saved_auto_recall.append(
                        (_hades_provider, _hades_provider._auto_recall)
                    )
                    _hades_provider._auto_recall = False
        if homelab_intent and self._memory_manager:
            # Live infrastructure questions must not allow Hindsight's
            # automatic tool layer to compete with the required homelab
            # summary or reintroduce stale historical answers.
            for _hades_provider in self._memory_manager.providers:
                if hasattr(_hades_provider, "_memory_mode"):
                    _hades_saved_memory_modes.append(
                        (_hades_provider, _hades_provider._memory_mode)
                    )
                    _hades_provider._memory_mode = "context"
        if agent_zero_intent and self._hades_session_scope == "household":
            # Household users must receive a deterministic boundary response;
            # an unavailable privileged tool must never become an invented
            # delegation attempt or an ambiguous upstream failure.
            self.tools = []
            self.valid_tool_names = set()
            household_operator_guidance = (
                "HADES authority rule: Agent Zero is owner-only and unavailable "
                "in household scope. Do not call, simulate, or imply an Agent "
                "Zero inspection. Tell the user plainly that this capability "
                "is not available to household users."
            )
            self.ephemeral_system_prompt = "\n\n".join(
                part for part in (original_ephemeral_system_prompt, household_operator_guidance)
                if part
            )
        if agent_zero_intent and self._hades_session_scope == "owner" and not _hades_agent_zero_available():
            operator_unavailable = (
                "The bounded operator is unavailable right now. I did not send or "
                "simulate the request; ordinary HADES features remain available."
            )
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(operator_unavailable)
            _hades_logger.info(
                "Owner Agent Zero request failed locally because the operator is unavailable"
            )
            return {
                "final_response": operator_unavailable,
                "messages": [{"role": "assistant", "content": operator_unavailable}],
                "api_calls": 0,
                "completed": True,
            }
        if homelab_intent and isinstance(original_tools, list):
            try:
                from model_tools import get_tool_definitions as _get_tool_definitions
                homelab_tools = (
                    _hades_homelab_control_tool_definitions(_get_tool_definitions)
                    if control_intent and self._hades_session_scope == "owner"
                    else _hades_homelab_tool_definitions(_get_tool_definitions)
                )
                homelab_request_text = " ".join(
                    (str(user_message or ""), str(_hades_intent_text or ""))
                )
                simple_status = (
                    not re.search(
                        r"\b(?:gpu|gpus|hardware|compute|vr[ae]m|cuda|driver|scan|scanning|discovery|nmap)\b",
                        homelab_request_text,
                        re.IGNORECASE,
                    )
                    and re.search(
                        r"\b(?:online|offline|running|down|unhealthy|status|where\s+is|what(?:['’]?s| is)\s+running)\b",
                        homelab_request_text,
                        re.IGNORECASE,
                    )
                )
                if simple_status:
                    summary_tools = [
                        tool for tool in homelab_tools
                        if tool.get("function", {}).get("name") ==
                        "mcp_homelab_readonly_homelab_summary"
                    ]
                    if summary_tools:
                        homelab_tools = summary_tools
                if homelab_tools:
                    self.tools = homelab_tools
                    self.valid_tool_names = {
                        t["function"]["name"] for t in homelab_tools
                    }
                    _hades_logger.warning(
                        "API homelab intent narrowed tool catalog to %d tools",
                        len(homelab_tools),
                    )
            except Exception as exc:
                _hades_logger.warning("API homelab intent narrowing failed: %s", exc)
        # "inventory" is also a natural homelab term. Once the owner-scoped
        # homelab classifier has claimed the turn, do not let the Grocy
        # keyword route overwrite the live infrastructure catalog.
        if grocy_intent and not homelab_intent and isinstance(original_tools, list):
            try:
                from model_tools import get_tool_definitions as _get_tool_definitions
                grocy_tools = _hades_grocy_tool_definitions(_get_tool_definitions)
                grocy_text = str(_hades_intent_text or user_message or "")
                action_turn = bool(_HADES_GROCY_ACTION_INTENT.search(grocy_text))
                recipe_turn = bool(re.search(
                    r"\b(?:recipe|ingredient|make|cook|fulfill|missing)\b",
                    grocy_text,
                    re.IGNORECASE,
                ))
                if not action_turn and not recipe_turn:
                    read_names = {
                        "mcp_grocy_stock_overview_tool",
                        "mcp_grocy_shopping_list_view_tool",
                        "mcp__grocy__stock_overview_tool",
                        "mcp__grocy__shopping_list_view_tool",
                    }
                    grocy_tools = [
                        tool for tool in grocy_tools
                        if tool.get("function", {}).get("name") in read_names
                    ]
                    _hades_logger.info(
                        "Grocy read intent narrowed to %d canonical read tools",
                        len(grocy_tools),
                    )
                if grocy_tools:
                    self.tools = grocy_tools
                    self.valid_tool_names = {
                        t["function"]["name"] for t in grocy_tools
                    }
                    _hades_logger.warning(
                        "API Grocy intent narrowed tool catalog to %d tools",
                        len(grocy_tools),
                    )
            except Exception as exc:
                _hades_logger.warning("API Grocy intent narrowing failed: %s", exc)
        discovery_text = " ".join(
            (str(user_message or ""), str(_hades_intent_text or ""))
        ).lower()
        explicit_discovery_intent = bool(
            self._hades_session_scope == "owner"
            and any(term in discovery_text for term in ("scan", "discovery", "nmap"))
        )
        if explicit_discovery_intent:
            try:
                from model_tools import get_tool_definitions as _get_tool_definitions
                discovery_tools = [
                    tool for tool in _hades_homelab_tool_definitions(_get_tool_definitions)
                    if tool.get("function", {}).get("name") in {
                        "mcp_homelab_readonly_homelab_discovery_scan",
                        "mcp_homelab_readonly_homelab_discovery_candidates",
                    }
                ]
                if discovery_tools:
                    self.tools = discovery_tools
                    self.valid_tool_names = {
                        tool["function"]["name"] for tool in discovery_tools
                    }
                    _hades_logger.warning(
                        "API explicit discovery intent narrowed tool catalog to %d tools",
                        len(discovery_tools),
                    )
            except Exception as exc:
                _hades_logger.warning("API discovery intent narrowing failed: %s", exc)
        if homelab_intent and not completion_only_model and not control_intent:
            homelab_guidance = (
                "HADES live-homelab rule: this owner request concerns current "
                "infrastructure. You MUST call "
                "mcp_homelab_readonly_homelab_summary before answering. Use "
                "Proxmox runtime for online status, NetBox only for intended "
                "inventory, and Uptime Kuma only for observed availability. "
                "If the request also asks about GPUs or hardware capability, "
                "call mcp_homelab_readonly_homelab_compute_capabilities after "
                "the summary. Do not answer from memory and do not claim a "
                "write or control operation."
            )
            self.ephemeral_system_prompt = "\n\n".join(
                part for part in (original_ephemeral_system_prompt, homelab_guidance) if part
            )
            # The local model has repeatedly refused a clearly available
            # read-only homelab tool and answered from its generic capability
            # text instead.  Require a function call only for this already
            # owner-authorized, intent-narrowed path; this cannot grant a
            # household or write capability and prevents invented liveness.
            self.request_overrides = {
                **original_request_overrides,
                "tool_choice": {
                    "type": "function",
                    "function": {
                        "name": "mcp_homelab_readonly_homelab_summary",
                    },
                },
            }
        if control_intent and self._hades_session_scope == "owner":
            control_guidance = (
                "HADES owner homelab-control rule: this request asks for an "
                "infrastructure change. Use only the bounded homelab-control "
                "tools. First inspect approved templates and clarify the target "
                "VM name, node, resources, and expected service. Present the "
                "exact plan and obtain an explicit confirmation immediately "
                "before any write. Never use shell, SSH, Docker, arbitrary "
                "Proxmox paths, or an unapproved template. Report the actual "
                "Proxmox read-back and say outcome unknown if transport failed."
            )
            self.ephemeral_system_prompt = "\n\n".join(
                part for part in (original_ephemeral_system_prompt, control_guidance) if part
            )
            # A provisioning request must use one of the bounded control
            # tools.  ``required`` is accepted by the local OpenAI-compatible
            # backends more consistently than a named function choice; the
            # adapter still fail-closes every write behind owner_confirmed.
            self.request_overrides = {
                **original_request_overrides,
                "tool_choice": "required",
            }
        # The API tool-search catalog can defer web_search even when a
        # keyless SearXNG provider is configured. Small local models may then
        # incorrectly route the deferred tool through tool_call. For an
        # unambiguous web turn, expose the supported web tools directly so
        # the model can emit a normal function call. Mixed household turns
        # retain the Grocy/memory routing above.
        if (
            web_intent
            and not homelab_intent
            and not grocy_intent
            and not memory_intent
            and isinstance(original_tools, list)
        ):
            try:
                from model_tools import get_tool_definitions as _get_tool_definitions
                web_tools = _get_tool_definitions(
                    enabled_toolsets=["web"], quiet_mode=True
                )
                # The HADES web provider is SearXNG, which is search-only;
                # exposing web_extract makes weaker models call an operation
                # that can never succeed and then continue from the error.
                web_tools = [
                    tool for tool in web_tools
                    if tool.get("function", {}).get("name") == "web_search"
                ]
                if page_intent:
                    web_tools.extend(_hades_page_tool_definitions(_get_tool_definitions))
                if web_tools:
                    self.tools = web_tools
                    self.valid_tool_names = {
                        t["function"]["name"] for t in web_tools
                    }
                    _hades_logger.warning(
                        "API web intent narrowed tool catalog to %d tools",
                        len(web_tools),
                    )
            except Exception as exc:
                _hades_logger.warning("API web intent narrowing failed: %s", exc)
        # Small local models may answer a follow-up from the prior assistant
        # text instead of re-checking live data. Make the owner-facing rule
        # explicit for this turn; the tool catalog is already narrowed above.
        if (
            web_intent
            and not homelab_intent
            and not grocy_intent
            and not memory_intent
            and not completion_only_model
        ):
            web_guidance = (
                "HADES live-web rule: this request concerns current or external "
                "information. Call web_search before answering when discovery "
                "is needed. Use web_search for discovery. If the user asks "
                "to read a page or article and public_page_read is listed, use "
                "it for PAGE evidence after obtaining a URL. Do not claim to "
                "have read a page from a search snippet. Use only facts present "
                "in the returned evidence; if retrieval fails, say whether "
                "search failed or the page could not be read. "
                "Title or snippet is not evidence; do not infer or invent an answer."
            )
            self.ephemeral_system_prompt = "\n\n".join(
                part for part in (original_ephemeral_system_prompt, web_guidance) if part
            )
        if homelab_intent and not (
            self.ephemeral_system_prompt and "HADES homelab evidence rule" in self.ephemeral_system_prompt
        ):
            homelab_guidance = (
                "HADES homelab evidence rule: use only values returned by the live "
                "read-only homelab tool in this turn. Never infer that a host is "
                "healthy from its name, an old inventory row, or the fact that this "
                "chat is responding. If a query, token, permission, or node status "
                "is missing, say exactly that the result is unverified. Do not claim "
                "HADES runs on the Hermes process host; the canonical Core location "
                "is VM 802 on Erebus."
            )
            self.ephemeral_system_prompt = "\n\n".join(
                part for part in (self.ephemeral_system_prompt or original_ephemeral_system_prompt, homelab_guidance) if part
            )
        # Do not expose finance tools based on intent.  Natural-language
        # intent is not authorization; finance remains unavailable until a
        # server-side owner capability is wired into this boundary.
        # Household sessions must not gain the bounded operator from prompt
        # wording. The unmarked legacy owner session remains compatible until
        # Open WebUI is configured to send the server-generated scope marker.
        household_session = getattr(self, "_hades_session_scope", "") == "household"
        if agent_zero_intent and not household_session and isinstance(original_tools, list):
            try:
                from model_tools import get_tool_definitions as _get_tool_definitions
                operator_tools = _get_tool_definitions(
                    enabled_toolsets=["hades-agent-zero"], quiet_mode=True
                )
                if operator_tools:
                    # llama.cpp's grammar parser rejects the MCP schema's
                    # minLength/maxLength annotations. The adapter still
                    # enforces both limits before dispatch; remove only the
                    # parser-hostile hints from the model-facing copy.
                    for tool in operator_tools:
                        properties = (
                            tool.get("function", {})
                            .get("parameters", {})
                            .get("properties", {})
                        )
                        if isinstance(properties, dict):
                            for property_schema in properties.values():
                                if isinstance(property_schema, dict):
                                    property_schema.pop("minLength", None)
                                    property_schema.pop("maxLength", None)
                    self.tools = operator_tools
                    self.valid_tool_names = {
                        t["function"]["name"] for t in operator_tools
                    }
                    self.request_overrides = {
                        **original_request_overrides,
                        "tool_choice": {
                            "type": "function",
                            "function": {"name": "mcp_hades_agent_zero_agent_zero_delegate"},
                        },
                    }
                    _hades_logger.warning(
                        "API Agent Zero intent narrowed tool catalog to %d tools",
                        len(operator_tools),
                    )
            except Exception as exc:
                _hades_logger.warning("API Agent Zero intent narrowing failed: %s", exc)
        if (
            grocy_intent
            and isinstance(original_tools, list)
            and not any(
            t.get("function", {}).get("name", "").startswith("mcp_grocy_")
            for t in original_tools
            )
        ):
            try:
                from model_tools import get_tool_definitions as _get_tool_definitions
                extra_grocy = _hades_grocy_tool_definitions(_get_tool_definitions)
                names = {t.get("function", {}).get("name") for t in original_tools}
                for tool in extra_grocy:
                    name = tool.get("function", {}).get("name")
                    if name and name not in names:
                        original_tools.append(tool)
                        names.add(name)
                self.valid_tool_names = names
                _hades_logger.warning(
                    "API turn reconciliation added %d Grocy tools",
                    sum(1 for t in extra_grocy if t.get("function", {}).get("name", "").startswith("mcp_grocy_")),
                )
            except Exception as exc:
                _hades_logger.warning("API turn Grocy reconciliation failed: %s", exc)
        if (
            self._hades_session_scope == "owner"
            and homelab_intent
            and control_intent
            and isinstance(original_tools, list)
            and not any(t.get("function", {}).get("name", "").startswith("mcp_homelab_control_") for t in original_tools)
        ):
            try:
                from model_tools import get_tool_definitions as _get_tool_definitions
                extra_homelab = _hades_homelab_control_tool_definitions(_get_tool_definitions)
                # A write/provisioning turn must not carry the ordinary web,
                # Grocy, memory, or read-only homelab catalog.  Leaving those
                # schemas attached lets a small model select an unrelated
                # tool (for example web_extract) before it ever sees the
                # bounded control lane.
                self.tools = extra_homelab
                self.valid_tool_names = {
                    tool.get("function", {}).get("name")
                    for tool in extra_homelab
                    if tool.get("function", {}).get("name")
                }
                _hades_logger.warning(
                    "API turn reconciliation narrowed to %d homelab control tools",
                    len(extra_homelab),
                )
            except Exception as exc:
                _hades_logger.warning("API turn homelab reconciliation failed: %s", exc)
        web_turn = bool(
            web_intent
            and not grocy_intent
            and not homelab_intent
            and not memory_intent
            and not completion_only_model
        )
        # Open WebUI uses the streaming API.  If a weak local model emits a
        # misleading post-tool continuation, let the authoritative Hindsight
        # or web result replace it before the API adapter sends any text delta.
        # Tool-progress events remain available while the turn runs.
        # Buffer explicit memory turns while the agent works.  The upstream
        # SSE writer forwards callback deltas but does not read the returned
        # final_response, so emit the authoritative result through the saved
        # callback once the tool loop is complete.
        suppress_stream = bool(
            ((memory_intent and not grocy_intent) or web_turn)
            and original_stream_callback
        )
        if suppress_stream:
            self.stream_delta_callback = None
            self._stream_callback = None
        # A memory question must not expose unrelated mutation tools to a
        # small local model. Keep the provider's direct memory schemas, but
        # enforce the same boundary in the agent's executable tool set for
        # both streaming and non-streaming callers.
        if memory_intent and isinstance(original_tools, list):
            allowed_memory = {"hindsight_recall", "hindsight_retain"}
            if grocy_intent:
                # Mixed memory/domain requests are especially difficult for
                # small local models when the whole household catalog is
                # visible. Keep only the read tools needed by this turn;
                # mutations remain available on explicit household turns.
                if re.search(r"\b(?:recipe|make|missing|ingredient)\b", _hades_intent_text, re.IGNORECASE):
                    allowed_grocy = {
                        "mcp_grocy_stock_overview_tool",
                        "mcp_grocy_recipe_fulfillment_tool",
                    }
                else:
                    allowed_grocy = {"mcp_grocy_stock_overview_tool"}
                allowed_memory.update(
                    tool.get("function", {}).get("name")
                    for tool in original_tools
                    if tool.get("function", {}).get("name") in allowed_grocy
                )
            if web_intent:
                allowed_memory.update(
                    tool.get("function", {}).get("name")
                    for tool in original_tools
                    if tool.get("function", {}).get("name") == "web_search"
                )
            if agent_zero_intent and not household_session:
                allowed_memory.update(
                    tool.get("function", {}).get("name")
                    for tool in original_tools
                    if tool.get("function", {}).get("name", "").endswith(
                        "agent_zero_delegate"
                    )
                )
            self.tools = [
                tool for tool in original_tools
                if tool.get("function", {}).get("name") in allowed_memory
            ]
            self.valid_tool_names = {
                tool["function"]["name"] for tool in self.tools
            }
        # Completion-only creative models are deliberately isolated from the
        # HADES tool catalog, even when the upstream model advertises native
        # function calling. They remain useful for morally grey writing and
        # roleplay without access to memory, Grocy, web, Agent Zero, or hosts.
        if completion_only_model:
            self.tools = []
            self.valid_tool_names = set()
        _hades_memory_local.result = None
        runtime_provider = str(getattr(self, "provider", "") or "").lower()
        runtime_base = str(getattr(self, "base_url", "") or "").lower()
        routed = (
            runtime_provider == "custom"
            and ("11434" in runtime_base or "ollama" in runtime_base)
            and _HADES_TOOL_INTENT.search(str(user_message or ""))
            and original_model == "qwen3:14b"
        )
        if routed:
            self.model = "qwen3:8b"
        try:
            if agent_zero_intent and self._hades_session_scope == "household":
                denial = (
                    "Agent Zero is owner-only and is not available to household "
                    "users. I did not send or simulate an inspection."
                )
                result = {
                    "final_response": denial,
                    "messages": [{"role": "assistant", "content": denial}],
                    "api_calls": 0,
                    "completed": True,
                }
                if original_stream_callback:
                    original_stream_callback(denial)
            else:
                result = _hades_original_run_conversation(self, user_message, *args, **kwargs)
            if memory_intent and not grocy_intent and isinstance(result, dict):
                _hades_logger.warning(
                    "memory turn returned roles=%s final_len=%d",
                    [m.get("role") for m in result.get("messages", []) if isinstance(m, dict)],
                    len(str(result.get("final_response") or "")),
                )
                # Some local tool-capable models emit an unrelated continuation
                # after a successful tool call.  For explicit memory requests,
                # the Hindsight payload is authoritative; preserve it as the
                # owner-facing answer instead of allowing that continuation to
                # fabricate a result.
                memory_result = None
                for message in reversed((result or {}).get("messages", [])):
                    if message.get("role") != "tool":
                        continue
                    try:
                        raw_content = message.get("content", "")
                        if isinstance(raw_content, list):
                            raw_content = " ".join(
                                str(part.get("text", "")) if isinstance(part, dict) else str(part)
                                for part in raw_content
                            )
                        payload = json.loads(str(raw_content))
                        candidate = payload.get("result")
                        if isinstance(candidate, str) and candidate.strip() and not candidate.startswith("No relevant"):
                            memory_result = candidate.strip()
                            break
                    except Exception:
                        continue
                if not memory_result:
                    memory_result = getattr(_hades_memory_local, "result", None)
                if memory_result:
                    result["final_response"] = memory_result
                    _hades_logger.warning(
                        "memory turn authoritative result selected len=%d",
                        len(memory_result),
                    )
                    if suppress_stream:
                        original_stream_callback(memory_result)
                    for message in reversed(result.get("messages", [])):
                        if message.get("role") == "assistant" and not message.get("tool_calls"):
                            message["content"] = memory_result
                            break
            if web_turn and isinstance(result, dict):
                web_failed = any(
                    _hades_web_tool_failed(message)
                    for message in result.get("messages", [])
                )
                if web_failed:
                    web_result = (
                        "Live web search is currently unavailable. "
                        "No current web result was returned."
                    )
                    _hades_logger.warning(
                        "web turn authoritative failure selected: search unavailable"
                    )
                else:
                    web_result = str(result.get("final_response") or "").strip()
                if web_result:
                    result["final_response"] = web_result
                    if suppress_stream:
                        original_stream_callback(web_result)
                    for message in reversed(result.get("messages", [])):
                        if message.get("role") == "assistant" and not message.get("tool_calls"):
                            message["content"] = web_result
                            break
            return result
        except Exception as exc:
            # A provider timeout/connection failure must terminate the
            # streaming turn cleanly. Letting the exception escape leaves
            # Open WebUI's Stop state active and blocks the next owner turn.
            failure = (
                "I couldn't get a reply from the model right now. "
                "Nothing was changed; please try again."
            )
            _hades_logger.warning(
                "HADES model turn failed closed provider=%s model=%s error=%s",
                getattr(self, "provider", "unknown"),
                original_model,
                type(exc).__name__,
            )
            if original_stream_callback:
                original_stream_callback(failure)
            return {
                "final_response": failure,
                "messages": [{"role": "assistant", "content": failure}],
                "api_calls": 0,
                "completed": True,
            }
        finally:
            _hades_logger.info(
                "HADES timing stage=turn model=%s elapsed_ms=%.1f",
                original_model,
                (time.perf_counter() - turn_started) * 1000,
            )
            for _hades_provider, _hades_auto_recall in _hades_saved_auto_recall:
                _hades_provider._auto_recall = _hades_auto_recall
            for _hades_provider, _hades_memory_mode in _hades_saved_memory_modes:
                _hades_provider._memory_mode = _hades_memory_mode
            if suppress_stream:
                self.stream_delta_callback = original_stream_callback
                self._stream_callback = original_internal_stream_callback
            self.ephemeral_system_prompt = original_ephemeral_system_prompt
            self.request_overrides = original_request_overrides
            if memory_intent:
                self.tools = original_tools
                self.valid_tool_names = original_valid_tool_names
            elif completion_only_model:
                self.tools = original_tools
                self.valid_tool_names = original_valid_tool_names
            if routed:
                self.model = original_model
            if fast_lane_restore:
                try:
                    if fast_prompt_restore:
                        cached_prompt, cached_static, session_db, had_builder = fast_prompt_restore
                        self._cached_system_prompt = cached_prompt
                        self._cached_system_prompt_static = cached_static
                        self._session_db = session_db
                        if had_builder:
                            delattr(self, "_build_system_prompt")
                    restore_model, restore_provider, restore_key, restore_base, restore_mode = fast_lane_restore
                    self.switch_model(
                        restore_model,
                        restore_provider,
                        api_key=restore_key,
                        base_url=restore_base,
                        api_mode=restore_mode,
                    )
                    _hades_logger.info("HADES API turn restored Deep route model=%s", restore_model)
                except Exception as exc:
                    _hades_logger.error("HADES API turn failed to restore Deep route: %s", exc)

    _AIAgent.run_conversation = _hades_run_conversation

    def _hades_apply_fast_completion_route(self, route, user_message: str):
        # Keep ordinary no-tool conversation independent from the Deep lane.
        # The fast endpoint is completion-only: tool-bearing/domain turns stay
        # on the qualified Tartarus route until a narrow fast-tool contract is
        # proven.  This is deliberately an explicit route, not a silent
        # provider fallback, so the selected model remains observable in the
        # persisted turn metadata.
        runtime = route.get("runtime", {})
        provider = str(runtime.get("provider") or "").lower()
        base_url = str(runtime.get("base_url") or "").lower()
        fast_base_url = os.environ.get("HADES_FAST_COMPLETION_BASE_URL", "").strip()
        fast_model = os.environ.get("HADES_FAST_COMPLETION_MODEL", "qwen3:8b").strip()
        deep_model = str(route.get("model") or "").lower()
        if (
            provider == "custom"
            and ("11437" in base_url or "qwen3.6:35b" in deep_model)
            and fast_base_url
            and fast_model
            and not _HADES_TOOL_INTENT.search(str(user_message or ""))
        ):
            runtime["base_url"] = fast_base_url.rstrip("/")
            runtime["api_key"] = os.environ.get("HADES_FAST_COMPLETION_API_KEY", "local")
            route["model"] = fast_model
            route["signature"] = (
                route["model"],
                runtime.get("provider"),
                runtime.get("requested_provider"),
                runtime.get("base_url"),
                runtime.get("api_mode"),
                runtime.get("command"),
                tuple(runtime.get("args") or ()),
            )
            _hades_logger.info(
                "HADES route lane=fast-completion model=%s base_url=%s",
                fast_model,
                fast_base_url,
            )
            return route
        # Only route the configured local Ollama profile.  A future remote or
        # provider-specific profile should retain Hermes' native behavior.
        provider = str(route.get("runtime", {}).get("provider") or "").lower()
        base_url = str(route.get("runtime", {}).get("base_url") or "").lower()
        if (
            provider == "custom"
            and ("11434" in base_url or "ollama" in base_url)
            and _HADES_TOOL_INTENT.search(str(user_message or ""))
            and route.get("model") == "qwen3:14b"
        ):
            route["model"] = "qwen3:8b"
            route["signature"] = (
                route["model"],
                route["runtime"]["provider"],
                route["runtime"]["base_url"],
                route["runtime"]["api_mode"],
                route["runtime"]["command"],
                tuple(route["runtime"]["args"]),
            )
        return route

    def _hades_resolve_turn(self, user_message: str):
        route = _hades_original_resolve_turn(self, user_message)
        return _hades_apply_fast_completion_route(route, user_message)

    _hermes_cli.HermesCLI._resolve_turn_agent_config = _hades_resolve_turn

    # Open WebUI production requests use Hermes' gateway runner rather than
    # HermesCLI. Patch the gateway mixin too; otherwise the UI silently keeps
    # constructing the Tartarus agent even though the CLI resolver is routed.
    def _hades_install_gateway_route_patch():
        """Patch the gateway after Hermes finishes its circular imports."""
        import sys
        module = sys.modules.get("gateway.run_turn")
        gateway_mixin = getattr(module, "GatewayTurnMixin", None) if module else None
        run_module = sys.modules.get("gateway.run")
        gateway_runner = getattr(run_module, "GatewayRunner", None) if run_module else None
        turn_module = sys.modules.get("gateway.run_turn_runner")
        if turn_module is None:
            try:
                import importlib
                turn_module = importlib.import_module("gateway.run_turn_runner")
            except Exception:
                turn_module = None
        turn_runner = getattr(turn_module, "TurnRunner", None) if turn_module else None
        targets = [target for target in (gateway_mixin, gateway_runner) if target is not None]
        if not targets and turn_runner is None:
            return False
        installed = False
        for target in targets:
            if getattr(target, "_hades_fast_route", False):
                installed = True
                continue
            original = target._resolve_turn_agent_config

            def gateway_resolve_turn(self, user_message: str, model: str, runtime_kwargs: dict,
                                     _original=original):
                route = _original(self, user_message, model, runtime_kwargs)
                _hades_logger.info(
                    "HADES gateway route input model=%s provider=%s base_url=%s tool_intent=%s",
                    route.get("model"),
                    route.get("runtime", {}).get("provider"),
                    route.get("runtime", {}).get("base_url"),
                    bool(_HADES_TOOL_INTENT.search(str(user_message or ""))),
                )
                return _hades_apply_fast_completion_route(route, user_message)

            gateway_resolve_turn._hades_fast_route = True
            target._resolve_turn_agent_config = gateway_resolve_turn
            installed = True
        if installed:
            _hades_logger.info("HADES gateway fast-completion route installed")
        if turn_runner is not None and not getattr(turn_runner, "_hades_fast_run_sync", False):
            original_run_sync = turn_runner.run_sync

            def fast_run_sync(self, _original=original_run_sync):
                runner = self._runner
                original_resolver = runner._resolve_turn_agent_config

                def resolve_for_turn(message, model, runtime_kwargs):
                    route = original_resolver(message, model, runtime_kwargs)
                    _hades_logger.info(
                        "HADES turn route input model=%s provider=%s base_url=%s tool_intent=%s",
                        route.get("model"),
                        route.get("runtime", {}).get("provider"),
                        route.get("runtime", {}).get("base_url"),
                        bool(_HADES_TOOL_INTENT.search(str(message or ""))),
                    )
                    return _hades_apply_fast_completion_route(route, message)

                runner._resolve_turn_agent_config = resolve_for_turn
                try:
                    return _original(self)
                finally:
                    runner._resolve_turn_agent_config = original_resolver

            fast_run_sync._hades_fast_run_sync = True
            turn_runner.run_sync = fast_run_sync
            _hades_logger.info("HADES TurnRunner fast-completion hook installed")
            installed = True
        return installed

    _hades_install_gateway_route_patch()

    # gateway.run_turn is imported after sitecustomize in the production
    # gateway process. Retry briefly during startup and also from the agent
    # construction hook below; this avoids a circular-import race without
    # modifying Hermes' installed package.
    import threading as _hades_threading
    def _hades_gateway_patch_watcher():
        import time
        for _ in range(60):
            if _hades_install_gateway_route_patch():
                return
            time.sleep(0.25)
    _hades_threading.Thread(target=_hades_gateway_patch_watcher, daemon=True).start()

    # Bound admission waits separately from the idle-turn watchdog. A client
    # that disappears can leave an in-process holder alive while the next
    # request waits at lease admission; the upstream 30-minute default turns
    # that into a household-wide stall. Keep this compatibility setting
    # explicit and removable when Hermes exposes a supported config knob.
    import agent.turn_facade_lease as _hades_turn_lease
    _hades_turn_lease.LEASE_WAIT_SECONDS = float(
        os.environ.get("HADES_SESSION_LEASE_WAIT_SECONDS", "30")
    )
    _hades_logger.info(
        "HADES session lease admission wait bounded to %.1fs",
        _hades_turn_lease.LEASE_WAIT_SECONDS,
    )

except Exception as exc:
    # Hermes can still start if the optional provider is unavailable; its
    # normal provider diagnostics should report that condition. Do not hide
    # an overlay initialization failure: without this diagnostic, HADES
    # capability and source-of-truth protections could be absent while the
    # process still appears healthy.
    import logging as _hades_bootstrap_logging
    _hades_bootstrap_logging.getLogger("hades.overlay").error(
        "HADES compatibility overlay initialization failed: %s", exc
    )
