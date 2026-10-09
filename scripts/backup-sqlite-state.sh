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
[[ ! -L "$DESTINATION" ]] || { printf 'FAIL backup destination must not be a symlink\n' >&2; exit 1; }
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1090
source "$repo_dir/config/versions.env"
command -v python3 >/dev/null 2>&1 || { printf 'FAIL python3 is required for SQLite backup validation\n' >&2; exit 1; }

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

sqlite_backup() {
  python3 - "$1" "$2" <<'PY'
import sqlite3
import sys

source = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
destination = sqlite3.connect(sys.argv[2])
try:
    source.backup(destination)
finally:
    destination.close()
    source.close()
PY
}

sqlite_integrity() {
  python3 - "$1" <<'PY'
import sqlite3
import sys

connection = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro&immutable=1", uri=True)
try:
    rows = connection.execute("PRAGMA integrity_check").fetchall()
finally:
    connection.close()
if rows != [("ok",)]:
    raise SystemExit("SQLite integrity check failed")
PY
}

backup_container_python hades-open-webui /app/backend/data/webui.db open-webui.db
open_webui_auth_state=absent
require_auth_state_backup=${HADES_REQUIRE_OPEN_WEBUI_AUTH_STATE_BACKUP:-0}
webui_env=$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' hades-open-webui 2>/dev/null || true)
if printf '%s\n' "$webui_env" | grep -q '^REDIS_URL='; then
  require_auth_state_backup=1
fi
if docker inspect hades-open-webui-auth-state >/dev/null 2>&1; then
  docker exec hades-open-webui-auth-state valkey-cli ping | grep -qx PONG || {
    printf 'FAIL Open WebUI auth-state Valkey is not healthy\n' >&2
    exit 1
  }
  [[ -n "${HADES_OPEN_WEBUI_VALKEY_IMAGE:-}" ]] || {
    printf 'FAIL pinned Valkey image is required to validate auth-state backup\n' >&2
    exit 1
  }
  last_save_before=$(docker exec hades-open-webui-auth-state valkey-cli --raw LASTSAVE | tr -d '\r')
  [[ "$last_save_before" =~ ^[0-9]+$ ]] || { printf 'FAIL invalid Valkey LASTSAVE value\n' >&2; exit 1; }
  docker exec hades-open-webui-auth-state valkey-cli BGSAVE >/dev/null
  saved=0
  for _ in $(seq 1 90); do
    persistence=$(docker exec hades-open-webui-auth-state valkey-cli --raw INFO persistence)
    last_save_after=$(docker exec hades-open-webui-auth-state valkey-cli --raw LASTSAVE | tr -d '\r')
    in_progress=$(printf '%s\n' "$persistence" | sed -n 's/^rdb_bgsave_in_progress://p' | tr -d '\r')
    save_status=$(printf '%s\n' "$persistence" | sed -n 's/^rdb_last_bgsave_status://p' | tr -d '\r')
    if [[ "$in_progress" == 0 && "$save_status" == ok && "$last_save_after" =~ ^[0-9]+$ && "$last_save_after" -gt "$last_save_before" ]]; then
      saved=1
      break
    fi
    sleep 1
  done
  [[ "$saved" == 1 ]] || { printf 'FAIL Valkey RDB snapshot did not complete successfully\n' >&2; exit 1; }
  docker cp hades-open-webui-auth-state:/data/dump.rdb "$output/open-webui-auth-state.rdb"
  [[ -s "$output/open-webui-auth-state.rdb" ]] || { printf 'FAIL Valkey RDB snapshot is empty\n' >&2; exit 1; }
  docker run --rm --network none --entrypoint valkey-check-rdb \
    -v "$output:/backup:ro" "$HADES_OPEN_WEBUI_VALKEY_IMAGE" \
    /backup/open-webui-auth-state.rdb >/dev/null
  chmod 600 "$output/open-webui-auth-state.rdb"
  open_webui_auth_state=present
