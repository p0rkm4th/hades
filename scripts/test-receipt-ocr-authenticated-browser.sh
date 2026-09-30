#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Disposable browser acceptance for owner-scoped receipt OCR. Both services
# behind Open WebUI are synthetic host fixtures; no production endpoint is used.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
suffix="$$"
webui_image=${HADES_RECEIPT_UI_IMAGE:-hades-open-webui:receipt-browser-$suffix}
remove_image=0
webui_name="hades-receipt-browser-$suffix"
webui_volume="hades-receipt-browser-$suffix"
work=$(mktemp -d "${TMPDIR:-/tmp}/hades-receipt-browser.XXXXXX")
webui_port=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')
fixture_pid=''
step='preflight'

cleanup() {
  local status=$?
  trap - EXIT
  if ((status != 0)); then
    echo "FAIL authenticated receipt browser at step '$step'" >&2
    docker logs --tail 45 "$webui_name" >&2 2>/dev/null || true
    [[ ! -f "$work/fixture.log" ]] || tail -n 20 "$work/fixture.log" >&2 || true
  fi
  if [[ -n "$fixture_pid" ]]; then kill "$fixture_pid" >/dev/null 2>&1 || true; wait "$fixture_pid" >/dev/null 2>&1 || true; fi
  docker rm -f "$webui_name" >/dev/null 2>&1 || true
  docker volume rm "$webui_volume" >/dev/null 2>&1 || true
  if ((remove_image)); then docker image rm "$webui_image" >/dev/null 2>&1 || true; fi
  find "$work" -depth -mindepth 1 -delete 2>/dev/null || true
  rmdir "$work" 2>/dev/null || true
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

for binary in docker curl python3 node; do command -v "$binary" >/dev/null; done
export HADES_PLAYWRIGHT_MODULE=${HADES_PLAYWRIGHT_MODULE:-playwright}; node -e 'require(process.env.HADES_PLAYWRIGHT_MODULE)' >/dev/null 2>&1 || { echo 'FAIL local Playwright dependency unavailable' >&2; exit 2; }
if [[ -z ${HADES_RECEIPT_UI_IMAGE:-} ]]; then
  step='building WebUI image from current HADES source'
  docker build -f "$repo_dir/webui/Dockerfile" -t "$webui_image" "$repo_dir"
  remove_image=1
else
  docker image inspect "$webui_image" >/dev/null
fi
docker_gateway=$(docker network inspect bridge --format '{{range .IPAM.Config}}{{.Gateway}}{{end}}' | head -n1)
[[ "$docker_gateway" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || { echo 'FAIL Docker bridge gateway unavailable' >&2; exit 2; }
chmod 700 "$work"
mkdir -m 700 "$work/ledger"
printf '%s\n' synthetic-receipt-grocy-key >"$work/grocy.key"
chmod 600 "$work/grocy.key"
if [[ -n ${HADES_RECEIPT_BROWSER_FIXTURE:-} ]]; then
  cp "$HADES_RECEIPT_BROWSER_FIXTURE" "$work/receipt.png"
else
  python3 - "$work/receipt.png" <<'PY'
import struct,sys,zlib
def chunk(kind,data):
    return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data)&0xffffffff)
png=(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',1,1,8,2,0,0,0))+
     chunk(b'IDAT',zlib.compress(b'\x00\xff\xff\xff'))+chunk(b'IEND',b''))
open(sys.argv[1],'wb').write(png)
PY
fi
[[ -s "$work/receipt.png" ]] || { echo 'FAIL synthetic receipt image unavailable' >&2; exit 2; }

step='starting synthetic OCR and Grocy fixture'
python3 - "$docker_gateway" "$work" <<'PY' >"$work/fixture.log" 2>&1 &
import json, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

bind, directory = sys.argv[1:]
root = Path(directory)
lock = threading.Lock()
state = {"stock": 0, "ocr_calls": 0, "grocy": []}
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *_): pass
    def send_json(self, code, value, session=None):
        payload = ("event: message\ndata: " + json.dumps(value) + "\n\n").encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(payload)))
        if session: self.send_header("Mcp-Session-Id", session)
        self.end_headers(); self.wfile.write(payload)
    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if self.path == "/mcp":
            value = json.loads(raw or b"{}")
            method = value.get("method")
            if method == "initialize":
                self.send_json(200, {"jsonrpc":"2.0","id":value.get("id"),"result":{"protocolVersion":"2025-06-18","capabilities":{},"serverInfo":{"name":"synthetic-ocr","version":"1"}}}, "synthetic-receipt-session")
            elif method == "notifications/initialized":
                self.send_response(202); self.send_header("Content-Length","0"); self.end_headers()
            elif method == "tools/call" and self.headers.get("Mcp-Session-Id") == "synthetic-receipt-session":
                args = value.get("params",{}).get("arguments",{})
                assert args.get("mime") == "image/png" and args.get("image_base64")
                with lock: state["ocr_calls"] += 1
                # PaddleOCR can return the right-column amount before the
                # product text. Preserve boxes so the route must reconstruct
                # visual rows instead of trusting OCR array order.
                result = {
                    "rec_texts":["Synthetic Market","4.29","Whole Milk","Total","4.29"],
                    "rec_scores":[0.99,0.99,0.99,0.99,0.99],
                    "rec_boxes":[[90,60,350,90],[500,120,570,150],[90,120,300,150],[90,180,200,210],[500,180,570,210]],
                }
                content = {"jsonrpc":"2.0","id":value.get("id"),"result":{"content":[{"type":"text","text":json.dumps(result)}]}}
                self.send_json(200, content)
            else:
                self.send_json(400,{"jsonrpc":"2.0","id":value.get("id"),"error":{"code":-32601,"message":"unsupported synthetic MCP request"}})
            return
        if self.path == "/api/stock/products/11/add":
            assert self.headers.get("GROCY-API-KEY") == "synthetic-receipt-grocy-key"
            body = json.loads(raw or b"{}")
            with lock:
                state["stock"] += float(body["amount"])
                state["grocy"].append({"method":"POST","path":self.path,"body":body})
            return self.write_json(200,{"ok":True})
        self.write_json(404,{"error":"unknown synthetic route"})
    def do_GET(self):
        if self.path == "/__state":
            with lock: snapshot=json.loads(json.dumps(state))
            return self.write_json(200,snapshot)
        if not self.path.startswith("/api/") or self.headers.get("GROCY-API-KEY") != "synthetic-receipt-grocy-key":
            return self.write_json(401,{"error":"unauthorized"})
        with lock: state["grocy"].append({"method":"GET","path":self.path})
        if self.path == "/api/objects/products": return self.write_json(200,[{"id":11,"name":"Whole Milk"}])
        if self.path == "/api/stock/products/11":
            with lock: amount=state["stock"]
            return self.write_json(200,{"product_id":11,"amount_aggregated":amount})
        self.write_json(404,{"error":"unknown synthetic route"})
    def write_json(self, code, value):
        payload=json.dumps(value).encode(); self.send_response(code)
        self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(payload)))
        self.end_headers(); self.wfile.write(payload)
