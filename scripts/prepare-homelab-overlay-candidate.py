#!/usr/bin/env python3
"""Compose the current homelab read route into a deployment-local Hermes overlay copy."""
from __future__ import annotations

import argparse
import ast
import builtins
import hashlib
import os
import symtable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE = "_hades_direct_homelab_read"
EXTRA = {
    "_hades_ambiguous_media_device_clarification",
    "_hades_direct_homelab_backup_compound",
    "_hades_direct_proxmox_backup_read",
    "_hades_homelab_recent_activity_response",
    "_hades_direct_owner_location",
    "_hades_endpoint_continuation_response",
    "_hades_service_placement_intent",
    "_hades_monitor_question_is_diagnostic",
    "_hades_health_watch_intent",
}


def top_level(source: str, path: Path) -> ast.Module:
    return ast.parse(source, filename=str(path))


def functions(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    found: dict[str, ast.FunctionDef] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            if node.name in found:
                raise ValueError(f"duplicate top-level function: {node.name}")
            found[node.name] = node
    return found


def assigned_names(tree: ast.Module) -> dict[str, ast.stmt]:
    result: dict[str, ast.stmt] = {}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    result[target.id] = node
    return result


def function_closure(source_tree: ast.Module) -> set[str]:
    available = functions(source_tree)
    missing = {ROUTE, *EXTRA} - set(available)
    if missing:
        raise ValueError("source is missing required homelab functions: " + ", ".join(sorted(missing)))
    closure = {ROUTE, *EXTRA}
    while True:
        additions = {
            node.func.id
            for name in closure
            for node in ast.walk(available[name])
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in available
        }
        if additions <= closure:
            return closure
        closure |= additions


def referenced_globals(source: str, label: str, closure: set[str]) -> set[str]:
    root = symtable.symtable(source, label, "exec")
    tables: dict[str, list[symtable.SymbolTable]] = {}

    def visit(table: symtable.SymbolTable) -> None:
        if table.get_type() == "function":
            tables.setdefault(table.get_name(), []).append(table)
        for child in table.get_children():
            visit(child)

    visit(root)
    result: set[str] = set()

    def collect(table: symtable.SymbolTable) -> None:
        result.update(
            symbol.get_name() for symbol in table.get_symbols()
            if symbol.is_global() and symbol.is_referenced()
        )
        for child in table.get_children():
            collect(child)

    for name in closure:
        for table in tables.get(name, []):
            collect(table)
    return result


def replace_call_sites(active_text: str, tree: ast.Module) -> str:
    run_conversations = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_hades_run_conversation"
    ]
    run_conversation = run_conversations[0] if len(run_conversations) == 1 else None
    if run_conversation is None:
        raise ValueError("active overlay is missing _hades_run_conversation")
    lines = active_text.splitlines(keepends=True)
    replacements = []
    status_calls = 0
    request_calls = 0

    def is_self_getattr(node: ast.AST, attribute: str) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) == 3
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "self"
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == attribute
            and isinstance(node.args[2], ast.Constant)
            and node.args[2].value == ""
        )

    for node in ast.walk(run_conversation):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != ROUTE:
            continue
        old = ast.get_source_segment(active_text, node)
        first_arg = node.args[0] if node.args else None
        if isinstance(first_arg, ast.Constant) and first_arg.value == "homelab status and blockers":
            status_calls += 1
            if old == f'{ROUTE}("homelab status and blockers")':
                new = f'{ROUTE}("homelab status and blockers", getattr(self, "_hades_subject", ""), "owner")'
                replacements.append((node, old, new))
            elif (
                len(node.args) >= 3
                and isinstance(node.args[2], ast.Constant)
                and node.args[2].value == "owner"
            ):
                continue
            else:
                raise ValueError(f"unrecognized active owner homelab status call at line {node.lineno}")
        elif isinstance(first_arg, ast.Name) and first_arg.id == "user_message":
            request_calls += 1
            context = next((item.value for item in node.keywords if item.arg == "context_text"), None)
            if len(node.args) == 1 and not node.keywords:
                new = f'{ROUTE}(user_message, getattr(self, "_hades_subject", ""), self._hades_session_scope, context_text=_hades_intent_text)'
                replacements.append((node, old, new))
            elif (
                len(node.args) == 3
                and is_self_getattr(node.args[1], "_hades_subject")
                and (
                    is_self_getattr(node.args[2], "_hades_session_scope")
                    or (
                        isinstance(node.args[2], ast.Constant)
                        and node.args[2].value in {"owner", "household"}
                    )
                )
                and (
                    not node.keywords
                    or (
                        len(node.keywords) == 1
                        and node.keywords[0].arg == "context_text"
                        and isinstance(context, ast.Name)
                        and context.id in {"_hades_intent_text", "_early_hades_intent_text"}
                    )
                )
            ):
                # Preserve already composed explicit-scope routes, including
                # the legacy-overlay early route which carries follow-up text.
                continue
            elif isinstance(context, ast.Name) and context.id == "previous_user_text":
                new = old.replace("context_text=previous_user_text", "context_text=_hades_intent_text")
                if new == old:
                    raise ValueError(f"could not normalize active homelab context at line {node.lineno}")
                replacements.append((node, old, new))
            elif isinstance(context, ast.Name) and context.id in {
                "_hades_intent_text", "_early_hades_intent_text"
            }:
                continue
            else:
                raise ValueError(f"unrecognized active homelab request call at line {node.lineno}")
        else:
            raise ValueError(f"unrecognized active homelab call at line {node.lineno}")
    if status_calls > 1 or request_calls < 1:
        raise ValueError(
            f"expected at most one owner status call and at least one current request call; "
            f"found status={status_calls}, request={request_calls}"
        )
    offsets = []
    for node, old, new in replacements:
        offset = sum(map(len, lines[:node.lineno - 1])) + node.col_offset
        offsets.append((offset, offset + len(old), old, new))
    result = active_text
    for start, end, old, new in sorted(offsets, reverse=True):
        if result[start:end] != old:
            raise ValueError("active homelab call changed during composition")
        result = result[:start] + new + result[end:]
    return result


