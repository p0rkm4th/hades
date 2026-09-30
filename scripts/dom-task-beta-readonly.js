#!/usr/bin/env node

/* Authenticated, non-mutating Beta task-history comparison for any explicit
 * Open WebUI target. This script never proposes, approves, resumes, replans,
 * or cancels a task. The UI will persist its read-only chat turns normally. */
const fs = require('node:fs');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const base = (process.env.HADES_BETA_READONLY_BASE_URL || '').replace(/\/$/, '');
const emailFile = process.env.HADES_BETA_OWNER_EMAIL_FILE || '';
const passwordFile = process.env.HADES_BETA_OWNER_PASSWORD_FILE || '';
const report = process.env.HADES_BETA_READONLY_REPORT || '/tmp/hades-task-beta-readonly.json';

if (!base || !/^https?:\/\//.test(base)) throw new Error('set HADES_BETA_READONLY_BASE_URL explicitly');
if (!emailFile || !passwordFile) throw new Error('set owner credential file paths explicitly');
const email = fs.readFileSync(emailFile, 'utf8').trim();
const password = fs.readFileSync(passwordFile, 'utf8').trim();
if (!email || !password) throw new Error('owner credential files must be non-empty');

async function ask(browser, prompt) {
  const auth = await fetch(`${base}/api/v1/auths/ldap`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ user: email, password }),
  });
  if (!auth.ok) throw new Error(`owner login failed: HTTP ${auth.status}`);
  const body = await auth.json();
  if (!body.token) throw new Error('owner login returned no session token');

  const context = await browser.newContext({
    ignoreHTTPSErrors: base.startsWith('https://'),
    viewport: { width: 1440, height: 900 },
  });
  try {
    const page = await context.newPage();
    page.__hadesCompletionSeen = false;
    page.on('websocket', socket => socket.on('framereceived', data => {
      const frame = String(data);
      if (frame.includes('chat:completion') && (frame.includes('"done":true') || frame.includes('"finish_reason":"stop"'))) {
        page.__hadesCompletionSeen = true;
      }
    }));
    await context.addCookies([{ name: 'token', value: body.token, domain: new URL(base).hostname, path: '/' }]);
    await page.goto(`${base}/`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForSelector('#chat-input', { timeout: 30000 });
    const welcome = page.getByRole('button', { name: /okay,\s*let.s go/i });
    if (await welcome.count()) await welcome.first().click({ force: true });

    const selector = '#response-content-container .markdown-prose';
    const before = await page.locator(selector).count();
    const beforeText = before ? (await page.locator(selector).last().innerText()).trim() : '';
    await page.locator('#chat-input').fill(prompt);
    page.__hadesCompletionSeen = false;
    await page.locator('#send-message-button').click({ force: true });
    const deadline = Date.now() + Number(process.env.HADES_BETA_READONLY_WAIT_MS || 45000);
    while (Date.now() < deadline) {
      const responses = page.locator(selector);
      const count = await responses.count();
      const latest = count ? (await responses.last().innerText()).trim() : '';
      const stop = await page.locator('#message-input-container button[aria-label="Stop"]').count();
      if ((count > before || latest !== beforeText || page.__hadesCompletionSeen) && latest && !stop) return latest;
      await page.waitForTimeout(300);
    }
    const bodyText = (await page.locator('body').innerText()).toLowerCase();
    const responseCount = await page.locator(selector).count();
    const stopVisible = Boolean(await page.locator('#message-input-container button[aria-label="Stop"]').count());
    const signals = {
      unavailable: /service unavailable|temporarily unavailable|connection refused/.test(bodyText),
      modelError: /model error|failed to load model|no model available/.test(bodyText),
      authError: /unauthorized|authentication failed|sign in again/.test(bodyText),
      serverError: /internal server error|unexpected error|something went wrong/.test(bodyText),
    };
    throw new Error(JSON.stringify({ prompt, responseCount, stopVisible, signals }));
  } finally {
    await context.close();
  }
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const recent = await ask(browser, 'List my tasks');
    const completed = await ask(browser, 'Show completed tasks');
    const ownId = (recent.match(/\btask-[a-z0-9][a-z0-9-]{7,}\b/i) || [])[0] || '';
    const ownStatus = ownId ? await ask(browser, `Show task ${ownId}`) : '';
    const foreignId = `task-foreign-not-ours-${Date.now().toString(36)}`;
    const foreignStatus = await ask(browser, `Show task ${foreignId}`);
    const recentRecognized = /your recent tasks:/i.test(recent) || /there are no .*tasks recorded for this account/i.test(recent);
    const completedRecognized = /your recent tasks:/i.test(completed) || /there are no completed tasks recorded for this account/i.test(completed);
    const foreignHidden = /couldn't find a task/i.test(foreignStatus) && !foreignStatus.includes(foreignId);
    const ownInspectable = !ownId || (/status:/i.test(ownStatus) && ownStatus.includes(ownId));
    const result = {
      status: recentRecognized && completedRecognized && foreignHidden && ownInspectable ? 'PASS' : 'FAIL',
      checks: { recentRecognized, completedRecognized, ownTaskIdFound: Boolean(ownId), ownTaskInspectable: ownInspectable, foreignTaskHidden: foreignHidden },
      mutationPromptsSent: false,
    };
    fs.writeFileSync(report, `${JSON.stringify(result, null, 2)}\n`, { mode: 0o600 });
    fs.chmodSync(report, 0o600);
    console.log(JSON.stringify({ status: result.status, report }));
    if (result.status !== 'PASS') process.exitCode = 1;
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(JSON.stringify({ status: 'FAIL', error: error.message }));
  process.exitCode = 1;
});
