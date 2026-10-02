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
    "_hades_direct_owner_location",
    "_hades_endpoint_continuation_response",
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
    lines = active_text.splitlines(keepends=True)
    replacements = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != ROUTE:
            continue
        old = ast.get_source_segment(active_text, node)
        if old == f'{ROUTE}("homelab status and blockers")':
            new = f'{ROUTE}("homelab status and blockers", getattr(self, "_hades_subject", ""), "owner")'
        elif old == f"{ROUTE}(user_message)":
            new = f'{ROUTE}(user_message, getattr(self, "_hades_subject", ""), self._hades_session_scope, context_text=previous_user_text)'
        else:
            raise ValueError(f"unrecognized active homelab call at line {node.lineno}")
        offset = sum(map(len, lines[:node.lineno - 1])) + node.col_offset
        replacements.append((offset, offset + len(old), old, new))
    if len(replacements) != 2:
        raise ValueError(f"expected exactly two legacy owner homelab calls; found {len(replacements)}")
    result = active_text
    for start, end, old, new in sorted(replacements, reverse=True):
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
    block = '''
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
        if self._hades_session_scope == "owner" and re.search(
            r"\\bwhat(?:['’]s|s|\\s+is)\\s+[a-z0-9][a-z0-9 ._'’-]{0,60}?\\s+(?:doing|running)\\b",
            str(user_message or ""), re.IGNORECASE,
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
    lines = source.splitlines(keepends=True)
    lines[owner.end_lineno:owner.end_lineno] = block.splitlines(keepends=True)
    composed = "".join(lines)
    if "context_text=previous_user_text" in composed:
        composed = composed.replace(
            "context_text=previous_user_text", "context_text=_hades_intent_text", 1
        )
    return composed


def add_media_clarification(source: str) -> str:
    tree = ast.parse(source)
    definitions = functions(tree)
    if "_hades_ambiguous_media_device_clarification" not in definitions:
        raise ValueError("media clarification helper missing after composition")
    if any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "_hades_ambiguous_media_device_clarification"
        for node in ast.walk(tree)
    ):
        raise ValueError("media clarification call already exists; refusing duplicate insertion")
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
        raise ValueError("could not locate active non-briefing preflight route")
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
        and any(isinstance(target, ast.Name) and target.id == "direct_backup_response" for target in node.targets)
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
    runtime_globals = set(dir(builtins)) | {
        "__builtins__", "__file__", "__loader__", "__name__", "__package__", "__spec__"
    }
    missing = refs - active_bindings - closure - set(source_assignments) - runtime_globals
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