server=ThreadingHTTPServer((bind,0),Handler)
(root/"fixture.port").write_text(str(server.server_port))
(root/"fixture.state").write_text(json.dumps(state))
server.serve_forever()
PY
fixture_pid=$!
for _ in $(seq 1 50); do [[ -s "$work/fixture.port" ]] && break; kill -0 "$fixture_pid" 2>/dev/null || { cat "$work/fixture.log" >&2; exit 1; }; sleep .1; done
[[ -s "$work/fixture.port" ]] || { echo 'FAIL synthetic OCR/Grocy fixture did not bind' >&2; exit 1; }
fixture_url="http://host.docker.internal:$(cat "$work/fixture.port")"

start_webui() {
  docker run -d --name "$webui_name" --add-host host.docker.internal:host-gateway \
    -p "127.0.0.1:${webui_port}:8080" -e ENABLE_SIGNUP=true -e ENABLE_LOGIN_FORM=true \
    -e ENABLE_OLLAMA_API=false -e RAG_EMBEDDING_ENGINE=ollama \
    -e HADES_RECEIPT_OWNER_USER_ID="${owner_id:-}" \
    -e HADES_RECEIPT_OCR_URL="$fixture_url/mcp" \
    -e HADES_RECEIPT_GROCY_URL="$fixture_url" \
    -e HADES_RECEIPT_GROCY_API_KEY_FILE=/run/secrets/synthetic-grocy-api-key \
    -e HADES_RECEIPT_LEDGER_PATH=/var/lib/hades-receipt/fingerprints.json \
    -v "$webui_volume:/app/backend/data" \
    -v "$work/grocy.key:/run/secrets/synthetic-grocy-api-key:ro" \
    -v "$work/ledger:/var/lib/hades-receipt" "$webui_image" >/dev/null
  for _ in $(seq 1 120); do curl -fsS "http://127.0.0.1:${webui_port}/health" >/dev/null 2>&1 && break; sleep 1; done
  curl -fsS "http://127.0.0.1:${webui_port}/health" >/dev/null
}

