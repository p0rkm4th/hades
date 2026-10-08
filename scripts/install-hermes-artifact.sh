#!/usr/bin/env bash
set -Eeuo pipefail

prefix=/opt/hades-hermes
artifact=''
url=''
expected_sha=''
candidate=0
python_minors='11|12|13'
python_upper='3.14'
staging=''
python_overridden=${HADES_HERMES_PYTHON+x}
python_bin=${HADES_HERMES_PYTHON:-python3.13}
uv_bin=${HADES_UV_EXECUTABLE:-}
tmp=''
prefix_created=0
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cleanup() {
  local status=$?
  if (( prefix_created )) && (( status != 0 )); then rm -rf -- "$prefix"; fi
  [[ -z "$staging" || ! -d "$staging" ]] || rm -rf -- "$staging"
  [[ -z "$tmp" || ! -e "$tmp" ]] || rm -f -- "$tmp"
  return "$status"
}
trap cleanup EXIT
if [[ -f "$repo_dir/config/versions.env" ]]; then
  # shellcheck disable=SC1091
  source "$repo_dir/config/versions.env"
fi
uv_version=${HADES_HERMES_UV_VERSION:-}
if [[ -z "$uv_bin" ]]; then
  if [[ -n "$uv_version" && -x "/opt/hades-hermes-tools/uv-$uv_version/bin/uv" ]]; then
    uv_bin="/opt/hades-hermes-tools/uv-$uv_version/bin/uv"
  else
    uv_bin=$(command -v uv || true)
  fi
fi
while (($#)); do
  case "$1" in
    --prefix) prefix=${2:?--prefix needs a directory}; shift 2 ;;
    --artifact) artifact=${2:?--artifact needs a file}; shift 2 ;;
    --url) url=${2:?--url needs a URL}; shift 2 ;;
    --sha256) expected_sha=${2:?--sha256 needs a checksum}; shift 2 ;;
    --candidate) candidate=1; shift ;;
    -h|--help) echo 'usage: install-hermes-artifact.sh --prefix ABS_DIR [--candidate] [--artifact ABS_FILE | --url URL --sha256 SHA256]'; exit 0 ;;
    *) echo "FAIL unknown option: $1" >&2; exit 2 ;;
  esac
done
if (( candidate )); then
  HADES_HERMES_VERSION=${HADES_HERMES_CANDIDATE_VERSION:?missing Hermes candidate version}
  HADES_HERMES_SOURCE_VERSION=$HADES_HERMES_CANDIDATE_VERSION
  HADES_HERMES_SOURCE_COMMIT=${HADES_HERMES_CANDIDATE_SOURCE_COMMIT:?missing Hermes candidate source commit}
  candidate_url=${HADES_HERMES_CANDIDATE_SOURCE_URL:?missing Hermes candidate source URL}
  candidate_sha=${HADES_HERMES_CANDIDATE_SOURCE_SHA256:?missing Hermes candidate source checksum}
  [[ -z "$url" || "$url" == "$candidate_url" ]] || {
    echo 'FAIL Hermes candidate URL must match the pinned candidate source URL' >&2; exit 1;
  }
  [[ -z "$expected_sha" || "$expected_sha" == "$candidate_sha" ]] || {
    echo 'FAIL Hermes candidate checksum must match the pinned candidate source checksum' >&2; exit 1;
  }
  url=$candidate_url
  expected_sha=$candidate_sha
  if [[ -z "$python_overridden" ]]; then
    python_bin=python3.14
  fi
  python_minors='11|12|13|14'
  python_upper='3.15'
else
  production_sha=${HADES_HERMES_SOURCE_SHA256:?missing pinned Hermes source checksum}
  [[ -z "$expected_sha" || "$expected_sha" == "$production_sha" ]] || {
    echo 'FAIL Hermes source checksum must match the pinned production source checksum' >&2; exit 1;
  }
  expected_sha=$production_sha
