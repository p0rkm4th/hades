#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Render the same authenticated HADES theme on the old and candidate HADES
# Open WebUI images. Screenshots and the non-secret comparison manifest are
# retained in the output directory for human review; disposable DBs/containers
# and local login tokens are removed.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
baseline=${1:-hades-open-webui:0.11.1-hades-reconstructed}
candidate=${2:-hades-open-webui:0.11.4-candidate}
playwright_modules=${HADES_PLAYWRIGHT_NODE_MODULES:-${HOME}/.local/share/hades-playwright/node_modules}
playwright_module="$playwright_modules/playwright"
for image in "$baseline" "$candidate"; do
  docker image inspect "$image" >/dev/null 2>&1 || {
    echo "FAIL image is not cached: $image" >&2
    exit 2
  }
done
[[ -d "$playwright_module" ]] || { echo "FAIL Playwright module is unavailable: $playwright_module" >&2; exit 2; }

suffix=$$
baseline_container="hades-theme-baseline-$suffix"
candidate_container="hades-theme-candidate-$suffix"
network="hades-theme-compare-$suffix"
model_port=$((22000 + (suffix % 12000)))
output=${HADES_THEME_COMPARE_OUTPUT_DIR:-$(mktemp -d /tmp/hades-openwebui-theme-compare.XXXXXX)}
work=$(mktemp -d /tmp/hades-openwebui-theme-work.XXXXXX)
mkdir -p "$work/baseline" "$work/candidate"
cleanup() {
  docker stop "$baseline_container" "$candidate_container" >/dev/null 2>&1 || true
  kill "${backend_pid:-}" >/dev/null 2>&1 || true
  for container in "$baseline_container" "$candidate_container"; do
    for _ in $(seq 1 50); do
      docker inspect "$container" >/dev/null 2>&1 || break
      sleep 0.1
    done
  done
  docker network rm "$network" >/dev/null 2>&1 || true
  python3 -c 'import shutil,sys; shutil.rmtree(sys.argv[1],ignore_errors=True)' "$work"
}
trap cleanup EXIT INT TERM
mkdir -p "$output"

start_webui() {
  local name=$1 image=$2 data=$3
  docker run --rm -d --name "$name" --network "$network" -p 127.0.0.1::8080 \
    --add-host host.docker.internal:host-gateway \
    -e ENABLE_SIGNUP=true -e ENABLE_LOGIN_FORM=true \
    -e ENABLE_OLLAMA_API=false -e RAG_EMBEDDING_ENGINE=ollama \
    -v "$data:/app/backend/data" "$image" >/dev/null
  docker port "$name" 8080/tcp | sed 's/.*://'
}

docker network create "$network" >/dev/null
baseline_id=$(docker image inspect --format '{{.Id}}' "$baseline")
candidate_id=$(docker image inspect --format '{{.Id}}' "$candidate")
python3 "$repo_dir/scripts/synthetic-openai-backend.py" 0.0.0.0 "$model_port" >/dev/null 2>&1 &
backend_pid=$!
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:$model_port/v1/models" >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -fsS "http://127.0.0.1:$model_port/v1/models" >/dev/null
baseline_port=$(start_webui "$baseline_container" "$baseline_id" "$work/baseline")
candidate_port=$(start_webui "$candidate_container" "$candidate_id" "$work/candidate")
baseline_browser_url="http://$baseline_container:8080"
candidate_browser_url="http://$candidate_container:8080"

