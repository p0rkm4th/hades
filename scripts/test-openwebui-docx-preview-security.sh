#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
image=${1:?usage: test-openwebui-docx-preview-security.sh IMAGE}
bash "$repo_dir/scripts/verify-openwebui-candidate-artifact.sh" "$image"
image_id=$(docker image inspect --format '{{.Id}}' "$image" 2>/dev/null) || {
  echo 'FAIL candidate image must already exist locally; refusing an implicit pull' >&2
  exit 2
}
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
    'word/afchunk.html': '<!doctype html><html><body><script>window.__HADES_DOCX_XSS__="executed-altchunk"</script><p>Embedded document preview test</p></body></html>',
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

  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext();
    await context.addInitScript(() => { window.__HADES_DOCX_XSS__ = 'not-executed'; });
    await context.addInitScript((token) => localStorage.setItem('token', token), owner.token);
    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    const pageErrors = [];
    page.on('pageerror', (error) => pageErrors.push(String(error)));

    await page.goto(base);
    await page.waitForTimeout(700);
    await page.getByRole('button', { name: /Okay, Let's Go/ }).click().catch(() => {});
    await page.locator('input[type="file"]').first().setInputFiles(process.env.FIXTURE);
    await page.waitForTimeout(1000);
    await page.locator('#chat-input').fill('Summarize this security test document.');
    await page.locator('#chat-input').press('Enter');
    await page.getByText('Synthetic fixture response.', { exact: true }).waitFor();
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
    if (frames.some((frame) => frame.marker !== 'not-executed')) {
      throw new Error(`DOCX embedded script executed: ${JSON.stringify(frames)}`);
    }
    if (frames.some((frame) => frame.unsafeLinks !== 0)) {
      throw new Error(`unsafe javascript link survived preview: ${JSON.stringify(frames)}`);
    }
    if (pageErrors.length) throw new Error(`browser page errors: ${JSON.stringify(pageErrors)}`);

    console.log(JSON.stringify({
      result: 'PASS',
      image_id: process.env.IMAGE_ID,
      active_content_executed: false,
      unsafe_javascript_links: 0,
      preview_rendered: previewRendered,
      frame_count: frames.length
    }));
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error.stack); process.exit(1); });
JS

echo "PASS Open WebUI DOCX preview security regression: $image"
