#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
fake_hermes_pid=''
cleanup() {
  if [[ -n "$fake_hermes_pid" ]]; then
    kill "$fake_hermes_pid" 2>/dev/null || true
    wait "$fake_hermes_pid" 2>/dev/null || true
  fi
  find "$fixture" -depth -mindepth 1 -delete 2>/dev/null || true
  rmdir "$fixture" 2>/dev/null || true
}
trap cleanup EXIT
bash "$repo_dir/scripts/create-synthetic-private-fixture.sh" "$fixture/private" >/dev/null
inputs="$fixture/private/operator.env"
working_tree="$fixture/working"
sandbox="$fixture/sandbox"
mkdir -p "$working_tree/hermes" "$working_tree/integrations/public-research" "$fixture/bin"
chmod 0755 "$fixture" "$working_tree"
cp "$repo_dir/hermes/config.yaml.example" "$working_tree/hermes/config.yaml.example"
cp "$repo_dir/integrations/homelab_views.py" "$working_tree/integrations/homelab_views.py"
cp "$repo_dir/integrations/public-research/research.py" "$working_tree/integrations/public-research/research.py"
cp -a "$repo_dir/integrations/homelab-readonly" "$working_tree/integrations/homelab-readonly"
printf '\nHADES_HERMES_WORKING_DIRECTORY=%s\n' "$working_tree" >> "$inputs"
chmod 0600 "$inputs"
printf 'HADES_HERMES_WORKING_DIRECTORY=%s\n' "$working_tree" \
  > "$fixture/private/profile/hermes.env"
chmod 0600 "$fixture/private/profile/hermes.env"

# The doctor uses this read-only systemctl query to bind its check to the
# active unit. The stub is synthetic and emits only the configured test path.
cat > "$fixture/bin/systemctl" <<'SH'
#!/usr/bin/env bash
if [[ "$*" == 'show -p WorkingDirectory --value hades-hermes.service' &&
      -n "${HADES_TEST_UNIT_WORKDIR:-}" ]]; then
  printf '%s\n' "$HADES_TEST_UNIT_WORKDIR"
elif [[ "$*" == 'show -p EnvironmentFiles --value hades-hermes.service' &&
        -n "${HADES_TEST_ACTIVE_ENVFILES:-}" ]]; then
  printf '%s\n' "$HADES_TEST_ACTIVE_ENVFILES"
elif [[ "$*" == 'show -p MainPID --value hades-hermes.service' &&
        -n "${HADES_TEST_MAINPID:-}" ]]; then
  printf '%s\n' "$HADES_TEST_MAINPID"
else
  exit 1
fi
SH
chmod 0755 "$fixture/bin/systemctl"

bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$sandbox" --inputs "$inputs" >/dev/null
source "$inputs"
overlay_target="$sandbox${HADES_CONFIG_ROOT}/overlay/sitecustomize.py"
composition_target="$sandbox${HADES_CONFIG_ROOT}/overlay/sitecustomize.composition.json"
HADES_TEST_UNIT_WORKDIR="$working_tree"
HADES_TEST_ACTIVE_ENVFILES="$fixture/private/profile/hermes.env (ignore_errors=yes)
$fixture/deployment/hades-owner-policy.env (ignore_errors=yes)"
(
  cd "$working_tree"
  set -a
  source "$fixture/private/profile/hermes.env"
  set +a
  exec sleep 120
) &
fake_hermes_pid=$!
for _attempt in {1..50}; do
  [[ -r "/proc/$fake_hermes_pid/environ" ]] &&
    [[ "$(readlink -e "/proc/$fake_hermes_pid/cwd" 2>/dev/null || true)" == "$working_tree" ]] && break
  sleep 0.02
done
if ! PATH="$fixture/bin:$PATH" HADES_TEST_UNIT_WORKDIR="$HADES_TEST_UNIT_WORKDIR" \
  HADES_TEST_ACTIVE_ENVFILES="$HADES_TEST_ACTIVE_ENVFILES" HADES_TEST_MAINPID="$fake_hermes_pid" \
  bash "$repo_dir/scripts/hades-doctor.sh" --test-mode --root "$sandbox" --inputs "$inputs" \
  > "$fixture/tracked-overlay-doctor.out" 2>&1; then
  cat "$fixture/tracked-overlay-doctor.out" >&2
  echo 'FAIL doctor rejected the tracked overlay at its documented mode' >&2
  exit 1