for spec in "baseline:$baseline_port" "candidate:$candidate_port"; do
  label=${spec%%:*}
  port=${spec#*:}
  ready=false
  for _ in $(seq 1 120); do
    if curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1; then ready=true; break; fi
    sleep 1
  done
  [[ "$ready" == true ]] || {
    docker logs --tail 50 "hades-theme-${label}-$suffix" >&2
    echo "FAIL $label Open WebUI did not become healthy" >&2
    exit 1
  }
done

HADES_THEME_BASELINE_URL="http://127.0.0.1:$baseline_port" \
HADES_THEME_CANDIDATE_URL="http://127.0.0.1:$candidate_port" \
HADES_THEME_TOKEN_FILE="$work/tokens.json" \
HADES_THEME_MANIFEST="$output/manifest.json" \
HADES_THEME_MODEL_URL="http://host.docker.internal:$model_port/v1" \
python3 - "$baseline_id" "$candidate_id" <<'PY'
import json
import os
import sys
import time
from urllib.request import Request, urlopen

images = {'baseline': sys.argv[1], 'candidate': sys.argv[2]}
urls = {'baseline': os.environ['HADES_THEME_BASELINE_URL'], 'candidate': os.environ['HADES_THEME_CANDIDATE_URL']}
model_url = os.environ['HADES_THEME_MODEL_URL']
tokens = {}
manifest = {'theme': 'odysseus-neon', 'effect': 'none', 'model': 'synthetic-reconstruction-model', 'viewport': {'width': 1365, 'height': 850}, 'images': {}}

def request(url, path, payload=None, token=None):
    data = None if payload is None else json.dumps(payload).encode()
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = Request(url + path, data=data, headers=headers)
    with urlopen(req, timeout=20) as response:
        return json.load(response) if 'application/json' in response.headers.get('Content-Type', '') else response.read()

for label, url in urls.items():
    email = f'theme-{label}@example.invalid'
    signup = request(url, '/api/v1/auths/signup', {
        'name': f'Synthetic {label.title()}', 'email': email, 'password': 'Synthetic-Only-123!'
    })
    token = signup.get('token')
    if not token:
        raise SystemExit(f'FAIL {label} synthetic owner signup returned no token')
    settings = {'hades_theme': 'odysseus-neon', 'hades_background_effect': 'none'}
    request(url, '/api/v1/users/user/settings/update', settings, token)
    actual = request(url, '/api/v1/users/user/settings?raw=true', token=token)
    if actual.get('hades_theme') != settings['hades_theme'] or actual.get('hades_background_effect') != 'none':
        raise SystemExit(f'FAIL {label} theme settings did not persist: {actual}')
    request(url, '/openai/config/update', {
        'ENABLE_OPENAI_API': True,
        'OPENAI_API_BASE_URLS': [model_url],
        'OPENAI_API_KEYS': ['synthetic'],
        'OPENAI_API_CONFIGS': {},
    }, token)
    models = request(url, '/openai/models', token=token)
    if not any(row.get('id') == manifest['model'] for row in models.get('data', [])):
        raise SystemExit(f'FAIL {label} synthetic model is unavailable: {models}')
    tokens[label] = token
    manifest['images'][label] = {'image_id': images[label], 'reported_version': request(url, '/api/version'), 'settings_saved': True}
with open(os.environ['HADES_THEME_TOKEN_FILE'], 'w', encoding='utf-8') as stream:
    json.dump(tokens, stream)
os.chmod(os.environ['HADES_THEME_TOKEN_FILE'], 0o600)
with open(os.environ['HADES_THEME_MANIFEST'], 'w', encoding='utf-8') as stream:
    json.dump(manifest, stream, indent=2)
    stream.write('\n')
PY

HADES_THEME_TOKEN_FILE="$work/tokens.json" \
docker run --rm -i --network "$network" \
  -e PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
  -e HADES_PLAYWRIGHT_MODULE=/test/node_modules/playwright \
  -e HADES_THEME_TOKEN_FILE=/run/tokens.json \
  -e HADES_THEME_BASELINE_URL="$baseline_browser_url" \
  -e HADES_THEME_CANDIDATE_URL="$candidate_browser_url" \
  -e HADES_THEME_OUTPUT_DIR=/out \
  -v "$work/tokens.json:/run/tokens.json:ro" \
  -v "${HOME}/.cache/ms-playwright:/ms-playwright:ro" \
  -v "$playwright_modules:/test/node_modules:ro" \
  -v "$output:/out" \
  mcr.microsoft.com/playwright@sha256:b27e719ecbfef153e13fd24e8341736733bf2658b229677eb21ff57ff5d7fb29 node <<'JS'
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE);

