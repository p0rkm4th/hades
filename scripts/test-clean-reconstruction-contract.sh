#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tmp_root=$(mktemp -d)
trap 'find "$tmp_root" -depth -mindepth 1 -delete 2>/dev/null || true; rmdir "$tmp_root" 2>/dev/null || true' EXIT
bash "$repo_dir/scripts/create-synthetic-private-fixture.sh" "$tmp_root/private"
inputs="$tmp_root/private/operator.env"
sandbox="$tmp_root/sandbox"
identity_before=$(sha256sum "$tmp_root/private/identity"/* "$tmp_root/private"/*-secret "$tmp_root/private"/*-credential)
bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$sandbox" --inputs "$inputs"
identity_after_first=$(sha256sum "$tmp_root/private/identity"/* "$tmp_root/private"/*-secret "$tmp_root/private"/*-credential)
bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$sandbox" --inputs "$inputs"
identity_after_second=$(sha256sum "$tmp_root/private/identity"/* "$tmp_root/private"/*-secret "$tmp_root/private"/*-credential)
bash "$repo_dir/scripts/hades-doctor.sh" --test-mode --root "$sandbox" --inputs "$inputs"
bash "$repo_dir/scripts/validate-install.sh" --test-mode --root "$sandbox" --inputs "$inputs"
test "$identity_before" = "$identity_after_first" || { echo 'FAIL first install changed supplied identity secrets'; exit 1; }
test "$identity_before" = "$identity_after_second" || { echo 'FAIL rerun changed supplied identity secrets'; exit 1; }
test "$(grep -c '^manifest=' "$sandbox${tmp_root}/private/state/install-contract")" -eq 1
test -f "$sandbox${tmp_root}/private/config/reconstruction-manifest.json"
test "$(grep -c '^reconstruction_manifest=' "$sandbox${tmp_root}/private/state/install-contract")" -eq 1
test "$(grep -c '^layer=' "$sandbox${tmp_root}/private/state/install-contract")" -eq 1
echo 'PASS clean reconstruction contract is rerunnable and state-preserving'
