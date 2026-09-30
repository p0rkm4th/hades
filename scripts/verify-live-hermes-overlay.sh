#!/usr/bin/env bash
set -euo pipefail

# Read-only deployment drift check. The installed overlay path is deliberately
# an argument because it is operator topology, not public HADES configuration.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
installed=${1:-}
if [[ -z "$installed" ]]; then
  printf 'usage: %s /path/to/installed/sitecustomize.py\n' "$0" >&2
  exit 2
fi
[[ -f "$installed" && ! -L "$installed" ]] || {
  printf 'FAIL installed overlay is not a regular non-symlink file: %s\n' "$installed" >&2
  exit 1
}
cmp -s "$repo_dir/hermes/sitecustomize.py" "$installed" || {
  printf 'FAIL live Hermes overlay differs from repository overlay\n' >&2
  exit 1
}
python3 - "$installed" <<'PY'
from pathlib import Path
import sys
compile(Path(sys.argv[1]).read_text(encoding="utf-8"), sys.argv[1], "exec")
PY
printf 'PASS live Hermes overlay matches repository source\n'
sha256sum "$repo_dir/hermes/sitecustomize.py" "$installed"
