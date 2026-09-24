#!/usr/bin/env bash
set -euo pipefail

# Validate a private recovery directory without printing its contents.
# The directory layout is described in docs/backup-restore.md.

ROOT=${1:-}
if [[ -z "$ROOT" || ! -d "$ROOT" ]]; then
  printf 'usage: %s PRIVATE_RECOVERY_DIRECTORY\n' "$0" >&2
  exit 2
fi
if [[ -L "$ROOT" ]]; then
  printf 'FAIL recovery root must not be a symlink\n'
  exit 1
fi

link=$(find "$ROOT" -type l -print -quit)
if [[ -n "$link" ]]; then
  printf 'FAIL recovery tree contains a symlink\n'
  exit 1
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

if [[ -e "$ROOT/open-webui.db" && -e "$ROOT/lldap-users.db" && \
      -e "$ROOT/grocy.db" && -e "$ROOT/hermes-state.db" ]]; then
  check_sqlite 'Open WebUI' "$ROOT/open-webui.db"
  check_sqlite 'LLDAP' "$ROOT/lldap-users.db"
  check_sqlite 'Grocy' "$ROOT/grocy.db"
  check_sqlite 'Hermes' "$ROOT/hermes-state.db"
else
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
fi

json_count=0
while IFS= read -r -d '' path; do
  [[ -s "$path" ]] || { printf 'FAIL JSON artifact: empty\n'; exit 1; }
  python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$path"
  json_count=$((json_count + 1))
done < <(find "$ROOT" -type f -name '*.json' -print0)
printf 'PASS JSON artifacts: %s\n' "$json_count"

archive_count=0
while IFS= read -r -d '' archive; do
  archive_mode=$(stat -Lc '%a' "$archive")
  case "$archive_mode" in
    600|640|660) ;;
    *) printf 'FAIL recovery archive permissions: %s\n' "$archive_mode"; exit 1 ;;
  esac
  [[ -s "$archive" ]] || { printf 'FAIL recovery archive: empty\n'; exit 1; }
  gzip -t "$archive" >/dev/null 2>&1 || {
    printf 'FAIL recovery archive compression\n'
    exit 1
  }
  archive_listing=$(tar -tvzf "$archive")
  while IFS= read -r entry; do
    case "${entry:0:1}" in
      l|h)
        printf 'FAIL recovery archive contains a link\n'
        exit 1
        ;;
    esac
  done <<< "$archive_listing"
  while IFS= read -r entry; do
    case "$entry" in
      /*|../*|*/../*|..)
        printf 'FAIL recovery archive path\n'
        exit 1
        ;;
    esac
  done < <(tar -tzf "$archive")
  archive_count=$((archive_count + 1))
done < <(find "$ROOT" -type f \( -name '*.tar.gz' -o -name '*.tgz' \) \
  ! -name '*.failed-rehearsal' -print0)
printf 'PASS recovery archives: %s\n' "$archive_count"

metadata_count=0
while IFS= read -r -d '' metadata; do
  metadata_mode=$(stat -Lc '%a' "$metadata")
  case "$metadata_mode" in
    600|640) ;;
    *) printf 'FAIL recovery metadata permissions: %s\n' "$metadata"; exit 1 ;;
  esac
  metadata_checksum="$(dirname "$metadata")/SHA256SUMS"
  [[ -f "$metadata_checksum" ]] || { printf 'FAIL recovery metadata has no checksum manifest\n'; exit 1; }
  grep -q '  MANIFEST$' "$metadata_checksum" || { printf 'FAIL recovery metadata is not checksummed\n'; exit 1; }
  grep -q '^backup_format=1$' "$metadata" || { printf 'FAIL recovery metadata format\n'; exit 1; }
  grep -q '^hades_manifest_version=1$' "$metadata" || { printf 'FAIL recovery metadata manifest version\n'; exit 1; }
  for field in hermes_version open_webui_version lldap_image hindsight_image_digest grocy_image agent_zero_image actual_version; do
    grep -Eq "^${field}=.+$" "$metadata" || { printf 'FAIL recovery metadata field: %s\n' "$field"; exit 1; }
  done
  metadata_count=$((metadata_count + 1))
done < <(find "$ROOT" -type f -name MANIFEST -print0)
printf 'PASS recovery metadata manifests: %s\n' "$metadata_count"

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
