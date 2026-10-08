#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Disposable end-to-end native PostgreSQL backup/destroy/restore rehearsal.
# Uses only the manifest-pinned image and synthetic data in temporary Docker
# volumes. This is not a production backup or a production recovery command.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$repo_dir/config/versions.env"
backup_script="$repo_dir/scripts/backup-hindsight-native.sh"
pg_dump_path=${HADES_HINDSIGHT_PG_DUMP_PATH:-/home/hindsight/.pg0/installation/18.1.0/bin/pg_dump}
pg_restore_path=${HADES_HINDSIGHT_PG_RESTORE_PATH:-/home/hindsight/.pg0/installation/18.1.0/bin/pg_restore}
suffix="$$-$RANDOM"
source_name="hades-hindsight-restore-source-$suffix"
restore_name="hades-hindsight-restore-target-$suffix"
model_name="hades-hindsight-restore-model-$suffix"
network="hades-hindsight-restore-net-$suffix"
source_volume="hades-hindsight-restore-source-data-$suffix"
restore_volume="hades-hindsight-restore-target-data-$suffix"
bank="synthetic-restore-$suffix"
marker="synthetic-hindsight-restore-$suffix"
fact='The synthetic user prefers violet comet-42 markers.'
extractor_model=synthetic-hindsight-ui-extractor
work=$(mktemp -d "${TMPDIR:-/tmp}/hades-hindsight-restore.XXXXXX")
destination="$work/backup"
mkdir -m 700 "$destination"
credential_file="$work/db.env"
printf '%s\n' 'PGPASSWORD=hindsight' > "$credential_file"
chmod 600 "$credential_file"
model_state="$work/model-state"
model_requests="$work/model-requests.jsonl"
mkdir -m 700 "$model_state"
chmod 777 "$model_state"

test_image=${HADES_HINDSIGHT_TEST_IMAGE:-$HADES_HINDSIGHT_IMAGE}

fail() { printf 'FAIL %s\n' "$*" >&2; exit 1; }
cleanup() {
  local status=$?
  trap - EXIT
  docker rm -f "$source_name" "$restore_name" "$model_name" >/dev/null 2>&1 || true
  docker volume rm "$source_volume" "$restore_volume" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
  rm -rf -- "$work"
  exit "$status"
}
trap cleanup EXIT

command -v docker >/dev/null 2>&1 || fail 'docker is required'
command -v curl >/dev/null 2>&1 || fail 'curl is required'
command -v python3 >/dev/null 2>&1 || fail 'python3 is required'
[[ -x "$backup_script" ]] || fail 'native Hindsight backup helper is unavailable'
[[ "$test_image" =~ ^[^[:space:]@]+@sha256:[0-9a-f]{64}$ ]] ||
  fail 'HADES_HINDSIGHT_TEST_IMAGE must be an immutable repository-plus-sha256 reference'
docker image inspect "$test_image" >/dev/null 2>&1 ||
  fail 'selected immutable Hindsight test image is not available locally'

docker network create "$network" >/dev/null
docker run -d --name "$model_name" \
  --network "$network" --network-alias hades-mock \
  --entrypoint python3 \
  -v "$repo_dir/scripts/synthetic-hindsight-model.py:/tmp/synthetic-hindsight-model.py:ro" \
  -v "$model_state:/tmp/mock-state" \
  -e "HADES_SYNTHETIC_HINDSIGHT_MODEL=$extractor_model" \
  "$test_image" /tmp/synthetic-hindsight-model.py 0.0.0.0 \
  /tmp/mock-state/port /tmp/mock-state/requests.jsonl >/dev/null
model_port=''
for _ in $(seq 1 100); do
  candidate_port=$(docker exec "$model_name" cat /tmp/mock-state/port 2>/dev/null || true)
  if [[ "$candidate_port" =~ ^[0-9]+$ ]]; then
    model_port=$candidate_port
    break
  fi
  sleep 0.2
done
[[ "$model_port" =~ ^[0-9]+$ ]] || fail 'synthetic Hindsight model stub returned an invalid port'

