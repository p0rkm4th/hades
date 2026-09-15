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
echo 'PASS disposable pinned Hindsight API starts on 8888'
echo 'PASS disposable pinned Hindsight control plane initializes without collision'
