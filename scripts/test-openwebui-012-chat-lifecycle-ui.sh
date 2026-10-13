#!/usr/bin/env bash
set -Eeuo pipefail

# Authenticated browser acceptance for the isolated Open WebUI 0.12 candidate.
# Uses synthetic identity/model data and destroys its volume, network and
# containers at exit. It never connects to the production application.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$repo_dir/scripts/open-webui-candidate-test-runtime.sh"

candidate_image=${HADES_OPEN_WEBUI_012_CANDIDATE_IMAGE:-sha256:358ccb2f35f9959638fe0a77ced1f37e6fb5a4927e71c372f49cd28fb7fbc3c2}
suffix="$$-${RANDOM}"
network="hades-openwebui-012-ui-${suffix}"
volume="hades-openwebui-012-ui-${suffix}"
webui="hades-openwebui-012-ui-${suffix}"
webui_port=${HADES_OPENWEBUI_012_UI_PORT:-18902}
model_port=${HADES_OPENWEBUI_012_MODEL_PORT:-18903}
work=$(mktemp -d /tmp/hades-openwebui-012-ui.XXXXXX)
model_pid=''

cleanup() {
  local status=$?
  hades_candidate_runtime_cleanup
  docker rm -f "$webui" >/dev/null 2>&1 || true
  docker volume rm "$volume" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
  [[ -z "$model_pid" ]] || kill "$model_pid" >/dev/null 2>&1 || true
  rm -rf "$work"
  exit "$status"
}
trap cleanup EXIT

docker network create "$network" >/dev/null
docker volume create "$volume" >/dev/null
hades_candidate_runtime_start "$network" "openwebui-012-ui-${suffix}"

cat > "$work/model.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import time

