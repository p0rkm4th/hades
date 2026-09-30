#!/usr/bin/env node
const fs = require('node:fs');
const { protectedInput } = require('./dom-protected-input');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const base = process.env.HADES_DOM_BASE_URL || 'http://127.0.0.1:3000/';
const email = protectedInput('HADES_DOM_EMAIL') || fs.readFileSync(process.env.HADES_DOM_EMAIL_FILE, 'utf8').trim();
const password = protectedInput('HADES_DOM_PASSWORD') || fs.readFileSync(process.env.HADES_DOM_PASSWORD_FILE, 'utf8').trim();
const prompt = process.env.HADES_DOM_PROMPT || 'say hello';
const waitMs = Number(process.env.HADES_DOM_WAIT_MS || 35000);

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1440, height: 900 } });
  const login = await fetch(`${base.replace(/\/$/, '')}/api/v1/auths/signin`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!login.ok) throw new Error(`synthetic UI login failed: HTTP ${login.status}`);
  const { token } = await login.json();
  await context.addCookies([{ name: 'token', value: token, url: base }]);
  const page = await context.newPage();
  const errors = [];
  const chatRequests = [];
  page.on('request', request => {
    if (new URL(request.url()).pathname.endsWith('/api/chat/completions')) {
      chatRequests.push({ method: request.method(), url: request.url() });
    }
  });
  page.on('requestfailed', request => {
    if (new URL(request.url()).pathname.endsWith('/api/chat/completions')) {
      const row = chatRequests.findLast(item => item.url === request.url());
      if (row) row.failure = request.failure()?.errorText || 'request failed';
    }
  });
  page.on('pageerror', error => errors.push(error.message));
  let aborted = false;
  if (process.env.HADES_DOM_ABORT_CHAT === '1') {
    await page.route('**/api/chat/completions**', async route => {
      if (!aborted) {
        aborted = true;
        await route.abort('failed');
      } else {
        await route.continue();
      }
    });
  }
  await page.goto(`${base}/`, { waitUntil: 'commit', timeout: 30000 });
  await page.waitForSelector('#username, #chat-input', { timeout: 30000 });
  if (await page.locator('#username').count()) {
    await page.locator('#username').fill(email);
    await page.locator('#password').fill(password);
    await page.getByRole('button', { name: /authenticate/i }).click();
  }
  await page.waitForSelector('#chat-input', { timeout: 30000 });
  const welcome = page.getByRole('button', { name: /okay,\s*let.s go/i });
  if (await welcome.count()) await welcome.first().click({ force: true });
  const modelId = process.env.HADES_DOM_MODEL_ID;
  if (modelId) {
    const choose = page.getByRole('button', { name: /select a model/i });
    if (await choose.count()) {
      await choose.first().click();
      const option = page.getByText(modelId, { exact: true }).last();
      await option.waitFor({ state: 'visible', timeout: 10000 });
      await option.click();
    }
  }
  await page.getByRole('button', { name: 'New Chat' }).last().click();
  await page.waitForTimeout(300);
  await page.locator('#chat-input').fill(prompt);
  await page.locator('#chat-input').press('Enter');
  await page.waitForTimeout(waitMs);
  const state = await page.evaluate(() => ({
    stop: Boolean(document.querySelector('#message-input-container button[aria-label="Stop"]')),
    composer: document.querySelector('#chat-input')?.value || '',
    bodyTail: document.body.innerText.slice(-1800),
    visibleError: [...document.querySelectorAll('*')].some(node =>
      /there was an issue with the response|connection error|request timed out|failed to fetch|your request may have completed, so check before trying again/i.test(node.textContent || '')
    ),
  }));
  let recovery = null;
  if (process.env.HADES_DOM_ABORT_CHAT === '1') {
    const newChat = page.locator('[aria-label="New Chat"]:visible, #new-chat-button:visible, button:has-text("New Chat"):visible');
    if (!await newChat.count()) throw new Error('new-chat control is not visible after aborted turn');
    await newChat.last().click({ force: true });
    const clearDeadline = Date.now() + 5000;
    while (Date.now() < clearDeadline) {
      if (await page.locator('#response-content-container .markdown-prose').count() === 0) break;
      await page.waitForTimeout(200);
    }
    const beforeRecovery = await page.locator('#response-content-container .markdown-prose').count();
    if (beforeRecovery !== 0) throw new Error('new-chat control did not clear the prior assistant response');
    await page.waitForFunction(() => {
      const input = document.querySelector('#chat-input');
      return input && !input.disabled && !document.querySelector('#message-input-container button[aria-label="Stop"]');
    }, null, { timeout: 10000 });
    const recoveryRequest = page.waitForRequest(
      request => request.method() === 'POST' && new URL(request.url()).pathname.endsWith('/api/chat/completions'),
      { timeout: 10000 },
    ).catch(() => null);
    await page.locator('#chat-input').fill('hello recovery');
    await page.locator('#chat-input').press('Enter');
    if (!await recoveryRequest) throw new Error(`recovery prompt was not submitted; chat request count=${chatRequests.length}`);
    const recoveryDeadline = Date.now() + 15000;
    let recoveryText = '';
    while (Date.now() < recoveryDeadline) {
      const nodes = page.locator('#response-content-container .markdown-prose');
      const count = await nodes.count();
      const stop = await page.locator('#message-input-container button[aria-label="Stop"]').count();
      recoveryText = count > beforeRecovery ? ((await nodes.last().innerText()).trim()) : '';
      if (count > beforeRecovery && recoveryText && !stop) break;
      await page.waitForTimeout(300);
    }
    recovery = await page.evaluate(() => ({
      stop: Boolean(document.querySelector('#message-input-container button[aria-label="Stop"]')),
      text: [...document.querySelectorAll('#response-content-container .markdown-prose')].at(-1)?.innerText?.trim() || '',
      composer: document.querySelector('#chat-input')?.value || '',
    }));
    recovery.new_response = Boolean(recoveryText && recovery.text === recoveryText);
  }
  const passed = state.visibleError && !state.stop
    && (!recovery || (recovery.new_response && recovery.text && !recovery.stop));
  console.log(JSON.stringify({ status: passed ? 'PASS' : 'FAIL', prompt, waitMs, aborted, state, recovery, errors, chatRequests }));
  // A failed provider can leave a websocket teardown pending in the browser
  // runtime. The result above is already complete and must not be hidden by
  // harness cleanup; force the test process to terminate after reporting it.
  process.exit(passed ? 0 : 1);
})().catch(error => {
  console.error(JSON.stringify({ status: 'ERROR', error: error.message }));
  // Playwright can keep Chromium pipe handles alive after navigation errors.
  // Exit so the disposable fixture's shell trap can clean up reliably.
  process.exit(1);
});
