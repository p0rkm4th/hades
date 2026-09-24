#!/usr/bin/env bash
set -Eeuo pipefail

# Real pinned Open WebUI private-chat persistence and user-boundary soak.
# Everything is disposable: the model is synthetic, the WebUI state is a
# temporary volume, and the only published port is a loopback test port.
name="hades-private-chat-soak-$$"
volume="hades-private-chat-soak-$$"
webui_port=${HADES_PRIVATE_CHAT_WEBUI_PORT:-18795}
model_port=${HADES_PRIVATE_CHAT_MODEL_PORT:-18796}
image=${HADES_PRIVATE_CHAT_WEBUI_IMAGE:-hades-open-webui:0.11.1-hades-reconstructed}
tmp=$(mktemp -d /tmp/hades-private-chat-soak.XXXXXX)
cleanup() {
  docker rm -f "$name" >/dev/null 2>&1 || true
  docker volume rm "$volume" >/dev/null 2>&1 || true
  kill "${backend_pid:-}" >/dev/null 2>&1 || true
  if [[ -d "$tmp" ]]; then
    find "$tmp" -depth -mindepth 1 -delete 2>/dev/null || true
    rmdir "$tmp" 2>/dev/null || true
  fi
}
trap cleanup EXIT

cat > "$tmp/backend.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, os, time

MODEL = "synthetic-private-model"

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path != "/v1/models":
            self.send_response(404); self.end_headers(); return
        body = json.dumps({"data": [{"id": MODEL, "object": "model", "owned_by": "synthetic"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length) or b"{}")
        if self.path != "/v1/chat/completions":
            self.send_response(404); self.end_headers(); return
        user_text = next((m.get("content", "") for m in request.get("messages", []) if m.get("role") == "user"), "")
        reply = "Alpha-private-fact-confirmed" if "Alpha" in user_text else "Beta-private-fact-confirmed"
        body = json.dumps({
            "id": "synthetic-completion", "object": "chat.completion", "created": int(time.time()),
            "model": MODEL, "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("HADES_PRIVATE_CHAT_MODEL_PORT", "18796"))), Handler).serve_forever()
PY
python3 "$tmp/backend.py" >/dev/null 2>&1 &
backend_pid=$!
docker volume create "$volume" >/dev/null
docker run -d --name "$name" -p "127.0.0.1:${webui_port}:8080" \
  --add-host host.docker.internal:host-gateway \
  -e ENABLE_SIGNUP=true -e ENABLE_LOGIN_FORM=true -e ENABLE_OLLAMA_API=false \
  -e RAG_EMBEDDING_ENGINE=ollama -v "$volume:/app/backend/data" \
  "$image" >/dev/null

for _ in $(seq 1 90); do
  curl -fsS "http://127.0.0.1:${webui_port}/health" >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS "http://127.0.0.1:${webui_port}/health" >/dev/null

signup() {
  curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/auths/signup" \
    -H 'Content-Type: application/json' \
    --data "{\"name\":\"$1\",\"email\":\"$2\",\"password\":\"Synthetic-Only-123!\"}"
}
alpha=$(signup Alpha alpha-private@example.invalid)
alpha_token=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$alpha")
beta=$(curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/auths/add" \
  -H "Authorization: Bearer $alpha_token" -H 'Content-Type: application/json' \
  --data '{"name":"Beta","email":"beta-private@example.invalid","password":"Synthetic-Only-123!","role":"user"}')
beta_token=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$beta")

curl -fsS -X POST "http://127.0.0.1:${webui_port}/openai/config/update" \
  -H "Authorization: Bearer $alpha_token" -H 'Content-Type: application/json' \
  --data "{\"ENABLE_OPENAI_API\":true,\"OPENAI_API_BASE_URLS\":[\"http://host.docker.internal:${model_port}/v1\"],\"OPENAI_API_KEYS\":[\"synthetic\"],\"OPENAI_API_CONFIGS\":{}}" >/dev/null

message_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
assistant_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
session_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
body=$(python3 -c 'import json,sys; mid,aid,sid=sys.argv[1:]; print(json.dumps({"model":"synthetic-private-model","messages":[{"id":mid,"role":"user","content":"Alpha private fact"}],"stream":False,"parent_id":None,"id":aid,"session_id":sid,"user_message":{"id":mid,"role":"user","content":"Alpha private fact"}}))' "$message_id" "$assistant_id" "$session_id")
result="$tmp/result"
status=$(curl -sS -o "$result" -w '%{http_code}' -X POST "http://127.0.0.1:${webui_port}/api/chat/completions" \
  -H "Authorization: Bearer $alpha_token" -H 'Content-Type: application/json' --data "$body")
[[ "$status" == 200 ]] || { cat "$result" >&2; echo "FAIL private chat completion status: $status" >&2; exit 1; }
chat_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("chat_id", ""))' < "$result")
[[ -n "$chat_id" ]] || { cat "$result" >&2; echo 'FAIL private chat did not return a chat ID' >&2; exit 1; }
printf 'PASS Alpha private chat completion created %s\n' "$chat_id"

chat=""
for _ in $(seq 1 60); do
  chat=$(curl -fsS "http://127.0.0.1:${webui_port}/api/v1/chats/${chat_id}" -H "Authorization: Bearer $alpha_token" 2>/dev/null || true)
  grep -q 'Alpha-private-fact-confirmed' <<<"$chat" && break
  sleep 1
done
grep -q 'Alpha-private-fact-confirmed' <<<"$chat" || { echo 'FAIL Alpha response was not persisted' >&2; exit 1; }
printf 'PASS Alpha private response persisted\n'

beta_status=$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:${webui_port}/api/v1/chats/${chat_id}" -H "Authorization: Bearer $beta_token")
[[ "$beta_status" == 401 || "$beta_status" == 403 ]] || { echo "FAIL Beta accessed Alpha chat with HTTP $beta_status" >&2; exit 1; }
printf 'PASS Beta cannot retrieve Alpha private chat\n'

docker restart "$name" >/dev/null
for _ in $(seq 1 90); do
  curl -fsS "http://127.0.0.1:${webui_port}/health" >/dev/null 2>&1 && break
  sleep 1
done
reloaded=$(curl -fsS "http://127.0.0.1:${webui_port}/api/v1/chats/${chat_id}" -H "Authorization: Bearer $alpha_token")
grep -q 'Alpha-private-fact-confirmed' <<<"$reloaded" || { echo 'FAIL Alpha private response did not survive restart' >&2; exit 1; }
printf 'PASS Alpha private response survives Open WebUI restart\n'
printf 'PASS disposable Open WebUI private-chat soak\n'
