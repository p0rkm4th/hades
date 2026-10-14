#!/usr/bin/env bash
set -euo pipefail

die() { printf 'FAIL %s\n' "$1" >&2; exit 1; }
wait_for_health() {
  local service=$1 health_url=$2 attempt
  for attempt in {1..30}; do
    systemctl is-active --quiet "$service" || return 1
    if [[ -z $health_url ]] || curl --fail --silent --max-time 4 --output /dev/null "$health_url"; then
      return 0
    fi
    sleep 2
  done
  return 1
}
target= manifest_target= rollback_dir= expected_current= expected_rollback= service=hades-hermes.service
support_target= expected_support_current= expected_support_rollback=
python= health_url=
while (($#)); do
  case "$1" in
    --target|--manifest-target|--rollback-dir|--expected-current-sha256|--expected-rollback-sha256|--service|--python|--health-url|--support-target|--expected-support-current-sha256|--expected-support-rollback-sha256)
      (($# >= 2)) || die "missing value for $1"
      key=$1; value=$2; shift 2
      case "$key" in
        --target) target=$value ;;
        --manifest-target) manifest_target=$value ;;
        --rollback-dir) rollback_dir=$value ;;
        --expected-current-sha256) expected_current=$value ;;
        --expected-rollback-sha256) expected_rollback=$value ;;
        --service) service=$value ;;
        --python) python=$value ;;
        --health-url) health_url=$value ;;
        --support-target) support_target=$value ;;
        --expected-support-current-sha256) expected_support_current=$value ;;
        --expected-support-rollback-sha256) expected_support_rollback=$value ;;
      esac
      ;;
    *) die "unsupported argument" ;;
  esac
