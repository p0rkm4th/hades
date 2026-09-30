#!/usr/bin/env bash
set -euo pipefail
command -v docker >/dev/null 2>&1 || { echo 'FAIL docker is required for Hindsight runtime test' >&2; exit 1; }
source config/versions.env
docker image inspect "$HADES_HINDSIGHT_IMAGE" >/dev/null 2>&1 || { echo "FAIL pinned Hindsight image is not available locally: $HADES_HINDSIGHT_IMAGE" >&2; exit 1; }
name="hades-hindsight-runtime-${$}"
volume="hades-hindsight-runtime-data-${$}"
cleanup() { docker rm -f "$name" >/dev/null 2>&1 || true; docker volume rm "$volume" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker volume create "$volume" >/dev/null
docker run -d --name "$name" -p '127.0.0.1::8888' -p '127.0.0.1::9999' -v "$volume":/home/hindsight/.pg0 \
  -e HINDSIGHT_API_HOST=0.0.0.0 -e HINDSIGHT_API_PORT=8888 -e HINDSIGHT_API_ENABLE_OBSERVATIONS=true \
  -e HINDSIGHT_API_WORKER_ID="$name" \
  -e HINDSIGHT_API_LLM_BASE_URL=http://127.0.0.1:1 -e HINDSIGHT_API_LLM_API_KEY=synthetic "$HADES_HINDSIGHT_IMAGE" >/dev/null
api_port=$(docker inspect "$name" --format '{{(index (index .NetworkSettings.Ports "8888/tcp") 0).HostPort}}')
ready=0
for attempt in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${api_port}/health" >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
if [[ "$ready" != 1 ]]; then
  echo 'FAIL disposable Hindsight API did not become healthy' >&2
  docker logs "$name" 2>&1 | tail -40 >&2
  exit 1
fi
[[ "$(docker inspect "$name" --format '{{.State.Status}}')" == running ]] || {
  echo 'FAIL disposable Hindsight process is not running after API startup' >&2
  exit 1
}
if docker logs "$name" 2>&1 | grep -Eq 'EADDRINUSE|Failed to start server'; then
  echo 'FAIL disposable Hindsight reported an internal listener collision' >&2
  exit 1
fi
docker logs "$name" 2>&1 | grep -Fq 'Starting Control Plane' || {
  echo 'FAIL disposable Hindsight control plane did not initialize' >&2
  exit 1
}
docker logs "$name" 2>&1 | grep -Fq "Worker poller started (worker_id=$name)" || {
  echo 'FAIL disposable Hindsight worker did not start with its stable ID' >&2
  exit 1
}
bank="synthetic-worker-recovery-${$}"
curl -fsS --max-time 10 -X PUT "http://127.0.0.1:${api_port}/v1/default/banks/${bank}" \
  -H 'Content-Type: application/json' --data '{"name":"Synthetic worker recovery fixture"}' >/dev/null
memory_listing=$(curl -fsS --max-time 10 \
  "http://127.0.0.1:${api_port}/v1/default/banks/${bank}/memories/list?tags=hades-explicit-memory&tags_match=any&state=valid&limit=100")
python3 -c 'import json,sys; result=json.load(sys.stdin); assert isinstance(result.get("items"), list) and result.get("limit")==100 and result.get("offset")==0 and result.get("total")==0' \
  <<<"$memory_listing" || {
  echo 'FAIL pinned Hindsight memory-list endpoint or explicit-memory tag filter contract changed' >&2
  exit 1
}
psql=$(docker exec "$name" sh -lc 'find /home/hindsight/.pg0/installation -type f -name psql -print -quit')
[[ -n "$psql" ]] || { echo 'FAIL pinned Hindsight image has no PostgreSQL client for isolated recovery fixture' >&2; exit 1; }
matched=$(docker exec -e PGPASSWORD=hindsight "$name" "$psql" -h 127.0.0.1 -p 5432 -U hindsight -d hindsight -Atqc \
  "INSERT INTO async_operations (bank_id,operation_type,status,worker_id,task_payload) VALUES ('${bank}','retain','processing','${name}',NULL) RETURNING operation_id")
foreign=$(docker exec -e PGPASSWORD=hindsight "$name" "$psql" -h 127.0.0.1 -p 5432 -U hindsight -d hindsight -Atqc \
  "INSERT INTO async_operations (bank_id,operation_type,status,worker_id,task_payload) VALUES ('${bank}','retain','processing','synthetic-foreign-worker',NULL) RETURNING operation_id")
abandoned=$(docker exec -e PGPASSWORD=hindsight "$name" "$psql" -h 127.0.0.1 -p 5432 -U hindsight -d hindsight -Atqc \
  "INSERT INTO async_operations (bank_id,operation_type,status,worker_id,task_payload) VALUES ('${bank}','retain','processing','synthetic-previous-container-id',NULL) RETURNING operation_id")
[[ -n "$matched" && -n "$foreign" && -n "$abandoned" ]] || { echo 'FAIL could not seed synthetic processing rows' >&2; exit 1; }
docker restart "$name" >/dev/null
api_port=$(docker inspect "$name" --format '{{(index (index .NetworkSettings.Ports "8888/tcp") 0).HostPort}}')
ready=0
for attempt in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${api_port}/health" >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
if [[ "$ready" != 1 ]]; then
  echo 'FAIL pinned Hindsight API did not recover after synthetic worker restart' >&2
  docker logs "$name" 2>&1 | tail -40 >&2
  exit 1
fi
recovered=$(docker exec -e PGPASSWORD=hindsight "$name" "$psql" -h 127.0.0.1 -p 5432 -U hindsight -d hindsight -F ' ' -Atqc \
  "SELECT operation_id,status,COALESCE(worker_id,'-'),retry_count FROM async_operations WHERE operation_id IN ('${matched}','${foreign}','${abandoned}') ORDER BY operation_id")
printf '%s\n' "$recovered" | awk -v matched="$matched" -v foreign="$foreign" -v abandoned="$abandoned" '
  $1 == matched && $2 == "pending" && $3 == "-" && $4 == 1 {m=1}
  $1 == foreign && $2 == "processing" && $3 == "synthetic-foreign-worker" && $4 == 0 {f=1}
  $1 == abandoned && $2 == "processing" && $3 == "synthetic-previous-container-id" && $4 == 0 {o=1}
  END {if (!m || !f || !o) exit 1}' || {
  echo 'FAIL worker restart did not reclaim only its own synthetic processing row or altered another owner row' >&2
  printf '%s\n' "$recovered" >&2
  exit 1
}
echo 'PASS disposable pinned Hindsight API starts on 8888'
echo 'PASS disposable pinned Hindsight control plane initializes without collision'
echo 'PASS disposable pinned Hindsight worker starts with explicit stable ID'
echo 'PASS pinned Hindsight explicit-memory list endpoint and tagged response shape'
echo 'PASS stable worker restart reclaims its own processing row and preserves foreign/stale-ID rows'