fi
[[ "$prefix" == /* ]] || { echo 'FAIL Hermes prefix must be absolute' >&2; exit 1; }
validate_build_tools() {
  command -v "$python_bin" >/dev/null 2>&1 || { echo "FAIL Hermes requires Python >=3.11,<${python_upper}; interpreter not found: $python_bin" >&2; exit 1; }
  python_version=$("$python_bin" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null) || {
    echo 'FAIL could not read the Hermes Python interpreter version' >&2; exit 1;
  }
  [[ "$python_version" =~ ^3\.(${python_minors})$ ]] || {
    echo "FAIL Hermes ${HADES_HERMES_VERSION:-0.21.2} requires Python >=3.11,<${python_upper} (found ${python_version:-unknown})" >&2; exit 1;
  }
  [[ -n "$uv_bin" && -x "$uv_bin" ]] || { echo 'FAIL pinned uv is unavailable; run scripts/prepare-hades-host.sh --apply' >&2; exit 1; }
  uv_reported=$("$uv_bin" --version 2>/dev/null | awk '{print $1 " " $2}' || true)
  [[ "$uv_reported" == "uv $uv_version" ]] || {
    echo "FAIL Hermes build requires uv ${uv_version:-from config/versions.env} (found ${uv_reported:-unavailable})" >&2; exit 1;
  }
}
if [[ -n "$artifact" ]]; then
  [[ "$artifact" == /* && -f "$artifact" && ! -L "$artifact" ]] || { echo 'FAIL Hermes artifact must be an absolute regular file' >&2; exit 1; }
  [[ -n "$expected_sha" ]] || expected_sha="${HADES_HERMES_SOURCE_SHA256:-}"
else
  : "${url:=${HADES_HERMES_SOURCE_URL:?missing Hermes source URL}}"
  : "${expected_sha:=${HADES_HERMES_SOURCE_SHA256:?missing Hermes source checksum}}"
  validate_build_tools
  tmp=$(mktemp)
  staging=$(mktemp -d)
  curl --fail --silent --show-error --location --max-time 120 --output "$tmp" "$url"
  artifact=$tmp
fi
[[ "$expected_sha" =~ ^[0-9a-f]{64}$ ]] || { echo 'FAIL Hermes artifact checksum is invalid' >&2; exit 1; }
actual_sha=$(sha256sum "$artifact" | awk '{print $1}')
[[ "$actual_sha" == "$expected_sha" ]] || { echo 'FAIL Hermes artifact checksum mismatch' >&2; exit 1; }
validate_build_tools
staging=${staging:-$(mktemp -d)}
tar -xzf "$artifact" -C "$staging"
source_dir=$(find "$staging" -mindepth 1 -maxdepth 2 -type f -name pyproject.toml -printf '%h\n' -quit)
[[ -n "$source_dir" ]] || { echo 'FAIL Hermes source archive has no pyproject.toml' >&2; exit 1; }
[[ ! -e "$prefix" && ! -L "$prefix" ]] || { echo 'FAIL Hermes prefix already exists; choose a fresh versioned prefix' >&2; exit 1; }
mkdir -p "$prefix"
prefix_created=1
mv "$source_dir" "$prefix/source"
"$python_bin" -m venv "$prefix/venv"
(
  cd "$prefix/source"
  # Hermes 0.21.5 moved Hindsight out of its project extras into the plugin
  # catalog. Keep using the locked extra on releases that still declare it;
  # newer releases install the catalog plugin and its pinned dependencies
  # through Hermes' plugin manager instead.
  if "$prefix/venv/bin/python" - <<'PY'
import pathlib, tomllib
project = tomllib.loads(pathlib.Path("pyproject.toml").read_text())
raise SystemExit(0 if "hindsight" in project.get("project", {}).get("optional-dependencies", {}) else 1)
PY
  then
    extras=(--extra all --extra hindsight --locked)
  else
    extras=(--extra all --locked)
  fi
  UV_PROJECT_ENVIRONMENT="$prefix/venv" \
    UV_PYTHON="$prefix/venv/bin/python" \
    "$uv_bin" sync "${extras[@]}"
)
if [[ -f "$prefix/source/scripts/write_install_stamp.py" ]]; then
  source_commit=${HADES_HERMES_SOURCE_COMMIT:-}
  [[ "$source_commit" =~ ^[0-9a-f]{40}$ ]] || {
    echo 'FAIL Hermes release source commit must be pinned before writing install-stamp.json' >&2
    exit 1
  }
  "$prefix/venv/bin/python" "$prefix/source/scripts/write_install_stamp.py" \
    --output "$prefix/source/install-stamp.json" \
    --commit "$source_commit" \
    --base-version "${HADES_HERMES_SOURCE_VERSION:-${HADES_HERMES_VERSION:-unknown}}" \
    --distance 0 --source local --update-mechanism external
fi
install -d -m 0755 "$prefix/bin"
printf '%s\n' '#!/usr/bin/env bash' "exec $prefix/venv/bin/python -m hermes_cli.main \"\$@\"" > "$prefix/bin/hermes"
chmod 0755 "$prefix/bin/hermes"
printf 'artifact_url=%s\nartifact_version=%s\nartifact_sha256=%s\nsource_commit=%s\ninstallation=python-venv-uv-locked-editable\nsource=%s\n' \
  "${url:-local-file}" "${HADES_HERMES_SOURCE_VERSION:-unknown}" "$actual_sha" \
  "${HADES_HERMES_SOURCE_COMMIT:-unknown}" "$prefix/source" > "$prefix/provenance"
chmod 0644 "$prefix/provenance"
printf 'PASS Hermes %s installed from verified artifact %s\n' "${HADES_HERMES_VERSION:-unknown}" "$actual_sha"
