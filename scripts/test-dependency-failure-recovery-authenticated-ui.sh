#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Synthetic authenticated browser proof: a failed chat request is reported,
# then a new chat recovers through a deterministic local OpenAI-compatible model.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
suffix="$$"
webui_name="hades-failure-ui-webui-$suffix"
webui_volume="hades-failure-ui-data-$suffix"
work=$(mktemp -d "${TMPDIR:-/tmp}/hades-failure-ui.XXXXXX")
webui_port=${HADES_FAILURE_UI_WEBUI_PORT:-}
model_port=${HADES_FAILURE_UI_MODEL_PORT:-}
image=${HADES_HINDSIGHT_UI_WEBUI_IMAGE:-hades-open-webui:0.11.1-hades-reconstructed}
model_pid=''
step='preflight'

cleanup() {
  local status=$?
  trap - EXIT
  if ((status != 0)); then
    echo "FAIL dependency failure/recovery UI at step '$step'" >&2
    [[ -z "$webui_name" ]] || docker logs "$webui_name" 2>&1 | tail -n 40 >&2 || true
    [[ ! -f "$work/model.log" ]] || tail -n 30 "$work/model.log" >&2 || true
  fi
  [[ -z "$model_pid" ]] || { kill "$model_pid" >/dev/null 2>&1 || true; wait "$model_pid" >/dev/null 2>&1 || true; }
  docker rm -f "$webui_name" >/dev/null 2>&1 || true
  docker volume rm "$webui_volume" >/dev/null 2>&1 || true
  find "$work" -depth -mindepth 1 -delete 2>/dev/null || true
  rmdir "$work" 2>/dev/null || true
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

for binary in docker node curl python3; do command -v "$binary" >/dev/null; done
export HADES_PLAYWRIGHT_MODULE=${HADES_PLAYWRIGHT_MODULE:-playwright}; node -e 'require(process.env.HADES_PLAYWRIGHT_MODULE)' >/dev/null 2>&1 || { echo 'FAIL local Playwright dependency unavailable' >&2; exit 2; }
[[ -f "$repo_dir/scripts/dom-dependency-failure.js" ]] || { echo 'FAIL browser acceptance script missing' >&2; exit 2; }
docker image inspect "$image" >/dev/null
free_port() {
  python3 - <<'PY'
import socket
s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()
PY
}
[[ -n "$webui_port" ]] || webui_port=$(free_port)
[[ -n "$model_port" ]] || model_port=$(free_port)
for port in "$webui_port" "$model_port"; do
  if (echo >/dev/tcp/127.0.0.1/"$port") >/dev/null 2>&1; then echo "FAIL occupied test port: $port" >&2; exit 2; fi
done
chmod 700 "$work"

cat >"$work/model.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, os, time
MODEL = "synthetic-recovery-model"
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args): pass
    def do_GET(self):
        print("GET", self.path, flush=True)
        if self.path.rstrip("/") != "/v1/models": self.send_response(404); self.end_headers(); return
        body=json.dumps({"data":[{"id":MODEL,"object":"model","owned_by":"synthetic"}]}).encode()
        self.send_response(200); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        print("POST", self.path, flush=True)
        self.rfile.read(int(self.headers.get("Content-Length","0")))
        if self.path != "/v1/chat/completions": self.send_response(404); self.end_headers(); return
        now=int(time.time())
        chunks=[
          {"id":"synthetic-recovery","object":"chat.completion.chunk","created":now,"model":MODEL,"choices":[{"index":0,"delta":{"role":"assistant","content":"Synthetic recovery succeeded."},"finish_reason":None}]},
          {"id":"synthetic-recovery","object":"chat.completion.chunk","created":now,"model":MODEL,"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]},
        ]
        self.send_response(200); self.send_header("Content-Type","text/event-stream"); self.send_header("Cache-Control","no-cache"); self.end_headers()
        for chunk in chunks: self.wfile.write(("data: "+json.dumps(chunk)+"\n\n").encode()); self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()
ThreadingHTTPServer(("0.0.0.0",int(os.environ["MODEL_PORT"])),Handler).serve_forever()
PY

step='starting deterministic local responder and disposable Open WebUI'
MODEL_PORT="$model_port" python3 "$work/model.py" >"$work/model.log" 2>&1 &
model_pid=$!
for _ in $(seq 1 40); do curl -fsS "http://127.0.0.1:${model_port}/v1/models" >/dev/null 2>&1 && break; sleep .25; done
curl -fsS "http://127.0.0.1:${model_port}/v1/models" >/dev/null
docker volume create "$webui_volume" >/dev/null
docker run -d --name "$webui_name" --add-host host.docker.internal:host-gateway \
  -p "127.0.0.1:${webui_port}:8080" -e ENABLE_SIGNUP=true -e ENABLE_LOGIN_FORM=true \
  -e ENABLE_OLLAMA_API=false -e RAG_EMBEDDING_ENGINE=ollama \
  -v "$webui_volume:/app/backend/data" "$image" >/dev/null
for _ in $(seq 1 120); do curl -fsS "http://127.0.0.1:${webui_port}/health" >/dev/null 2>&1 && break; sleep 1; done
curl -fsS "http://127.0.0.1:${webui_port}/health" >/dev/null

step='creating synthetic Alpha identity and configuring local responder'
signup=$(curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/auths/signup" \
  -H 'Content-Type: application/json' \
  --data '{"name":"Alpha","email":"alpha-failure@example.invalid","password":"Synthetic-Only-123!"}')
alpha_token=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$signup")
curl -fsS -X POST "http://127.0.0.1:${webui_port}/openai/config/update" \
  -H "Authorization: Bearer $alpha_token" -H 'Content-Type: application/json' \
  --data "{\"ENABLE_OPENAI_API\":true,\"OPENAI_API_BASE_URLS\":[\"http://host.docker.internal:${model_port}/v1\"],\"OPENAI_API_KEYS\":[\"synthetic-only\"],\"OPENAI_API_CONFIGS\":{}}" >/dev/null
models=$(curl -fsS "http://127.0.0.1:${webui_port}/openai/models" -H "Authorization: Bearer $alpha_token")
model_id=$(python3 -c 'import json,sys; print(next((x["id"] for x in json.load(sys.stdin)["data"] if x.get("id")=="synthetic-recovery-model"), ""))' <<<"$models")
[[ -n "$model_id" ]] || { echo 'FAIL synthetic local responder model is not visible to Alpha' >&2; exit 1; }

step='authenticated browser failure then recovery acceptance'
report="$work/acceptance.json"
HADES_DOM_BASE_URL="http://127.0.0.1:${webui_port}" \
  HADES_DOM_EMAIL=alpha-failure@example.invalid \
  HADES_DOM_PASSWORD='Synthetic-Only-123!' \
  HADES_DOM_MODEL_ID="$model_id" \
  HADES_DOM_PROMPT='synthetic dependency failure probe' \
  HADES_DOM_WAIT_MS=3000 HADES_DOM_ABORT_CHAT=1 \
  node "$repo_dir/scripts/dom-dependency-failure.js" | tee "$report"
install -m 600 "$report" "${HADES_FAILURE_UI_REPORT:-/tmp/hades-dependency-failure-ui-$$.json}"
echo 'PASS synthetic authenticated failure is visible and a fresh chat recovers through the local responder'
