#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
trap 'rm -rf -- "$fixture"' EXIT
bash "$repo_dir/scripts/create-synthetic-private-fixture.sh" "$fixture/private"
sandbox="$fixture/sandbox"
inputs="$fixture/private/operator.env"

if HADES_TEST_FAIL_AFTER_PREPARE=1 bash "$repo_dir/scripts/install-hades.sh" \
    --test-mode --root "$sandbox" --inputs "$inputs" >/dev/null 2>&1; then
  echo 'FAIL injected partial installation unexpectedly succeeded'
  exit 1
fi
marker="$sandbox${fixture}/private/state/install-contract"
[[ -f "$marker" ]] || { echo 'FAIL interrupted install lost prepared marker'; exit 1; }
grep -qx 'phase=prepared' "$marker" || { echo 'FAIL interrupted install marker is not diagnosable'; exit 1; }
sentinel="$sandbox${fixture}/private/state/operator-state.marker"
printf 'preserve-this-state\n' > "$sentinel"

bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$sandbox" --inputs "$inputs" >/dev/null
bash "$repo_dir/scripts/hades-doctor.sh" --test-mode --root "$sandbox" --inputs "$inputs" >/dev/null
bash "$repo_dir/scripts/validate-install.sh" --test-mode --root "$sandbox" --inputs "$inputs" >/dev/null
grep -qx 'preserve-this-state' "$sentinel" || { echo 'FAIL rerun replaced persistent state'; exit 1; }
grep -qx 'phase=prepared' "$marker" || { echo 'FAIL rerun produced an invalid phase'; exit 1; }
echo 'PASS partial-install recovery preserves prepared state and reruns cleanly'
