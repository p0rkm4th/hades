#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "$0")/.." && pwd)
script="$repo_dir/scripts/backup-hindsight-native.sh"
[[ -x "$script" ]] || { echo 'FAIL Hindsight backup helper is not executable'; exit 1; }
bash -n "$script"
grep -Fq -- '--env-file "$credential_file"' "$script" || {
  echo 'FAIL helper does not pass the protected env file through Docker'; exit 1;
}
grep -Fq -- 'pg_restore_path' "$script" || {
  echo 'FAIL helper omits archive validation'; exit 1;
}
grep -Fq -- 'sha256sum "$(basename "$output")"' "$script" || {
  echo 'FAIL helper omits checksum sidecar'; exit 1;
}
if grep -Eq '^[[:space:]]*echo[[:space:]].*(PGPASSWORD|credential_file)' "$script"; then
  echo 'FAIL helper may print credential metadata'; exit 1
fi
if grep -Eq '^[[:space:]]*docker exec.*PGPASSWORD=' "$script"; then
  echo 'FAIL helper places the password in a docker command argument'; exit 1
fi
fixture=$(mktemp -d)
trap 'rm -rf "$fixture"' EXIT
mkdir -p "$fixture/bin" "$fixture/destination"
chmod 700 "$fixture/destination"
printf '%s\n' 'PGPASSWORD=synthetic-only' > "$fixture/credential.env"
chmod 600 "$fixture/credential.env"
cat > "$fixture/bin/docker" <<'DOCKER'
#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in
  inspect)
    if [[ " $* " == *'State.Status'* ]]; then
      printf 'running\n'
    else
      printf 'synthetic-container\n'
    fi
    ;;
  exec)
    shift
    while [[ "${1:-}" == '-i' || "${1:-}" == '--env-file' ]]; do
      if [[ "$1" == '--env-file' ]]; then shift 2; else shift; fi
    done
    container=${1:?container}; shift
    command=${1:?command}; shift
    case "$command" in
      */pg_dump) printf '%s\n' 'synthetic-pg-custom-archive' ;;
      sh) cat >/dev/null ;;
      *) printf 'unexpected fake docker command\n' >&2; exit 1 ;;
    esac
    ;;
  *) printf 'unexpected fake docker operation\n' >&2; exit 1 ;;
esac
DOCKER
chmod 755 "$fixture/bin/docker"
PATH="$fixture/bin:$PATH" HADES_HINDSIGHT_DB_ENV_FILE="$fixture/credential.env" \
  "$script" "$fixture/destination" >/dev/null
archive=$(find "$fixture/destination" -type f -name '*.dump' -print -quit)
[[ -s "$archive" ]] || { echo 'FAIL disposable helper produced no archive'; exit 1; }
(cd "$(dirname "$archive")" && sha256sum -c "$(basename "$archive").SHA256SUM" >/dev/null)
printf '%s\n' 'OTHER=not-allowed' > "$fixture/bad.env"
chmod 600 "$fixture/bad.env"
if PATH="$fixture/bin:$PATH" HADES_HINDSIGHT_DB_ENV_FILE="$fixture/bad.env" \
  "$script" "$fixture/destination" >/dev/null 2>&1; then
  echo 'FAIL malformed credential env file was accepted'; exit 1
fi
echo 'PASS disposable Hindsight archive/checksum path and credential rejection'
echo 'PASS Hindsight native backup helper is fail-closed and secret-safe'
