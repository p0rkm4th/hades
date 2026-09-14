#!/usr/bin/env bash
set -euo pipefail

# Public-safe drift guard for the deliberately small tracked deployment set.
# Private operator topology is documented, but never copied into this check.
expected=(deploy/agent-zero.compose.yaml deploy/grocy.compose.yaml deploy/lldap.compose.yaml)
mapfile -t actual < <(find deploy -maxdepth 1 -type f -name '*.compose.yaml' -print | sort)
[[ "${actual[*]}" == "${expected[*]}" ]] || {
  printf 'FAIL tracked compose set drifted: %s\n' "${actual[*]}" >&2
  exit 1
}

for file in "${expected[@]}"; do
  grep -Eq '^services:' "$file" || { printf 'FAIL services missing: %s\n' "$file" >&2; exit 1; }
  case "$file" in
    deploy/agent-zero.compose.yaml) image_ref='image: ${HADES_AGENT_ZERO_IMAGE:?set HADES_AGENT_ZERO_IMAGE from config/versions.env}' ;;
    deploy/grocy.compose.yaml) image_ref='image: ${HADES_GROCY_IMAGE:?set HADES_GROCY_IMAGE from config/versions.env}' ;;
    deploy/lldap.compose.yaml) image_ref='image: ${HADES_LLDAP_IMAGE:?set HADES_LLDAP_IMAGE from config/versions.env}' ;;
  esac
  grep -Fq "$image_ref" "$file" || { printf 'FAIL image is not sourced from the authoritative pin: %s\n' "$file" >&2; exit 1; }
  if grep -En '(^|:)\s*(privileged|network_mode):\s*(true|host)' "$file"; then
    printf 'FAIL authority-amplifying compose setting: %s\n' "$file" >&2
    exit 1
  fi
done

for component in LLDAP 'Open WebUI' Hindsight Grocy 'Actual Budget / Finance MCP' 'Hermes 0.14 baseline' 'Agent Zero' SearXNG 'HADES policy/assets/adapters'; do
  grep -Eq "\| ${component} \|" docs/component-manifest.md || {
    printf 'FAIL manifest component missing: %s\n' "$component" >&2
    exit 1
  }
done
python3 - <<'PY'
import json
from pathlib import Path
manifest = json.loads(Path('config/reconstruction-manifest.json').read_text())
if manifest.get('source_of_truth') != 'config/versions.env' or len(manifest.get('components', [])) != 9:
    raise SystemExit('FAIL machine reconstruction manifest is incomplete')
identity = Path('docs/shared-identity.md').read_text()
if 'historical disposable staging proof' not in identity or 'config/versions.env' not in identity:
    raise SystemExit('FAIL historical identity versions are not clearly separated from current pins')
PY

printf 'PASS tracked deployment set and reconstruction manifest are aligned\n'