(async () => {
  const tokens = JSON.parse(fs.readFileSync(process.env.HADES_THEME_TOKEN_FILE, 'utf8'));
  const runs = [
    ['candidate', process.env.HADES_THEME_CANDIDATE_URL],
    ['baseline', process.env.HADES_THEME_BASELINE_URL],
  ];
  const browser = await chromium.launch({ headless: true });
  const report = {};
  try {
    for (const [label, base] of runs) {
      console.log(`BROWSER ${label} ${base}`);
      const context = await browser.newContext({ viewport: { width: 1365, height: 850 }, deviceScaleFactor: 1 });
      await context.addCookies([{ name: 'token', value: tokens[label], url: `${base}/` }]);
      const page = await context.newPage();
      const errors = [];
      const serverErrors = [];
      page.on('pageerror', error => errors.push(String(error)));
      page.on('response', response => {
        if (response.status() >= 500) serverErrors.push({ url: new URL(response.url()).pathname, status: response.status() });
      });
      page.on('console', message => {
        if (message.type() === 'error') console.error(`BROWSER_CONSOLE ${label} ${message.text()}`);
      });
      page.on('requestfailed', request => console.error(`REQUEST_FAILED ${label} ${request.url()} ${request.failure()?.errorText || ''}`));
      page.on('crash', () => console.error(`PAGE_CRASH ${label} at ${page.url()}`));
      await page.addInitScript(token => localStorage.setItem('token', token), tokens[label]);
      await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 60000 });
      await page.waitForSelector('#chat-input', { state: 'attached', timeout: 60000 });
      const welcome = page.getByRole('button', { name: /okay,\s*let.s go/i });
      if (await welcome.count()) await welcome.first().click({ force: true });
      const modelSelector = page.getByRole('button', { name: /select a model/i });
      if (await modelSelector.count()) {
        await modelSelector.first().click();
        const modelOption = page.getByText('synthetic-reconstruction-model', { exact: true }).last();
        await modelOption.waitFor({ state: 'visible', timeout: 15000 });
        await modelOption.click();
      }
      await page.waitForFunction(() => document.documentElement.classList.contains('hades-theme-odysseus-neon'), null, { timeout: 20000 });
      await page.waitForTimeout(1500);
      const state = await page.evaluate(() => ({
        title: document.title,
        theme: [...document.documentElement.classList].find(value => value.startsWith('hades-theme-')) || null,
        effect: [...document.documentElement.classList].find(value => value.startsWith('hades-effect-')) || null,
        composerVisible: !!document.querySelector('#chat-input') && document.querySelector('#chat-input').getBoundingClientRect().width > 0,
        themeStylesheet: [...document.styleSheets].some(sheet => sheet.href && sheet.href.includes('/static/hades-theme.css')),
        themeScript: [...document.scripts].some(script => script.src.includes('/static/hades-theme.js')),
        viewport: { width: innerWidth, height: innerHeight },
        background: getComputedStyle(document.body).backgroundColor,
        bodyTextLength: document.body.innerText.length,
        versionNotice: document.body.innerText.split('\n').find(line => /new version|update for the latest/i.test(line)) || null,
      }));
      if (state.theme !== 'hades-theme-odysseus-neon' || !state.composerVisible || !state.themeStylesheet || !state.themeScript) {
        throw new Error(`${label} rendered state failed: ${JSON.stringify(state)}`);
      }
      if (errors.length) throw new Error(`${label} browser errors: ${errors.join(' | ')}`);
      await page.screenshot({ path: path.join(process.env.HADES_THEME_OUTPUT_DIR, `${label}.png`), fullPage: true });
      report[label] = { ...state, pageErrors: errors, serverErrors };
      await context.close();
      console.log(`PASS ${label} rendered HADES theme, composer, and static assets`);
    }
  } finally {
    await browser.close();
  }
  fs.writeFileSync(path.join(process.env.HADES_THEME_OUTPUT_DIR, 'render-report.json'), JSON.stringify(report, null, 2) + '\n');
})().catch(error => { console.error(error); process.exitCode = 1; });
JS

echo "PASS rendered HADES theme comparison artifacts: $output"
echo "Images: baseline=$baseline_id candidate=$candidate_id"
