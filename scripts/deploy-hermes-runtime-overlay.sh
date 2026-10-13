#!/usr/bin/env bash
set -euo pipefail

die() { printf 'FAIL %s\n' "$1" >&2; exit 1; }
candidate= manifest= manifest_target= target= expected_current= expected_candidate= expected_manifest= rollback_dir= service= python= health_url=
config_inputs=()
while (($#)); do
  case "$1" in
    --candidate|--manifest|--manifest-target|--target|--expected-current-sha256|--expected-candidate-sha256|--expected-manifest-sha256|--rollback-dir|--service|--python|--health-url|--config-input)
      (($# >= 2)) || die "missing value for $1"
      key=$1; value=$2; shift 2
      case "$key" in
        --candidate) candidate=$value ;;
        --manifest) manifest=$value ;;
        --manifest-target) manifest_target=$value ;;
        --target) target=$value ;;
        --expected-current-sha256) expected_current=$value ;;
        --expected-candidate-sha256) expected_candidate=$value ;;
        --expected-manifest-sha256) expected_manifest=$value ;;
        --rollback-dir) rollback_dir=$value ;;
        --service) service=$value ;;
        --python) python=$value ;;
        --health-url) health_url=$value ;;
        --config-input) config_inputs+=("$value") ;;
      esac
      ;;
    *) die "unsupported argument" ;;
  esac
done

