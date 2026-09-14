#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tmp_root=$(mktemp -d)
trap 'rmdir "$tmp_root" 2>/dev/null || true' EXIT
if bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$tmp_root" --inputs "$tmp_root/missing.env" >/dev/null 2>&1; then
  echo 'FAIL missing operator input was accepted'; exit 1
fi
if [[ -e "$tmp_root/var" || -e "$tmp_root/etc" ]]; then
  echo 'FAIL failed preflight mutated the target'; exit 1
fi
echo 'PASS missing-input failure is clear and non-mutating'
cp "$repo_dir/config/operator-inputs.env.example" "$tmp_root/unsupported.env"
chmod 600 "$tmp_root/unsupported.env"
sed -i 's/^HADES_INPUTS_VERSION=.*/HADES_INPUTS_VERSION=999/' "$tmp_root/unsupported.env"
if bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$tmp_root/unsupported-root" --inputs "$tmp_root/unsupported.env" >/dev/null 2>&1; then
  echo 'FAIL unsupported operator input version was accepted'; exit 1
fi
if [[ -e "$tmp_root/unsupported-root/var" || -e "$tmp_root/unsupported-root/etc" ]]; then
  echo 'FAIL unsupported input version mutated the target'; exit 1
fi
echo 'PASS unsupported-input-version failure is clear and non-mutating'
cp "$repo_dir/config/operator-inputs.env.example" "$tmp_root/relative.env"
chmod 600 "$tmp_root/relative.env"
sed -i 's#^HADES_STATE_ROOT=.*#HADES_STATE_ROOT=relative-state#' "$tmp_root/relative.env"
if bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$tmp_root/relative-root" --inputs "$tmp_root/relative.env" >/dev/null 2>&1; then
  echo 'FAIL relative operator path was accepted'; exit 1
fi
if [[ -e "$tmp_root/relative-root/var" || -e "$tmp_root/relative-root/etc" || -e relative-state ]]; then
  echo 'FAIL relative input path mutated the target'; exit 1
fi
echo 'PASS relative-input-path failure is clear and non-mutating'
ln -s "$repo_dir/config/operator-inputs.env.example" "$tmp_root/symlink.env"
if bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$tmp_root/symlink-root" --inputs "$tmp_root/symlink.env" >/dev/null 2>&1; then
  echo 'FAIL symlinked operator input was accepted'; exit 1
fi
if [[ -e "$tmp_root/symlink-root/var" || -e "$tmp_root/symlink-root/etc" ]]; then
  echo 'FAIL symlinked input mutated the target'; exit 1
fi
echo 'PASS symlinked-input failure is clear and non-mutating'

fixture=$(mktemp -d)
trap 'rm -rf -- "$tmp_root" "$fixture"' EXIT
bash "$repo_dir/scripts/create-synthetic-private-fixture.sh" "$fixture/private"
fixture_root="$fixture/target"
sed -E -i 's#alpine:3\.20@sha256:[0-9a-f]+#alpine:latest#' "$fixture/private/records/open-webui.compose.yaml"
if bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$fixture_root" --inputs "$fixture/private/operator.env" >/dev/null 2>&1; then
  echo 'FAIL unpinned private image was accepted'; exit 1
fi
if [[ -e "$fixture_root/var" || -e "$fixture_root/etc" ]]; then
  echo 'FAIL invalid private image mutated the target'; exit 1
fi
echo 'PASS unpinned-private-image failure is clear and non-mutating'

bash "$repo_dir/scripts/create-synthetic-private-fixture.sh" "$fixture/invalid"
invalid_root="$fixture/invalid-target"
printf 'not: valid: compose\n' > "$fixture/invalid/records/hindsight.compose.yaml"
chmod 600 "$fixture/invalid/records/hindsight.compose.yaml"
if bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$invalid_root" --inputs "$fixture/invalid/operator.env" >/dev/null 2>&1; then
  echo 'FAIL invalid private compose was accepted'; exit 1
fi
if [[ -e "$invalid_root/var" || -e "$invalid_root/etc" ]]; then
  echo 'FAIL invalid private compose mutated the target'; exit 1
fi
echo 'PASS invalid-private-compose failure is clear and non-mutating'

bash "$repo_dir/scripts/create-synthetic-private-fixture.sh" "$fixture/permissions"
permissions_root="$fixture/permissions-target"
chmod 644 "$fixture/permissions/grocy-api-key"
if bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$permissions_root" --inputs "$fixture/permissions/operator.env" >/dev/null 2>&1; then
  echo 'FAIL unsafe synthetic secret permissions were accepted'; exit 1
fi
if [[ -e "$permissions_root/var" || -e "$permissions_root/etc" ]]; then
  echo 'FAIL unsafe synthetic secret permissions mutated the target'; exit 1
fi
if bash "$repo_dir/scripts/hades-doctor.sh" --test-mode --root "$permissions_root" --inputs "$fixture/permissions/operator.env" >/dev/null 2>&1; then
  echo 'FAIL doctor accepted unsafe synthetic secret permissions'; exit 1
fi
echo 'PASS unsafe-secret-permissions failure is clear and non-mutating'

bash "$repo_dir/scripts/create-synthetic-private-fixture.sh" "$fixture/boundary"
boundary_root="$fixture/boundary-target"
cat >> "$fixture/boundary/records/hindsight.compose.yaml" <<'EOF'
    privileged: true
EOF
if bash "$repo_dir/scripts/hades-doctor.sh" --test-mode --root "$boundary_root" --inputs "$fixture/boundary/operator.env" >/dev/null 2>&1; then
  echo 'FAIL authority-amplifying private Compose record passed doctor'; exit 1
fi
if [[ -e "$boundary_root/var" || -e "$boundary_root/etc" ]]; then
  echo 'FAIL doctor boundary failure mutated the target'; exit 1
fi
echo 'PASS authority-amplifying Compose failure is clear and non-mutating'
