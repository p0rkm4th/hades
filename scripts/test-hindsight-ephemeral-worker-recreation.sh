#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$repo_dir/config/versions.env"
command -v docker >/dev/null 2>&1 || { echo 'FAIL docker is required' >&2; exit 2; }
command -v curl >/dev/null 2>&1 || { echo 'FAIL curl is required' >&2; exit 2; }
docker image inspect "$HADES_HINDSIGHT_IMAGE" >/dev/null 2>&1 || {
  echo 'FAIL pinned Hindsight image is not available locally' >&2
  exit 2
}

name="hades-hindsight-ephemeral-worker-$$"
volume="hades-hindsight-ephemeral-worker-data-$$"
bank="synthetic-ephemeral-worker-$$"
psql_bin=''
old_worker_id=''
new_worker_id=''
operation_id=''
cleanup() {
  docker rm -f "$name" >/dev/null 2>&1 || true
  docker volume rm "$volume" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker volume create "$volume" >/dev/null

start_worker() {
  local configured_id=${1:-}
  local -a worker_env=(
    -e HINDSIGHT_API_HOST=0.0.0.0
    -e HINDSIGHT_API_PORT=8888
    -e HINDSIGHT_API_ENABLE_OBSERVATIONS=true
    -e HINDSIGHT_API_LLM_BASE_URL=http://127.0.0.1:1
    -e HINDSIGHT_API_LLM_API_KEY=synthetic-only
  )
  if [[ -n "$configured_id" ]]; then
    worker_env+=(-e "HINDSIGHT_API_WORKER_ID=$configured_id")
  fi
  docker run -d --name "$name" \
    -p '127.0.0.1::8888' -p '127.0.0.1::9999' \
    -v "$volume:/home/hindsight/.pg0" "${worker_env[@]}" \
    "$HADES_HINDSIGHT_IMAGE" >/dev/null
  local api_port
  api_port=$(docker inspect "$name" --format '{{(index (index .NetworkSettings.Ports "8888/tcp") 0).HostPort}}')
  for _ in $(seq 1 60); do
    if curl -fsS --max-time 2 "http://127.0.0.1:${api_port}/health" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  curl -fsS --max-time 5 "http://127.0.0.1:${api_port}/health" >/dev/null || {
    echo 'FAIL disposable Hindsight did not become healthy' >&2
    exit 1
  }
  local expected_id=$configured_id
  if [[ -z "$expected_id" ]]; then
    expected_id=$(docker inspect "$name" --format '{{.Config.Hostname}}')
  fi
  local ready=0
  for _ in $(seq 1 30); do
    if docker logs "$name" 2>&1 | grep -Fq "Worker poller started (worker_id=$expected_id)"; then
      ready=1
      break
    fi
    sleep 1
  done
  [[ "$ready" == 1 ]] || {
    echo 'FAIL disposable Hindsight worker did not start with its expected identity' >&2
    exit 1
  }
  psql_bin=$(docker exec "$name" sh -lc 'find /home/hindsight/.pg0/installation -type f -name psql -print -quit')
  [[ -n "$psql_bin" ]] || { echo 'FAIL pinned Hindsight image has no psql client' >&2; exit 1; }
}

api_port_for_current() {
  docker inspect "$name" --format '{{(index (index .NetworkSettings.Ports "8888/tcp") 0).HostPort}}'
}

start_worker
old_worker_id=$(docker inspect "$name" --format '{{.Config.Hostname}}')
curl -fsS --max-time 10 -X PUT "http://127.0.0.1:$(api_port_for_current)/v1/default/banks/${bank}" \
  -H 'Content-Type: application/json' \
  --data '{"name":"Synthetic ephemeral worker recreation fixture"}' >/dev/null
operation_id=$(docker exec -e PGPASSWORD=hindsight "$name" "$psql_bin" \
  -h 127.0.0.1 -p 5432 -U hindsight -d hindsight -Atqc \
  "INSERT INTO async_operations (bank_id,operation_type,status,worker_id,task_payload) VALUES ('${bank}','retain','processing','${old_worker_id}',NULL) RETURNING operation_id")
[[ -n "$operation_id" ]] || { echo 'FAIL could not seed synthetic processing row' >&2; exit 1; }

# Simulate an unclean worker/container loss. A graceful stop releases owned
# work and would not exercise recovery by worker identity.
docker kill "$name" >/dev/null
docker rm "$name" >/dev/null
start_worker
new_worker_id=$(docker inspect "$name" --format '{{.Config.Hostname}}')
[[ "$old_worker_id" != "$new_worker_id" ]] || {
  echo 'FAIL removing and recreating the container unexpectedly preserved its default worker identity' >&2
  exit 1
}
readback=$(docker exec -e PGPASSWORD=hindsight "$name" "$psql_bin" \
  -h 127.0.0.1 -p 5432 -U hindsight -d hindsight -Atqc \
  "SELECT status || '|' || COALESCE(worker_id,'-') || '|' || retry_count FROM async_operations WHERE operation_id='${operation_id}'")
[[ "$readback" == "processing|${old_worker_id}|0" ]] || {
  echo 'FAIL recreated worker changed a synthetic row owned by the removed default ID' >&2
  echo "expected=processing|${old_worker_id}|0 actual=${readback} new_worker_id=${new_worker_id}" >&2
  exit 1
}

docker stop --time 60 "$name" >/dev/null
docker rm "$name" >/dev/null
start_worker "$old_worker_id"
readback=$(docker exec -e PGPASSWORD=hindsight "$name" "$psql_bin" \
  -h 127.0.0.1 -p 5432 -U hindsight -d hindsight -Atqc \
  "SELECT status || '|' || COALESCE(worker_id,'-') || '|' || retry_count FROM async_operations WHERE operation_id='${operation_id}'")
[[ "$readback" == 'pending|-|1' ]] || {
  echo 'FAIL explicitly restoring the original worker ID did not recover its own synthetic row' >&2
  exit 1
}

echo 'PASS disposable Hindsight container recreation changes the default worker identity'
echo 'PASS a processing row owned by the removed default identity remains untouched after recreation'
echo 'PASS restoring the original identity safely returns only its synthetic row to pending'