step='creating synthetic authenticated identities'
docker volume create "$webui_volume" >/dev/null
owner_id=''
start_webui
alpha_json=$(curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/auths/signup" \
  -H 'Content-Type: application/json' \
  --data '{"name":"Synthetic Alpha","email":"alpha-receipt@example.invalid","password":"Synthetic-Only-123!"}')
alpha_token=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$alpha_json")
owner_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$alpha_json")
curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/auths/add" \
  -H "Authorization: Bearer $alpha_token" -H 'Content-Type: application/json' \
  --data '{"name":"Synthetic Beta","email":"beta-receipt@example.invalid","password":"Synthetic-Only-123!","role":"user"}' >/dev/null
docker rm -f "$webui_name" >/dev/null
start_webui

step='authenticated household and owner browser acceptance'
cat >"$work/browser.js" <<'JS'
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');
const base=process.env.HADES_RECEIPT_TEST_URL, file=process.env.HADES_RECEIPT_TEST_FILE;
async function login(email) {
  const response=await fetch(`${base}/api/v1/auths/signin`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({email,password:'Synthetic-Only-123!'})});
  if (!response.ok) throw Error(`synthetic account signin failed: HTTP ${response.status}`);
  const {token}=await response.json();
  const browser=await chromium.launch({headless:true});
  const context=await browser.newContext({viewport:{width:1280,height:900}});
  await context.addCookies([{name:'token',value:token,url:`${base}/`}]);
  const page=await context.newPage();
  await page.goto(base,{waitUntil:'domcontentloaded'});
  await page.waitForSelector('#chat-input',{timeout:30000});
  const welcome=page.getByRole('button',{name:/okay,\s*let.s go/i});
  if (await welcome.count()) await welcome.first().click({force:true});
  const updateToast=page.locator('.absolute.bottom-8.right-8.z-50');
  try { await updateToast.waitFor({state:'visible',timeout:1200}); await updateToast.getByRole('button').click(); } catch (_) {}
  return {browser,context,page};
}
async function attachReceipt(page) {
  const inputs=page.locator('input[type="file"]');
  if (!(await inputs.count())) throw Error('Open WebUI file input missing');
  await inputs.last().setInputFiles(file);
}
async function attachAndOpen(page) {
  await attachReceipt(page);
  const review=page.getByRole('button',{name:'Review receipt',exact:true});
  await review.waitFor({state:'visible',timeout:15000}); await review.click();
  await page.getByRole('button',{name:'Preview OCR',exact:true}).click();
}
(async()=>{
  const beta=await login('beta-receipt@example.invalid');
  try {
    await attachReceipt(beta.page);
    await beta.page.waitForFunction(()=>window.__hadesUploadedFileIds?.size>0,{timeout:15000});
    await beta.page.waitForTimeout(500);
    if (await beta.page.getByRole('button',{name:'Review receipt',exact:true}).count()) throw Error('household saw the owner-only receipt action');
    const denied=await beta.page.evaluate(async()=>{
      const token=localStorage.getItem('token');
      const body=new FormData(); body.append('file',new File([new Uint8Array([1,2,3])],'synthetic-beta.png',{type:'image/png'}));
      const response=await fetch('/api/v1/hades/receipt/preview',{method:'POST',headers:{Authorization:`Bearer ${token}`},body});
      return {status:response.status,payload:await response.json()};
    });
    if (denied.status!==403 || denied.payload?.detail!=='Receipt OCR preview is owner-only.') throw Error('direct household preview did not fail closed: '+JSON.stringify(denied));
  } finally { await beta.browser.close(); }
  const owner=await login('alpha-receipt@example.invalid');
  try {
    await attachAndOpen(owner.page);
    await owner.page.waitForFunction(()=>!document.querySelector('#hades-receipt-ocr-modal')?.innerText.includes('Running local OCR preview'),{timeout:20000});
    const modal=owner.page.locator('#hades-receipt-ocr-modal');
    const preview=await modal.innerText();
    if (!preview.includes('Whole Milk') || !preview.includes('nothing has been added yet')) throw Error('owner preview did not render review-only item: '+preview);
    const confirm=owner.page.getByRole('button',{name:'Confirm and add to pantry',exact:true});
    if (!(await confirm.count())) throw Error('owner review did not offer explicit confirmation');
    await confirm.click();
    await owner.page.getByText(/Grocy confirmed the update\./).waitFor({timeout:15000});
  } finally { await owner.browser.close(); }
  console.log('PASS authenticated Beta is denied receipt OCR before downstream calls');
  console.log('PASS authenticated Alpha reviews synthetic OCR, explicitly confirms, and receives canonical Grocy read-back');
})().catch(error=>{console.error(error.stack||error);process.exit(1)});
JS
HADES_RECEIPT_TEST_URL="http://127.0.0.1:${webui_port}" HADES_RECEIPT_TEST_FILE="$work/receipt.png" \
  node "$work/browser.js"

step='verifying synthetic downstream isolation and canonical read-back'
python3 - "$docker_gateway" "$(cat "$work/fixture.port")" <<'PY'
import json,sys,urllib.request
url=f'http://{sys.argv[1]}:{sys.argv[2]}/__state'
with urllib.request.urlopen(url,timeout=3) as response: state=json.load(response)
assert state['ocr_calls']==1, state
assert state['stock']==1, state
assert [row for row in state['grocy'] if row['method']=='POST']==[{'method':'POST','path':'/api/stock/products/11/add','body':{'amount':1.0}}], state
assert len([row for row in state['grocy'] if row['path']=='/api/objects/products'])==1, state
assert len([row for row in state['grocy'] if row['path']=='/api/stock/products/11'])==1, state
print('PASS synthetic backend observed one owner OCR call, one explicit stock write, and one canonical read-back; Beta caused zero backend calls')
PY
echo 'PASS disposable authenticated receipt browser acceptance'