elif [[ "$require_auth_state_backup" == 1 ]]; then
  printf 'FAIL P0 backup requires the Open WebUI auth-state store\n' >&2
  exit 1
fi

lldap_container=${HADES_LLDAP_CONTAINER:-hades-lldap-production}
backup_container_quiesced "$lldap_container" /data/users.db lldap-users.db
backup_container_php hades-grocy /config/data/grocy.db grocy.db

hermes_source=${HADES_HERMES_STATE_DB:-}
[[ -n "$hermes_source" ]] || {
  printf 'FAIL HADES_HERMES_STATE_DB is required\n' >&2
  exit 2
}
[[ -s "$hermes_source" ]] || { printf 'FAIL Hermes state database missing: %s\n' "$hermes_source" >&2; exit 1; }
sqlite_backup "$hermes_source" "$output/hermes-state.db"

phase3_source=${HADES_EPSILON_PHASE3_STATE_FILE:-}
if [[ -z "$phase3_source" ]]; then
  epsilon_source=${HADES_EPSILON_STATE_FILE:-}
  if [[ -z "$epsilon_source" ]]; then
    hermes_home=${HERMES_HOME:-/var/lib/hades}
    epsilon_source="$hermes_home/profiles/hades/state/epsilon-automation.sqlite"
  fi
  phase3_source="$(dirname "$epsilon_source")/phase3/automations.sqlite"
fi
phase3_state=absent
if [[ -e "$phase3_source" || -L "$phase3_source" ]]; then
  [[ -f "$phase3_source" && ! -L "$phase3_source" ]] || {
    printf 'FAIL Phase 3 state database must be a regular non-symlink file\n' >&2
    exit 1
  }
  sqlite_backup "$phase3_source" "$output/phase3-automation.db"
  chmod 600 "$output/phase3-automation.db"
  phase3_state=present
fi

for path in "$output"/*.db; do
  [[ -s "$path" ]] || { printf 'FAIL empty backup: %s\n' "$path" >&2; exit 1; }
  sqlite_integrity "$path" || {
    printf 'FAIL SQLite integrity: %s\n' "$path" >&2
    exit 1
  }
done
cat > "$output/MANIFEST" <<EOF
backup_format=1
created_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
hades_manifest_version=$HADES_MANIFEST_VERSION
hermes_version=$HADES_HERMES_VERSION
open_webui_version=$HADES_OPEN_WEBUI_VERSION
lldap_image=$HADES_LLDAP_IMAGE
hindsight_image_digest=$HADES_HINDSIGHT_IMAGE_DIGEST
grocy_image=$HADES_GROCY_IMAGE
agent_zero_image=$HADES_AGENT_ZERO_IMAGE
searxng_image_record=$HADES_SEARXNG_IMAGE_RECORD
actual_version=$HADES_ACTUAL_VERSION
grocy_adapter_revision=$HADES_GROCY_ADAPTER_REVISION
agent_zero_adapter_revision=$HADES_AGENT_ZERO_ADAPTER_REVISION
phase3_state=$phase3_state
open_webui_auth_state=$open_webui_auth_state
open_webui_valkey_image=$HADES_OPEN_WEBUI_VALKEY_IMAGE
EOF
chmod 600 "$output/MANIFEST"
backup_files=("$output"/*.db "$output"/*.rdb "$output"/MANIFEST)
(cd "$output" && sha256sum "${backup_files[@]##*/}" > SHA256SUMS)
chmod 600 "$output/SHA256SUMS"
printf 'PASS SQLite backup: %s\n' "$output"
artifact_count=$(find "$output" -maxdepth 1 -type f -name '*.db' | wc -l)
printf 'PASS artifacts=%s metadata=1 checksums=1 phase3_state=%s open_webui_auth_state=%s\n' "$artifact_count" "$phase3_state" "$open_webui_auth_state"