def add_household_route(source: str) -> str:
    tree = ast.parse(source)
    candidates = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and "self._hades_session_scope" in ast.unparse(node.test)
        and "owner" in ast.unparse(node.test)
        and "_compound_briefing" not in ast.unparse(node.test)
        and any(
            isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == ROUTE
            for child in ast.walk(node)
        )
    ]
    if len(candidates) != 1:
        raise ValueError("could not uniquely locate the active owner homelab route")
    owner = candidates[0]
    if owner.end_lineno > len(source.splitlines()):
        raise ValueError("invalid owner route boundary")
    run_conversation = next(
        (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
         and node.name == "_hades_run_conversation"),
        None,
    )
    auxiliary_guards = [
        node for node in ast.walk(run_conversation) if isinstance(node, ast.If)
        and any(isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
                and child.func.id == "_hades_is_hermes_auxiliary_prompt"
                for child in ast.walk(node.test))
    ] if run_conversation else []
    run_text = ast.get_source_segment(source, run_conversation) or ""
    has_early_household_service_guard = (
        "Household service-health boundary completed before staged automation routing" in run_text
    )
    placement_guards = [
        node for node in ast.walk(run_conversation) if isinstance(node, ast.If)
        and "_hades_service_placement_intent" in ast.unparse(node.test)
    ] if run_conversation else []
    managed_server_guards = [
        node for node in ast.walk(run_conversation) if isinstance(node, ast.If)
        and "_server_actor_turn" in ast.unparse(node.test)
        and "_server_status_turn" in ast.unparse(node.test)
    ] if run_conversation else []
    if len(auxiliary_guards) == 1:
        early_insertion = auxiliary_guards[0].end_lineno
    elif not auxiliary_guards and has_early_household_service_guard and placement_guards:
        early_insertion = min(placement_guards, key=lambda node: node.lineno).lineno - 1
    elif not auxiliary_guards and len(managed_server_guards) == 1:
        # Older production overlays have no auxiliary-prompt guard. Insert the
        # read-only route immediately before the managed-server router so
        # infrastructure placement/health questions cannot be mistaken for
        # HADES-managed workload requests.
        early_insertion = managed_server_guards[0].lineno - 1
    else:
        raise ValueError("could not uniquely locate a safe early homelab route anchor")
    if has_early_household_service_guard:
        required_early_markers = (
            "_hades_service_placement_intent(",
            "_hades_household_game_health_intent(",
            "Owner model-capacity follow-up failed closed without model invocation",
        )
        if any(marker not in run_text for marker in required_early_markers):
            raise ValueError("existing early homelab route is incomplete; refusing duplicate or partial composition")
    early_block = '''
        _early_hades_intent_text = _hades_conversation_intent_text(
            user_message, kwargs.get("conversation_history")
        )
        if getattr(self, "_hades_session_scope", "") == "owner":
            early_proxmox_backup_response = _hades_direct_proxmox_backup_read(
                user_message, getattr(self, "_hades_subject", ""), "owner"
            )
            if early_proxmox_backup_response:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(early_proxmox_backup_response)
                _hades_logger.info("Owner Proxmox backup read completed before managed-server routing")
                return {
                    "final_response": early_proxmox_backup_response,
                    "messages": [{"role": "assistant", "content": early_proxmox_backup_response}],
                    "api_calls": 0,
                    "completed": True,
                }
            early_compound_backup_response = _hades_direct_homelab_backup_compound(
                user_message, getattr(self, "_hades_subject", ""), "owner"
            )
            if early_compound_backup_response:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(early_compound_backup_response)
                _hades_logger.info("Owner compound homelab and backup read completed before managed-server routing")
                return {
                    "final_response": early_compound_backup_response,
                    "messages": [{"role": "assistant", "content": early_compound_backup_response}],
                    "api_calls": 0,
                    "completed": True,
                }
            early_owner_homelab_response = _hades_direct_homelab_read(
                user_message, getattr(self, "_hades_subject", ""), "owner",
                context_text=_early_hades_intent_text,
            )
            if early_owner_homelab_response:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(early_owner_homelab_response)
                _hades_logger.info("Owner direct homelab read completed before managed-server routing")
                return {
                    "final_response": early_owner_homelab_response,
                    "messages": [{"role": "assistant", "content": early_owner_homelab_response}],
                    "api_calls": 0,
                    "completed": True,
                }
        if getattr(self, "_hades_session_scope", "") == "household":
            early_household_homelab_response = _hades_direct_homelab_read(
                user_message, getattr(self, "_hades_subject", ""), "household",
                context_text=_early_hades_intent_text,
            )
            if early_household_homelab_response:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(early_household_homelab_response)
                _hades_logger.info("Household direct homelab boundary completed before managed-server routing")
                return {
                    "final_response": early_household_homelab_response,
                    "messages": [{"role": "assistant", "content": early_household_homelab_response}],
                    "api_calls": 0,
                    "completed": True,
                }
        if getattr(self, "_hades_session_scope", "") in {"owner", "household"} and _hades_service_placement_intent(
            user_message, getattr(self, "_hades_session_scope", "")
        ):
            service_placement_response = _hades_direct_homelab_read(
                user_message,
                getattr(self, "_hades_subject", ""),
                getattr(self, "_hades_session_scope", ""),
            )
            if service_placement_response:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(service_placement_response)
                _hades_logger.info(
                    "Service-placement inventory read completed before managed-server routing"
                )
                return {
                    "final_response": service_placement_response,
                    "messages": [{"role": "assistant", "content": service_placement_response}],
                    "api_calls": 0,
                    "completed": True,
                }
        if getattr(self, "_hades_session_scope", "") == "household" and _hades_service_health_target(user_message):
            household_service_health_response = _hades_direct_homelab_read(
                user_message,
                getattr(self, "_hades_subject", ""),
                "household",
            )
            if household_service_health_response:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(household_service_health_response)
                _hades_logger.info(
                    "Household service-health boundary completed before staged automation routing"
                )
                return {
                    "final_response": household_service_health_response,
                    "messages": [{"role": "assistant", "content": household_service_health_response}],
                    "api_calls": 0,
                    "completed": True,
                }
        if _hades_household_game_health_intent(
            user_message, getattr(self, "_hades_session_scope", "")
        ):
            game_health_response = _hades_direct_homelab_read(
                user_message,
                getattr(self, "_hades_subject", ""),
                getattr(self, "_hades_session_scope", ""),
            )
            if game_health_response:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(game_health_response)
                _hades_logger.info(
                    "Household game-server health read completed before managed-server routing"
                )
                return {
                    "final_response": game_health_response,
                    "messages": [{"role": "assistant", "content": game_health_response}],
                    "api_calls": 0,
                    "completed": True,
                }
        if self._hades_session_scope == "owner" and re.fullmatch(
            r"\\s*what\\s+about\\s+(?:a\\s+)?\\d+(?:\\.\\d+)?\\s*(?:gb|gib)\\s+(?:one|model)\\s*[?.!]*\\s*",
            str(user_message or ""), re.IGNORECASE,
        ):
            unavailable_response = (
                "I can't confirm whether that model fits or recommend a host: current per-host "
                "GPU load and free VRAM are not connected, and runtime memory needs are unknown."
            )
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(unavailable_response)
            _hades_logger.info("Owner model-capacity follow-up failed closed without model invocation")
            return {
                "final_response": unavailable_response,
                "messages": [{"role": "assistant", "content": unavailable_response}],
                "api_calls": 0,
                "completed": True,
            }
'''
    late_block = '''
        if self._hades_session_scope == "household":
            household_homelab_response = _hades_direct_homelab_read(
                user_message, getattr(self, "_hades_subject", ""),
                self._hades_session_scope, context_text=previous_user_text,
            )
            if household_homelab_response:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(household_homelab_response)
                _hades_logger.info("Household direct homelab read completed without model invocation")
                return {
                    "final_response": household_homelab_response,
                    "messages": [{"role": "assistant", "content": household_homelab_response}],
                    "api_calls": 0,
                    "completed": True,
                }
        if self._hades_session_scope == "owner" and (
            _hades_homelab_named_check_target(user_message)
            or re.search(
                r"\\bwhat(?:['’]s|s|\\s+is)\\s+[a-z0-9][a-z0-9 ._'’-]{0,60}?\\s+(?:doing|running)\\b|"
                r"\\bwhat(?:['’]s|\\s+is)\\s+wrong\\s+with\\s+[a-z0-9][a-z0-9 ._'’-]{0,60}?\\s*[?.!]*$",
                str(user_message or ""), re.IGNORECASE,
            )
        ):
            target = _hades_homelab_target_from_question(user_message)
            subject_name = f" for {target}" if target else ""
            unavailable_response = (
                f"I couldn't verify current runtime or workload status{subject_name} "
                "from the configured homelab sources, so I won't guess."
            )
            callback = getattr(self, "stream_delta_callback", None)
            if callback:
                callback(unavailable_response)
            _hades_logger.info("Owner node-activity read failed closed without model invocation")
            return {
                "final_response": unavailable_response,
                "messages": [{"role": "assistant", "content": unavailable_response}],
                "api_calls": 0,
                "completed": True,
            }
'''
    owner_route_start = early_block.index(
        '        if getattr(self, "_hades_session_scope", "") == "owner":'
    )
    household_route_start = early_block.index(
        '        if getattr(self, "_hades_session_scope", "") == "household":', owner_route_start
    )
    placement_route_start = early_block.index(
        '        if getattr(self, "_hades_session_scope", "") in {"owner", "household"} and _hades_service_placement_intent(',
        household_route_start,
    )
    early_context = early_block[:owner_route_start]
    early_owner_route = early_block[owner_route_start:household_route_start]
    early_household_route = early_block[household_route_start:placement_route_start]

    lines = source.splitlines(keepends=True)
    # Capacity is known to lack live VRAM evidence, so stop it before any
    # request classification or live-read work. Named-node fallback stays
    # after the owner source read so it can use available evidence first.
    inserted_early_lines = 0
    if not has_early_household_service_guard:
        lines[early_insertion:early_insertion] = early_block.splitlines(keepends=True)
        inserted_early_lines = len(early_block.splitlines(keepends=True))
    else:
        missing_identity_routes = []
        needs_context = "_early_hades_intent_text = _hades_conversation_intent_text(" not in run_text
        if "Owner direct homelab read completed before managed-server routing" not in run_text:
            missing_identity_routes.append(early_owner_route)
        if "Household direct homelab boundary completed before managed-server routing" not in run_text:
            missing_identity_routes.append(early_household_route)
        if missing_identity_routes:
            identity_block = (early_context if needs_context else "") + "".join(missing_identity_routes)
            lines[early_insertion:early_insertion] = identity_block.splitlines(keepends=True)
            inserted_early_lines = len(identity_block.splitlines(keepends=True))
    lines = "".join(lines).splitlines(keepends=True)
    has_late_household_read = "Household direct homelab read completed without model invocation" in run_text
    if not has_late_household_read:
        insertion = owner.end_lineno + inserted_early_lines
        lines[insertion:insertion] = late_block.splitlines(keepends=True)
    composed = "".join(lines)
    return composed


