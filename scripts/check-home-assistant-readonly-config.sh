#!/usr/bin/env bash
set -euo pipefail

# Validate the proposed Home Assistant observation boundary without contacting
# Home Assistant. Tokens and entity identifiers are never printed.

missing=0
invalid=0

require_value() {
  local name=$1 value=${!1-}
  if [[ -z "$value" ]]; then
    printf 'BLOCKED %s is not configured\n' "$name"
    missing=1
  fi
}

require_value HADES_HOME_ASSISTANT_URL
require_value HADES_HOME_ASSISTANT_TOKEN
require_value HADES_HOME_ASSISTANT_ENTITY_ALLOWLIST

if [[ -n "${HADES_HOME_ASSISTANT_URL-}" ]]; then
  if [[ ! "$HADES_HOME_ASSISTANT_URL" =~ ^https://[^[:space:]]+$ || "$HADES_HOME_ASSISTANT_URL" == *example.invalid* ]]; then
    printf 'FAIL HADES_HOME_ASSISTANT_URL is not a real HTTPS endpoint\n'
    invalid=1
  fi
fi

if [[ -n "${HADES_HOME_ASSISTANT_ENTITY_ALLOWLIST-}" ]]; then
  IFS=',' read -r -a entities <<< "$HADES_HOME_ASSISTANT_ENTITY_ALLOWLIST"
  if ((${#entities[@]} == 0)); then
    printf 'FAIL Home Assistant entity allowlist is empty\n'
    invalid=1
  fi
  for entity in "${entities[@]}"; do
    entity=$(printf '%s' "$entity" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    if [[ ! "$entity" =~ ^[a-z0-9_]+\.[a-z0-9_]+$ ]]; then
      printf 'FAIL Home Assistant entity allowlist contains an invalid entity\n'
      invalid=1
      continue
    fi
    # Match security/high-impact terms as entity-name components. A loose
    # substring check would incorrectly reject benign IDs such as
    # sensor.indoor_temperature ("indoor" contains "door").
    if [[ "$entity" =~ (^|[._-])(lock|garage|alarm|camera|door|security|gate)([._-]|$) ]]; then
      printf 'FAIL Home Assistant entity allowlist contains an excluded security/high-impact entity\n'
      invalid=1
    fi
  done
fi

if (( invalid )); then
  exit 1
fi
if (( missing )); then
  printf 'Home Assistant read-only configuration is incomplete; no network probes were made\n'
  exit 2
fi

printf 'PASS Home Assistant read-only configuration shape\n'
printf 'PASS security-sensitive entity exclusions\n'
printf 'PASS no network probes performed\n'