fi
chmod 0666 "$overlay_target"
if output=$(PATH="$fixture/bin:$PATH" HADES_TEST_UNIT_WORKDIR="$HADES_TEST_UNIT_WORKDIR" \
  HADES_TEST_ACTIVE_ENVFILES="$HADES_TEST_ACTIVE_ENVFILES" HADES_TEST_MAINPID="$fake_hermes_pid" \
  bash "$repo_dir/scripts/hades-doctor.sh" --test-mode --root "$sandbox" --inputs "$inputs" 2>&1); then
  echo 'FAIL doctor accepted unsafe permissions on a tracked Hermes overlay' >&2
  exit 1
fi
grep -Fq 'tracked Hermes overlay is missing, linked, or not mode 0644' <<<"$output" || {
  echo 'FAIL doctor did not identify unsafe tracked-overlay permissions' >&2
  exit 1
}
chmod 0644 "$overlay_target"
kill "$fake_hermes_pid" 2>/dev/null || true
wait "$fake_hermes_pid" 2>/dev/null || true
fake_hermes_pid=''
chmod 0666 "$overlay_target"
if output=$(bash "$repo_dir/scripts/validate-install.sh" --test-mode --root "$sandbox" --inputs "$inputs" 2>&1); then
  echo 'FAIL install validator accepted unsafe permissions on a tracked Hermes overlay' >&2
  exit 1
fi
grep -Fq 'tracked Hermes overlay permissions must be mode 0644' <<<"$output" || {
  echo 'FAIL install validator did not identify unsafe tracked overlay permissions' >&2
  exit 1
}
chmod 0644 "$overlay_target"
printf '\n# deployment-local sentinel\nLOCAL_OVERLAY_VALUE = "keep-me"\n' >> "$overlay_target"
before_custom_overlay=$(sha256sum "$overlay_target" | awk '{print $1}')
if bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$sandbox" --inputs "$inputs" >/dev/null 2>&1; then
  echo 'FAIL installer overwrote a customized Hermes overlay without a composition manifest' >&2
  exit 1
fi
[[ "$(sha256sum "$overlay_target" | awk '{print $1}')" == "$before_custom_overlay" ]] || {
  echo 'FAIL installer changed a customized Hermes overlay after rejecting it' >&2
  exit 1
}
composition_dir="$fixture/hermes-overlay-candidate"
mkdir -m 0700 "$composition_dir"
candidate_overlay="$composition_dir/sitecustomize.py"
candidate_manifest="$composition_dir/sitecustomize.composition.json"
python3 "$repo_dir/scripts/prepare-homelab-overlay-candidate.py" \
  --repo "$repo_dir" --active-overlay "$overlay_target" \
  --output "$candidate_overlay" --manifest-output "$candidate_manifest" >/dev/null
bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$sandbox" --inputs "$inputs" \
  --hermes-overlay-candidate "$candidate_overlay" \
  --hermes-overlay-manifest "$candidate_manifest" >/dev/null
grep -Fq 'LOCAL_OVERLAY_VALUE = "keep-me"' "$overlay_target"
[[ -f "$composition_target" && "$(stat -c '%a' "$composition_target")" == 640 ]] || {
  echo 'FAIL installer did not preserve the mode-0640 composition manifest' >&2
  exit 1
}
grep -Fxq "hermes_overlay_composition_manifest_sha256=$(sha256sum "$composition_target" | awk '{print $1}')" \
  "$sandbox${HADES_STATE_ROOT}/install-contract" || {
    echo 'FAIL installer did not bind the composition manifest in its marker' >&2
    exit 1
  }
