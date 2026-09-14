#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
installer="$repo_dir/scripts/install-hades.sh"
manifest="$repo_dir/docs/component-manifest.md"

agent_config_line=$(grep -nF "invalid compose contract: agent-zero" "$installer" | cut -d: -f1)
agent_line=$(awk -v start="$agent_config_line" 'NR > start && /compose_cmd/ && /up -d/ {print NR; exit}' "$installer")
searx_line=$(grep -nF 'docker compose -f "$HADES_SEARXNG_COMPOSE_FILE" up -d' "$installer" | cut -d: -f1)
hermes_line=$(grep -nF 'install -m 0644 "$HADES_HERMES_SERVICE_FILE"' "$installer" | cut -d: -f1)

[[ -n "$agent_line" && -n "$searx_line" && -n "$hermes_line" ]] || {
  echo 'FAIL installer order markers are missing'; exit 1;
}
[[ "$agent_line" -lt "$searx_line" && "$searx_line" -lt "$hermes_line" ]] || {
  echo 'FAIL installer dependency order is not Agent Zero, SearXNG, Hermes'; exit 1;
}
grep -q '| Agent Zero |.*| 6 |' "$manifest" || { echo 'FAIL manifest Agent Zero order changed'; exit 1; }
grep -q '| SearXNG |.*| 7 |' "$manifest" || { echo 'FAIL manifest SearXNG order changed'; exit 1; }
echo 'PASS installer and manifest dependency order'
