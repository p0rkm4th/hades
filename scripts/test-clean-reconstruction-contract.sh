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
marker="$sandbox${tmp_root}/private/state/install-contract"
if source_revision=$(git -c "safe.directory=$repo_dir" -C "$repo_dir" rev-parse --verify HEAD 2>/dev/null); then
  source_tree=$(git -c "safe.directory=$repo_dir" -C "$repo_dir" rev-parse 'HEAD^{tree}')
  if [[ -z "$(git -c "safe.directory=$repo_dir" -C "$repo_dir" status --porcelain=v1 --untracked-files=all)" ]]; then
    source_clean=true
  else
    source_clean=false
  fi
else
  source_revision=archive
  source_tree=unavailable
  source_clean=unknown
fi
test "$(grep -c '^source_revision=' "$marker")" -eq 1
test "$(grep -c '^source_tree=' "$marker")" -eq 1
test "$(grep -c '^source_clean=' "$marker")" -eq 1
grep -Fxq "source_revision=$source_revision" "$marker"
grep -Fxq "source_tree=$source_tree" "$marker"
grep -Fxq "source_clean=$source_clean" "$marker"
echo 'PASS clean reconstruction contract is rerunnable and state-preserving'
