#!/usr/bin/env bash
set -Eeuo pipefail

prefix=/opt/hades-hermes
artifact=''
url=''
expected_sha=''
staging=''
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
hermes_source_version=${HADES_HERMES_SOURCE_VERSION:-${HADES_HERMES_VERSION:-}}
hermes_source_commit=${HADES_HERMES_SOURCE_COMMIT:-}
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
    --version) hermes_source_version=${2:?--version needs a version}; shift 2 ;;
    --commit) hermes_source_commit=${2:?--commit needs a commit SHA}; shift 2 ;;
    -h|--help) echo 'usage: install-hermes-artifact.sh --prefix ABS_DIR [--artifact ABS_FILE | --url URL --sha256 SHA256] [--version VERSION --commit SHA]'; exit 0 ;;
    *) echo "FAIL unknown option: $1" >&2; exit 2 ;;
  esac
done
[[ "$prefix" == /* ]] || { echo 'FAIL Hermes prefix must be absolute' >&2; exit 1; }
validate_build_tools() {
  command -v "$python_bin" >/dev/null 2>&1 || { echo "FAIL Hermes requires Python 3.11 through 3.13; interpreter not found: $python_bin" >&2; exit 1; }
  python_version=$("$python_bin" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null) || {
    echo 'FAIL could not read the Hermes Python interpreter version' >&2; exit 1;
  }
  [[ "$python_version" =~ ^3\.(11|12|13)$ ]] || {
    if [[ "$python_version" == '3.14' && "$hermes_source_version" == '0.21.6' ]]; then
      : # Hermes 0.21.6's published project metadata supports Python 3.14.
    else
      echo "FAIL Hermes ${hermes_source_version:-unknown} requires Python >=3.11,<3.14 (found ${python_version:-unknown})" >&2; exit 1
    fi
  }
  [[ -n "$uv_bin" && -x "$uv_bin" ]] || { echo 'FAIL pinned uv is unavailable; run scripts/prepare-hades-host.sh --apply' >&2; exit 1; }
  uv_reported=$("$uv_bin" --version 2>/dev/null | awk '{print $1 " " $2}' || true)
  [[ "$uv_reported" == "uv $uv_version" ]] || {
    echo "FAIL Hermes build requires uv ${uv_version:-from config/versions.env} (found ${uv_reported:-unavailable})" >&2; exit 1;
  }
}
case "$hermes_source_version" in
  0.21.2) hermes_sync_args=(--extra all --extra hindsight --locked) ;;
  # Hermes 0.21.6 moved Hindsight to its external memory-plugin catalog; its
  # pyproject no longer declares the 0.21.2 `hindsight` extra.
  0.21.6)
    hermes_sync_args=(--extra all --locked)
    hermes_source_commit=${hermes_source_commit:-${HADES_HERMES_CANDIDATE_SOURCE_COMMIT:-}}
    [[ "$hermes_source_commit" =~ ^[0-9a-f]{40}$ ]] || {
      echo 'FAIL Hermes 0.21.6 install requires its exact source commit SHA' >&2; exit 1;
    }
    ;;
  *) echo "FAIL Hermes ${hermes_source_version:-unknown} has no reviewed dependency-install profile" >&2; exit 1 ;;
esac
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
  UV_PROJECT_ENVIRONMENT="$prefix/venv" \
    UV_PYTHON="$prefix/venv/bin/python" \
    "$uv_bin" sync "${hermes_sync_args[@]}"
)
if [[ "$hermes_source_version" == '0.21.6' ]]; then
  stamp_writer="$prefix/source/scripts/write_install_stamp.py"
  [[ -f "$stamp_writer" ]] || { echo 'FAIL Hermes 0.21.6 source lacks its native install-stamp writer' >&2; exit 1; }
  "$python_bin" "$stamp_writer" \
    --output "$prefix/source/install-stamp.json" \
    --commit "$hermes_source_commit" \
    --base-version "$hermes_source_version" \
    --distance 0 --source build --update-mechanism external
fi
install -d -m 0755 "$prefix/bin"
printf '%s\n' '#!/usr/bin/env bash' "exec $prefix/venv/bin/python -m hermes_cli.main \"\$@\"" > "$prefix/bin/hermes"
chmod 0755 "$prefix/bin/hermes"
printf 'artifact_url=%s\nartifact_version=%s\nartifact_sha256=%s\ninstallation=python-venv-uv-locked-editable\nsource=%s\n' \
  "${url:-local-file}" "${hermes_source_version:-unknown}" "$actual_sha" "$prefix/source" > "$prefix/provenance"
chmod 0644 "$prefix/provenance"
printf 'PASS Hermes %s installed from verified artifact %s\n' "${hermes_source_version:-unknown}" "$actual_sha"
