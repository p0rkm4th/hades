#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
python3 - "$repo_dir/hermes/sitecustomize.py" <<'PY'
import ast
import sys
from pathlib import Path

tree = ast.parse(Path(sys.argv[1]).read_text(encoding="utf-8"))
route_functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_hades_apply_fast_completion_route"]
assert len(route_functions) == 1, "expected one HADES fast-route helper"
assert [arg.arg for arg in route_functions[0].args.args] == ["route", "user_message"], "fast-route helper signature drifted"
calls = [
    node for node in ast.walk(tree)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Name)
    and node.func.id == "_hades_apply_fast_completion_route"
]
assert calls and all(len(node.args) == 2 for node in calls), "fast-route call arity mismatch"
print("PASS HADES fast-route helper and call signatures agree")
PY
tmp_root=${TMPDIR:-/tmp}/hades-overlay-contract.$$
mkdir -p "$tmp_root"
trap 'find "$tmp_root" -depth -type f -delete; find "$tmp_root" -depth -type d -empty -delete' EXIT
cp "$repo_dir/hermes/sitecustomize.py" "$tmp_root/sitecustomize.py"
bash "$repo_dir/scripts/verify-live-hermes-overlay.sh" "$tmp_root/sitecustomize.py" >/dev/null
printf '\n# drift fixture\n' >> "$tmp_root/sitecustomize.py"
if bash "$repo_dir/scripts/verify-live-hermes-overlay.sh" "$tmp_root/sitecustomize.py" >/dev/null 2>&1; then
  printf 'FAIL overlay drift was accepted\n' >&2
  exit 1
fi
printf 'PASS live Hermes overlay drift contract\n'
