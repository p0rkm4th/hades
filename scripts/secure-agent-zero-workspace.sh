#!/usr/bin/env bash
set -Eeuo pipefail

container=${1:-hades-agent-zero}
wait_seconds=${HADES_AGENT_ZERO_WORKSPACE_WAIT_SECONDS:-120}
[[ "$wait_seconds" =~ ^[0-9]+$ ]] || { echo 'FAIL invalid Agent Zero workspace wait interval' >&2; exit 2; }

ready=0
for ((i=0; i<=wait_seconds; i++)); do
  if docker exec "$container" test -f /a0/usr/.env >/dev/null 2>&1; then
    ready=1
    break
  fi
  (( i == wait_seconds )) || sleep 1
done
(( ready )) || { echo 'FAIL Agent Zero private workspace environment file was not created' >&2; exit 1; }

docker exec --user 0 "$container" chmod 600 /a0/usr/.env >/dev/null || {
  echo 'FAIL could not secure Agent Zero private workspace environment file' >&2
  exit 1
}
mode=$(docker exec --user 0 "$container" stat -c '%a' /a0/usr/.env 2>/dev/null || true)
[[ "$mode" == 600 ]] || { echo 'FAIL Agent Zero private workspace environment file is not mode 0600' >&2; exit 1; }
echo 'PASS Agent Zero private workspace environment file is mode 0600'
