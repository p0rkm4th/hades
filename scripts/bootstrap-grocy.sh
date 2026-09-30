#!/usr/bin/env bash
set -Eeuo pipefail

if ((EUID != 0)); then
  echo 'FAIL run Grocy bootstrap with sudo' >&2
  exit 2
fi
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$repo_dir/config/versions.env"
[[ -n "${HADES_GROCY_IMAGE:-}" ]] || { echo 'FAIL pinned Grocy image is missing' >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { echo 'FAIL Docker is missing; run prepare-hades-host.sh --apply first' >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo 'FAIL curl is missing; run prepare-hades-host.sh --apply first' >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo 'FAIL Docker is not ready for Grocy bootstrap' >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo 'FAIL Docker Compose is unavailable' >&2; exit 1; }

container_exists=0
if docker inspect hades-grocy >/dev/null 2>&1; then
  project=$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' hades-grocy)
  [[ "$project" == hades-grocy ]] || { echo 'FAIL container name hades-grocy is owned by another Compose project' >&2; exit 1; }
  image=$(docker inspect -f '{{.Config.Image}}' hades-grocy)
  [[ "$image" == "$HADES_GROCY_IMAGE" ]] || { echo 'FAIL existing Grocy container does not match the pinned image; inspect and back up before changing it' >&2; exit 1; }
  bindings=$(docker inspect -f '{{json .HostConfig.PortBindings}}' hades-grocy)
  python3 -c 'import json,sys; x=json.loads(sys.argv[1]); expected={"80/tcp":[{"HostIp":"127.0.0.1","HostPort":"7003"}]}; sys.exit(0 if x==expected else 1)' "$bindings" || {
    echo 'FAIL existing Grocy listener is not restricted to 127.0.0.1:7003' >&2
    exit 1
  }
  container_exists=1
elif curl --silent --connect-timeout 1 --max-time 2 --output /dev/null http://127.0.0.1:7003/; then
  echo 'FAIL loopback port 7003 is occupied by an unknown service' >&2
  exit 1
fi

if ! docker network inspect hades-grocy-net >/dev/null 2>&1; then
  docker network create hades-grocy-net >/dev/null
fi

docker compose \
  --env-file "$repo_dir/config/versions.env" \
  --file "$repo_dir/deploy/grocy.compose.yaml" \
  up --detach grocy

ready=0
for _ in $(seq 1 60); do
  if curl --silent --fail --connect-timeout 2 --max-time 5 --output /dev/null http://127.0.0.1:7003/; then
    ready=1
    break
  fi
  sleep 1
done
[[ "$ready" == 1 ]] || { echo 'FAIL Grocy did not become reachable on its loopback listener' >&2; exit 1; }

if ((container_exists)); then
  echo 'PASS existing pinned Grocy bootstrap service is ready; persistent state was retained'
else
  echo 'PASS pinned Grocy bootstrap service is ready on 127.0.0.1:7003'
fi
cat <<'EOF'
NEXT: open Grocy locally (or through an SSH tunnel), sign in with the upstream
first-run account, immediately change its password, then use Manage API keys to
issue the HADES adapter key. Save that issued key in the protected file named
by HADES_GROCY_API_KEY_FILE before running install-hades.sh. Random text is not
a valid Grocy API key. Grocy remains bound to loopback during this bootstrap.
EOF
