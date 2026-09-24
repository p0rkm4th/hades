#!/usr/bin/env bash
set -euo pipefail

record=${1:?usage: validate-laptop-decommission-record.sh RECORD}
[[ -f "$record" ]] || { echo "FAIL cleanup record not found: $record"; exit 1; }

allowed=(
  schema production_services_disabled production_containers_removed
  allowlisted_cleanup ambiguous_material_preserved
  disk_usage_before_after_recorded operator_notes
)

if ! awk '
  BEGIN {
    split("schema production_services_disabled production_containers_removed allowlisted_cleanup ambiguous_material_preserved disk_usage_before_after_recorded operator_notes", names)
    for (i in names) allowed[names[i]] = 1
  }
  /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
  index($0, "=") == 0 { print "FAIL cleanup record line has no key=value separator"; bad = 1; next }
  { key = substr($0, 1, index($0, "=") - 1) }
  key !~ /^[a-z][a-z0-9_]*$/ { print "FAIL invalid cleanup field name: " key; bad = 1; next }
  !(key in allowed) { print "FAIL unknown cleanup field: " key; bad = 1; next }
  seen[key]++ { print "FAIL duplicate cleanup field: " key; bad = 1 }
  END { exit bad }
' "$record"; then
  exit 1
fi

for key in "${allowed[@]}"; do
  value=$(awk -F= -v wanted="$key" '$1 == wanted {sub(/^[^=]*=/, ""); print; exit}' "$record")
  [[ -n "$value" ]] || { echo "FAIL missing cleanup field: $key"; exit 1; }
  case "$key" in
    schema)
      [[ "$value" == laptop-production-decommission/v1 ]] || { echo 'FAIL cleanup schema'; exit 1; }
      ;;
    operator_notes)
      [[ "$value" != REQUIRED && "$value" != NOT\ RUN ]] || { echo 'FAIL cleanup operator_notes'; exit 1; }
      ;;
    *)
      [[ "$value" == PASS ]] || { echo "FAIL $key is not PASS"; exit 1; }
      ;;
  esac
done

if grep -Eiq '(password|token|secret|bearer|api[_-]?key)[[:space:]]*=' "$record"; then
  echo 'FAIL cleanup record contains secret-like material'
  exit 1
fi

echo 'PASS laptop decommission record is complete and secret-free'