# An ordinary installer rerun must discover the installed manifest and keep the
# composed overlay, even when the staging candidate has been removed.
candidate_hash=$(sha256sum "$overlay_target" | awk '{print $1}')
rm -rf "$composition_dir"
bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$sandbox" --inputs "$inputs" >/dev/null
[[ "$(sha256sum "$overlay_target" | awk '{print $1}')" == "$candidate_hash" ]] || {
  echo 'FAIL installer rerun replaced a verified deployment-local overlay' >&2
  exit 1
}
bash "$repo_dir/scripts/validate-install.sh" --test-mode --root "$sandbox" --inputs "$inputs" >/dev/null
export HADES_TEST_UNIT_WORKDIR="$working_tree"
export HADES_TEST_ACTIVE_ENVFILES="$fixture/private/profile/hermes.env (ignore_errors=yes)
$fixture/deployment/hades-owner-policy.env (ignore_errors=yes)"
start_fake_hermes() {
  local process_cwd=$1 source_extra=${2:-} clear_working_directory=${3:-false}
  (
    cd "$process_cwd"
    set -a
    source "$fixture/private/profile/hermes.env"
    if [[ -n "$source_extra" ]]; then source "$source_extra"; fi
    if [[ "$clear_working_directory" == true ]]; then unset HADES_HERMES_WORKING_DIRECTORY; fi
    set +a
    exec sleep 120
  ) &
  fake_hermes_pid=$!
  export HADES_TEST_MAINPID="$fake_hermes_pid"
  for _attempt in {1..50}; do
    [[ -r "/proc/$fake_hermes_pid/environ" ]] &&
      [[ "$(readlink -e "/proc/$fake_hermes_pid/cwd" 2>/dev/null || true)" == "$process_cwd" ]] && return 0
    sleep 0.02
  done
  echo 'FAIL synthetic Hermes process did not become inspectable' >&2
  exit 1
}
stop_fake_hermes() {
  if [[ -n "$fake_hermes_pid" ]]; then
    kill "$fake_hermes_pid" 2>/dev/null || true
    wait "$fake_hermes_pid" 2>/dev/null || true
    fake_hermes_pid=''
  fi
}
run_doctor() {
  PATH="$fixture/bin:$PATH" \
    HADES_TEST_UNIT_WORKDIR="${HADES_TEST_UNIT_WORKDIR:-}" \
    HADES_TEST_ACTIVE_ENVFILES="${HADES_TEST_ACTIVE_ENVFILES:-}" \
    HADES_TEST_MAINPID="${HADES_TEST_MAINPID:-}" \
    bash "$repo_dir/scripts/hades-doctor.sh" --test-mode --root "$sandbox" --inputs "$inputs"
}
run_production_mode_doctor() {
  PATH="$fixture/bin:$PATH" \
    HADES_TEST_UNIT_WORKDIR="${HADES_TEST_UNIT_WORKDIR:-}" \
    HADES_TEST_ACTIVE_ENVFILES="${HADES_TEST_ACTIVE_ENVFILES:-}" \
    HADES_TEST_MAINPID="${HADES_TEST_MAINPID:-}" \
    bash "$repo_dir/scripts/hades-doctor.sh" --root "$sandbox" --inputs "$inputs"
}
expect_package_failure() {
  local expected=$1 output
  if output=$(run_doctor 2>&1); then
    echo "FAIL doctor accepted homelab package mutation: $expected" >&2
    exit 1
  fi
  grep -Fq "$expected" <<<"$output" || {
    echo "FAIL doctor did not report expected package failure: $expected" >&2
    exit 1
  }
  ! grep -Fq "$working_tree" <<<"$output" || {
    echo 'FAIL doctor exposed the configured working-directory path' >&2
    exit 1
  }
}

start_fake_hermes "$working_tree"
if ! HADES_TEST_UNIT_WORKDIR="$working_tree" run_doctor > "$fixture/doctor-pass.out" 2>&1; then
  cat "$fixture/doctor-pass.out" >&2
  exit 1
fi
grep -Fq 'PASS Hermes homelab runtime package matches the installed source revision' "$fixture/doctor-pass.out"
grep -Fq 'PASS active Hermes process directory and environment match the configured package' "$fixture/doctor-pass.out"
! grep -Fq "$working_tree" "$fixture/doctor-pass.out" || {
  echo 'FAIL doctor exposed the configured working-directory path' >&2
  exit 1
}
chmod 0666 "$overlay_target"
if output=$(run_doctor 2>&1); then
  echo 'FAIL doctor accepted an unsafe composed Hermes overlay mode' >&2
  exit 1
fi
grep -Fq 'overlay permissions must be mode 0600 or 0640' <<<"$output" || {
  echo 'FAIL doctor did not identify unsafe composed overlay permissions' >&2
  exit 1
}
if output=$(bash "$repo_dir/scripts/validate-install.sh" --test-mode --root "$sandbox" --inputs "$inputs" 2>&1); then
  echo 'FAIL install validator accepted an unsafe composed Hermes overlay mode' >&2
  exit 1
