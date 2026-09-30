#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Verify that changing an account to the non-verified `pending` role blocks an
# already-issued browser token at the authenticated chat boundary.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$repo_dir/config/versions.env"
image=${HADES_DISABLED_ROLE_TEST_IMAGE:-hades-open-webui:0.11.1-hades-reconstructed}
command -v docker >/dev/null 2>&1 || { echo 'FAIL Docker is required' >&2; exit 2; }
image_id=$(docker image inspect --format '{{.Id}}' "$image" 2>/dev/null) || {
  echo 'FAIL the pinned local HADES Open WebUI image is unavailable; refusing an implicit pull' >&2
  exit 2
}
container="hades-disabled-role-session-$$"
docker run --rm -d --name "$container" -p 127.0.0.1::8080 \
  -e ENABLE_SIGNUP=true -e ENABLE_LOGIN_FORM=true \
  -e ENABLE_OLLAMA_API=false -e RAG_EMBEDDING_ENGINE=ollama \
  "$image_id" >/dev/null
cleanup() {
  docker stop "$container" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM
port=$(docker port "$container" 8080/tcp | sed 's/.*://')
HADES_TEST_WEBUI_URL="http://127.0.0.1:$port" python3 - <<'PY'
import json
import os
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

base = os.environ["HADES_TEST_WEBUI_URL"]

def request(method, path, payload=None, token=None):
    headers = {"Accept": "application/json"}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(base + path, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=10) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")

for attempt in range(60):
    try:
        status, _ = request("GET", "/health")
        if status == 200:
            break
    except (OSError, TimeoutError):
        pass
    time.sleep(1)
else:
    raise SystemExit("FAIL disposable Open WebUI did not become healthy")

status, admin = request("POST", "/api/v1/auths/signup", {
    "name": "Synthetic Admin", "email": "admin-disabled-role@example.invalid",
    "password": "Synthetic-Only-123!",
})
if status != 200 or not isinstance(admin, dict) or not admin.get("token"):
    raise SystemExit(f"FAIL disposable admin signup (HTTP {status})")
admin_token = admin["token"]

status, account = request("POST", "/api/v1/auths/add", {
    "name": "Synthetic Disabled Account", "email": "disabled-role@example.invalid",
    "password": "Synthetic-Only-123!", "role": "user",
}, admin_token)
if status != 200 or not isinstance(account, dict) or not account.get("token"):
    raise SystemExit(f"FAIL disposable user creation (HTTP {status})")
account_token = account["token"]

status, users = request("GET", "/api/v1/users/", token=admin_token)
if status != 200:
    raise SystemExit(f"FAIL disposable user inventory (HTTP {status})")
if isinstance(users, dict):
    users = users.get("users", users.get("items", []))
subject = next((row.get("id") for row in users if row.get("email") == "disabled-role@example.invalid"), None)
if not subject:
    raise SystemExit("FAIL could not resolve synthetic user's stable Open WebUI ID")

status, _ = request("GET", "/api/v1/users/user/info", token=account_token)
if status != 200:
    raise SystemExit(f"FAIL enabled user could not use verified-user route (HTTP {status})")

status, _ = request("POST", f"/api/v1/users/{subject}/update", {"role": "pending"}, admin_token)
if status != 200:
    raise SystemExit(f"FAIL admin could not disable synthetic account by role (HTTP {status})")

# Reuse the token minted while the account was enabled. Both a normal verified
# route and the OpenAI-compatible chat endpoint must reject it before model or
# HADES tool execution.
for path, payload in (
    ("/api/v1/users/user/info", None),
    ("/openai/chat/completions", {"model": "synthetic-unavailable", "messages": [{"role": "user", "content": "run a HADES tool"}]}),
):
    status, _ = request("POST" if payload else "GET", path, payload, account_token)
    if status != 401:
        raise SystemExit(f"FAIL disabled account's existing token was accepted at {path} (HTTP {status})")

print("PASS existing authenticated token is rejected after its UI role becomes pending")
print("PASS Open WebUI chat-completion boundary returns HTTP 401 before the completion handler")
PY
cleanup
trap - EXIT INT TERM
for _ in $(seq 1 50); do
  docker inspect "$container" >/dev/null 2>&1 || break
  sleep 0.1
done
if docker inspect "$container" >/dev/null 2>&1; then
  echo 'FAIL disposable Open WebUI container remains after cleanup' >&2
  exit 1
fi
