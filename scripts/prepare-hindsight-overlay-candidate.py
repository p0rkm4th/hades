#!/usr/bin/env python3
"""Replace only the HADES direct-memory function in a deployed overlay copy."""
from __future__ import annotations

import argparse
import ast
import hashlib
import os
from pathlib import Path

FUNCTION_NAME = "_hades_direct_memory_response"


def function_node(source: str, label: str) -> ast.FunctionDef:
    tree = ast.parse(source, filename=label)
    found = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == FUNCTION_NAME
    ]
    if len(found) != 1:
        raise ValueError(f"{label} must define exactly one {FUNCTION_NAME}")
    return found[0]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--active-overlay", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--source", type=Path,
        default=Path(__file__).resolve().parents[1] / "hermes/sitecustomize.py",
    )
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
    active_node = function_node(active_text, str(active))
    source_node = function_node(source_text, str(source_path))
    if active_node.col_offset != source_node.col_offset:
        raise SystemExit("FAIL overlay function nesting differs; refusing to compose")
    if ast.dump(active_node.args) != ast.dump(source_node.args):
        raise SystemExit("FAIL overlay function signature differs; refusing to compose")

    active_lines = active_text.splitlines(keepends=True)
    source_lines = source_text.splitlines(keepends=True)
    replacement = source_lines[source_node.lineno - 1:source_node.end_lineno]
    result_lines = (
        active_lines[:active_node.lineno - 1]
        + replacement
        + active_lines[active_node.end_lineno:]
    )
    candidate_bytes = "".join(result_lines).encode("utf-8")
    candidate_text = candidate_bytes.decode("utf-8")
    compile(candidate_text, str(output), "exec")
    candidate_node = function_node(candidate_text, str(output))
    if ast.get_source_segment(candidate_text, candidate_node) != ast.get_source_segment(source_text, source_node):
        raise SystemExit("FAIL candidate function does not match repository source")
    replacement_size = source_node.end_lineno - source_node.lineno + 1
    suffix = active_lines[active_node.end_lineno:]
    if result_lines[active_node.lineno - 1 + replacement_size:] != suffix:
        raise SystemExit("FAIL candidate changed content outside target function")
    prefix = active_lines[:active_node.lineno - 1]
    if result_lines[:len(prefix)] != prefix:
        raise SystemExit("FAIL candidate changed content before target function")

    fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(candidate_bytes)
        stream.flush()
        os.fsync(stream.fileno())
    print(f"PASS replaced only {FUNCTION_NAME}; non-target content preserved")
    print(f"active_sha256={digest(active_bytes)}")
    print(f"source_sha256={digest(source_bytes)}")
    print(f"candidate_sha256={digest(candidate_bytes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
