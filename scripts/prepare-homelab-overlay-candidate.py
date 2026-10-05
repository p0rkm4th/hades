#!/usr/bin/env python3
"""Copy two current homelab wrappers into a deployment-local overlay copy."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
from pathlib import Path

FUNCTIONS = (
    "_hades_homelab_guest_visibility_response",
    "_hades_household_homelab_boundary_response",
)
LOADER = "_hades_load_homelab_views"


def _manifest_module():
    path = Path(__file__).resolve().with_name("hermes-overlay-composition.py")
    spec = importlib.util.spec_from_file_location("_hades_overlay_composition", path)
    if spec is None or spec.loader is None:
        raise SystemExit("FAIL overlay composition manifest helper is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_private_new(path: Path, data: bytes) -> None:
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise SystemExit("FAIL candidate output and manifest must be new paths") from None
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    if path.stat().st_mode & 0o777 != 0o600:
        path.unlink(missing_ok=True)
        raise SystemExit("FAIL candidate artifact permissions are not mode 0600")


def read_regular(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise SystemExit(f"FAIL {label} must be a regular non-symlink file")
    return path.read_bytes()


def source_spans(
    data: bytes, label: str, names: tuple[str, ...], require_loader_call: bool = False
) -> dict[str, tuple[int, int]]:
    try:
        text = data.decode("utf-8")
        tree = ast.parse(text, filename=label)
    except (UnicodeError, SyntaxError):
        raise SystemExit(f"FAIL {label} is not valid UTF-8 Python") from None

    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line.encode("utf-8")))

    spans: dict[str, tuple[int, int]] = {}
    for name in names:
        matches = [
            node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
        ]
        top_level = [
            node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
        ]
        if len(matches) != 1 or len(top_level) != 1 or matches[0] is not top_level[0]:
            raise SystemExit(f"FAIL {label} must define exactly one top-level {name}")
        node = matches[0]
        if node.decorator_list or node.lineno < 1 or node.end_lineno is None:
            raise SystemExit(f"FAIL {label} has an unsupported {name} definition")
        start = offsets[node.lineno - 1]
        end = offsets[node.end_lineno]
        if require_loader_call and LOADER not in {
            child.func.id for child in ast.walk(node)
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
        }:
            raise SystemExit(f"FAIL {label} {name} does not use the compatibility loader")
        spans[name] = (start, end)
    return spans


def compose(active: bytes, source: bytes, active_label: str, source_label: str) -> bytes:
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
    parser.add_argument("--manifest-output", required=True, type=Path)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()

    repo = args.repo.resolve(strict=True)
    canonical_source = repo / "hermes/sitecustomize.py"
    source_arg = args.source or canonical_source
    if source_arg.is_symlink() or source_arg.resolve(strict=True) != canonical_source.resolve(strict=True):
        raise SystemExit("FAIL source must be the tracked Hermes overlay in the selected repository")
    active_path = args.active_overlay.resolve(strict=True)
    source_path = source_arg.resolve(strict=True)
    output = args.output.absolute()
    manifest_output = args.manifest_output.absolute()
    if args.active_overlay.is_symlink() or source_arg.is_symlink():
        raise SystemExit("FAIL input overlays must be regular files, not symlinks")
    outputs = {output, manifest_output}
    if len(outputs) != 2 or outputs & {active_path, source_path}:
        raise SystemExit("FAIL candidate output and manifest paths must be distinct from inputs")
    for path in outputs:
        if path.exists() or path.is_symlink():
            raise SystemExit("FAIL candidate output and manifest must be new paths")
        if not path.parent.is_dir():
            raise SystemExit("FAIL candidate output parent directory must exist")

    active = read_regular(active_path, "active overlay")
    source = read_regular(source_path, "candidate source")
    candidate = compose(active, source, str(active_path), str(source_path))
    manifest = _manifest_module().build_manifest(repo, active, candidate)
    manifest_bytes = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    written: list[Path] = []
    try:
        _write_private_new(output, candidate)
        written.append(output)
        _write_private_new(manifest_output, manifest_bytes)
        written.append(manifest_output)
    except BaseException:
        for path in written:
            path.unlink(missing_ok=True)
        raise
    print("PASS composed two homelab wrappers and wrote a mode-0600 identity manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