[[ $(id -u) == 0 ]] || die "deployment must run as root through the approved scoped privilege path"
for value in "$candidate" "$manifest" "$manifest_target" "$target" "$expected_current" "$expected_candidate" "$expected_manifest" "$rollback_dir" "$service" "$python"; do
[[ -n $value ]] || die "all deployment identity and rollback arguments are required"
done
[[ -n $health_url ]] || die "an approved Hermes health URL is required"
for path in "$candidate" "$manifest" "$manifest_target" "$target" "$rollback_dir" "$python"; do [[ $path == /* ]] || die "filesystem paths must be absolute"; done
[[ $service == hades-hermes.service ]] || die "service differs from the qualified Hermes unit"
[[ $(basename "$target") == sitecustomize.py && $(basename "$manifest_target") == sitecustomize.runtime.json && $(dirname "$target") == "$(dirname "$manifest_target")" ]] || die "runtime artifact and manifest must use the same overlay directory"
[[ $(basename "$rollback_dir") == runtime-convergence-* && -d $(dirname "$rollback_dir") && ! -L $(dirname "$rollback_dir") ]] || die "rollback path must be a new directory under the protected backup root"
[[ $(realpath -e "$(dirname "$target")") == "$(dirname "$target")" && $(realpath -e "$(dirname "$rollback_dir")") == "$(dirname "$rollback_dir")" ]] || die "runtime and rollback parents must be canonical directories"
[[ -f $candidate && ! -L $candidate && -f $manifest && ! -L $manifest ]] || die "candidate and manifest must be regular files"
[[ -f $target && ! -L $target && -d $(dirname "$target") ]] || die "runtime target must be a regular file in an existing directory"
[[ ! -L $manifest_target ]] || die "manifest target must not be a symlink"
[[ $expected_current =~ ^[0-9a-f]{64}$ && $expected_candidate =~ ^[0-9a-f]{64}$ && $expected_manifest =~ ^[0-9a-f]{64}$ ]] || die "checksums must be lowercase SHA-256 values"
[[ $(sha256sum "$target" | awk '{print $1}') == "$expected_current" ]] || die "active runtime checksum changed; recompose before deployment"
[[ $(sha256sum "$candidate" | awk '{print $1}') == "$expected_candidate" ]] || die "candidate checksum differs from the approved checksum"
[[ $(sha256sum "$manifest" | awk '{print $1}') == "$expected_manifest" ]] || die "manifest checksum differs from the approved checksum"
python3 - "$manifest" "$expected_candidate" <<'PY'
import hashlib, json, sys
from pathlib import Path
manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected = sys.argv[2]
core = {key: value for key, value in manifest.items() if key != "manifest_id"}
canonical = (json.dumps(core, sort_keys=True, separators=(",", ":")) + "\n").encode()
if manifest.get("schema") != "hades/hermes-runtime-overlay/v1":
    raise SystemExit("unsupported runtime manifest")
if manifest.get("generated_artifact", {}).get("sha256") != expected:
    raise SystemExit("manifest artifact identity mismatch")
if manifest.get("manifest_id") != hashlib.sha256(canonical).hexdigest():
    raise SystemExit("runtime manifest identity mismatch")
PY
config_args=()
for item in "${config_inputs[@]}"; do config_args+=(--config-input "$item"); done
python3 "$(dirname "$0")/hermes-runtime-artifact.py" verify-config \
  --manifest "$manifest" "${config_args[@]}" >/dev/null \
  || die "live deployment configuration differs from the qualified manifest"

hermes_version=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["hermes_version"])' "$manifest")
python3 "$(dirname "$0")/hermes-runtime-artifact.py" verify-live \
  --installed "$target" --service "$service" --python "$python" \
  --expected-sha256 "$expected_current" --hermes-version "$hermes_version" >/dev/null \
  || die "active overlay is not the artifact selected by the current Hermes process"

install -d -m 0700 "$rollback_dir"
chown 0:0 "$rollback_dir"
chmod 0700 "$rollback_dir"
[[ $(stat -c '%u:%g:%a' "$rollback_dir") == 0:0:700 ]] || die "rollback directory is not protected"
[[ -z $(find "$rollback_dir" -mindepth 1 -maxdepth 1 -print -quit) ]] || die "rollback directory must be empty"
cp -a -- "$target" "$rollback_dir/sitecustomize.py"
[[ $(sha256sum "$rollback_dir/sitecustomize.py" | awk '{print $1}') == "$expected_current" ]] || die "rollback copy failed checksum verification"
target_metadata=$(stat -c '%u:%g:%a:%C' "$target")
deployment_started=0
rollback_attempted=0
current_tmp=

atomic_replace_preserving_target() {
  local source=$1 destination=$2 context
  current_tmp=$(mktemp "$(dirname "$destination")/.runtime-overlay.XXXXXX")
  if [[ -e $destination && ! -L $destination ]]; then
    cp -a -- "$destination" "$current_tmp"
    cat -- "$source" > "$current_tmp"
    chown --reference="$destination" "$current_tmp"
    chmod --reference="$destination" "$current_tmp"
    context=$(stat -c '%C' "$destination")
    if [[ $context != '?' ]] && command -v chcon >/dev/null 2>&1; then chcon "$context" "$current_tmp"; fi
  else
    install -o 0 -g 0 -m 0600 -- "$source" "$current_tmp"
  fi
  mv -Tf -- "$current_tmp" "$destination"
  current_tmp=
}

restore_file() {
  local backup=$1 destination=$2
  current_tmp=$(mktemp "$(dirname "$destination")/.runtime-rollback.XXXXXX")
  rm -f -- "$current_tmp" || return 1
  cp -a -- "$backup" "$current_tmp" || return 1
  mv -Tf -- "$current_tmp" "$destination" || return 1
  current_tmp=
}

health_check() {
  systemctl is-active --quiet "$service" || return 1
  if [[ -n $health_url ]]; then
    curl --fail --silent --show-error --max-time 8 --output /dev/null "$health_url" || return 1
  fi
}

rollback() {
  rollback_attempted=1
  printf 'ROLLBACK restoring verified prior overlay\n' >&2
  restore_file "$rollback_dir/sitecustomize.py" "$target" || return 1
  if [[ -f $rollback_dir/manifest.json ]]; then
    restore_file "$rollback_dir/manifest.json" "$manifest_target" || return 1
  else
    rm -f -- "$manifest_target" || return 1
  fi
  systemctl restart "$service" || return 1
  health_check || return 1
  [[ $(sha256sum "$target" | awk '{print $1}') == "$expected_current" ]] || return 1
  local rollback_args=("$(dirname "$0")/hermes-runtime-artifact.py" verify-live
    --installed "$target" --service "$service" --python "$python"
    --expected-sha256 "$expected_current" --hermes-version "$hermes_version")
  [[ -z $health_url ]] || rollback_args+=(--health-url "$health_url")
  python3 "${rollback_args[@]}" >/dev/null || return 1
  deployment_started=0
}

on_exit() {
  local status=$?
  if [[ -n $current_tmp ]]; then rm -f -- "$current_tmp" || true; current_tmp=; fi
  if ((status != 0 && deployment_started == 1 && rollback_attempted == 0)); then
    if rollback; then
      printf 'ROLLBACK verified; previous runtime restored\n' >&2
    else
      printf 'ROLLBACK FAILED; inspect the preserved artifact and service immediately\n' >&2
    fi
  fi
  exit "$status"
}
trap on_exit EXIT

if [[ -f $manifest_target && ! -L $manifest_target ]]; then cp -a -- "$manifest_target" "$rollback_dir/manifest.json"; fi
deployment_started=1
atomic_replace_preserving_target "$candidate" "$target"
atomic_replace_preserving_target "$manifest" "$manifest_target"
[[ $(sha256sum "$target" | awk '{print $1}') == "$expected_candidate" ]] || die "installed checksum mismatch"
[[ $(stat -c '%u:%g:%a:%C' "$target") == "$target_metadata" ]] || die "runtime ownership, mode, or SELinux context changed"
[[ $(sha256sum "$manifest_target" | awk '{print $1}') == "$expected_manifest" ]] || die "installed manifest checksum mismatch"

systemctl restart "$service"
health_check || die "candidate service health failed"

verify_args=("$(dirname "$0")/hermes-runtime-artifact.py" verify-live
  --artifact "$candidate" --manifest "$manifest" --installed "$target"
  --expected-sha256 "$expected_candidate" --expected-manifest-sha256 "$expected_manifest"
  --service "$service" --python "$python")
[[ -z $health_url ]] || verify_args+=(--health-url "$health_url")
for item in "${config_inputs[@]}"; do verify_args+=(--config-input "$item"); done
if ! python3 "${verify_args[@]}"; then
  die "runtime identity failed"
fi
deployment_started=0
printf 'PASS Hermes runtime overlay deployed with rollback at %s\n' "$rollback_dir"
