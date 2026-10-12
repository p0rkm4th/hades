#!/usr/bin/env python3
"""Compose qualified automatic-retain policy into an installed Hermes overlay copy."""
from __future__ import annotations

import argparse
import ast
import hashlib
import os
from pathlib import Path

CONSTANTS = (
    "_HADES_MEMORY_SECRET",
    "_HADES_DURABLE_MEMORY_CLAIMS",
    "_HADES_MEMORY_UNTRUSTED_PROVENANCE",
    "_HADES_EDITOR_CORRECTION",
)
REPLACED_CONSTANTS = (
    "_HADES_HOMELAB_INTENT",
    "_HADES_NETWORK_INVENTORY_INTENT",
    "_HADES_NONPERSONAL_STATE_INTENT",
)
FUNCTIONS = (
    "_hades_capability_matrix_path",
    "_hades_configured_homelab_alias_match",
    "_hades_configured_homelab_records",
    "_hades_homelab_service_placement_intent",
    "_hades_automatic_memory_qualification",
    "_hades_automatic_memory_actor_bound",
    "_hades_sync_qualified_memory_turn",
)
REPLACED_FUNCTIONS = (
    "_hades_broad_homelab_status_intent",
    "_hades_homelab_conflict_intent",
    "_hades_homelab_guest_visibility_intent",
    "_hades_homelab_resource_ranking_intent",
    "_hades_homelab_service_coverage_intent",
    "_hades_nonpersonal_state_turn",
    "_hades_service_health_target",
    "_hades_should_skip_automatic_memory",
    "_hades_sync_turn",
)
RUNTIME_HOOK = "_hades_sync_turn"
INSERT_BEFORE = "_hades_subject_from_session_key"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def definitions(text: str, label: str) -> tuple[ast.Module, dict[str, ast.AST]]:
    tree = ast.parse(text, filename=label)
    found: dict[str, list[ast.AST]] = {
        name: [] for name in (*CONSTANTS, *REPLACED_CONSTANTS, *FUNCTIONS, *REPLACED_FUNCTIONS, INSERT_BEFORE)
    }
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in found:
            found[node.name].append(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id in found:
                    found[target.id].append(node)
    duplicates = [name for name, nodes in found.items() if len(nodes) > 1]
    if duplicates:
        raise ValueError(f"{label} has duplicate composition symbols: {', '.join(duplicates)}")
    return tree, {name: nodes[0] for name, nodes in found.items() if nodes}


def source_block(source_lines: list[str], nodes: list[ast.AST]) -> str:
    ordered = sorted(nodes, key=lambda node: node.lineno)
    return "\n\n".join(
        "".join(source_lines[node.lineno - 1:node.end_lineno]).rstrip("\n")
        for node in ordered
    ) + "\n\n\n"


def compose(active_bytes: bytes, source_bytes: bytes) -> bytes:
    active_text = active_bytes.decode("utf-8")
    source_text = source_bytes.decode("utf-8")
    _, active = definitions(active_text, "active overlay")
    _, source = definitions(source_text, "canonical source")
    required = (*CONSTANTS, *REPLACED_CONSTANTS, *FUNCTIONS, *REPLACED_FUNCTIONS, INSERT_BEFORE)
    missing = [name for name in required if name not in source]
    if missing:
        raise ValueError(f"canonical source lacks required symbols: {', '.join(missing)}")
    missing_anchor = [name for name in (*REPLACED_FUNCTIONS, INSERT_BEFORE) if name not in active]
    if missing_anchor:
        raise ValueError(f"active overlay lacks safe composition anchors: {', '.join(missing_anchor)}")
    already_present = [name for name in (*CONSTANTS, *FUNCTIONS) if name in active]
    if already_present:
        raise ValueError(f"active overlay already contains policy symbols: {', '.join(already_present)}")

    active_hook, source_hook = active[RUNTIME_HOOK], source[RUNTIME_HOOK]
    for name in REPLACED_FUNCTIONS:
        active_node, source_node = active[name], source[name]
        if not isinstance(active_node, ast.FunctionDef) or not isinstance(source_node, ast.FunctionDef):
            raise ValueError(f"{name} must be a regular function")
        compatible_skip_signature = (
            name == "_hades_should_skip_automatic_memory"
            and [arg.arg for arg in active_node.args.args]
            == [arg.arg for arg in source_node.args.args[:len(active_node.args.args)]]
            and len(source_node.args.defaults) >= len(source_node.args.args) - len(active_node.args.args)
        )
        same_signature = ast.dump(active_node.args) == ast.dump(source_node.args)
        if active_node.col_offset != source_node.col_offset or not (same_signature or compatible_skip_signature):
            raise ValueError(f"{name} nesting or signature differs; refusing to compose")

    active_lines = active_text.splitlines(keepends=True)
    source_lines = source_text.splitlines(keepends=True)
    additions = source_block(source_lines, [source[name] for name in (*CONSTANTS, *FUNCTIONS)])
    replacement_text = {
        name: source_block(source_lines, [source[name]])
        for name in REPLACED_CONSTANTS
    }
    replacement_text = {
        **replacement_text,
        **{
            name: "".join(source_lines[source[name].lineno - 1:source[name].end_lineno])
            for name in REPLACED_FUNCTIONS
        },
    }
    # Assert the source hook is exactly the actor-bound qualification adapter.
    hook_calls = {
        node.func.id for node in ast.walk(source_hook)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    if "_hades_sync_qualified_memory_turn" not in hook_calls:
        raise ValueError("canonical runtime hook does not call the qualified retain boundary")

    edits = [
        *[
            (active[name].lineno - 1, active[name].end_lineno, replacement_text[name])
            for name in (*REPLACED_CONSTANTS, *REPLACED_FUNCTIONS)
        ],
        (active[INSERT_BEFORE].lineno - 1, active[INSERT_BEFORE].lineno - 1, additions),
    ]
    result = active_lines[:]
    for start, end, replacement in sorted(edits, reverse=True):
        result[start:end] = [replacement] if replacement else []
    candidate = "".join(result).encode("utf-8")
    candidate_text = candidate.decode("utf-8")
    compile(candidate_text, "<composed-hindsight-overlay>", "exec")
    _, composed = definitions(candidate_text, "composed overlay")
    for name in (*CONSTANTS, *FUNCTIONS, *REPLACED_CONSTANTS, *REPLACED_FUNCTIONS):
        expected = source_block(source_lines, [source[name]])
        actual_node = composed[name]
        actual = "".join(candidate_text.splitlines(keepends=True)[actual_node.lineno - 1:actual_node.end_lineno])
        if actual.rstrip("\n") != expected.rstrip("\n"):
            raise ValueError(f"composed symbol differs from canonical source: {name}")
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--active-overlay", required=True, type=Path)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1] / "hermes/sitecustomize.py")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    active = args.active_overlay.resolve(strict=True)
    source = args.source.resolve(strict=True)
    output = args.output.absolute()
    if active.is_symlink() or source.is_symlink():
        raise SystemExit("FAIL active/source overlays must be regular files, not symlinks")
    if output in {active, source} or output.exists() or output.is_symlink():
        raise SystemExit("FAIL candidate output must be a new path")
    if not output.parent.is_dir():
        raise SystemExit("FAIL candidate output parent directory must exist")
    active_bytes, source_bytes = active.read_bytes(), source.read_bytes()
    try:
        candidate = compose(active_bytes, source_bytes)
    except (SyntaxError, UnicodeError, ValueError) as exc:
        raise SystemExit(f"FAIL automatic-retain overlay composition refused: {exc}") from None
    fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(candidate)
        stream.flush()
        os.fsync(stream.fileno())
    print("PASS composed only canonical automatic-retain policy dependencies and runtime hooks")
    print(f"active_sha256={digest(active_bytes)}")
    print(f"source_sha256={digest(source_bytes)}")
    print(f"candidate_sha256={digest(candidate)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
