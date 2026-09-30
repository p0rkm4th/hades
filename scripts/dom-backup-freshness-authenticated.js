#!/usr/bin/env node

/* Authenticated owner-equivalent read-only backup freshness acceptance. */
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const base = (process.env.HADES_BACKUP_UI_BASE_URL || '').replace(/\/$/, '');
const email = process.env.HADES_BACKUP_UI_EMAIL;
const password = process.env.HADES_BACKUP_UI_PASSWORD;
const modelId = process.env.HADES_BACKUP_UI_MODEL_ID;
const expectedBefore = process.env.HADES_BACKUP_UI_DB_SHA256;
const stateFile = process.env.HADES_BACKUP_UI_STATE_FILE;
if (!base || !email || !password || !modelId || !expectedBefore || !stateFile) {
  throw new Error('synthetic backup UI inputs are required');
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  try {
    const login = await fetch(`${base}/api/v1/auths/signin`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!login.ok) throw new Error(`synthetic owner login failed: HTTP ${login.status}`);
    const { token } = await login.json();
    const context = await browser.newContext({ viewport: { width: 1365, height: 850 } });
    try {
      await context.addCookies([{ name: 'token', value: token, url: `${base}/` }]);
      const page = await context.newPage();
      await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForSelector('#chat-input', { timeout: 30000 });
      const welcome = page.getByRole('button', { name: /okay,\s*let.s go/i });
      if (await welcome.count()) await welcome.first().click({ force: true });
      const choose = page.getByRole('button', { name: /select a model/i });
      if (await choose.count()) {
        await choose.first().click();
        const option = page.getByText(modelId, { exact: true }).last();
        await option.waitFor({ state: 'visible', timeout: 10000 });
        await option.click();
      }
      const prompts = [process.env.HADES_BACKUP_UI_PROMPT || 'Do we have a recent backup?'];
      const answers = [];
      for (const prompt of prompts) {
        const messages = page.locator('#response-content-container .markdown-prose');
        const before = await messages.count();
        await page.locator('#chat-input').fill(prompt);
        const send = page.locator('#send-message-button:visible');
        if (await send.count()) await send.last().click({ force: true });
        else await page.locator('#chat-input').press('Enter');
        const deadline = Date.now() + 30000;
        let text = '';
        while (Date.now() < deadline) {
          const current = page.locator('#response-content-container .markdown-prose');
          if (await current.count() > before) text = (await current.last().innerText()).trim();
          const streaming = await page.locator('#message-input-container button[aria-label="Stop"]').count();
          if (text && !streaming) break;
          await page.waitForTimeout(200);
        }
        if (!/HADES repository backup:\s*healthy/i.test(text)) {
          throw new Error(`backup freshness answer omitted the canonical healthy state for ${JSON.stringify(prompt)}: ${text}`);
        }
        if (!/last successful check 2026-09-25 12:34 UTC/i.test(text)) {
          throw new Error(`backup freshness answer omitted the canonical check time for ${JSON.stringify(prompt)}: ${text}`);
        }
        if (!/Infrastructure repository backup:\s*stale and needs attention/i.test(text)) {
          throw new Error(`backup freshness answer hid the stale infrastructure backup for ${JSON.stringify(prompt)}: ${text}`);
        }
        if (!/last successful check 2026-09-25 12:00 UTC/i.test(text) || !/latest check 2026-09-26 12:34 UTC/i.test(text)) {
          throw new Error(`backup freshness answer omitted stale-state history for ${JSON.stringify(prompt)}: ${text}`);
        }
        if (/shall i run|should i run|do you want me to run/i.test(text)) {
          throw new Error(`read-only freshness question was turned into a run action for ${JSON.stringify(prompt)}: ${text}`);
        }
        answers.push({ prompt, answer: text });
      }
      const after = await fetch(`${base}/api/v1/chats/?page=1`, {
        headers: { authorization: `Bearer ${token}` },
      });
      if (!after.ok) throw new Error(`authenticated chat history failed: HTTP ${after.status}`);
      const payload = await after.json();
      const rows = Array.isArray(payload) ? payload : (payload.items || payload.chats || []);
      const persistedPrompts = new Set();
      for (const chat of rows.slice(0, 10)) {
        const id = chat.id || chat.chat_id;
        if (!id) continue;
        const detail = await fetch(`${base}/api/v1/chats/${encodeURIComponent(id)}`, {
          headers: { authorization: `Bearer ${token}` },
        });
        if (detail.ok) {
          const serializedChat = JSON.stringify(await detail.json());
          for (const prompt of prompts) if (serializedChat.includes(prompt)) persistedPrompts.add(prompt);
        }
      }
      if (!prompts.every(prompt => persistedPrompts.has(prompt))) throw new Error('all isolated backup freshness prompts did not persist in authenticated history');
      const fs = require('node:fs');
      const crypto = require('node:crypto');
      const stateHash = crypto.createHash('sha256').update(fs.readFileSync(stateFile)).digest('hex');
      if (stateHash !== expectedBefore) throw new Error('read-only freshness route changed lifecycle database bytes');
      const report = {
        status: 'PASS',
        prompts: answers,
        authenticatedChatPersistence: 'PASS',
        modelInvocation: 'NONE (direct canonical status route for each turn)',
        stateDatabaseSha256Before: expectedBefore,
        stateDatabaseSha256After: stateHash,
      };
      const out = process.env.HADES_BACKUP_UI_REPORT || '/tmp/hades-backup-freshness-ui.json';
      fs.writeFileSync(out, `${JSON.stringify(report, null, 2)}\n`, { mode: 0o600 });
      fs.chmodSync(out, 0o600);
      console.log(JSON.stringify({ status: 'PASS', report: out, answers: answers.length }));
    } finally {
      await context.close();
    }
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  console.error(JSON.stringify({ status: 'FAIL', error: error.message }));
  process.exitCode = 1;
});
