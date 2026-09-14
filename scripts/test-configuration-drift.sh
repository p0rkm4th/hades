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
  rg -q '^services:' "$file" || { printf 'FAIL services missing: %s\n' "$file" >&2; exit 1; }
  rg -q 'image: .+@sha256:[0-9a-f]{64}' "$file" || { printf 'FAIL unpinned image: %s\n' "$file" >&2; exit 1; }
  if rg -n '(^|:)\s*(privileged|network_mode):\s*(true|host)' "$file"; then
    printf 'FAIL authority-amplifying compose setting: %s\n' "$file" >&2
    exit 1
  fi
done

for component in LLDAP 'Open WebUI' Hindsight Grocy 'Hermes 0.14 baseline' 'Agent Zero' SearXNG 'HADES policy/assets/adapters'; do
  rg -q "\| ${component} \|" docs/component-manifest.md || {
    printf 'FAIL manifest component missing: %s\n' "$component" >&2
    exit 1
  }
done

printf 'PASS tracked deployment set and reconstruction manifest are aligned\n'
