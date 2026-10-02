#!/usr/bin/env bash
set -euo pipefail

record=${1:?usage: validate-destination-owner-acceptance.sh RECORD}
[[ -f "$record" ]] || { echo "FAIL acceptance record not found: $record"; exit 1; }

required_keys=(
  schema environment destination destination_endpoint owner_login
  existing_conversation_visible new_conversation_model_response
  private_memory_recall private_memory_correction grocy_read
  grocy_mutation_and_canonical_readback recipe_interaction web_search
  agent_zero_delegation household_authorization_boundaries restart_persistence
  mobile_or_private_network_client source_laptop_not_used owner_accepted_cutover
)

if ! awk '
  BEGIN {
    split("schema environment destination destination_endpoint owner_login existing_conversation_visible new_conversation_model_response private_memory_recall private_memory_correction grocy_read grocy_mutation_and_canonical_readback recipe_interaction web_search agent_zero_delegation household_authorization_boundaries restart_persistence mobile_or_private_network_client source_laptop_not_used owner_accepted_cutover operator_notes", names)
    for (i in names) allowed[names[i]] = 1
  }
  /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
  index($0, "=") == 0 { print "FAIL acceptance record line has no key=value separator"; bad = 1; next }
  { key = substr($0, 1, index($0, "=") - 1) }
  key !~ /^[a-z][a-z0-9_]*$/ { print "FAIL invalid acceptance field name: " key; bad = 1; next }
  !(key in allowed) { print "FAIL unknown acceptance field: " key; bad = 1; next }
  seen[key]++ { print "FAIL duplicate acceptance field: " key; bad = 1 }
  END { exit bad }
' "$record"; then
  exit 1
fi

for key in "${required_keys[@]}"; do
  value=$(awk -F= -v wanted="$key" '$1 == wanted {sub(/^[^=]*=/, ""); print; exit}' "$record")
  [[ -n "$value" ]] || { echo "FAIL missing acceptance field: $key"; exit 1; }
  case "$key" in
    schema)
      [[ "$value" == destination-owner-acceptance/v1 ]] || { echo 'FAIL schema'; exit 1; }
      ;;
    environment)
      [[ "$value" == REAL_DESTINATION ]] || { echo 'FAIL record is not REAL_DESTINATION'; exit 1; }
      ;;
    destination)
      [[ "$value" == hades-core ]] || { echo 'FAIL destination'; exit 1; }
      ;;
    destination_endpoint)
      [[ "$value" == hades.example.test:3000 ]] || { echo 'FAIL destination endpoint'; exit 1; }
      ;;
    *)
      [[ "$value" == PASS ]] || { echo "FAIL $key is not PASS"; exit 1; }
      ;;
  esac
done

operator_notes=$(awk -F= '$1 == "operator_notes" {sub(/^[^=]*=/, ""); print; exit}' "$record")
[[ -n "$operator_notes" && "$operator_notes" != REQUIRED && "$operator_notes" != NOT\ RUN ]] || {
  echo 'FAIL operator_notes must contain a non-placeholder human record'
  exit 1
}

if grep -Eiq '(password|token|secret|bearer|api[_-]?key)[[:space:]]*=' "$record"; then
  echo 'FAIL acceptance record contains secret-like material'
  exit 1
fi

echo 'PASS real destination owner-acceptance record is complete and secret-free'
