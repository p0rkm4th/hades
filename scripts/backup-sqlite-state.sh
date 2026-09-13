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
output="$DESTINATION/hades-sqlite-$stamp"
install -d -m 700 "$output"

backup_container_python() {
  local container=$1 source=$2 name=$3 tmp
  tmp="/tmp/hades-sqlite-backup-$stamp-$name"
  docker exec "$container" python3 -c 'import sqlite3,sys; src=sqlite3.connect(sys.argv[1]); dst=sqlite3.connect(sys.argv[2]); src.backup(dst); dst.close(); src.close()' "$source" "$tmp"
  docker cp "$container:$tmp" "$output/$name"
  docker exec "$container" python3 -c 'import os,sys; os.unlink(sys.argv[1])' "$tmp"
}

backup_container_php() {
  local container=$1 source=$2 name=$3 tmp
  tmp="/tmp/hades-sqlite-backup-$stamp-$name"
  docker exec "$container" php -r '$src=new PDO("sqlite:".$argv[1]); $src->exec("VACUUM INTO " . $src->quote($argv[2]));' "$source" "$tmp"
  docker cp "$container:$tmp" "$output/$name"
  docker exec "$container" php -r 'unlink($argv[1]);' "$tmp"
}

backup_container_python hades-open-webui /app/backend/data/webui.db open-webui.db
backup_container_python hades-lldap-production /data/users.db lldap-users.db
backup_container_php hades-grocy /config/grocy.db grocy.db

hermes_source=${HADES_HERMES_STATE_DB:-}
[[ -s "$hermes_source" ]] || { printf 'FAIL Hermes state database missing: %s\n' "$hermes_source" >&2; exit 1; }
sqlite3 "$hermes_source" ".backup '$output/hermes-state.db'"

for path in "$output"/*.db; do
  [[ -s "$path" ]] || { printf 'FAIL empty backup: %s\n' "$path" >&2; exit 1; }
  chmod 600 "$path"
done
(cd "$output" && sha256sum ./*.db > SHA256SUMS)
chmod 600 "$output/SHA256SUMS"
printf 'PASS SQLite backup: %s\n' "$output"
printf 'PASS artifacts=4 checksums=1\n'