fi
grep -Fq 'overlay permissions must be mode 0600 or 0640' <<<"$output" || {
  echo 'FAIL install validator did not identify unsafe composed overlay permissions' >&2
  exit 1
}
chmod 0640 "$overlay_target"

# The generated service contract binds HADES_HERMES_WORKING_DIRECTORY into
# the systemd process environment. If a running process does not have it,
# production-mode doctor must fail even when unit cwd and profile file match.
stop_fake_hermes
start_fake_hermes "$working_tree" '' true
if output=$(run_production_mode_doctor 2>&1); then
  echo 'FAIL production-mode doctor accepted Hermes without its runtime working-directory environment' >&2
  exit 1
fi
grep -Fq 'FAIL active Hermes process directory or environment differs from the configured package' <<<"$output"
! grep -Fq "$working_tree" <<<"$output" || {
  echo 'FAIL production-mode doctor exposed the configured working-directory path' >&2
  exit 1
}
stop_fake_hermes
start_fake_hermes "$working_tree"

sed "s#^HADES_HERMES_WORKING_DIRECTORY=.*#HADES_HERMES_WORKING_DIRECTORY=$fixture/other-environment-directory#" \
  "$fixture/private/profile/hermes.env" > "$fixture/private/profile/hermes.env.next"
mv "$fixture/private/profile/hermes.env.next" "$fixture/private/profile/hermes.env"
if output=$(run_doctor 2>&1); then
  echo 'FAIL doctor accepted a Hermes profile environment working-directory mismatch' >&2
  exit 1
fi
grep -Fq 'FAIL Hermes profile environment working directory differs from the active service' <<<"$output"
! grep -Fq "$working_tree" <<<"$output" || {
  echo 'FAIL doctor exposed the configured working-directory path' >&2
  exit 1
}
sed "s#^HADES_HERMES_WORKING_DIRECTORY=.*#HADES_HERMES_WORKING_DIRECTORY=$working_tree#" \
  "$fixture/private/profile/hermes.env" > "$fixture/private/profile/hermes.env.next"
mv "$fixture/private/profile/hermes.env.next" "$fixture/private/profile/hermes.env"

HADES_TEST_ACTIVE_ENVFILES="$fixture/other-profile/hermes.env (ignore_errors=yes)"
if output=$(run_doctor 2>&1); then
  echo 'FAIL doctor accepted an active Hermes profile-source mismatch' >&2
  exit 1
fi
grep -Fq 'FAIL active Hermes profile source differs from configured profile' <<<"$output"
! grep -Fq "$fixture/private/profile" <<<"$output" || {
  echo 'FAIL doctor exposed the configured profile path' >&2
  exit 1
}
HADES_TEST_ACTIVE_ENVFILES="$fixture/private/profile/hermes.env (ignore_errors=yes)
$fixture/deployment/hades-owner-policy.env (ignore_errors=yes)"

# Reproduce ExecStart's later shell-source ordering: a loaded later env file
# can override the value in hermes.env even while the unit's WorkingDirectory
# and required profile-source checks still match.
grocy_env="$fixture/private/records/grocy-mcp.env"
printf 'HADES_HERMES_WORKING_DIRECTORY=%s\n' "$fixture/override-directory" > "$grocy_env"
chmod 0600 "$grocy_env"
stop_fake_hermes
HADES_TEST_ACTIVE_ENVFILES="$fixture/private/profile/hermes.env (ignore_errors=yes)
$grocy_env (ignore_errors=yes)"
start_fake_hermes "$working_tree" "$grocy_env"
if output=$(run_doctor 2>&1); then
  echo 'FAIL doctor accepted a running Hermes process redirected by a later environment source' >&2
  exit 1
fi
grep -Fq 'FAIL active Hermes process directory or environment differs from the configured package' <<<"$output"
! grep -Fq "$working_tree" <<<"$output" &&
  ! grep -Fq "$fixture/override-directory" <<<"$output" || {
  echo 'FAIL doctor exposed a private runtime path' >&2
  exit 1
}
: > "$grocy_env"
stop_fake_hermes
HADES_TEST_ACTIVE_ENVFILES="$fixture/private/profile/hermes.env (ignore_errors=yes)
$fixture/deployment/hades-owner-policy.env (ignore_errors=yes)"
mkdir -p "$fixture/other-process-directory"
start_fake_hermes "$fixture/other-process-directory"
if output=$(run_doctor 2>&1); then
  echo 'FAIL doctor accepted a running Hermes process with a decoy cwd' >&2
  exit 1
