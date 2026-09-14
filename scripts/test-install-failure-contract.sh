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
