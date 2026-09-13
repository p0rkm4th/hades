#!/usr/bin/env bash
set -euo pipefail

# Validate a private recovery directory without printing its contents.
# The directory layout is described in docs/backup-restore.md.

ROOT=${1:-}
if [[ -z "$ROOT" || ! -d "$ROOT" ]]; then
  printf 'usage: %s PRIVATE_RECOVERY_DIRECTORY\n' "$0" >&2
  exit 2
fi

mode=$(stat -Lc '%a' "$ROOT")
case "$mode" in
  700|750|770|600) ;;
  *) printf 'FAIL recovery root permissions: %s\n' "$mode"; exit 1 ;;
esac

check_sqlite() {
  local label=$1 path=$2 result file_mode
  if [[ ! -s "$path" ]]; then
    printf 'FAIL %s: missing or empty\n' "$label"
    exit 1
  fi
  file_mode=$(stat -Lc '%a' "$path")
  case "$file_mode" in
    600|640|660) ;;
    *) printf 'FAIL %s permissions: %s\n' "$label" "$file_mode"; exit 1 ;;
  esac
  result=$(sqlite3 "$path" 'pragma integrity_check;')
  [[ "$result" == ok ]] || { printf 'FAIL %s integrity\n' "$label"; exit 1; }
  printf 'PASS %s SQLite integrity\n' "$label"
}

check_sqlite 'Open WebUI' "$ROOT/open-webui-data/webui.db"
check_sqlite 'LLDAP' "$ROOT/lldap-data/users.db"
check_sqlite 'Hermes' "$ROOT/hermes-profile/state.db"

if [[ -e "$ROOT/grocy-config/grocy.db" ]]; then
  check_sqlite 'Grocy' "$ROOT/grocy-config/grocy.db"
elif [[ -e "$ROOT/grocy.db" ]]; then
  check_sqlite 'Grocy' "$ROOT/grocy.db"
else
  printf 'FAIL Grocy: missing\n'
  exit 1
fi

json_count=0
while IFS= read -r -d '' path; do
  [[ -s "$path" ]] || { printf 'FAIL JSON artifact: empty\n'; exit 1; }
  python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$path"
  json_count=$((json_count + 1))
done < <(find "$ROOT" -type f -name '*.json' -print0)
printf 'PASS JSON artifacts: %s\n' "$json_count"

checksum_count=0
while IFS= read -r -d '' manifest; do
  manifest_mode=$(stat -Lc '%a' "$manifest")
  case "$manifest_mode" in
    600|640|660) ;;
    *) printf 'FAIL checksum manifest permissions: %s\n' "$manifest_mode"; exit 1 ;;
  esac
  if ! (cd "$(dirname "$manifest")" && sha256sum -c "$(basename "$manifest")" >/dev/null 2>&1); then
    printf 'FAIL checksum manifest verification\n'
    exit 1
  fi
  checksum_count=$((checksum_count + 1))
done < <(find "$ROOT" -type f -name 'SHA256SUMS' -print0)
printf 'PASS checksum manifests: %s\n' "$checksum_count"
printf 'Recovery artifact validation passed\n'
