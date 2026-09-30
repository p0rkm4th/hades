#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tmp_root=$(mktemp -d)
trap 'rmdir "$tmp_root" 2>/dev/null || true' EXIT
cp "$repo_dir/config/operator-inputs.env.example" "$tmp_root/operator.env"
chmod 600 "$tmp_root/operator.env"
mkdir -p "$tmp_root/secrets"
chmod 700 "$tmp_root/secrets"
bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$tmp_root" --inputs "$tmp_root/operator.env" >/dev/null
marker="$tmp_root/var/lib/hades/install-contract"
if source_revision=$(git -c "safe.directory=$repo_dir" -C "$repo_dir" rev-parse --verify HEAD 2>/dev/null); then
  source_tree=$(git -c "safe.directory=$repo_dir" -C "$repo_dir" rev-parse 'HEAD^{tree}')
else
  source_revision=archive
  source_tree=unavailable
fi
grep -Fxq "source_revision=$source_revision" "$marker"
grep -Fxq "source_tree=$source_tree" "$marker"
source_revision_count=$(grep -c '^source_revision=' "$marker")
source_tree_count=$(grep -c '^source_tree=' "$marker")
source_clean_count=$(grep -c '^source_clean=' "$marker")
test "$source_revision_count" -eq 1 && test "$source_tree_count" -eq 1 && test "$source_clean_count" -eq 1
sed -i 's/^source_revision=.*/source_revision=stale-source-revision/' "$marker"
if bash "$repo_dir/scripts/validate-install.sh" --test-mode --root "$tmp_root" --inputs "$tmp_root/operator.env" >/dev/null 2>&1; then
  echo 'FAIL stale source revision was accepted by validation'; exit 1
fi
if bash "$repo_dir/scripts/hades-doctor.sh" --test-mode --root "$tmp_root" --inputs "$tmp_root/operator.env" >/dev/null 2>&1; then
  echo 'FAIL stale source revision was accepted by doctor'; exit 1
fi
sed -i "s/^source_revision=.*/source_revision=$source_revision/" "$marker"
sed -i 's/^source_tree=.*/source_tree=stale-source-tree/' "$marker"
if bash "$repo_dir/scripts/validate-install.sh" --test-mode --root "$tmp_root" --inputs "$tmp_root/operator.env" >/dev/null 2>&1; then
  echo 'FAIL stale source tree was accepted by validation'; exit 1
fi
if bash "$repo_dir/scripts/hades-doctor.sh" --test-mode --root "$tmp_root" --inputs "$tmp_root/operator.env" >/dev/null 2>&1; then
  echo 'FAIL stale source tree was accepted by doctor'; exit 1
fi
sed -i "s/^source_tree=.*/source_tree=$source_tree/" "$marker"
sed -i 's/^manifest=.*/manifest=stale-manifest/' "$marker"
if bash "$repo_dir/scripts/validate-install.sh" --test-mode --root "$tmp_root" --inputs "$tmp_root/operator.env" >/dev/null 2>&1; then
  echo 'FAIL stale manifest was accepted by validation'; exit 1
fi
if bash "$repo_dir/scripts/hades-doctor.sh" --test-mode --root "$tmp_root" --inputs "$tmp_root/operator.env" >/dev/null 2>&1; then
  echo 'FAIL stale manifest was accepted by doctor'; exit 1
fi
sed -i 's/"manifest_version": 1/"manifest_version": 99/' "$tmp_root/etc/hades/reconstruction-manifest.json"
if bash "$repo_dir/scripts/validate-install.sh" --test-mode --root "$tmp_root" --inputs "$tmp_root/operator.env" >/dev/null 2>&1; then
  echo 'FAIL stale reconstruction manifest was accepted by validation'; exit 1
fi
if bash "$repo_dir/scripts/hades-doctor.sh" --test-mode --root "$tmp_root" --inputs "$tmp_root/operator.env" >/dev/null 2>&1; then
  echo 'FAIL stale reconstruction manifest was accepted by doctor'; exit 1
fi
cp "$repo_dir/config/reconstruction-manifest.json" "$tmp_root/etc/hades/reconstruction-manifest.json"
cp "$repo_dir/hermes/sitecustomize.py" "$tmp_root/etc/hades/overlay/sitecustomize.py"
printf '\n# synthetic provenance tamper\n' >> "$tmp_root/etc/hades/overlay/sitecustomize.py"
if bash "$repo_dir/scripts/validate-install.sh" --test-mode --root "$tmp_root" --inputs "$tmp_root/operator.env" >/dev/null 2>&1; then
  echo 'FAIL tampered HADES layer was accepted by validation'; exit 1
fi
if bash "$repo_dir/scripts/hades-doctor.sh" --test-mode --root "$tmp_root" --inputs "$tmp_root/operator.env" >/dev/null 2>&1; then
  echo 'FAIL tampered HADES layer was accepted by doctor'; exit 1
fi
echo 'PASS stale installation manifest is rejected'
