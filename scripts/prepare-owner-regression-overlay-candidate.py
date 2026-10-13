#!/usr/bin/env python3
"""Compose the qualified owner-regression fixes onto the exact live overlay.

The production sitecustomize overlay contains deployment-local behavior and is
not interchangeable with the repository copy. This composer applies only the
reviewed routing/precedence changes and fails if either input differs from the
checksums supplied by the operator.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import os
from pathlib import Path


REPLACED_ASSIGNMENTS = (
    "_HADES_SHARED_MEMORY_INTENT",
    "_HADES_HOUSEHOLD_INVENTORY_CONTEXT",
    "_HADES_NONPERSONAL_STATE_INTENT",
)
PROVISIONING_PATTERN_OLD = r"spin\s+up"
PROVISIONING_PATTERN_NEW = r"spin\s+(?:(?:one|it|a|the)\s+)?up"
GROCY_READ_GATE_OLD = r"\b(?:recipes?|ingredients?|make|cook|fulfill|missing)\\b"
GROCY_READ_GATE_NEW = r"\b(?:recipes?|ingredients?|make|cook|fulfill|missing)\b"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_regular(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise SystemExit(f"FAIL {label} must be a regular, non-symlink file")
    return path.read_bytes()


def top_level_nodes(text: str) -> list[ast.stmt]:
    return ast.parse(text).body


def line_offsets(text: str) -> list[int]:
    result = [0]
    for line in text.splitlines(keepends=True):
        result.append(result[-1] + len(line.encode("utf-8")))
    return result


def node_span(text: str, node: ast.AST) -> tuple[int, int]:
    offsets = line_offsets(text)
    return offsets[node.lineno - 1], offsets[node.end_lineno]


def named_functions(text: str, name: str) -> list[ast.FunctionDef]:
    return [
        node for node in top_level_nodes(text)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]


def assignment_name(node: ast.stmt) -> str | None:
    targets = node.targets if isinstance(node, ast.Assign) else (
        [node.target] if isinstance(node, ast.AnnAssign) else []
    )
    if len(targets) == 1 and isinstance(targets[0], ast.Name):
        return targets[0].id
    return None


def replace_top_level_function(active: str, source: str, name: str, *, active_index: int = 0) -> str:
    active_matches = named_functions(active, name)
    source_matches = named_functions(source, name)
    if len(active_matches) <= active_index or len(source_matches) != 1:
        raise SystemExit(f"FAIL expected active/source definition shape for {name}")
    old, new = active_matches[active_index], source_matches[0]
    if ast.dump(old.args) != ast.dump(new.args):
        raise SystemExit(f"FAIL incompatible function signature for {name}")
    a, b = node_span(active, old)
    c, d = node_span(source, new)
    return active.encode("utf-8")[:a].decode("utf-8") + source.encode("utf-8")[c:d].decode("utf-8") + active.encode("utf-8")[b:].decode("utf-8")


def replace_top_level_assignment(active: str, source: str, name: str) -> str:
    active_matches = [node for node in top_level_nodes(active) if assignment_name(node) == name]
    source_matches = [node for node in top_level_nodes(source) if assignment_name(node) == name]
    if len(active_matches) != 1 or len(source_matches) != 1:
        raise SystemExit(f"FAIL expected one active/source assignment for {name}")
    a, b = node_span(active, active_matches[0])
    c, d = node_span(source, source_matches[0])
    return active.encode("utf-8")[:a].decode("utf-8") + source.encode("utf-8")[c:d].decode("utf-8") + active.encode("utf-8")[b:].decode("utf-8")


def insert_grocy_list_guard(text: str) -> str:
    matches = named_functions(text, "_hades_direct_grocy_recipe_read")
    if len(matches) != 1:
        raise SystemExit("FAIL expected one active _hades_direct_grocy_recipe_read")
    fn = matches[0]
    segment = ast.get_source_segment(text, fn) or ""
    anchor = '    text = str(user_text or "")\n'
    if segment.count(anchor) != 1:
        raise SystemExit("FAIL active Grocy recipe reader has unexpected initialization")
    replacement = anchor + (
        '    if _hades_grocy_read_operation(text) == "recipes_list_tool":\n'
        '        return None\n'
    )
    start, end = node_span(text, fn)
    return text.encode("utf-8")[:start].decode("utf-8") + segment.replace(anchor, replacement, 1) + text.encode("utf-8")[end:].decode("utf-8")


def extract_finance_period_block(source: str) -> str:
    finance = named_functions(source, "_hades_direct_finance_guidance")
    if len(finance) != 1:
        raise SystemExit("FAIL source finance guidance definition is ambiguous")
    candidates = [
        node for node in ast.walk(finance[0])
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "trailing_year_request" for target in node.targets)
    ]
    ends = [
        node for node in ast.walk(finance[0])
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "ytd_request" for target in node.targets)
    ]
    if len(candidates) != 1 or len(ends) != 1:
        raise SystemExit("FAIL source finance period block shape is unexpected")
    start_line = candidates[0].lineno
    end_line = ends[0].lineno
    lines = source.splitlines(keepends=True)
    block = "".join(lines[start_line - 1:end_line - 1])
    if not block or "posted net spending" not in block or "coverage_complete" not in block:
        raise SystemExit("FAIL source finance period block is incomplete")
    return block


def insert_finance_period_block(text: str, source: str) -> str:
    matches = named_functions(text, "_hades_p1_finance_merchant_calculation")
    if len(matches) != 1:
        raise SystemExit("FAIL expected one active finance merchant calculator")
    fn = matches[0]
    ytd_nodes = [
        node for node in ast.walk(fn)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "ytd_request" for target in node.targets)
    ]
    if len(ytd_nodes) != 1:
        raise SystemExit("FAIL active finance calculation insertion point is ambiguous")
    block = extract_finance_period_block(source)
    offsets = line_offsets(text)
    insert_at = offsets[ytd_nodes[0].lineno - 1]
    return text.encode("utf-8")[:insert_at].decode("utf-8") + block + text.encode("utf-8")[insert_at:].decode("utf-8")


def widen_finance_override(text: str) -> str:
    matches = named_functions(text, "_hades_direct_finance_guidance")
    if len(matches) != 2:
        raise SystemExit("FAIL active overlay must contain the reviewed two finance definitions")
    fn = matches[-1]
    start, end = node_span(text, fn)
    segment = text.encode("utf-8")[start:end].decode("utf-8")
    old_period = r"\b(?:year[ -]to[ -]date|ytd|this\s+year|since\s+january)\b"
    new_period = (
        r"\b(?:year[ -]to[ -]date|ytd|this\s+year|since\s+january|"
        r"(?:in|over|during)\s+(?:the\s+)?(?:last|past)\s+year|"
        r"(?:last|past)\s+12\s+months|(?:last|previous)\s+year)\b"
    )
    if segment.count(old_period) != 1:
        raise SystemExit("FAIL active finance override period classifier changed")
    segment = segment.replace(old_period, new_period, 1)
    if segment.count(r"\b(?:at|with|from)\s+\w") != 1:
        raise SystemExit("FAIL active finance override merchant classifier changed")
    segment = segment.replace(r"\b(?:at|with|from)\s+\w", r"\b(?:at|on|with|from)\s+\w", 1)
    return text.encode("utf-8")[:start].decode("utf-8") + segment + text.encode("utf-8")[end:].decode("utf-8")


def patch_legacy_turn_gates(text: str) -> str:
    if text.count(GROCY_READ_GATE_OLD) != 1:
        raise SystemExit("FAIL expected one malformed active Grocy read gate")
    text = text.replace(GROCY_READ_GATE_OLD, GROCY_READ_GATE_NEW, 1)
    provisioning_count = text.count(PROVISIONING_PATTERN_OLD)
    if provisioning_count < 3:
        raise SystemExit("FAIL expected active provisioning checks in the legacy overlay")
    text = text.replace(PROVISIONING_PATTERN_OLD, PROVISIONING_PATTERN_NEW)
    return text


def compose(active: bytes, source: bytes) -> bytes:
    active_text = active.decode("utf-8", errors="strict")
    source_text = source.decode("utf-8", errors="strict")
    # Constants define both routing eligibility and the read-only memory guard.
    for name in REPLACED_ASSIGNMENTS:
        active_text = replace_top_level_assignment(active_text, source_text, name)
    # Replace only reviewed operation/scope helpers. The alias helper is new in
    # the candidate and is inserted before its single-name compatibility API.
    for name in ("_hades_grocy_read_operation", "_hades_broad_homelab_status_intent", "_hades_homelab_read_followup_query"):
        active_text = replace_top_level_function(active_text, source_text, name)
    if named_functions(active_text, "_hades_configured_homelab_alias_matches"):
        raise SystemExit("FAIL live overlay unexpectedly already has the multi-alias helper")
    source_matches = named_functions(source_text, "_hades_configured_homelab_alias_matches")
    active_alias = named_functions(active_text, "_hades_configured_homelab_alias_match")
    if len(source_matches) != 1 or len(active_alias) != 1:
        raise SystemExit("FAIL configured homelab alias helpers are ambiguous")
    active_text = replace_top_level_function(active_text, source_text, "_hades_configured_homelab_alias_match")
    active_alias = named_functions(active_text, "_hades_configured_homelab_alias_match")[0]
    a, _ = node_span(active_text, active_alias)
    c, d = node_span(source_text, source_matches[0])
    active_text = active_text.encode("utf-8")[:a].decode("utf-8") + source_text.encode("utf-8")[c:d].decode("utf-8") + "\n\n" + active_text.encode("utf-8")[a:].decode("utf-8")
    active_text = insert_grocy_list_guard(active_text)
    active_text = insert_finance_period_block(active_text, source_text)
    active_text = widen_finance_override(active_text)
    active_text = patch_legacy_turn_gates(active_text)
    try:
        compile(active_text, "composed-sitecustomize.py", "exec")
        ast.parse(active_text)
    except SyntaxError as exc:
        raise SystemExit(f"FAIL composed overlay is invalid Python: {exc}") from None
    return active_text.encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--active-overlay", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-active-sha256", required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    args = parser.parse_args()
    active_path = args.active_overlay.resolve(strict=True)
    source_path = args.source.resolve(strict=True)
    output = args.output.absolute()
    if output.exists() or output.is_symlink() or output in {active_path, source_path}:
        raise SystemExit("FAIL output must be a new path distinct from both inputs")
    if not output.parent.is_dir():
        raise SystemExit("FAIL output parent directory does not exist")
    active = require_regular(active_path, "active overlay")
    source = require_regular(source_path, "candidate source")
    active_sha, source_sha = sha256(active), sha256(source)
    if active_sha != args.expected_active_sha256:
        raise SystemExit(f"FAIL active overlay checksum mismatch: {active_sha}")
    if source_sha != args.expected_source_sha256:
        raise SystemExit(f"FAIL candidate source checksum mismatch: {source_sha}")
    candidate = compose(active, source)
    fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(candidate)
        stream.flush()
        os.fsync(stream.fileno())
    print("PASS composed owner-regression fixes while preserving unrelated live overlay content")
    print(f"active_sha256={active_sha}")
    print(f"source_sha256={source_sha}")
    print(f"candidate_sha256={sha256(candidate)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