start_hindsight() {
  local name=$1 volume=$2 port
  docker run -d --name "$name" --network "$network" \
    -p '127.0.0.1::8888' -p '127.0.0.1::9999' \
    -v "$volume:/home/hindsight/.pg0" \
    -e HINDSIGHT_API_HOST=0.0.0.0 \
    -e HINDSIGHT_API_PORT=8888 \
    -e HINDSIGHT_API_ENABLE_OBSERVATIONS=true \
    -e HINDSIGHT_API_WORKER_ID=hades-hindsight-restore-test \
    -e HINDSIGHT_API_LLM_PROVIDER=ollama \
    -e "HINDSIGHT_API_LLM_MODEL=$extractor_model" \
    -e "HINDSIGHT_API_LLM_BASE_URL=http://hades-mock:${model_port}/v1" \
    -e HINDSIGHT_API_LLM_API_KEY=synthetic-only \
    "$test_image" >/dev/null
  port=$(docker inspect "$name" --format '{{(index (index .NetworkSettings.Ports "8888/tcp") 0).HostPort}}')
  for _ in $(seq 1 90); do
    if curl -fsS --max-time 2 "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
      printf '%s\n' "$port"
      return 0
    fi
    sleep 1
  done
  fail "disposable Hindsight service did not become healthy: $name"
}

find_pg_tool() {
  local name=$1 tool=$2 path
  path=$(docker exec "$name" sh -lc "find /home/hindsight/.pg0/installation -type f -name '$tool' -print -quit")
  [[ -n "$path" ]] || fail "pinned Hindsight image has no $tool binary"
  printf '%s\n' "$path"
}

docker volume create "$source_volume" >/dev/null
source_port=$(start_hindsight "$source_name" "$source_volume")
psql_path=$(find_pg_tool "$source_name" psql)

# Create one synthetic Hindsight bank/memory plus a SQL marker. No production
# identity, bank, operation, or memory is involved.
curl -fsS --max-time 10 -X PUT \
  "http://127.0.0.1:${source_port}/v1/default/banks/${bank}" \
  -H 'Content-Type: application/json' \
  --data '{"name":"Synthetic Hindsight backup restore fixture"}' >/dev/null
python3 - "$fact" "$work/retain.json" <<'PY'
import json, sys
with open(sys.argv[2], "w", encoding="utf-8") as out:
    json.dump({"items": [{"content": sys.argv[1], "context": "synthetic backup/restore acceptance", "tags": ["hades-explicit-memory"]}], "async": False}, out)
PY
python3 - "$work/recall.json" <<'PY'
import json, sys
with open(sys.argv[1], "w", encoding="utf-8") as out:
    json.dump({"query": "What markers does the synthetic user prefer? violet comet-42", "budget": "low", "max_tokens": 1200, "tags": ["hades-explicit-memory"], "tags_match": "any"}, out)
PY
curl -fsS --max-time 60 -X POST \
  "http://127.0.0.1:${source_port}/v1/default/banks/${bank}/memories" \
  -H 'Content-Type: application/json' --data-binary "@$work/retain.json" >/dev/null
docker exec --env-file "$credential_file" "$source_name" "$psql_path" \
  -h 127.0.0.1 -p 5432 -U hindsight -d hindsight -v ON_ERROR_STOP=1 \
  -c 'CREATE TABLE public.hades_backup_restore_probe (marker text PRIMARY KEY);' \
  -c "INSERT INTO public.hades_backup_restore_probe(marker) VALUES ('$marker');" >/dev/null