def add_media_clarification(source: str) -> str:
    tree = ast.parse(source)
    definitions = functions(tree)
    if "_hades_ambiguous_media_device_clarification" not in definitions:
        raise ValueError("media clarification helper missing after composition")
    existing_call_nodes = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "_hades_ambiguous_media_device_clarification"
    ]
    if len(existing_call_nodes) > 1:
        raise ValueError("multiple media clarification calls already exist; refusing duplicate insertion")
    if existing_call_nodes:
        existing_call = existing_call_nodes[0]
        run_conversation = next(
            (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
             and node.name == "_hades_run_conversation"),
            None,
        )
        if run_conversation is None or existing_call not in ast.walk(run_conversation):
            raise ValueError("existing media clarification call is outside _hades_run_conversation")
        if (
            len(existing_call.args) != 1
            or not isinstance(existing_call.args[0], ast.Name)
            or existing_call.args[0].id != "_preflight_text"
        ):
            raise ValueError("existing media clarification call has an unsupported input")
        return source
    route = next(
        (node for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and "not _compound_briefing" in ast.unparse(node.test)
         and "_hades_session_scope" in ast.unparse(node.test)
         and any(isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
                 and child.func.id in {"_hades_direct_grocy_expiry_read", "_hades_direct_grocy_expiry_recipe_compound_read"}
                 for child in ast.walk(node))),
        None,
    )
    if route is None:
        print("WARN active overlay has no supported Grocy preflight route; media clarification remains inactive")
        return source
    expiry = next(
        (node for node in route.body if isinstance(node, ast.If)
         and ast.unparse(node.test) == "_expiry_response"),
        None,
    )
    if expiry is None:
        raise ValueError("could not locate the active expiry response branch")
    block = '''
            _device_clarification = _hades_ambiguous_media_device_clarification(_preflight_text)
            if _device_clarification:
                callback = getattr(self, "stream_delta_callback", None)
                if callback:
                    callback(_device_clarification)
                return {
                    "final_response": _device_clarification,
                    "messages": [{"role": "assistant", "content": _device_clarification}],
                    "api_calls": 0,
                    "completed": True,
                }
'''
    lines = source.splitlines(keepends=True)
    lines[expiry.end_lineno:expiry.end_lineno] = block.splitlines(keepends=True)
    return "".join(lines)