MODEL = "synthetic-ui"

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path.rstrip("/") != "/v1/models":
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps({"data": [{"id": MODEL, "object": "model"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if self.path != "/v1/chat/completions":
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        chunks = [
            {"id": "synthetic", "object": "chat.completion.chunk", "created": int(time.time()),
             "model": MODEL, "choices": [{"index": 0, "delta": {"role": "assistant", "content": "Candidate UI reply."}, "finish_reason": None}]},
            {"id": "synthetic", "object": "chat.completion.chunk", "created": int(time.time()),
             "model": MODEL, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
        ]
        for chunk in chunks:
            self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

ThreadingHTTPServer(("0.0.0.0", int(os.environ["MODEL_PORT"])), Handler).serve_forever()
PY
MODEL_PORT="$model_port" python3 "$work/model.py" >/dev/null 2>&1 & model_pid=$!

docker run -d --name "$webui" -p "127.0.0.1:${webui_port}:8080" \
  "${HADES_CANDIDATE_RUNTIME_ARGS[@]}" \
  -v "$volume:/app/backend/data" \
  -e ENABLE_SIGNUP=true -e ENABLE_LOGIN_FORM=true -e ENABLE_OLLAMA_API=false \
  -e RAG_EMBEDDING_ENGINE=ollama "$candidate_image" >/dev/null

for _ in $(seq 1 90); do
  curl -fsS "http://127.0.0.1:${webui_port}/health" >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS "http://127.0.0.1:${webui_port}/health" >/dev/null

python3 - "$webui_port" "$model_port" "$work/credentials.json" <<'PY'
import json
import sys
import urllib.request

port, model_port, output = sys.argv[1:]
base = f"http://127.0.0.1:{port}"
email = "ui@example.invalid"
password = "Synthetic-Only-123!"
request = urllib.request.Request(
    base + "/api/v1/auths/signup",
    data=json.dumps({"name": "Synthetic UI", "email": email, "password": password}).encode(),
    headers={"Content-Type": "application/json"}, method="POST",
)
with urllib.request.urlopen(request) as response:
    auth = json.load(response)
request = urllib.request.Request(
    base + "/openai/config/update",
    data=json.dumps({
        "ENABLE_OPENAI_API": True,
        "OPENAI_API_BASE_URLS": [f"http://host.docker.internal:{model_port}/v1"],
        "OPENAI_API_KEYS": ["synthetic-only"],
        "OPENAI_API_CONFIGS": {},
    }).encode(),
    headers={"Authorization": "Bearer " + auth["token"], "Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request) as response:
    response.read()
with open(output, "w", encoding="utf-8") as handle:
    json.dump({"email": email, "password": password}, handle)
PY

BASE="http://127.0.0.1:${webui_port}" \
CREDENTIALS_FILE="$work/credentials.json" \
HADES_PLAYWRIGHT_MODULE="${HADES_PLAYWRIGHT_MODULE:-$HOME/.local/share/hades-playwright/node_modules/playwright}" \
node <<'JS'
const fs = require('node:fs');
const playwright = require(process.env.HADES_PLAYWRIGHT_MODULE);

(async () => {
  const credentials = JSON.parse(fs.readFileSync(process.env.CREDENTIALS_FILE, 'utf8'));
  const browser = await playwright.chromium.launch({headless: true});
  const context = await browser.newContext({viewport: {width: 1600, height: 1000}});
  const page = await context.newPage();
  const responses = [];
  page.on('response', response => {
    if (/\/api\/(chat|v1\/chats)/.test(response.url())) {
      responses.push({status: response.status(), method: response.request().method(), path: new URL(response.url()).pathname});
    }
  });

  try {
    await page.goto(process.env.BASE);
    await page.waitForSelector('#email', {timeout: 30000});
    await page.locator('#email').fill(credentials.email);
    await page.locator('#password').fill(credentials.password);
    await page.getByRole('button', {name: /sign in/i}).click();
    await page.waitForSelector('#chat-input', {timeout: 30000});
    const whatsNew = page.getByRole('button', {name: /okay, let.s go/i});
    if (await whatsNew.count()) await whatsNew.click();

    async function send(prompt, expectedResponses) {
      const previous = responses.filter(item => item.path === '/api/chat/completions').length;
      await page.locator('#chat-input').fill(prompt);
      await page.locator('#send-message-button').click();
      await page.waitForFunction(count => document.querySelectorAll('#response-content-container .markdown-prose').length >= count, expectedResponses, {timeout: 20000});
      await page.waitForFunction(() => !document.querySelector('#message-input-container button[aria-label="Stop"]'), null, {timeout: 20000}).catch(() => {});
      if (responses.filter(item => item.path === '/api/chat/completions').length <= previous) throw new Error(`no completion request for ${prompt}`);
    }

    await send('first synthetic UI turn', 1);
    await send('second synthetic UI turn', 2);
    const originalUrl = page.url();
    await page.reload();
    await page.waitForSelector('#chat-input', {timeout: 30000});
    await page.waitForFunction(() => document.querySelectorAll('#response-content-container .markdown-prose').length >= 2, null, {timeout: 15000});
    if (page.url() !== originalUrl) throw new Error('chat route changed after reload');

    await page.locator('button[aria-label="Edit"]').first().click({force: true});
    const edit = page.locator('textarea[id^="message-edit-"]');
    await edit.waitFor({timeout: 10000});
    await edit.fill('edited first synthetic UI turn');
    const editResponse = page.waitForResponse(response => response.url().endsWith('/api/chat/completions') && response.status() === 200, {timeout: 20000});
    await page.locator('#confirm-edit-message-button').click();
    await editResponse;
    await page.waitForFunction(() => document.body.innerText.includes('edited first synthetic UI turn'));

    const previousRegenerate = responses.filter(item => item.path === '/api/chat/completions').length;
    await page.locator('button[aria-label="Regenerate"]').last().evaluate(element => element.click());
    const regenerateResponse = page.waitForResponse(response => response.url().endsWith('/api/chat/completions') && response.status() === 200, {timeout: 20000});
    await page.getByRole('button', {name: 'Try Again', exact: true}).click({force: true});
    await regenerateResponse;
    await page.waitForFunction(count => document.querySelectorAll('#response-content-container .markdown-prose').length >= count, 1, {timeout: 20000});
    await page.waitForFunction(() => !document.querySelector('#message-input-container button[aria-label="Stop"]'), null, {timeout: 20000}).catch(() => {});
    if (responses.filter(item => item.path === '/api/chat/completions').length <= previousRegenerate) throw new Error('Try Again did not issue a new completion');

    const forkResponse = page.waitForResponse(response => /\/api\/v1\/chats\/[^/]+\/fork$/.test(new URL(response.url()).pathname), {timeout: 15000});
    await page.locator('button[aria-label="Fork chat"]').first().evaluate(element => element.click());
    const forked = await forkResponse;
    if (!forked.ok()) throw new Error(`fork failed: ${forked.status()}`);
    await page.waitForFunction(() => /\/c\/[0-9a-f-]+$/.test(location.pathname), null, {timeout: 10000});

    await page.locator('#new-chat-button').evaluate(element => element.click());
    await page.waitForFunction(() => location.pathname === '/', null, {timeout: 10000});
    await page.waitForSelector('#chat-input', {timeout: 15000});
    if (await page.locator('#response-content-container .markdown-prose').count()) throw new Error('new chat inherited prior conversation messages');

    for (let turn = 1; turn <= 8; turn++) await send(`long synthetic thread turn ${turn}`, turn);
    const threadId = new URL(page.url()).pathname.split('/').pop();
    const deleteResponse = page.waitForResponse(response => response.request().method() === 'DELETE' && new URL(response.url()).pathname.endsWith(`/chats/${threadId}`), {timeout: 15000});
    await page.locator('button[aria-label="Chat actions"]').last().click({force: true});
    await page.locator('#delete-chat-button').last().evaluate(element => element.click());
    const dialog = page.locator('[role="dialog"]');
    await dialog.waitFor({timeout: 10000});
    await dialog.getByRole('button', {name: /confirm/i}).last().evaluate(element => element.click());
    const deleted = await deleteResponse;
    if (!deleted.ok()) throw new Error(`delete failed: ${deleted.status()}`);
    await page.waitForFunction(() => location.pathname === '/', null, {timeout: 10000});
    await page.reload();
    await page.waitForSelector('#chat-input', {timeout: 15000});
    const finalState = await page.evaluate(() => ({
      url: location.pathname,
      dialogCount: document.querySelectorAll('[role="dialog"]').length,
      rows: [...document.querySelectorAll('a[href*="/c/"]')].map(element => element.innerText),
    }));
    if (finalState.dialogCount || finalState.rows.some(row => row.includes('long synthetic thread'))) throw new Error('deleted synthetic chat remains visible');

    const forkPath = new URL(forked.url()).pathname;
    if (!forkPath.endsWith('/fork')) throw new Error(`unexpected fork endpoint: ${forkPath}`);
    console.log(JSON.stringify({status: 'PASS', browser: 'Open WebUI 0.12.0 candidate', turns: 10, edited: true, regenerated: true, forked: true, reloaded: true, newChat: true, longThreadResponses: 8, deleted: true}));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(`FAIL ${error.stack || error}`); process.exit(1); });
JS
