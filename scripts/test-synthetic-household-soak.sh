#!/usr/bin/env bash
set -Eeuo pipefail

# This is a credential-free fresh-install soak at the contract/fixture level.
# It deliberately does not claim full Open WebUI, Hindsight, or Hermes
# application acceptance; those require real application records and a model.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
trap 'find "$fixture" -depth -mindepth 1 -delete; rmdir "$fixture" 2>/dev/null || true' EXIT

run_script() {
  local script_name=$1
  shift
  local output="$fixture/${script_name%.sh}.log"
  local status=0

  bash "$repo_dir/scripts/$script_name" "$@" >"$output" 2>&1 || status=$?
  if (( status != 0 )); then
    printf 'FAIL nested soak check %s (exit %s)\n' "$script_name" "$status" >&2
    cat "$output" >&2
    return "$status"
  fi
}

bash "$repo_dir/scripts/create-synthetic-private-fixture.sh" "$fixture/private"
run_script install-hades.sh --test-mode --root "$fixture/sandbox" --inputs "$fixture/private/operator.env"
run_script hades-doctor.sh --test-mode --root "$fixture/sandbox" --inputs "$fixture/private/operator.env"
run_script validate-install.sh --test-mode --root "$fixture/sandbox" --inputs "$fixture/private/operator.env"

run_script test-cross-domain-dogfood.sh
run_script test-multi-user-long-dogfood.sh
run_script test-hades-memory-intent.sh
run_script test-source-of-truth-fixture.sh
run_script test-grocy-recipe-authoring-boundary.sh
run_script test-recipe-ingest-contract.sh
run_script test-recipe-mcp-registration.sh
run_script test-receipt-ocr-dogfood.sh
run_script test-finance-file-boundary.sh
run_script test-finance-import-dogfood.sh
run_script test-homelab-fixture.sh
run_script test-homelab-discovery-parser.sh
run_script test-homelab-discovery-runner.sh
run_script test-homelab-readonly-adapter.sh
run_script test-homelab-control-boundary.sh
run_script test-home-assistant-fixture.sh
run_script test-local-voice-dogfood.sh
run_script test-synthetic-performance-contract.sh
run_script test-capability-boundary.sh
run_script test-agent-zero-boundary.sh
run_script test-synthetic-backup-restore.sh

test -f "$fixture/sandbox${fixture}/private/state/install-contract" || {
  printf 'FAIL synthetic soak did not preserve private install contract marker\n' >&2
  exit 1
}
printf 'PASS synthetic fresh-install household soak contract\n'
