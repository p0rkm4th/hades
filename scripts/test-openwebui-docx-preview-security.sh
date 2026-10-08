#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
image=${1:?usage: test-openwebui-docx-preview-security.sh IMAGE}
source "$repo_dir/config/versions.env"
image_id=$(docker image inspect --format '{{.Id}}' "$image" 2>/dev/null) || {
  echo 'FAIL candidate image must already exist locally; refusing an implicit pull' >&2
  exit 2
}
image_version=$(docker image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.version"}}')
if [[ "$image_version" == "$HADES_OPEN_WEBUI_CANDIDATE_VERSION" ]]; then
  bash "$repo_dir/scripts/verify-openwebui-candidate-artifact.sh" "$image"
elif [[ "$image_version" != "$HADES_OPEN_WEBUI_VERSION" ]]; then
  echo "FAIL DOCX Preview test image has an unsupported version label: $image_version" >&2
  exit 2
fi
playwright_module=${HADES_PLAYWRIGHT_MODULE:-${HOME}/.local/share/hades-playwright/node_modules/playwright}
[[ -d "$playwright_module" ]] || { echo 'FAIL Playwright module is unavailable' >&2; exit 2; }
node -e 'require(process.argv[1])' "$playwright_module" >/dev/null 2>&1 || {
  echo 'FAIL Playwright module cannot be loaded' >&2
  exit 2
}

suffix="$$-$RANDOM"
network="hades-docx-preview-$suffix"
mock="hades-docx-ollama-$suffix"
webui="hades-docx-webui-$suffix"
work=$(mktemp -d "${TMPDIR:-/tmp}/hades-docx-preview.XXXXXX")
cleanup() {
  docker rm -f "$webui" "$mock" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
  find "$work" -depth -mindepth 1 -delete 2>/dev/null || true
  rmdir "$work" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

docker network create "$network" >/dev/null
cat >"$work/mock-ollama.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/api/tags':
            self.send_error(404)
            return
        body = {'models': [{
            'name': 'hades-fixture:latest', 'model': 'hades-fixture:latest',
            'modified_at': '2026-10-01T00:00:00Z', 'size': 1024,
            'digest': 'synthetic-fixture',
            'details': {'format': 'gguf', 'family': 'fixture', 'families': ['fixture'],
                        'parameter_size': '1B', 'quantization_level': 'Q4'},
        }]}
        self.respond(body)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', '0'))
        if length:
            self.rfile.read(length)
        if self.path in ('/api/embeddings', '/api/embed'):
            self.respond({'embeddings': [[0.0] * 384]})
        elif self.path == '/api/chat':
            body = (json.dumps({
                'model': 'hades-fixture:latest',
                'created_at': '2026-10-01T00:00:00Z',
                'message': {'role': 'assistant', 'content': 'Synthetic fixture response.'},
                'done': True,
            }) + '\n').encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/x-ndjson')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def respond(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass

ThreadingHTTPServer(('0.0.0.0', 11434), Handler).serve_forever()
PY

python3 - "$work/fixture.docx" <<'PY'
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile

path = Path(sys.argv[1])
parts = {
    '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/afchunk.html" ContentType="text/html"/></Types>',
    '_rels/.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
    'word/document.xml': '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body><w:p><w:r><w:t>DOCX preview security test fixture</w:t></w:r><w:hyperlink r:id="rId2"><w:r><w:t>unsafe link marker</w:t></w:r></w:hyperlink></w:p><w:altChunk r:id="rId3"/><w:sectPr/></w:body></w:document>',
    'word/_rels/document.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="javascript:window.__HADES_DOCX_XSS__=&quot;executed-link&quot;" TargetMode="External"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/aFChunk" Target="afchunk.html"/></Relationships>',
    'word/afchunk.html': '''<!doctype html><html><body><script>(async()=>{try{const token=parent.localStorage.getItem("token");const files=await(await fetch("/api/v1/files/?content=false",{headers:{Authorization:`Bearer ${token}`} })).json();const victim=(files.items||[]).find(file=>file.filename==="beta-private-canary.txt");const response=victim?await fetch(`/api/v1/files/${victim.id}/content`,{headers:{Authorization:`Bearer ${token}`} }):null;const body=response?await response.text():"";parent.__HADES_DOCX_XSS__={executed:true,tokenPresent:!!token,victimStatus:response?.status??0,canaryRead:body.includes("BETA_PRIVATE_CANARY_93f40b")}}catch(error){parent.__HADES_DOCX_XSS__={executed:true,error:String(error)}}})();</script><p>Embedded document preview test</p></body></html>''',
}
with ZipFile(path, 'w', ZIP_DEFLATED) as archive:
    for name, content in parts.items():
        archive.writestr(name, content)
PY

docker run --rm -d --name "$mock" --network "$network" --network-alias ollama-mock \
  --entrypoint python3 -v "$work:/test:ro" "$image_id" /test/mock-ollama.py >/dev/null
docker run --rm -d --name "$webui" --network "$network" -p 127.0.0.1::8080 \
  -e ENABLE_SIGNUP=true -e ENABLE_LOGIN_FORM=true \
  -e OLLAMA_BASE_URL=http://ollama-mock:11434 -e RAG_EMBEDDING_ENGINE=ollama \
  "$image_id" >/dev/null
port=$(docker port "$webui" 8080/tcp | sed 's/.*://')
base="http://127.0.0.1:$port"
for _ in $(seq 1 90); do
  if curl -fsS "$base/health" >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -fsS "$base/health" >/dev/null || { echo 'FAIL disposable Open WebUI did not become healthy' >&2; exit 1; }

BASE="$base" IMAGE_ID="$image_id" FIXTURE="$work/fixture.docx" \
HADES_PLAYWRIGHT_MODULE="$playwright_module" node <<'JS'
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE);

(async () => {
  const base = process.env.BASE;
  const signup = await fetch(`${base}/api/v1/auths/signup`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      name: 'Synthetic DOCX Owner',
      email: 'docx-owner@example.invalid',
      password: 'Synthetic-Only-123!'
    })
  });
  const owner = await signup.json();
  if (signup.status !== 200 || !owner.token) throw new Error(`synthetic owner setup failed: HTTP ${signup.status}`);
  const betaResponse = await fetch(`${base}/api/v1/auths/add`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', Authorization: `Bearer ${owner.token}` },
    body: JSON.stringify({name: 'Synthetic Household', email: 'docx-household@example.invalid', password: 'Synthetic-Only-456!', role: 'user'})
  });
  const beta = await betaResponse.json();
  if (betaResponse.status !== 200 || !beta.token) throw new Error(`synthetic household setup failed: HTTP ${betaResponse.status}`);
  const victimUpload = new FormData();
  victimUpload.append('file', new Blob(['BETA_PRIVATE_CANARY_93f40b'], {type:'text/plain'}), 'beta-private-canary.txt');
  const victimResponse = await fetch(`${base}/api/v1/files/?process=false`, {
    method: 'POST', headers: {Authorization: `Bearer ${beta.token}`}, body: victimUpload
  });
  const victim = await victimResponse.json();
  if (victimResponse.status !== 200 || !victim.id) throw new Error(`private canary upload failed: HTTP ${victimResponse.status}`);

  const browser = await chromium.launch({ headless: true });
  try {
    const ownerContext = await browser.newContext();
    await ownerContext.addInitScript((token) => localStorage.setItem('token', token), owner.token);
    const ownerPage = await ownerContext.newPage();
    ownerPage.setDefaultTimeout(15000);
    await ownerPage.goto(base);
    await ownerPage.waitForTimeout(700);
    await ownerPage.getByRole('button', { name: /Okay, Let's Go/ }).click().catch(() => {});
    await ownerPage.locator('input[type="file"]').first().setInputFiles(process.env.FIXTURE);
    await ownerPage.waitForTimeout(1000);
    await ownerPage.locator('#chat-input').fill('Summarize this security test document.');
    await ownerPage.locator('#chat-input').press('Enter');
    await ownerPage.getByText('Synthetic fixture response.', { exact: true }).waitFor();
    const chatListResponse = await fetch(`${base}/api/v1/chats/?page=1`, {headers:{Authorization:`Bearer ${owner.token}`}});
    const chatList = await chatListResponse.json();
    let ownerChat = null;
    for (const item of chatList) {
      const response = await fetch(`${base}/api/v1/chats/${item.id}`, {headers:{Authorization:`Bearer ${owner.token}`}});
      if (!response.ok) continue;
      const candidate = await response.json();
      if (JSON.stringify(candidate.chat).includes('Summarize this security test document.')) { ownerChat = candidate; break; }
    }
    if (!ownerChat?.id) throw new Error('owner chat with uploaded document did not persist');
    const ownerChatSummary = JSON.stringify(ownerChat.chat);
    if (!ownerChatSummary.includes('fixture.docx')) {
      throw new Error(`saved owner chat omitted the uploaded DOCX attachment; chat keys: ${Object.keys(ownerChat.chat || {}).join(',')}`);
    }
    const shareResponse = await fetch(`${base}/api/v1/chats/${ownerChat.id}/share`, {
      method: 'POST', headers: {Authorization:`Bearer ${owner.token}`}
    });
    const sharedChat = await shareResponse.json();
    if (shareResponse.status !== 200 || !sharedChat.share_id) throw new Error(`shared-chat setup failed: HTTP ${shareResponse.status}`);
    const accessResponse = await fetch(`${base}/api/v1/chats/shared/${ownerChat.id}/access/update`, {
      method: 'POST',
      headers: {Authorization:`Bearer ${owner.token}`, 'content-type':'application/json'},
      body: JSON.stringify({access_grants:[{principal_type:'user', principal_id:beta.id, permission:'read'}]})
    });
    if (!accessResponse.ok) throw new Error(`household share grant failed: HTTP ${accessResponse.status}`);
    const betaSharedResponse = await fetch(`${base}/api/v1/chats/share/${sharedChat.share_id}`, {headers:{Authorization:`Bearer ${beta.token}`}});
    const betaShared = await betaSharedResponse.json();
    if (betaSharedResponse.status !== 200 || !JSON.stringify(betaShared.chat).includes('fixture.docx')) {
      throw new Error(`shared chat did not preserve DOCX attachment for household viewer: HTTP ${betaSharedResponse.status}`);
    }
    const cloneResponse = await fetch(`${base}/api/v1/chats/${sharedChat.share_id}/clone/shared`, {
      method: 'POST', headers: {Authorization:`Bearer ${beta.token}`}
    });
    const clonedChat = await cloneResponse.json();
    if (cloneResponse.status !== 200 || !clonedChat.id) throw new Error(`household could not open shared chat in its workspace: HTTP ${cloneResponse.status}`);
    console.log(JSON.stringify({shared_chat_attachment:'present', household_private_file_fixture:'present'}));

    const context = await browser.newContext();
    await context.addInitScript(() => { window.__HADES_DOCX_XSS__ = 'not-executed'; });
    await context.addInitScript((token) => localStorage.setItem('token', token), beta.token);
    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    const pageErrors = [];
    page.on('pageerror', (error) => pageErrors.push(String(error)));

    await page.goto(`${base}/c/${clonedChat.id}`);
    await page.waitForTimeout(700);
    await page.getByText('fixture.docx', { exact: true }).last().click();
    await page.getByText('Preview', { exact: true }).last().click();
    await page.getByText('DOCX preview security test fixture', { exact: true }).waitFor();
    await page.waitForTimeout(800);

    const frames = [];
    for (const frame of page.frames()) {
      frames.push({
        url: frame.url(),
        marker: await frame.evaluate(() => window.__HADES_DOCX_XSS__).catch(() => 'cross-origin'),
        unsafeLinks: await frame.locator('a[href^="javascript:"]').count().catch(() => -1)
      });
    }
    const dialog = page.locator('[role="dialog"]');
    const previewRendered = (await dialog.innerText()).includes('DOCX preview security test fixture');
    if (!previewRendered) throw new Error('DOCX preview did not render the harmless fixture text');
    const marker = await page.evaluate(() => window.__HADES_DOCX_XSS__);
    const expectVulnerable = process.env.EXPECT_VULNERABLE === '1';
    if (expectVulnerable) {
      if (!marker || marker === 'not-executed' || marker.executed !== true || marker.tokenPresent !== true || marker.victimStatus !== 200 || marker.canaryRead !== true) {
        throw new Error(`positive control did not demonstrate cross-user token theft and private-file read: ${JSON.stringify({marker,frames})}`);
      }
    } else if (marker !== 'not-executed' || frames.some((frame) => frame.marker !== 'not-executed')) {
      throw new Error(`DOCX embedded script executed or changed the parent marker: ${JSON.stringify({marker,frames})}`);
    }
    if (!expectVulnerable && frames.some((frame) => frame.unsafeLinks !== 0)) {
      throw new Error(`unsafe javascript link survived preview: ${JSON.stringify(frames)}`);
    }
    if (pageErrors.length) throw new Error(`browser page errors: ${JSON.stringify(pageErrors)}`);

    console.log(JSON.stringify({
      result: 'PASS',
      image_id: process.env.IMAGE_ID,
      active_content_executed: expectVulnerable,
      cross_user_token_theft: expectVulnerable ? 'positive control reproduced' : 'blocked',
      private_canary_read: expectVulnerable ? marker.canaryRead : false,
      unsafe_javascript_links: frames.reduce((total, frame) => total + frame.unsafeLinks, 0),
      preview_rendered: previewRendered,
      frame_count: frames.length
    }));
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error.stack); process.exit(1); });
JS

echo "PASS Open WebUI DOCX preview security regression: $image"