fi
grep -Fq 'FAIL active Hermes process directory or environment differs from the configured package' <<<"$output"
stop_fake_hermes
start_fake_hermes "$working_tree"

mv "$working_tree/integrations/homelab-readonly/server.py" \
  "$working_tree/integrations/homelab-readonly/server.py.missing"
expect_package_failure 'module set differs from the installed source revision'
mv "$working_tree/integrations/homelab-readonly/server.py.missing" \
  "$working_tree/integrations/homelab-readonly/server.py"

cp "$repo_dir/integrations/homelab-readonly/server.py" \
  "$working_tree/integrations/homelab-readonly/server.py.original"
printf '# synthetic byte drift\n' > "$working_tree/integrations/homelab-readonly/server.py"
expect_package_failure 'differs from the installed source revision'
mv "$working_tree/integrations/homelab-readonly/server.py.original" \
  "$working_tree/integrations/homelab-readonly/server.py"

printf '# synthetic extra module\n' > "$working_tree/integrations/homelab-readonly/extra.py"
expect_package_failure 'module set differs from the installed source revision'
mv "$working_tree/integrations/homelab-readonly/extra.py" \
  "$working_tree/integrations/homelab-readonly/extra.py.disabled"

ln -s server.py "$working_tree/integrations/homelab-readonly/extra.py"
expect_package_failure 'contains a symlink or non-regular Python module'
mv "$working_tree/integrations/homelab-readonly/extra.py" \
  "$working_tree/integrations/homelab-readonly/extra-link.disabled"

HADES_TEST_UNIT_WORKDIR="$fixture/other-active-directory"
export HADES_TEST_UNIT_WORKDIR
if output=$(run_doctor 2>&1); then
  echo 'FAIL doctor accepted an active Hermes working directory mismatch' >&2
  exit 1
fi
grep -Fq 'FAIL configured Hermes working directory differs from the active service' <<<"$output"
! grep -Fq "$working_tree" <<<"$output" || {
  echo 'FAIL doctor exposed the configured working-directory path' >&2
  exit 1
}
HADES_TEST_UNIT_WORKDIR="$working_tree"
HADES_TEST_ACTIVE_ENVFILES=''
if output=$(run_doctor 2>&1); then
  grep -Fq 'WARN homelab runtime package identity is unknown; active Hermes profile sources are unavailable' <<<"$output"
else
  echo 'FAIL doctor rejected unavailable active Hermes profile-source evidence in test mode' >&2
  exit 1
fi
HADES_TEST_ACTIVE_ENVFILES="$fixture/private/profile/hermes.env (ignore_errors=yes)
$fixture/deployment/hades-owner-policy.env (ignore_errors=yes)"
HADES_TEST_MAINPID=''
if output=$(run_doctor 2>&1); then
  grep -Fq 'WARN homelab runtime package identity is unknown; active Hermes process identity is unavailable' <<<"$output"
else
  echo 'FAIL doctor rejected unavailable active Hermes process evidence in test mode' >&2
  exit 1
fi
HADES_TEST_MAINPID="$fake_hermes_pid"

unset HADES_TEST_UNIT_WORKDIR
unset HADES_TEST_ACTIVE_ENVFILES
run_doctor > "$fixture/doctor-unknown.out"
grep -Fq 'WARN homelab runtime package identity is unknown; active Hermes working directory is unavailable' \
  "$fixture/doctor-unknown.out"

marker="$sandbox$fixture/private/state/install-contract"
sed -i 's/^source_revision=.*/source_revision=archive/' "$marker"
sed -i 's/^source_tree=.*/source_tree=unavailable/' "$marker"
HADES_TEST_UNIT_WORKDIR="$working_tree" run_doctor > "$fixture/doctor-source-unknown.out"
grep -Fq 'WARN homelab runtime package identity is unknown; installed source or working-directory input is unavailable' \
  "$fixture/doctor-source-unknown.out"
! grep -Fq "$working_tree" "$fixture/doctor-source-unknown.out" || {
  echo 'FAIL doctor exposed the configured working-directory path' >&2
  exit 1
}

echo 'PASS doctor binds homelab runtime package checks to the active unit and recorded source revision'
