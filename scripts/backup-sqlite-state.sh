#!/usr/bin/env bash
set -euo pipefail

# Create a private, consistent SQLite snapshot of the production state that
# is currently supported by the runtime tooling. This does not back up
# Hindsight PostgreSQL, Agent Zero, or secrets; those require their native
# operator procedures described in docs/backup-restore.md.

DESTINATION=${1:-}
if [[ -z "$DESTINATION" || ! -d "$DESTINATION" ]]; then
  printf 'usage: %s EXISTING_PRIVATE_DIRECTORY\n' "$0" >&2
  exit 2
fi

mode=$(stat -Lc '%a' "$DESTINATION")
case "$mode" in
  700|750|770|600) ;;
  *) printf 'FAIL destination permissions: %s\n' "$mode" >&2; exit 1 ;;
esac

umask 077
stamp=$(date +%Y%m%d-%H%M%S)
output=$(mktemp -d "$DESTINATION/hades-sqlite-${stamp}-XXXXXX")
chmod 700 "$output"
quiesced_container=""

restore_quiesced_container() {
  if [[ -n "$quiesced_container" ]]; then
    docker start "$quiesced_container" >/dev/null 2>&1 || true
    wait_for_container_ready "$quiesced_container" >/dev/null 2>&1 || true
    quiesced_container=""
  fi
}

trap restore_quiesced_container EXIT

backup_container_python() {
  local container=$1 source=$2 name=$3 tmp
  tmp="/tmp/hades-sqlite-backup-$stamp-$name"
  docker exec "$container" python3 -c 'import sqlite3,sys; src=sqlite3.connect(sys.argv[1]); dst=sqlite3.connect(sys.argv[2]); src.backup(dst); dst.close(); src.close()' "$source" "$tmp"
  docker cp "$container:$tmp" "$output/$name"
  docker exec "$container" python3 -c 'import os,sys; os.unlink(sys.argv[1])' "$tmp"
  chmod 600 "$output/$name"
}

backup_container_php() {
  local container=$1 source=$2 name=$3 tmp
  tmp="/tmp/hades-sqlite-backup-$stamp-$name"
  docker exec "$container" php -r '$src=new PDO("sqlite:".$argv[1]); $src->exec("VACUUM INTO " . $src->quote($argv[2]));' "$source" "$tmp"
  docker cp "$container:$tmp" "$output/$name"
  docker exec "$container" php -r 'unlink($argv[1]);' "$tmp"
  chmod 600 "$output/$name"
}

wait_for_container_ready() {
  local container=$1 state health
  for _ in $(seq 1 30); do
    state=$(docker inspect --format '{{.State.Status}}' "$container" 2>/dev/null || true)
    health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$container" 2>/dev/null || true)
    if [[ "$state" == running && ( "$health" == healthy || -z "$health" ) ]]; then
      return 0
    fi
    sleep 2
  done
  printf 'FAIL container did not become ready: %s\n' "$container" >&2
  return 1
}

backup_container_quiesced() {
  local container=$1 source=$2 name=$3
  docker stop "$container" >/dev/null
  quiesced_container="$container"
  if ! docker cp "$container:$source" "$output/$name"; then
    if docker start "$container" >/dev/null && \
       wait_for_container_ready "$container"; then
      quiesced_container=""
    fi
    return 1
  fi
  docker start "$container" >/dev/null
  wait_for_container_ready "$container"
  quiesced_container=""
  chmod 600 "$output/$name"
}

backup_container_python hades-open-webui /app/backend/data/webui.db open-webui.db
backup_container_quiesced hades-lldap-production /data/users.db lldap-users.db
backup_container_php hades-grocy /config/data/grocy.db grocy.db

hermes_source=${HADES_HERMES_STATE_DB:-}
[[ -n "$hermes_source" ]] || {
  printf 'FAIL HADES_HERMES_STATE_DB is required\n' >&2
  exit 2
}
[[ -s "$hermes_source" ]] || { printf 'FAIL Hermes state database missing: %s\n' "$hermes_source" >&2; exit 1; }
sqlite3 "$hermes_source" ".backup '$output/hermes-state.db'"

for path in "$output"/*.db; do
  [[ -s "$path" ]] || { printf 'FAIL empty backup: %s\n' "$path" >&2; exit 1; }
  sqlite3 "$path" 'pragma integrity_check;' | grep -qx ok || {
    printf 'FAIL SQLite integrity: %s\n' "$path" >&2
    exit 1
  }
done
(cd "$output" && sha256sum ./*.db > SHA256SUMS)
chmod 600 "$output/SHA256SUMS"
printf 'PASS SQLite backup: %s\n' "$output"
printf 'PASS artifacts=4 checksums=1\n'