verify_memory() {
  local api_port=$1 label=$2 list recall
  list=$(curl -fsS --max-time 20 \
    "http://127.0.0.1:${api_port}/v1/default/banks/${bank}/memories/list?tags=hades-explicit-memory&tags_match=any&state=valid&limit=100") ||
    fail "$label Hindsight memory list request failed"
  python3 -c 'import json,sys; d=json.loads(sys.stdin.read()); items=d.get("items",[]); assert any("violet comet-42" in str(x.get("text","")).casefold() and "hades-explicit-memory" in x.get("tags",[]) for x in items)' <<<"$list" ||
    fail "$label Hindsight canonical memory listing did not contain the synthetic fact"
  recall=$(curl -fsS --max-time 60 -X POST \
    "http://127.0.0.1:${api_port}/v1/default/banks/${bank}/memories/recall" \
    -H 'Content-Type: application/json' --data-binary "@$work/recall.json") ||
    fail "$label Hindsight memory recall request failed"
  python3 -c 'import json,sys; d=json.loads(sys.stdin.read()); rows=d.get("results",[]); assert any("violet comet-42" in str(x.get("text","")).casefold() for x in rows)' <<<"$recall" ||
    fail "$label Hindsight recall did not return the synthetic fact"
}
verify_memory "$source_port" source

HADES_HINDSIGHT_CONTAINER="$source_name" \
HADES_HINDSIGHT_DB_ENV_FILE="$credential_file" \
  "$backup_script" "$destination" >/dev/null
archive=$(find "$destination" -maxdepth 1 -type f -name 'hindsight-*.dump' -print -quit)
[[ -s "$archive" ]] || fail 'native Hindsight backup helper produced no archive'
archive_name=$(basename "$archive")
(cd "$destination" && sha256sum -c "$archive_name.SHA256SUM" >/dev/null) ||
  fail 'synthetic Hindsight backup checksum validation failed'

# Destroy the source container and its only database volume before restoring.
docker rm -f "$source_name" >/dev/null
docker volume rm "$source_volume" >/dev/null

docker volume create "$restore_volume" >/dev/null
restore_port=$(start_hindsight "$restore_name" "$restore_volume")
restore_path=$(find_pg_tool "$restore_name" pg_restore)
cat "$archive" | docker exec -i --env-file "$credential_file" "$restore_name" \
  sh -c 'set -eu; tool=$1; archive=$(mktemp /tmp/hades-restore.XXXXXX); trap '\''rm -f "$archive"'\'' EXIT; cat > "$archive"; "$tool" --clean --if-exists --no-owner --no-acl --exit-on-error -h 127.0.0.1 -p 5432 -U hindsight -d hindsight "$archive"' \
  sh "$restore_path" >/dev/null

restored_psql=$(find_pg_tool "$restore_name" psql)
restored_marker=$(docker exec --env-file "$credential_file" "$restore_name" "$restored_psql" \
  -h 127.0.0.1 -p 5432 -U hindsight -d hindsight -Atqc \
  "SELECT marker FROM public.hades_backup_restore_probe WHERE marker='${marker}'")
[[ "$restored_marker" == "$marker" ]] || fail 'synthetic marker was not present after native restore'
curl -fsS --max-time 5 "http://127.0.0.1:${restore_port}/health" >/dev/null ||
  fail 'restored Hindsight service did not remain healthy'
verify_memory "$restore_port" restored
if docker exec "$model_name" test -s /tmp/mock-state/requests.jsonl; then
  docker exec "$model_name" cat /tmp/mock-state/requests.jsonl > "$model_requests"
  python3 - "$model_requests" "$extractor_model" <<'PY'
import json, sys
rows=[json.loads(line) for line in open(sys.argv[1], encoding="utf-8") if line.strip()]
assert rows and all(row.get("model") == sys.argv[2] for row in rows), rows
assert all(row.get("path", "").endswith(("/api/chat", "/v1/chat/completions")) for row in rows), rows
PY
else
  fail 'Hindsight never called the synthetic extraction model'
fi

printf '%s\n' 'PASS pinned Hindsight native backup and checksum validation'
printf '%s\n' 'PASS source database container and volume destroyed before restore'
printf '%s\n' 'PASS native pg_restore recovered the synthetic marker into a fresh volume'
printf '%s\n' 'PASS Hindsight canonical memory list and recall returned the synthetic fact before and after restore'
printf '%s\n' 'PASS restored Hindsight service health; disposable resources removed on exit'
