#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tmp_root=$(mktemp -d)
trap 'rm -f "$tmp_root/operator.env"; rmdir "$tmp_root" 2>/dev/null || true' EXIT
cp "$repo_dir/config/operator-inputs.env.example" "$tmp_root/operator.env"
chmod 600 "$tmp_root/operator.env"; mkdir -p "$tmp_root/secrets"; chmod 700 "$tmp_root/secrets"
bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$tmp_root" --inputs "$tmp_root/operator.env"
bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$tmp_root" --inputs "$tmp_root/operator.env"
bash "$repo_dir/scripts/hades-doctor.sh" --test-mode --root "$tmp_root" --inputs "$tmp_root/operator.env"
bash "$repo_dir/scripts/validate-install.sh" --test-mode --root "$tmp_root" --inputs "$tmp_root/operator.env"
test "$(grep -c '^manifest=' "$tmp_root/var/lib/hades/install-contract")" -eq 1
test -f "$tmp_root/etc/hades/reconstruction-manifest.json"
echo 'PASS clean reconstruction contract is rerunnable and state-preserving'
