#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tmp_root=$(mktemp -d)
trap 'find "$tmp_root" -depth -mindepth 1 -delete 2>/dev/null || true; rmdir "$tmp_root" 2>/dev/null || true' EXIT
fixture_repo="$tmp_root/source"
mkdir -p "$fixture_repo/scripts" "$fixture_repo/config"
cp "$repo_dir/scripts/install-hades.sh" "$fixture_repo/scripts/install-hades.sh"
cp "$repo_dir/config/versions.env" "$fixture_repo/config/versions.env"
cp "$repo_dir/config/operator-inputs.env.example" "$fixture_repo/config/operator.env"

git -C "$fixture_repo" init -q
git -C "$fixture_repo" config user.email fixture@example.invalid
git -C "$fixture_repo" config user.name fixture
git -C "$fixture_repo" add scripts config
git -C "$fixture_repo" commit -qm 'clean source fixture'

if output=$(bash "$fixture_repo/scripts/install-hades.sh" --preflight \
    --inputs "$fixture_repo/config/operator.env" 2>&1); then
  echo 'FAIL clean source fixture unexpectedly passed the incomplete private-input preflight'
  exit 1
fi
if grep -q 'requires a clean Git worktree' <<<"$output"; then
  echo 'FAIL committed clean source was incorrectly classified as dirty'
  exit 1
fi

printf 'uncommitted-source-change\n' > "$fixture_repo/untracked.marker"
if output=$(bash "$fixture_repo/scripts/install-hades.sh" --preflight \
    --inputs "$fixture_repo/config/operator.env" 2>&1); then
  echo 'FAIL production preflight accepted an untracked source file'
  exit 1
fi
grep -q 'production installation requires a clean Git worktree' <<<"$output" || {
  echo 'FAIL dirty-source preflight did not report the actionable source-identity failure'
  exit 1
}
echo 'PASS production install requires committed clean source and rejects untracked changes before host checks'
