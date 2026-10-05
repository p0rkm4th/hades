#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
trap 'find "$fixture" -depth -mindepth 1 -delete 2>/dev/null || true; rmdir "$fixture" 2>/dev/null || true' EXIT
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
if [[ "$*" != 'show -p WorkingDirectory --value hades-hermes.service' ||
      -z "${HADES_TEST_UNIT_WORKDIR:-}" ]]; then
  exit 1
fi
printf '%s\n' "$HADES_TEST_UNIT_WORKDIR"
SH
chmod 0755 "$fixture/bin/systemctl"

bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$sandbox" --inputs "$inputs" >/dev/null
export HADES_TEST_UNIT_WORKDIR="$working_tree"
run_doctor() {
  PATH="$fixture/bin:$PATH" HADES_TEST_UNIT_WORKDIR="${HADES_TEST_UNIT_WORKDIR:-}" \
    bash "$repo_dir/scripts/hades-doctor.sh" --test-mode --root "$sandbox" --inputs "$inputs"
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

if ! HADES_TEST_UNIT_WORKDIR="$working_tree" run_doctor > "$fixture/doctor-pass.out" 2>&1; then
  cat "$fixture/doctor-pass.out" >&2
  exit 1
fi
grep -Fq 'PASS Hermes homelab runtime package matches the installed source revision' "$fixture/doctor-pass.out"
grep -Fq 'PASS active Hermes working directory matches operator input' "$fixture/doctor-pass.out"
! grep -Fq "$working_tree" "$fixture/doctor-pass.out" || {
  echo 'FAIL doctor exposed the configured working-directory path' >&2
  exit 1
}

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

unset HADES_TEST_UNIT_WORKDIR
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