done
[[ $(id -u) == 0 ]] || die "rollback must run as root through the approved scoped privilege path"
[[ -n $target && -n $manifest_target && -n $rollback_dir && -n $python && -n $support_target && -n $expected_support_current && -n $expected_support_rollback ]] || die "target, manifest, support, rollback, and interpreter paths are required"
for path in "$target" "$manifest_target" "$rollback_dir" "$python" "$support_target"; do [[ $path == /* ]] || die "filesystem paths must be absolute"; done
[[ $(basename "$target") == sitecustomize.py && $(basename "$manifest_target") == sitecustomize.runtime.json && $(dirname "$target") == "$(dirname "$manifest_target")" ]] || die "runtime artifact and manifest paths do not match"
[[ $(basename "$support_target") == homelab_views.py && $(dirname "$support_target") == "$(dirname "$target")" ]] || die "runtime support path differs from overlay directory"
[[ $(basename "$rollback_dir") == runtime-convergence-* && -d $(dirname "$rollback_dir") && ! -L $(dirname "$rollback_dir") ]] || die "rollback path differs from the protected backup root"
[[ $(realpath -e "$(dirname "$target")") == "$(dirname "$target")" && $(realpath -e "$(dirname "$rollback_dir")") == "$(dirname "$rollback_dir")" ]] || die "runtime and rollback parents must be canonical directories"
[[ $service == hades-hermes.service ]] || die "service differs from the qualified Hermes unit"
[[ -n $health_url ]] || die "an approved Hermes health URL is required"
[[ $expected_current =~ ^[0-9a-f]{64}$ && $expected_rollback =~ ^[0-9a-f]{64}$ ]] || die "checksums must be lowercase SHA-256 values"
[[ $expected_support_current =~ ^[0-9a-f]{64}$ && ( $expected_support_rollback == absent || $expected_support_rollback =~ ^[0-9a-f]{64}$ ) ]] || die "support checksums or absent marker are invalid"
[[ -d $rollback_dir && ! -L $rollback_dir && $(stat -c '%u:%g:%a' "$rollback_dir") == 0:0:700 ]] || die "rollback directory is not protected"
[[ -f $target && ! -L $target && -f $rollback_dir/sitecustomize.py && ! -L $rollback_dir/sitecustomize.py ]] || die "runtime or rollback artifact is unavailable"
[[ -f $support_target && ! -L $support_target ]] || die "active runtime support module is unavailable"
[[ ! -L $manifest_target && (! -e $manifest_target || -f $manifest_target) ]] || die "runtime manifest must be a regular file when present"
[[ $(sha256sum "$target" | awk '{print $1}') == "$expected_current" ]] || die "active runtime drifted; rollback refused"
[[ $(sha256sum "$rollback_dir/sitecustomize.py" | awk '{print $1}') == "$expected_rollback" ]] || die "rollback artifact checksum differs"
[[ $(sha256sum "$support_target" | awk '{print $1}') == "$expected_support_current" ]] || die "active runtime support checksum differs"
if [[ $expected_support_rollback == absent ]]; then [[ -f $rollback_dir/homelab_views.absent ]] || die "rollback support absence marker is missing"
else [[ -f $rollback_dir/homelab_views.py && $(sha256sum "$rollback_dir/homelab_views.py" | awk '{print $1}') == "$expected_support_rollback" ]] || die "rollback support artifact checksum differs"; fi

attempt_dir=$(mktemp -d "$rollback_dir/.rollback-attempt.XXXXXX")
chmod 0700 "$attempt_dir"
cp -a -- "$target" "$attempt_dir/sitecustomize.py"
cp -a -- "$support_target" "$attempt_dir/homelab_views.py"
manifest_existed=0
if [[ -f $manifest_target ]]; then
  cp -a -- "$manifest_target" "$attempt_dir/manifest.json"
  manifest_existed=1
fi
rollback_started=0
current_tmp=

restore_attempt_state() {
  local temporary
  temporary=$(mktemp "$(dirname "$target")/.runtime-rollback-recovery.XXXXXX")
  rm -f -- "$temporary" || return 1
  cp -a -- "$attempt_dir/sitecustomize.py" "$temporary" || return 1
  mv -Tf -- "$temporary" "$target" || return 1
  temporary=$(mktemp "$(dirname "$support_target")/.runtime-support-recovery.XXXXXX")
  rm -f -- "$temporary" || return 1
  cp -a -- "$attempt_dir/homelab_views.py" "$temporary" || return 1
  mv -Tf -- "$temporary" "$support_target" || return 1
  if ((manifest_existed == 1)); then
    temporary=$(mktemp "$(dirname "$manifest_target")/.manifest-rollback-recovery.XXXXXX")
    rm -f -- "$temporary" || return 1
    cp -a -- "$attempt_dir/manifest.json" "$temporary" || return 1
    mv -Tf -- "$temporary" "$manifest_target" || return 1
  else
    rm -f -- "$manifest_target" || return 1
  fi
  systemctl restart "$service" || return 1
  wait_for_health "$service" "$health_url" || return 1
  [[ $(sha256sum "$target" | awk '{print $1}') == "$expected_current" ]] || return 1
  local args=("$(dirname "$0")/hermes-runtime-artifact.py" verify-live
    --installed "$target" --service "$service" --python "$python"
    --expected-sha256 "$expected_current" --hermes-version 0.21.2)
  [[ -z $health_url ]] || args+=(--health-url "$health_url")
  python3 "${args[@]}" >/dev/null || return 1
}

on_exit() {
  local status=$?
  if [[ -n $current_tmp ]]; then rm -f -- "$current_tmp" || true; current_tmp=; fi
  if ((status != 0 && rollback_started == 1)); then
    if restore_attempt_state; then
      printf 'ROLLBACK OPERATION FAILED; candidate runtime restored and verified\n' >&2
    else
      printf 'ROLLBACK RECOVERY FAILED; inspect the preserved current artifact immediately\n' >&2
    fi
  fi
  exit "$status"
}
trap on_exit EXIT

rollback_started=1
temporary=$(mktemp "$(dirname "$target")/.runtime-rollback.XXXXXX")
rm -f -- "$temporary"
  cp -a -- "$rollback_dir/sitecustomize.py" "$temporary"
  mv -Tf -- "$temporary" "$target"
if [[ $expected_support_rollback == absent ]]; then
  rm -f -- "$support_target"
else
  temporary=$(mktemp "$(dirname "$support_target")/.runtime-support-rollback.XXXXXX")
  rm -f -- "$temporary"
  cp -a -- "$rollback_dir/homelab_views.py" "$temporary"
  mv -Tf -- "$temporary" "$support_target"
fi
if [[ -f $rollback_dir/manifest.json ]]; then
  temporary=$(mktemp "$(dirname "$manifest_target")/.manifest-rollback.XXXXXX")
  rm -f -- "$temporary"
  cp -a -- "$rollback_dir/manifest.json" "$temporary"
  mv -Tf -- "$temporary" "$manifest_target"
else
  rm -f -- "$manifest_target"
fi
systemctl restart "$service"
wait_for_health "$service" "$health_url" || die "Hermes health failed after rollback"
if [[ $expected_support_rollback == absent ]]; then [[ ! -e $support_target ]] || die "rollback support absence was not restored"
else [[ $(sha256sum "$support_target" | awk '{print $1}') == "$expected_support_rollback" ]] || die "rollback support checksum differs"; fi
verify_args=("$(dirname "$0")/hermes-runtime-artifact.py" verify-live
  --installed "$target" --service "$service" --python "$python"
  --expected-sha256 "$expected_rollback" --hermes-version 0.21.2)
[[ -z $health_url ]] || verify_args+=(--health-url "$health_url")
python3 "${verify_args[@]}" || die "Hermes did not load the exact rollback artifact"
rollback_started=0
printf 'PASS Hermes runtime rollback verified: sha256=%s\n' "$expected_rollback"
