#!/usr/bin/env bash
set -Eeuo pipefail

# Start the real pinned application images together on an isolated Docker
# network. This is a component-composition check only: it publishes no host
# ports, uses synthetic state/secrets, and does not claim Hermes/WebUI
# end-to-end behavior or fresh-guest reconstruction.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
source "$repo_dir/config/versions.env"
command -v docker >/dev/null 2>&1 || { echo 'HOST-SENSITIVE: docker is required' >&2; exit 2; }
webui_tag=${HADES_OPEN_WEBUI_ARTIFACT_TAG:-hades-open-webui:0.11.1-hades-reconstructed}
webui_id=$(docker image inspect "$webui_tag" --format '{{.Id}}' 2>/dev/null || true)
[[ "$webui_id" =~ ^sha256:[0-9a-f]{64}$ ]] || {
  echo "HOST-SENSITIVE: local immutable Open WebUI artifact is missing: $webui_tag" >&2
  exit 2
}
webui_image="${webui_tag}@${webui_id}"

suffix=$$
network="hades-reconstruct-$suffix"
work=$(mktemp -d /tmp/hades-full-reconstruct.XXXXXX)
names=(
  "hades-recon-lldap-$suffix"
  "hades-recon-grocy-$suffix"
  "hades-recon-agent-$suffix"
  "hades-recon-hindsight-$suffix"
  "hades-recon-searx-$suffix"
  "hades-recon-webui-$suffix"
)
volumes=(
  "hades-recon-lldap-data-$suffix"
  "hades-recon-grocy-data-$suffix"
  "hades-recon-agent-data-$suffix"
)

cleanup() {
  for name in "${names[@]}"; do docker rm -f "$name" >/dev/null 2>&1 || true; done
  docker network rm "$network" >/dev/null 2>&1 || true
  for volume in "${volumes[@]}"; do docker volume rm "$volume" >/dev/null 2>&1 || true; done
  if [[ -d "$work/searx" ]]; then
    docker run --rm -v "$work/searx:/x" alpine:3.20 chown -R "$(id -u):$(id -g)" /x >/dev/null 2>&1 || true
  fi
  find "$work" -depth -mindepth 1 -delete 2>/dev/null || true
  rmdir "$work" 2>/dev/null || true
}
trap cleanup EXIT

docker network create "$network" >/dev/null
mkdir -p "$work/identity" "$work/webui" "$work/hindsight" "$work/searx"
for secret in jwt_secret key_seed admin_password; do
  printf 'synthetic-%s\n' "$secret" > "$work/identity/$secret"
  chmod 600 "$work/identity/$secret"
done

docker run -d --name "${names[0]}" --network "$network" \
  -e UID=1000 -e GID=1000 -e TZ=America/Chicago \
  -e LLDAP_LDAP_BASE_DN=dc=hades,dc=local -e LLDAP_LDAP_USER_DN=admin \
  -e LLDAP_LDAP_USER_EMAIL=admin@hades.local \
  -e LLDAP_JWT_SECRET_FILE=/run/secrets/jwt -e LLDAP_KEY_SEED_FILE=/run/secrets/seed \
  -e LLDAP_LDAP_USER_PASS_FILE=/run/secrets/pass \
  -v "$work/identity/jwt_secret:/run/secrets/jwt:ro" \
  -v "$work/identity/key_seed:/run/secrets/seed:ro" \
  -v "$work/identity/admin_password:/run/secrets/pass:ro" \
  -v "${volumes[0]}:/data" "$HADES_LLDAP_IMAGE" >/dev/null
docker run -d --name "${names[1]}" --network "$network" \
  -e PUID=1000 -e PGID=1000 -e TZ=America/Chicago \
  -v "${volumes[1]}:/config" "$HADES_GROCY_IMAGE" >/dev/null
docker run -d --name "${names[2]}" --network "$network" \
  --cap-drop ALL --cap-add SETUID --cap-add SETGID \
  --security-opt no-new-privileges:true --tmpfs /tmp --tmpfs /root \
  -v "${volumes[2]}:/a0/usr" "$HADES_AGENT_ZERO_IMAGE" >/dev/null
docker run -d --name "${names[3]}" --network "$network" \
  --add-host host.docker.internal:host-gateway \
  -e HINDSIGHT_API_HOST=0.0.0.0 -e HINDSIGHT_API_PORT=8888 \
  -e HINDSIGHT_API_ENABLE_OBSERVATIONS=true \
  -e HINDSIGHT_API_LLM_BASE_URL=http://host.docker.internal:18080 \
  -e HINDSIGHT_API_LLM_API_KEY=synthetic \
  -v "$work/hindsight:/home/hindsight/.pg0" "$HADES_HINDSIGHT_IMAGE" >/dev/null
docker run -d --name "${names[4]}" --network "$network" \
  -v "$work/searx:/etc/searxng" "$HADES_SEARXNG_IMAGE_RECORD" >/dev/null
docker run -d --name "${names[5]}" --network "$network" \
  --add-host host.docker.internal:host-gateway \
  -e ENABLE_SIGNUP=false -e WEBUI_AUTH=true \
  -e OPENAI_API_BASE_URLS=http://host.docker.internal:18642/v1 \
  -e OPENAI_API_KEYS=synthetic -v "$work/webui:/app/backend/data" \
  "$webui_image" >/dev/null

for name in "${names[@]}"; do
  for _ in $(seq 1 60); do
    [[ "$(docker inspect -f '{{.State.Status}}' "$name" 2>/dev/null || true)" == running ]] && break
    sleep 1
  done
  [[ "$(docker inspect -f '{{.State.Status}}' "$name" 2>/dev/null || true)" == running ]] || {
    echo "FAIL reconstructed image is not running: $name" >&2
    docker logs --tail 30 "$name" >&2 || true
    exit 1
  }
  printf 'PASS %s running\n' "$name"
done

probe() {
  local name=$1 port=$2 path=$3
  for _ in $(seq 1 90); do
    if docker run --rm --network "$network" alpine:3.20 \
      wget -q -T 5 -O /dev/null "http://${name}:${port}${path}"; then
      printf 'PASS internal health %s:%s%s\n' "$name" "$port" "$path"
      return
    fi
    sleep 1
  done
  echo "FAIL internal health $name:$port$path" >&2
  docker logs --tail 30 "$name" >&2 || true
  exit 1
}

probe "${names[0]}" 17170 /health
probe "${names[1]}" 80 /
probe "${names[3]}" 8888 /health
probe "${names[5]}" 8080 /health
printf 'PASS disposable actual-image reconstruction startup and health\n'
