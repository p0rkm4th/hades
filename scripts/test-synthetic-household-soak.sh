#!/usr/bin/env bash
set -Eeuo pipefail

# This is a credential-free fresh-install soak at the contract/fixture level.
# It deliberately does not claim full Open WebUI, Hindsight, or Hermes
# application acceptance; those require real application records and a model.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
trap 'find "$fixture" -depth -mindepth 1 -delete; rmdir "$fixture" 2>/dev/null || true' EXIT

bash "$repo_dir/scripts/create-synthetic-private-fixture.sh" "$fixture/private"
bash "$repo_dir/scripts/install-hades.sh" --test-mode --root "$fixture/sandbox" --inputs "$fixture/private/operator.env" >/dev/null
bash "$repo_dir/scripts/hades-doctor.sh" --test-mode --root "$fixture/sandbox" --inputs "$fixture/private/operator.env" >/dev/null
bash "$repo_dir/scripts/validate-install.sh" --test-mode --root "$fixture/sandbox" --inputs "$fixture/private/operator.env" >/dev/null

bash "$repo_dir/scripts/test-cross-domain-dogfood.sh" >/dev/null
bash "$repo_dir/scripts/test-multi-user-long-dogfood.sh" >/dev/null
bash "$repo_dir/scripts/test-hades-memory-intent.sh" >/dev/null
bash "$repo_dir/scripts/test-source-of-truth-fixture.sh" >/dev/null
bash "$repo_dir/scripts/test-grocy-recipe-authoring-boundary.sh" >/dev/null
bash "$repo_dir/scripts/test-recipe-ingest-contract.sh" >/dev/null
bash "$repo_dir/scripts/test-recipe-mcp-registration.sh" >/dev/null
bash "$repo_dir/scripts/test-receipt-ocr-dogfood.sh" >/dev/null
bash "$repo_dir/scripts/test-finance-file-boundary.sh" >/dev/null
bash "$repo_dir/scripts/test-homelab-fixture.sh" >/dev/null
bash "$repo_dir/scripts/test-homelab-discovery-parser.sh" >/dev/null
bash "$repo_dir/scripts/test-homelab-discovery-runner.sh" >/dev/null
bash "$repo_dir/scripts/test-homelab-readonly-adapter.sh" >/dev/null
bash "$repo_dir/scripts/test-homelab-control-boundary.sh" >/dev/null
bash "$repo_dir/scripts/test-home-assistant-fixture.sh" >/dev/null
bash "$repo_dir/scripts/test-local-voice-dogfood.sh" >/dev/null
bash "$repo_dir/scripts/test-synthetic-performance-contract.sh" >/dev/null
bash "$repo_dir/scripts/test-capability-boundary.sh" >/dev/null
bash "$repo_dir/scripts/test-agent-zero-boundary.sh" >/dev/null
bash "$repo_dir/scripts/test-synthetic-backup-restore.sh" >/dev/null

test -f "$fixture/sandbox${fixture}/private/state/install-contract" || {
  printf 'FAIL synthetic soak did not preserve private install contract marker\n' >&2
  exit 1
}
printf 'PASS synthetic fresh-install household soak contract\n'
