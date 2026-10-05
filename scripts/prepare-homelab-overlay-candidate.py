#!/usr/bin/env python3
"""Compose the tracked read-only guest-visibility wrapper into an overlay copy."""

from __future__ import annotations

import argparse
import ast
import os
import stat
from pathlib import Path

FUNCTIONS = ("_hades_homelab_guest_visibility_response",)
LOADER = "_hades_load_homelab_views"


def read_regular(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise SystemExit(f"FAIL {label} must be a regular non-symlink file")
    return path.read_bytes()


def source_spans(data: bytes, label: str, names: tuple[str, ...], require_loader_call: bool = False) -> dict[str, tuple[int, int]]:
    try:
        text = data.decode("utf-8", errors="strict")
        tree = ast.parse(text, filename=label)
    except (UnicodeError, SyntaxError):
        raise SystemExit(f"FAIL {label} is not valid UTF-8 Python") from None
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line.encode("utf-8")))
    spans: dict[str, tuple[int, int]] = {}
    for name in names:
        matches = [node for node in ast.walk(tree)
                   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
        top_level = [node for node in tree.body
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
        if len(matches) != 1 or len(top_level) != 1 or matches[0] is not top_level[0]:
            raise SystemExit(f"FAIL {label} must define exactly one top-level {name}")
        node = matches[0]
        if node.decorator_list or node.lineno < 1 or node.end_lineno is None:
            raise SystemExit(f"FAIL {label} has an unsupported {name} definition")
        if require_loader_call and LOADER not in {
            child.func.id for child in ast.walk(node)
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
        }:
            raise SystemExit(f"FAIL {label} {name} does not use the compatibility loader")
        spans[name] = (offsets[node.lineno - 1], offsets[node.end_lineno])
    return spans


def compose(active: bytes, source: bytes, active_label: str = "active overlay", source_label: str = "tracked overlay") -> bytes:
    active_spans = source_spans(active, active_label, FUNCTIONS)
    source_spans_by_name = source_spans(source, source_label, FUNCTIONS, True)
    source_spans(active, active_label, (LOADER,))
    source_spans(source, source_label, (LOADER,))
    replacements = []
    for name in FUNCTIONS:
        source_start, source_end = source_spans_by_name[name]
        active_start, active_end = active_spans[name]
        replacements.append((active_start, active_end, source[source_start:source_end]))
    result = active
    for start, end, replacement in sorted(replacements, reverse=True):
        result = result[:start] + replacement + result[end:]
    try:
        compile(result, active_label, "exec")
    except SyntaxError:
        raise SystemExit("FAIL composed overlay is not valid Python") from None
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--active-overlay", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1] / "hermes/sitecustomize.py")
    args = parser.parse_args()
    if args.active_overlay.is_symlink() or args.source.is_symlink():
        raise SystemExit("FAIL input overlays must be regular files, not symlinks")
    active_path = args.active_overlay.resolve(strict=True)
    source_path = args.source.resolve(strict=True)
    output = args.output.absolute()
    if output in {active_path, source_path} or output.exists() or output.is_symlink():
        raise SystemExit("FAIL candidate output must be a new path")
    if not output.parent.is_dir():
        raise SystemExit("FAIL candidate output parent directory must exist")
    candidate = compose(read_regular(active_path, "active overlay"), read_regular(source_path, "candidate source"), str(active_path), str(source_path))
    try:
        fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise SystemExit("FAIL candidate output must be a new path") from None
    with os.fdopen(fd, "wb") as stream:
        stream.write(candidate)
        stream.flush()
        os.fsync(stream.fileno())
    if stat.S_IMODE(output.stat().st_mode) != 0o600:
        output.unlink(missing_ok=True)
        raise SystemExit("FAIL candidate overlay permissions are not mode 0600")
    print("PASS composed tracked guest-visibility wrapper; preserved remaining overlay bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
