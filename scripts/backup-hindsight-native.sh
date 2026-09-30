#!/usr/bin/env bash
set -Eeuo pipefail

# Create a private, consistent Hindsight PostgreSQL custom-format backup.
# The credential file is passed to docker exec by Docker; its contents are
# never printed, copied into the container, or committed to the repository.

destination=${1:-}
credential_file=${HADES_HINDSIGHT_DB_ENV_FILE:-}
container=${HADES_HINDSIGHT_CONTAINER:-hades-hindsight}
pg_dump_path=${HADES_HINDSIGHT_PG_DUMP_PATH:-/home/hindsight/.pg0/installation/18.1.0/bin/pg_dump}
pg_restore_path=${HADES_HINDSIGHT_PG_RESTORE_PATH:-/home/hindsight/.pg0/installation/18.1.0/bin/pg_restore}

fail() { printf 'FAIL %s\n' "$*" >&2; exit 1; }

[[ -n "$destination" && -d "$destination" ]] || fail 'usage: backup-hindsight-native.sh EXISTING_PRIVATE_DIRECTORY'
[[ ! -L "$destination" ]] || fail 'destination must not be a symlink'
[[ -n "$credential_file" && -f "$credential_file" && ! -L "$credential_file" ]] ||
  fail 'HADES_HINDSIGHT_DB_ENV_FILE must point to a regular credential env file'

destination_mode=$(stat -Lc '%a' "$destination")
case "$destination_mode" in
  700|750|770|600) ;;
  *) fail 'destination permissions must be private' ;;
esac

credential_mode=$(stat -Lc '%a' "$credential_file")
case "$credential_mode" in
  600|640) ;;
  *) fail 'credential env file permissions must be 0600 or 0640' ;;
esac

# Accept only a single non-empty PGPASSWORD assignment, with optional blank or
# comment lines. This keeps unrelated secrets out of the docker exec request.
awk '
  /^[[:space:]]*($|#)/ { next }
  /^PGPASSWORD=.+$/ { count++; next }
  { bad=1 }
  END { exit (bad || count != 1) }
' "$credential_file" || fail 'credential env file must contain only one PGPASSWORD assignment'

docker inspect --type container "$container" >/dev/null 2>&1 || fail "container not found: $container"
state=$(docker inspect --format '{{.State.Status}}' "$container")
[[ "$state" == running ]] || fail "container is not running: $container"

command -v docker >/dev/null 2>&1 || fail 'docker is required'
umask 077
stamp=$(date -u +%Y%m%d-%H%M%S)
partial="$destination/.hindsight-${stamp}.partial"
output="$destination/hindsight-${stamp}.dump"

preserve_failed_partial() {
  if [[ -e "$partial" && ! -e "$output" ]]; then
    mv "$partial" "$partial.failed-rehearsal" 2>/dev/null || true
  fi
}
trap preserve_failed_partial EXIT

docker exec --env-file "$credential_file" "$container" \
  "$pg_dump_path" --format=custom --no-password \
  -h 127.0.0.1 -p 5432 -U hindsight -d hindsight > "$partial" ||
  fail 'pg_dump failed; no database mutation was performed'
[[ -s "$partial" ]] || fail 'pg_dump produced an empty archive'
chmod 600 "$partial"

# Stream the archive into a short-lived container file for pg_restore. The
# file is removed by the container-side exit trap; no database data is changed.
verify_path="/tmp/hades-hindsight-verify-${stamp}.dump"
cat "$partial" | docker exec -i "$container" sh -c \
  'set -eu; verify=$1; restore=$2; trap '\''rm -f "$verify"'\'' EXIT; cat > "$verify"; "$restore" --list "$verify" >/dev/null' \
  sh "$verify_path" "$pg_restore_path" ||
  fail 'pg_restore archive listing failed'

mv "$partial" "$output"
chmod 600 "$output"
(cd "$destination" && sha256sum "$(basename "$output")" > "$(basename "$output").SHA256SUM")
chmod 600 "$output.SHA256SUM"
trap - EXIT
printf 'PASS Hindsight native archive and structure validation\n'
printf 'PASS checksum sidecar created\n'
