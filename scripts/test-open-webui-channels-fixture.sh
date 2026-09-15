#!/usr/bin/env bash
set -euo pipefail

# Disposable authenticated acceptance for pinned Open WebUI Channels.
name=hades-channels-fixture
volume=hades-channels-fixture-data
port=18769

docker rm -f "$name" >/dev/null 2>&1 || true
docker volume rm "$volume" >/dev/null 2>&1 || true
docker volume create "$volume" >/dev/null
docker run -d --name "$name" \
  -p "127.0.0.1:${port}:8080" \
  -v "$volume":/app/backend/data \
  -e ENABLE_SIGNUP=true \
  -e ENABLE_CHANNELS=true \
  -e USER_PERMISSIONS_FEATURES_CHANNELS=true \
  -e ENABLE_LOGIN_FORM=true \
  hades-open-webui:channel-stage >/dev/null

cleanup() {
  docker rm -f "$name" >/dev/null 2>&1 || true
  docker volume rm "$volume" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for attempt in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" == 60 ]]; then
    echo "FAIL Open WebUI fixture did not become healthy" >&2
    exit 1
  fi
  sleep 1
done

signup=$(curl -fsS -X POST "http://127.0.0.1:${port}/api/v1/auths/signup" \
  -H 'Content-Type: application/json' \
  --data '{"name":"Alpha","email":"alpha@example.invalid","password":"Synthetic-Only-123!"}')
token=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$signup")

config=$(curl -fsS "http://127.0.0.1:${port}/api/v1/auths/admin/config" \
  -H "Authorization: Bearer $token")
python3 -c 'import json,sys; x=json.load(sys.stdin); assert x.get("ENABLE_CHANNELS") is True' <<<"$config"

channel=$(curl -fsS -X POST "http://127.0.0.1:${port}/api/v1/channels/create" \
  -H "Authorization: Bearer $token" \
  -H 'Content-Type: application/json' \
  --data '{"name":"household","description":"Synthetic household","type":"standard","is_private":true,"access_grants":[]}')
python3 -c 'import json,sys; x=json.load(sys.stdin); assert x.get("name")=="household" and x.get("is_private") is True' <<<"$channel"

anonymous_status=$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:${port}/api/v1/channels/")
if [[ "$anonymous_status" != 401 && "$anonymous_status" != 403 ]]; then
  echo "FAIL anonymous Channels access returned HTTP ${anonymous_status}" >&2
  exit 1
fi

echo "PASS authenticated disposable Channels feature and private-channel creation"
echo "PASS anonymous Channels access denied (HTTP ${anonymous_status})"
