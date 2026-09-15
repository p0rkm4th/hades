#!/usr/bin/env bash
set -euo pipefail

# Disposable authenticated acceptance for pinned Open WebUI Channels.
name=hades-channels-fixture
volume=hades-channels-fixture-data
port=${HADES_CHANNELS_WEBUI_PORT:-18769}
image=${HADES_CHANNELS_WEBUI_IMAGE:-hades-open-webui:channel-stage}

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
  "$image" >/dev/null

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

beta_signup=$(curl -fsS -X POST "http://127.0.0.1:${port}/api/v1/auths/add" \
  -H "Authorization: Bearer $token" \
  -H 'Content-Type: application/json' \
  --data '{"name":"Beta","email":"beta@example.invalid","password":"Synthetic-Only-456!","role":"user"}')
beta_token=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$beta_signup")
beta_user_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$beta_signup")

beta_admin_status=$(curl -sS -o /dev/null -w '%{http_code}' \
  "http://127.0.0.1:${port}/api/v1/auths/admin/config" \
  -H "Authorization: Bearer $beta_token")
if [[ "$beta_admin_status" != 401 && "$beta_admin_status" != 403 ]]; then
  echo "FAIL Beta received admin config access (HTTP ${beta_admin_status})" >&2
  exit 1
fi
beta_standard_status=$(curl -sS -o /dev/null -w '%{http_code}' -X POST \
  "http://127.0.0.1:${port}/api/v1/channels/create" \
  -H "Authorization: Bearer $beta_token" \
  -H 'Content-Type: application/json' \
  --data '{"name":"beta-must-not-create-standard","description":"","type":"standard","is_private":true,"access_grants":[]}')
if [[ "$beta_standard_status" != 401 && "$beta_standard_status" != 403 ]]; then
  echo "FAIL Beta created a standard channel (HTTP ${beta_standard_status})" >&2
  exit 1
fi

dogfood_channel=$(curl -fsS -X POST "http://127.0.0.1:${port}/api/v1/channels/create" \
  -H "Authorization: Bearer $token" \
  -H 'Content-Type: application/json' \
  --data "$(printf '{\"name\":\"household-dogfood\",\"description\":\"Synthetic membership\",\"type\":\"group\",\"is_private\":true,\"user_ids\":[\"%s\"]}' "$beta_user_id")")
dogfood_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$dogfood_channel")

initial_messages=$(curl -fsS "http://127.0.0.1:${port}/api/v1/channels/${dogfood_id}/messages" \
  -H "Authorization: Bearer $beta_token")
python3 -c 'import json,sys; assert json.load(sys.stdin) == []' <<<"$initial_messages"

if ! curl -fsS "http://127.0.0.1:${port}/api/v1/channels/${dogfood_id}" \
  -H "Authorization: Bearer $beta_token" >/dev/null; then
  echo "FAIL Beta cannot read the explicitly shared channel" >&2
  exit 1
fi
if ! curl -fsS -X POST "http://127.0.0.1:${port}/api/v1/channels/${dogfood_id}/messages/post" \
  -H "Authorization: Bearer $beta_token" \
  -H 'Content-Type: application/json' \
  --data '{"content":"Synthetic Beta shared household message","data":{},"meta":{}}' >/dev/null; then
  echo "FAIL Beta cannot post to the explicitly shared channel" >&2
  exit 1
fi
messages=$(curl -fsS "http://127.0.0.1:${port}/api/v1/channels/${dogfood_id}/messages" \
  -H "Authorization: Bearer $token")
python3 -c 'import json,sys; x=json.load(sys.stdin); assert any("Synthetic Beta shared household message" in m.get("content","") for m in x)' <<<"$messages"

docker restart "$name" >/dev/null
for attempt in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" == 60 ]]; then
    echo "FAIL Open WebUI fixture did not recover after restart" >&2
    exit 1
  fi
  sleep 1
done
reloaded_messages=$(curl -fsS "http://127.0.0.1:${port}/api/v1/channels/${dogfood_id}/messages" \
  -H "Authorization: Bearer $token")
python3 -c 'import json,sys; x=json.load(sys.stdin); assert any("Synthetic Beta shared household message" in m.get("content","") for m in x)' <<<"$reloaded_messages"

anonymous_status=$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:${port}/api/v1/channels/")
if [[ "$anonymous_status" != 401 && "$anonymous_status" != 403 ]]; then
  echo "FAIL anonymous Channels access returned HTTP ${anonymous_status}" >&2
  exit 1
fi

echo "PASS authenticated disposable Channels feature and private-channel creation"
echo "PASS newly created shared conversation has no inherited message history"
echo "PASS synthetic Beta membership, shared post, and Alpha read-back"
echo "PASS shared message remains available after disposable Open WebUI restart"
echo "PASS channel membership does not grant Beta admin authority (config/create denied)"
echo "PASS anonymous Channels access denied (HTTP ${anonymous_status})"