def add_backup_routes(source: str) -> str:
    """Keep current owner backup composition ahead of the legacy Backup Check path."""
    tree = ast.parse(source)
    definitions = functions(tree)
    if "_hades_direct_homelab_backup_compound" not in definitions:
        raise ValueError("owner homelab backup composition helper is missing")
    existing = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"_hades_direct_homelab_backup_compound", "_hades_direct_proxmox_backup_read"}
        and any(isinstance(arg, ast.Name) and arg.id == "user_message" for arg in node.args)
    ]
    if existing:
        has_compound = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_hades_direct_homelab_backup_compound" for n in existing)
        has_proxmox = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_hades_direct_proxmox_backup_read" for n in existing)
        if not (has_compound and has_proxmox):
            raise ValueError("active backup route is only partially composed")
        return source

    candidates = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id in {"direct_backup_response", "_backup_response"} for target in node.targets)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "_hades_phase2_backup_response"
    ]
    if len(candidates) != 1:
        raise ValueError("could not uniquely locate the legacy direct Backup Check route")
    anchor = candidates[0]
    indent = " " * anchor.col_offset
    block = f'''{indent}proxmox_backup_response = _hades_direct_proxmox_backup_read(
{indent}    user_message, getattr(self, "_hades_subject", ""),
{indent}    self._hades_session_scope, _phase2_session_key,
{indent})
{indent}if proxmox_backup_response:
{indent}    callback = getattr(self, "stream_delta_callback", None)
{indent}    if callback:
{indent}        callback(proxmox_backup_response)
{indent}    _hades_logger.info("Owner Proxmox backup read completed without model invocation")
{indent}    return {{
{indent}        "final_response": proxmox_backup_response,
{indent}        "messages": [{{"role": "assistant", "content": proxmox_backup_response}}],
{indent}        "api_calls": 0,
{indent}        "completed": True,
{indent}    }}
{indent}compound_status_response = _hades_direct_homelab_backup_compound(
{indent}    user_message,
{indent}    getattr(self, "_hades_subject", ""),
{indent}    self._hades_session_scope,
{indent}    _phase2_session_key,
{indent})
{indent}if compound_status_response:
{indent}    callback = getattr(self, "stream_delta_callback", None)
{indent}    if callback:
{indent}        callback(compound_status_response)
{indent}    _hades_logger.info("Owner compound homelab and backup read completed without model invocation")
{indent}    return {{
{indent}        "final_response": compound_status_response,
{indent}        "messages": [{{"role": "assistant", "content": compound_status_response}}],
{indent}        "api_calls": 0,
{indent}        "completed": True,
{indent}    }}
'''
    lines = source.splitlines(keepends=True)
    lines[anchor.lineno - 1:anchor.lineno - 1] = block.splitlines(keepends=True)
    return "".join(lines)

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--active-overlay", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source", type=Path, default=ROOT / "hermes/sitecustomize.py")
    args = parser.parse_args()
    active = args.active_overlay.resolve(strict=True)
    source_path = args.source.resolve(strict=True)
    output = args.output.absolute()
    if active.is_symlink() or source_path.is_symlink():
        raise SystemExit("FAIL overlays must be regular files, not symlinks")
    if output in {active, source_path} or output.exists() or output.is_symlink():
        raise SystemExit("FAIL candidate output must be a new path")
    if not output.parent.is_dir():
        raise SystemExit("FAIL candidate output parent directory must exist")
    active_bytes = active.read_bytes()
    source_bytes = source_path.read_bytes()
    active_text = active_bytes.decode("utf-8")
    source_text = source_bytes.decode("utf-8")
    active_tree = top_level(active_text, active)
    source_tree = top_level(source_text, source_path)
    source_functions = functions(source_tree)
    active_functions = functions(active_tree)
    closure = function_closure(source_tree)
    refs = referenced_globals(source_text, str(source_path), closure)
    source_assignments = assigned_names(source_tree)
    active_assignments = assigned_names(active_tree)
    source_lines = source_text.splitlines(keepends=True)
    active_lines = active_text.splitlines(keepends=True)
    patches: list[tuple[int, int, list[str]]] = []
    additions: list[str] = []
    for name in closure:
        node = source_functions[name]
        replacement = source_lines[node.lineno - 1:node.end_lineno]
        if name in active_functions:
            active_node = active_functions[name]
            if active_node.col_offset != node.col_offset:
                raise SystemExit(f"FAIL nesting differs for {name}; refusing to compose")
            patches.append((active_node.lineno, active_node.end_lineno, replacement))
        else:
            additions.extend(replacement)
    for name in refs & set(source_assignments):
        node = source_assignments[name]
        replacement = source_lines[node.lineno - 1:node.end_lineno]
        if name in active_assignments:
            if ast.dump(active_assignments[name], include_attributes=False) != ast.dump(node, include_attributes=False):
                patches.append((active_assignments[name].lineno, active_assignments[name].end_lineno, replacement))
        else:
            additions.extend(replacement)
    # Existing imports/constants outside this focused closure are deployment-local
    # contracts. Fail rather than copying or guessing when one is absent.
    source_bindings = set(source_functions) | set(source_assignments)
    active_bindings = set(active_functions) | set(active_assignments)
    for node in source_tree.body:
        if isinstance(node, ast.Import):
            source_bindings.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            source_bindings.update(alias.asname or alias.name for alias in node.names)
    for node in active_tree.body:
        if isinstance(node, ast.Import):
            active_bindings.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            active_bindings.update(alias.asname or alias.name for alias in node.names)
    missing_import_bindings = set()
    imports_to_add = []
    for node in source_tree.body:
        if isinstance(node, ast.Import):
            bound = {alias.asname or alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            bound = {alias.asname or alias.name for alias in node.names}
        else:
            continue
        needed = (refs & bound) - active_bindings
        if needed:
            imports_to_add.extend(source_lines[node.lineno - 1:node.end_lineno])
            missing_import_bindings.update(needed)
    runtime_globals = set(dir(builtins)) | {
        "__builtins__", "__file__", "__loader__", "__name__", "__package__", "__spec__"
    }
    missing = refs - active_bindings - closure - set(source_assignments) - missing_import_bindings - runtime_globals
    if missing:
        raise SystemExit("FAIL required overlay globals are absent: " + ", ".join(sorted(missing)))
    text = replace_call_sites(active_text, active_tree)
    lines = text.splitlines(keepends=True)
    for start, end, replacement in sorted(patches, reverse=True):
        lines[start - 1:end] = replacement
    text = "".join(lines)
    if additions:
        tree = ast.parse(text)
        direct = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == ROUTE)
        lines = text.splitlines(keepends=True)
        lines[direct.lineno - 1:direct.lineno - 1] = ["\n"] + additions + ["\n"]
        text = "".join(lines)
    if imports_to_add:
        tree = ast.parse(text)
        import_nodes = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
        insert_at = max((node.end_lineno for node in import_nodes), default=1)
        lines = text.splitlines(keepends=True)
        lines[insert_at:insert_at] = imports_to_add
        text = "".join(lines)
    text = add_household_route(text)
    text = add_media_clarification(text)
    text = add_backup_routes(text)
    candidate_bytes = text.encode("utf-8")
    compile(text, str(output), "exec")
    fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(candidate_bytes)
        stream.flush()
        os.fsync(stream.fileno())
    print("PASS composed focused homelab and household routes; active overlay untouched")
    print(f"closure_functions={len(closure)} active_sha256={digest(active_bytes)}")
    print(f"source_sha256={digest(source_bytes)} candidate_sha256={digest(candidate_bytes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
