#!/usr/bin/env bash
set -Eeuo pipefail

image=${1:?usage: test-open-webui-stream-progress-preface.sh IMMUTABLE_IMAGE}
version=$(docker image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.version"}}')
[[ "$version" == "0.11.4" ]] || { echo "FAIL expected Open WebUI 0.11.4, got ${version:-unknown}" >&2; exit 2; }
command -v node >/dev/null
playwright_module=${HADES_PLAYWRIGHT_MODULE:-${HOME}/.local/share/hades-playwright/node_modules/playwright}
[[ -d "$playwright_module" ]] || { echo "FAIL Playwright module unavailable" >&2; exit 2; }

suffix=$$
name="hades-stream-preface-$suffix"
volume="hades-stream-preface-$suffix"
webui_port=${HADES_STREAM_PREFACE_WEBUI_PORT:-18895}
model_port=${HADES_STREAM_PREFACE_MODEL_PORT:-18896}
tmp=$(mktemp -d /tmp/hades-stream-preface.XXXXXX)
chmod 700 "$tmp"
cleanup() {
  docker rm -f "$name" >/dev/null 2>&1 || true
  docker volume rm "$volume" >/dev/null 2>&1 || true
  kill "${backend_pid:-}" >/dev/null 2>&1 || true
  find "$tmp" -depth -mindepth 1 -delete 2>/dev/null || true
  rmdir "$tmp" 2>/dev/null || true
}
trap cleanup EXIT

cat > "$tmp/backend.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, os, time
MODEL = 'synthetic-stream-model'
PREFACE = 'I’ll inspect the code, make the requested change, and verify it before reporting back.'
ANSWER = 'The test fails because rectangle_area adds width and height. It should multiply them.'
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args): pass
    def do_GET(self):
        if self.path.rstrip('/') != '/v1/models':
            self.send_response(404); self.end_headers(); return
        body=json.dumps({'data':[{'id':MODEL,'object':'model','owned_by':'synthetic'}]}).encode()
        self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        req=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}')
        if self.path.rstrip('/') != '/v1/chat/completions':
            self.send_response(404); self.end_headers(); return
        self.send_response(200)
        self.send_header('Content-Type','text/event-stream' if req.get('stream') else 'application/json')
        self.send_header('Cache-Control','no-cache'); self.send_header('Connection','close'); self.end_headers()
        if req.get('stream'):
            # This mirrors Hermes' custom tool event. Open WebUI should ignore it.
            self.wfile.write(b'event: hermes.tool.progress\ndata: {"tool":"read_file","status":"running"}\n\n'); self.wfile.flush(); time.sleep(.5)
            for text in (PREFACE+'\n\n', ANSWER):
                frame={'id':'synthetic-stream','object':'chat.completion.chunk','created':int(time.time()),'model':MODEL,'choices':[{'index':0,'delta':{'content':text},'finish_reason':None}]}
                self.wfile.write(('data: '+json.dumps(frame,ensure_ascii=False)+'\n\n').encode()); self.wfile.flush(); time.sleep(1)
            self.wfile.write(b'data: {"id":"synthetic-stream","object":"chat.completion.chunk","created":0,"model":"synthetic-stream-model","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'); self.wfile.flush()
        else:
            body=json.dumps({'id':'synthetic-stream','object':'chat.completion','created':int(time.time()),'model':MODEL,'choices':[{'index':0,'message':{'role':'assistant','content':ANSWER},'finish_reason':'stop'}]}).encode()
            self.wfile.write(body)
ThreadingHTTPServer(('0.0.0.0',int(os.environ['MODEL_PORT'])),Handler).serve_forever()
PY

