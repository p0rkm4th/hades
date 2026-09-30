#!/usr/bin/env node
const fs = require('node:fs');
const { protectedInput } = require('./dom-protected-input');
let playwright;
try { playwright = require('playwright'); } catch (_) { playwright = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright'); }

const base = process.env.HADES_DOM_BASE_URL || 'http://127.0.0.1:3000/';
const email = protectedInput('HADES_DOM_EMAIL');
const password = protectedInput('HADES_DOM_PASSWORD');
const reportFile = process.env.HADES_DOM_REPORT || '/tmp/hades-dom-lifecycle-diagnose.json';
const events = [];
const safe = url => { try { const u = new URL(url); return `${u.origin}${u.pathname}`; } catch (_) { return '<invalid>'; } };

(async () => {
  const browser = await playwright.chromium.launch({ headless: true });
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  page.on('console', m => { if (m.type() === 'error') events.push({ type: 'console-error', text: m.text() }); });
  page.on('pageerror', e => events.push({ type: 'page-error', text: e.message, stack: e.stack || '' }));
  page.on('requestfailed', r => events.push({ type: 'request-failed', url: safe(r.url()), error: r.failure()?.errorText }));
  page.on('request', r => {
    const url = r.url();
    if (/\/api\/(chat|tasks)|\/ws|websocket/i.test(url)) events.push({ type: 'request', method: r.method(), url: safe(url), postData: /chat\/completions/.test(url) ? '<redacted>' : undefined });
  });
  page.on('response', async r => {
    const url = r.url();
    if (!/\/api\/(chat|tasks)|\/ws|websocket/i.test(url)) return;
    const item = { type: 'response', status: r.status(), url: safe(url) };
    if (r.status() >= 400 || /\/api\/chat\/completions$/.test(url)) {
      try { item.body = (await r.text()).slice(0, 2000); } catch (_) {}
    }
    events.push(item);
  });
  page.on('websocket', ws => {
    events.push({ type: 'websocket', url: safe(ws.url()) });
    const frame = data => {
      let value;
      try { value = JSON.stringify(data); } catch (_) { value = String(data); }
      return value
        .replace(/("(?:token|access_token|authorization)"\s*:\s*")([^"]+)(")/gi, '$1<redacted>$3')
        .replace(/(\\"(?:token|access_token|authorization)\\"\s*:\s*\\")([^\\"]+)(\\")/gi, '$1<redacted>$3')
        .replace(/\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/g, '<redacted-jwt>')
        .slice(0, 1000);
    };
    ws.on('framereceived', data => events.push({ type: 'ws-received', size: String(data).length, preview: frame(data) }));
    ws.on('framesent', data => events.push({ type: 'ws-sent', size: String(data).length, preview: frame(data) }));
  });
  try {
    await page.goto(base, { waitUntil: 'commit', timeout: 30000 });
    await page.waitForSelector('#username, #chat-input', { timeout: 30000 });
    const ldap = page.locator('#username');
    if (await ldap.count()) {
      await ldap.fill(email);
      await page.locator('#password').fill(password);
      await page.getByRole('button', { name: /authenticate/i }).click();
    }
    await page.waitForSelector('#chat-input', { timeout: 30000 });
    await page.locator('#chat-input').fill('say exactly: lifecycle probe ok');
    await page.locator('#chat-input').press('Enter');
    const settleDeadline = Date.now() + Number(process.env.HADES_DOM_DIAG_WAIT_MS || 15000);
    while (Date.now() < settleDeadline) {
      const settled = await page.evaluate(() => ({
        assistant: [...document.querySelectorAll('#response-content-container .markdown-prose')]
          .at(-1)?.innerText?.trim() || '',
        stop: Boolean(document.querySelector('#message-input-container button[aria-label="Stop"]')),
      }));
      if (settled.assistant && !settled.stop) break;
      await page.waitForTimeout(500);
    }
    const state = await page.evaluate(() => ({
      url: location.href,
      stop: Boolean(document.querySelector('#message-input-container button[aria-label="Stop"]')),
      composer: document.querySelector('#chat-input')?.value || '',
      assistants: [...document.querySelectorAll('#response-content-container .markdown-prose')].map(n => n.innerText),
      bodyTail: document.body.innerText.slice(-1800),
    }));
    if (!state.assistants.some(text => text.trim()) || state.stop) {
      throw new Error(`DOM lifecycle did not settle cleanly: assistant=${Boolean(state.assistants.some(text => text.trim()))} stop=${state.stop}`);
    }
    const report = { status: 'OK', state, events };
    fs.writeFileSync(reportFile, `${JSON.stringify(report, null, 2)}\n`, { mode: 0o600 });
    console.log(JSON.stringify(report));
  } finally { await browser.close(); }
})().catch(error => { console.error(JSON.stringify({ status: 'FAIL', error: error.message, events })); process.exitCode = 1; });
