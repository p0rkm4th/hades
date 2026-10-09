# Shared disposable auth-state runtime for Open WebUI candidate tests.
# Source this file, then call hades_candidate_runtime_start NETWORK SUFFIX.

hades_candidate_runtime_start() {
  local network=$1 suffix=$2
  source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/config/versions.env"
  HADES_CANDIDATE_VALKEY="hades-candidate-valkey-${suffix}"
  HADES_CANDIDATE_VALKEY_VOLUME="hades-candidate-valkey-${suffix}"
  docker volume create "$HADES_CANDIDATE_VALKEY_VOLUME" >/dev/null
  docker run -d --name "$HADES_CANDIDATE_VALKEY" --network "$network" --network-alias hades-valkey \
    -v "$HADES_CANDIDATE_VALKEY_VOLUME:/data" "$HADES_OPEN_WEBUI_VALKEY_IMAGE" \
    valkey-server --appendonly yes --appendfsync always >/dev/null
  for _ in $(seq 1 30); do
    if docker exec "$HADES_CANDIDATE_VALKEY" valkey-cli ping 2>/dev/null | rg -q PONG; then break; fi
    sleep 1
  done
  docker exec "$HADES_CANDIDATE_VALKEY" valkey-cli ping | rg -q PONG
  HADES_CANDIDATE_RUNTIME_ARGS=(
    --network "$network"
    --add-host host.docker.internal:host-gateway
    -e REDIS_URL=redis://hades-valkey:6379/0
    -e WEBSOCKET_MANAGER=redis
    -e WEBSOCKET_REDIS_URL=redis://hades-valkey:6379/1
  )
}

hades_candidate_runtime_cleanup() {
  docker rm -f "${HADES_CANDIDATE_VALKEY:-}" >/dev/null 2>&1 || true
  docker volume rm "${HADES_CANDIDATE_VALKEY_VOLUME:-}" >/dev/null 2>&1 || true
}