cat > "$tmp/browser.cjs" <<'JS'
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE);
const base = process.env.WEBUI_URL;
const model = 'synthetic-stream-model';
const password = 'Synthetic-Only-123!';
async function api(path, token, body) {
  const response = await fetch(`${base}${path}`, {
    method: body ? 'POST' : 'GET',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(body ? {'content-type':'application/json'} : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await response.text();
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return text ? JSON.parse(text) : null;
}
async function main() {
  const user = await api('/api/v1/auths/signup', null, {name:'Synthetic Stream Owner',email:'stream-owner@example.invalid',password});
  const token = user.token;
  await api('/openai/config/update', token, {
    ENABLE_OPENAI_API:true,
    OPENAI_API_BASE_URLS:[`http://host.docker.internal:${process.env.MODEL_PORT}/v1`],
    OPENAI_API_KEYS:['synthetic-only'], OPENAI_API_CONFIGS:{},
  });
  const tasks = await api('/api/v1/tasks/config', token);
  for (const key of ['ENABLE_TITLE_GENERATION','ENABLE_FOLLOW_UP_GENERATION','ENABLE_TAGS_GENERATION']) tasks[key] = false;
  await api('/api/v1/tasks/config/update', token, tasks);
  let models;
  for (let n=0;n<20;n++) {
    models = await api('/api/models', token);
    if (models.data?.some(row=>row.id===model)) break;
    await new Promise(resolve=>setTimeout(resolve,250));
  }
  if (!models.data?.some(row=>row.id===model)) throw new Error('synthetic OpenAI model was not discovered');

  const browser = await chromium.launch({headless:true});
  try {
    const context = await browser.newContext({viewport:{width:1365,height:850}});
    await context.addCookies([{name:'token',value:token,url:`${base}/`}]);
    const page = await context.newPage();
    await page.goto(base,{waitUntil:'domcontentloaded',timeout:30000});
    await page.waitForSelector('#chat-input',{timeout:30000});
    const welcome=page.getByRole('button',{name:/okay,\s*let.s go/i});
    if (await welcome.count()) await welcome.first().click({force:true});
    const selector=page.getByRole('button',{name:/select a model/i});
    if (await selector.count()) {
      await selector.first().click();
      await page.getByText(model,{exact:true}).last().waitFor({state:'visible',timeout:15000});
      await page.getByText(model,{exact:true}).last().click();
    }
    const input=page.locator('#chat-input');
    await input.fill('Fix this failing test.');
    const sent=Date.now(); await input.press('Enter');
    await page.waitForFunction((text)=>document.querySelector('#response-content-container')?.innerText.includes(text),
      'I’ll inspect the code, make the requested change, and verify it before reporting back.',{timeout:15000});
    const preface_ms=Date.now()-sent;
    const at_preface=await page.locator('#response-content-container').innerText();
    if (at_preface.includes('The test fails because')) throw new Error('final answer arrived before progress preface was observed');
    await page.waitForFunction(()=>document.querySelector('#response-content-container')?.innerText.includes('It should multiply them.'),null,{timeout:30000});
    const chat_id=page.url().match(/\/c\/([^/?#]+)/)?.[1];
    if (!chat_id) throw new Error('chat URL did not contain a persistent chat ID');
    let persisted;
    for (let n=0;n<20;n++) {
      persisted=await api(`/api/v1/chats/${chat_id}`,token);
      const dump=JSON.stringify(persisted);
      if (dump.includes('I’ll inspect the code') && dump.includes('It should multiply them.')) break;
      await new Promise(resolve=>setTimeout(resolve,300));
    }
    const saved=JSON.stringify(persisted);
    if (!saved.includes('I’ll inspect the code') || !saved.includes('It should multiply them.')) throw new Error('assistant stream was not persisted completely');
    await page.reload({waitUntil:'domcontentloaded',timeout:30000});
    await page.waitForFunction(()=>document.querySelector('#response-content-container')?.innerText.includes('It should multiply them.'),null,{timeout:30000});
    const rendered=(await page.locator('#response-content-container').innerText()).trim();
    if (!rendered.includes('I’ll inspect the code') || !rendered.includes('It should multiply them.')) throw new Error('preface or answer missing after reload');
    if (/hermes\.tool\.progress|read_file/.test(rendered)) throw new Error('internal tool event leaked into chat text');
    console.log(JSON.stringify({version:await (await fetch(`${base}/api/version`)).json(),preface_visible_ms:preface_ms,preface_visible_before_final:true,assistant_stream_persisted:true,reload_rendered_both:true,tool_event_text_leaked:false}));
  } finally { await browser.close(); }
}
main().catch(error=>{console.error(error.stack||error);process.exit(1);});
JS

MODEL_PORT="$model_port" python3 "$tmp/backend.py" >"$tmp/backend.log" 2>&1 &
backend_pid=$!
for _ in $(seq 1 30); do curl -fsS "http://127.0.0.1:${model_port}/v1/models" >/dev/null 2>&1 && break; sleep 0.2; done
curl -fsS "http://127.0.0.1:${model_port}/v1/models" >/dev/null
docker volume create "$volume" >/dev/null
docker run -d --name "$name" -p "127.0.0.1:${webui_port}:8080" \
  --add-host host.docker.internal:host-gateway \
  -e ENABLE_SIGNUP=true -e ENABLE_LOGIN_FORM=true -e ENABLE_OLLAMA_API=false \
  -e WEBUI_SECRET_KEY=synthetic-stream-preface-key -e RAG_EMBEDDING_ENGINE=ollama \
  -v "$volume:/app/backend/data" "$image" >/dev/null
for _ in $(seq 1 120); do curl -fsS "http://127.0.0.1:${webui_port}/health" >/dev/null 2>&1 && break; sleep 1; done
curl -fsS "http://127.0.0.1:${webui_port}/health" >/dev/null
WEBUI_URL="http://127.0.0.1:${webui_port}" MODEL_PORT="$model_port" \
  HADES_PLAYWRIGHT_MODULE="$playwright_module" node "$tmp/browser.cjs"
echo "PASS Open WebUI 0.11.4 renders and persists the workspace progress preface"
