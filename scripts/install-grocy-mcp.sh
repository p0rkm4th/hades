#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
source "$repo_dir/config/versions.env"
prefix=/opt/hades-grocy-mcp
python_bin=''
prefix_created=0
cleanup() {
  status=$?
  trap - EXIT
  if ((prefix_created)) && ((status != 0)); then rm -rf -- "$prefix"; fi
  exit "$status"
}
trap cleanup EXIT
while (($#)); do
  case "$1" in
    --prefix) prefix=${2:?--prefix needs an absolute directory}; shift 2 ;;
    --python) python_bin=${2:?--python needs an interpreter}; shift 2 ;;
    *) echo "FAIL unknown option: $1" >&2; exit 2 ;;
  esac
done
[[ "$prefix" == /* ]] || { echo 'FAIL Grocy MCP prefix must be absolute' >&2; exit 2; }
if [[ -z "$python_bin" ]]; then
  for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then python_bin=$(command -v "$candidate"); break; fi
  done
fi
[[ -x "$python_bin" ]] || { echo "FAIL Python is unavailable for Grocy MCP: $python_bin" >&2; exit 1; }

if [[ -e "$prefix" || -L "$prefix" ]]; then
  [[ -d "$prefix" && ! -L "$prefix" && -d "$prefix/venv" && ! -L "$prefix/venv" && -x "$prefix/venv/bin/grocy-mcp" ]] || {
    echo "FAIL existing Grocy MCP installation is incomplete: $prefix" >&2; exit 1;
  }
  installed=$("$prefix/venv/bin/python" -c 'import importlib.metadata as m; print(m.version("grocy-mcp"))')
  [[ "$installed" == "$HADES_GROCY_MCP_VERSION" ]] || {
    echo "FAIL existing Grocy MCP version $installed differs from pinned $HADES_GROCY_MCP_VERSION" >&2; exit 1;
  }
  expected_lock=$(sha256sum "$repo_dir/integrations/grocy-mcp/requirements.lock" | awk '{print $1}')
  recorded_lock=$(awk -F= '$1 == "lock_sha256" {print $2}' "$prefix/manifest" 2>/dev/null || true)
  [[ "$recorded_lock" == "$expected_lock" ]] || {
    echo 'FAIL installed Grocy MCP dependency lock differs from the repository; preserve it and use a fresh reviewed target' >&2; exit 1;
  }
  echo "PASS pinned Grocy MCP $installed already installed"
  exit 0
fi

parent=$(dirname "$prefix")
mkdir -p "$parent"
mkdir -m 0755 "$prefix"
prefix_created=1
"$python_bin" -m venv "$prefix/venv"
PIP_NO_CACHE_DIR=1 "$prefix/venv/bin/python" -m pip install --quiet --disable-pip-version-check --no-input -r "$repo_dir/integrations/grocy-mcp/requirements.lock"
installed=$("$prefix/venv/bin/python" -c 'import importlib.metadata as m; print(m.version("grocy-mcp"))')
[[ "$installed" == "$HADES_GROCY_MCP_VERSION" && -x "$prefix/venv/bin/grocy-mcp" ]] || {
  echo 'FAIL installed Grocy MCP does not match the pinned executable contract' >&2; exit 1;
}
printf 'version=%s\nlock_sha256=%s\n' "$installed" "$(sha256sum "$repo_dir/integrations/grocy-mcp/requirements.lock" | awk '{print $1}')" > "$prefix/manifest"
chmod 0644 "$prefix/manifest"
prefix_created=0
echo "PASS pinned Grocy MCP $installed installed at $prefix"
