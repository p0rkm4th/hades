#!/usr/bin/env bash
set -Eeuo pipefail

prefix=/opt/hades-hermes
artifact=''
url=''
expected_sha=''
staging=''
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [[ -f "$repo_dir/config/versions.env" ]]; then
  # shellcheck disable=SC1091
  source "$repo_dir/config/versions.env"
fi
while (($#)); do
  case "$1" in
    --prefix) prefix=${2:?--prefix needs a directory}; shift 2 ;;
    --artifact) artifact=${2:?--artifact needs a file}; shift 2 ;;
    --url) url=${2:?--url needs a URL}; shift 2 ;;
    --sha256) expected_sha=${2:?--sha256 needs a checksum}; shift 2 ;;
    -h|--help) echo 'usage: install-hermes-artifact.sh --prefix ABS_DIR [--artifact ABS_FILE | --url URL --sha256 SHA256]'; exit 0 ;;
    *) echo "FAIL unknown option: $1" >&2; exit 2 ;;
  esac
done
[[ "$prefix" == /* ]] || { echo 'FAIL Hermes prefix must be absolute' >&2; exit 1; }
if [[ -n "$artifact" ]]; then
  [[ "$artifact" == /* && -f "$artifact" && ! -L "$artifact" ]] || { echo 'FAIL Hermes artifact must be an absolute regular file' >&2; exit 1; }
  [[ -n "$expected_sha" ]] || expected_sha="${HADES_HERMES_SOURCE_SHA256:-}"
else
  : "${url:=${HADES_HERMES_SOURCE_URL:?missing Hermes source URL}}"
  : "${expected_sha:=${HADES_HERMES_SOURCE_SHA256:?missing Hermes source checksum}}"
  tmp=$(mktemp)
  staging=$(mktemp -d)
  trap 'find "$staging" -depth -delete 2>/dev/null || true; rmdir "$staging" 2>/dev/null || true; find "$tmp" -delete 2>/dev/null || true' EXIT
  curl --fail --silent --show-error --location --max-time 120 --output "$tmp" "$url"
  artifact=$tmp
fi
[[ "$expected_sha" =~ ^[0-9a-f]{64}$ ]] || { echo 'FAIL Hermes artifact checksum is invalid' >&2; exit 1; }
actual_sha=$(sha256sum "$artifact" | awk '{print $1}')
[[ "$actual_sha" == "$expected_sha" ]] || { echo 'FAIL Hermes artifact checksum mismatch' >&2; exit 1; }
python_bin=''
for candidate in python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    python_bin=$(command -v "$candidate")
    break
  fi
done
[[ -n "$python_bin" ]] || {
  echo 'FAIL Hermes requires Python 3.11 or newer; install a compatible python3.x package' >&2
  exit 1
}
staging=${staging:-$(mktemp -d)}
trap 'find "$staging" -depth -delete 2>/dev/null || true; rmdir "$staging" 2>/dev/null || true' EXIT
tar -xzf "$artifact" -C "$staging"
source_dir=$(find "$staging" -mindepth 1 -maxdepth 2 -type f -name pyproject.toml -printf '%h\n' -quit)
[[ -n "$source_dir" ]] || { echo 'FAIL Hermes source archive has no pyproject.toml' >&2; exit 1; }
mkdir -p "$prefix"
"$python_bin" -m venv "$prefix/venv"
"$prefix/venv/bin/python" -m pip install --disable-pip-version-check --no-cache-dir --upgrade pip >/dev/null
# Upstream intentionally rejects ordinary wheel/sdist builds. Its documented
# package-build escape hatch is HERMES_NIX_BUILD=1; use it only for this
# verified source archive so the installed venv remains self-contained after
# the staging directory is removed.
HERMES_NIX_BUILD=1 "$prefix/venv/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
  "${source_dir}[all]" "hindsight-client==${HADES_HERMES_HINDSIGHT_CLIENT_VERSION:-0.6.1}" >/dev/null
install -d -m 0755 "$prefix/bin"
printf '%s\n' '#!/usr/bin/env bash' "exec $prefix/venv/bin/python -m hermes_cli.main \"\$@\"" > "$prefix/bin/hermes"
chmod 0755 "$prefix/bin/hermes"
printf 'artifact_url=%s\nartifact_version=%s\nartifact_sha256=%s\ninstallation=python-venv\n' \
  "${url:-local-file}" "${HADES_HERMES_SOURCE_VERSION:-unknown}" "$actual_sha" > "$prefix/provenance"
chmod 0644 "$prefix/provenance"
printf 'PASS Hermes %s installed from verified artifact %s\n' "${HADES_HERMES_VERSION:-0.14.0}" "$actual_sha"
