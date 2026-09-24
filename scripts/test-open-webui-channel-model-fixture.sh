#!/usr/bin/env bash
set -euo pipefail
name=hades-channel-model-fixture
volume=hades-channel-model-fixture-data
port=${HADES_CHANNEL_MODEL_WEBUI_PORT:-18792}
backend_port=${HADES_CHANNEL_MODEL_BACKEND_PORT:-18793}
image=${HADES_CHANNEL_MODEL_WEBUI_IMAGE:-hades-open-webui:channel-stage-patched}
tmp=$(mktemp -d)
backend="$tmp/backend.py"
trap 'docker rm -f "$name" >/dev/null 2>&1 || true; docker volume rm "$volume" >/dev/null 2>&1 || true; kill "${backend_pid:-}" >/dev/null 2>&1 || true; rm -rf -- "$tmp"' EXIT
cat >"$backend" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, os, time
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args): pass
    def do_GET(self):
        if self.path.rstrip("/") != "/v1/models": self.send_response(404); self.end_headers(); return
        body=json.dumps({"data":[{"id":"synthetic-channel-model","object":"model","owned_by":"synthetic"}]}).encode()
        self.send_response(200); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length","0")))
        if self.path != "/v1/chat/completions": self.send_response(404); self.end_headers(); return
        chunks=[{"id":"synthetic","object":"chat.completion.chunk","created":int(time.time()),"model":"synthetic-channel-model","choices":[{"index":0,"delta":{"role":"assistant","content":"SYNTHETIC-CHANNEL-REPLY"},"finish_reason":None}]},{"id":"synthetic","object":"chat.completion.chunk","created":int(time.time()),"model":"synthetic-channel-model","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}]
        self.send_response(200); self.send_header("Content-Type","text/event-stream"); self.send_header("Cache-Control","no-cache"); self.end_headers()
        for chunk in chunks: self.wfile.write(("data: "+json.dumps(chunk)+chr(10)+chr(10)).encode()); self.wfile.flush()
        self.wfile.write(("data: [DONE]"+chr(10)+chr(10)).encode()); self.wfile.flush()
ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("HADES_CHANNEL_MODEL_BACKEND_PORT", "18793"))),Handler).serve_forever()
PY
docker rm -f "$name" >/dev/null 2>&1 || true
docker volume rm "$volume" >/dev/null 2>&1 || true
docker volume create "$volume" >/dev/null
HADES_CHANNEL_MODEL_BACKEND_PORT="$backend_port" python3 "$backend" >/dev/null 2>&1 &
backend_pid=$!
for attempt in $(seq 1 30); do
    curl -fsS "http://127.0.0.1:${backend_port}/v1/models" >/dev/null 2>&1 && break
    [[ "$attempt" == 30 ]] && { echo 'FAIL synthetic model backend did not become ready' >&2; exit 1; }
    sleep 1
done
docker run -d --name "$name" -p "127.0.0.1:${port}:8080" --add-host host.docker.internal:host-gateway -v "$volume":/app/backend/data -e ENABLE_SIGNUP=true -e ENABLE_CHANNELS=true -e USER_PERMISSIONS_FEATURES_CHANNELS=true -e ENABLE_LOGIN_FORM=true -e ENABLE_OLLAMA_API=false -e RAG_EMBEDDING_ENGINE=ollama "$image" >/dev/null
for attempt in $(seq 1 60); do
    curl -fsS "http://127.0.0.1:${port}/health" >/dev/null 2>&1 && break
    [[ "$attempt" == 60 ]] && { echo 'FAIL Open WebUI model fixture did not become healthy' >&2; exit 1; }
    sleep 1
done
signup=$(curl -fsS -X POST "http://127.0.0.1:${port}/api/v1/auths/signup" -H 'Content-Type: application/json' --data '{"name":"Alpha","email":"alpha@example.invalid","password":"Synthetic-Only-123!"}')
token=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$signup")
curl -fsS -X POST "http://127.0.0.1:${port}/openai/config/update" -H "Authorization: Bearer $token" -H 'Content-Type: application/json' --data "{\"ENABLE_OPENAI_API\":true,\"OPENAI_API_BASE_URLS\":[\"http://host.docker.internal:${backend_port}/v1\"],\"OPENAI_API_KEYS\":[\"synthetic\"],\"OPENAI_API_CONFIGS\":{}}" >/dev/null
models=$(curl -fsS "http://127.0.0.1:${port}/openai/models" -H "Authorization: Bearer $token")
python3 -c 'import json,sys; assert any(x["id"]=="synthetic-channel-model" for x in json.load(sys.stdin)["data"])' <<<"$models"
channel=$(curl -fsS -X POST "http://127.0.0.1:${port}/api/v1/channels/create" -H "Authorization: Bearer $token" -H 'Content-Type: application/json' --data '{"name":"model-dogfood","description":"","type":"standard","is_private":true,"access_grants":[]}')
channel_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$channel")
curl -fsS -X POST "http://127.0.0.1:${port}/api/v1/channels/${channel_id}/messages/post" -H "Authorization: Bearer $token" -H 'Content-Type: application/json' --data '{"content":"<@M:synthetic-channel-model|HADES> say hello","data":{},"meta":{}}' >/dev/null
for attempt in $(seq 1 30); do
    messages=$(curl -fsS "http://127.0.0.1:${port}/api/v1/channels/${channel_id}/messages" -H "Authorization: Bearer $token")
    root_id=$(python3 -c 'import json,sys; x=json.load(sys.stdin); print(x[0]["id"] if x else "")' <<<"$messages")
    thread=""
    if [[ -n "$root_id" ]]; then
        thread=$(curl -fsS "http://127.0.0.1:${port}/api/v1/channels/${channel_id}/messages/${root_id}/thread" -H "Authorization: Bearer $token")
    fi
    grep -q 'SYNTHETIC-CHANNEL-REPLY' <<<"$thread" && break
    [[ "$attempt" == 30 ]] && { echo 'FAIL channel model response was not persisted' >&2; exit 1; }
    sleep 1
done
echo 'PASS Channels model mention reaches the synthetic OpenAI backend'
echo 'PASS streamed model response is persisted in the channel timeline'
