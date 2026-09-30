#!/usr/bin/env node

/* Synthetic authenticated UI proof that bare confirmations stay chat-scoped. */
const fs = require('node:fs');
const crypto = require('node:crypto');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const base = (process.env.HADES_CONFIRM_UI_BASE_URL || '').replace(/\/$/, '');
const email = process.env.HADES_CONFIRM_UI_EMAIL;
const password = process.env.HADES_CONFIRM_UI_PASSWORD;
const modelId = process.env.HADES_CONFIRM_UI_MODEL_ID;
const stateFile = process.env.HADES_CONFIRM_UI_STATE_FILE;
const events = [];
if (!base || !email || !password || !modelId || !stateFile) {
  throw new Error('synthetic confirmation UI inputs are required');
}

const sha256 = () => crypto.createHash('sha256').update(fs.readFileSync(stateFile)).digest('hex');

async function waitForChatReady(page) {
  await page.waitForFunction(() => {
    const input = document.querySelector('#chat-input');
    const stop = document.querySelector('#message-input-container button[aria-label="Stop"]');
    return input && !input.disabled && !stop;
  }, null, { timeout: 10000 });
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

      async function ask(prompt, expected, targetPage = page) {
        const selector = '#response-content-container .markdown-prose';
        const before = await targetPage.locator(selector).count();
        await waitForChatReady(targetPage);
        const input = targetPage.locator('#chat-input');
        await input.fill(prompt);
        const submission = targetPage.waitForRequest(
          request => request.method() === 'POST' && new URL(request.url()).pathname.endsWith('/api/chat/completions'),
          { timeout: 10000 },
        ).catch(() => null);
        await input.press('Enter');
        if (!await submission) {
          const diagnostic = await targetPage.evaluate(() => ({
            url: location.href,
            inputDisabled: document.querySelector('#chat-input')?.disabled ?? null,
            inputValue: document.querySelector('#chat-input')?.value ?? null,
            sendDisabled: document.querySelector('#send-message-button')?.disabled ?? null,
            stopVisible: Boolean(document.querySelector('#message-input-container button[aria-label="Stop"]')),
          }));
          throw new Error(`Open WebUI did not submit ${JSON.stringify(prompt)}: ${JSON.stringify(diagnostic)}`);
        }
        const deadline = Date.now() + 30000;
        while (Date.now() < deadline) {
          const messages = targetPage.locator(selector);
          if (await messages.count() > before) {
            const text = (await messages.last().innerText()).trim();
            const streaming = await targetPage.locator('#message-input-container button[aria-label="Stop"]').count();
            if (text && !streaming) {
              if (!expected.test(text)) throw new Error(`unexpected answer to ${JSON.stringify(prompt)}: ${text}`);
              events.push({ prompt, answer: text, url: targetPage.url() });
              return text;
            }
          }
          await targetPage.waitForTimeout(200);
        }
        const diagnostic = await targetPage.evaluate(() => ({
          url: location.href,
          bodyTail: document.body.innerText.slice(-600),
          inputValue: document.querySelector('#chat-input')?.value ?? null,
          stopVisible: Boolean(document.querySelector('#message-input-container button[aria-label="Stop"]')),
        }));
        throw new Error(`no settled answer for ${JSON.stringify(prompt)} after Open WebUI submission: ${JSON.stringify(diagnostic)}`);
      }

      async function persistedChatId(expectedText) {
        const chatsResponse = await fetch(`${base}/api/v1/chats/?page=1`, {
          headers: { authorization: `Bearer ${token}` },
        });
        if (!chatsResponse.ok) throw new Error(`authenticated chat list failed: HTTP ${chatsResponse.status}`);
        const payload = await chatsResponse.json();
        const rows = Array.isArray(payload) ? payload : (payload.items || payload.chats || []);
        for (const chat of rows.slice(0, 15)) {
          const id = chat.id || chat.chat_id;
          if (!id) continue;
          const detail = await fetch(`${base}/api/v1/chats/${encodeURIComponent(id)}`, {
            headers: { authorization: `Bearer ${token}` },
          });
          if (detail.ok && JSON.stringify(await detail.json()).toLowerCase().includes(expectedText.toLowerCase())) return id;
        }
        throw new Error(`authenticated chat history did not persist ${JSON.stringify(expectedText)}`);
      }

      const firstPrompt = await ask('Run Backup Check.', /shall i run it now/i);
      const stateHashBeforeCrossChat = sha256();
      const firstChatId = await persistedChatId('Shall I run it now?');
      const firstUrl = `${base}/c/${encodeURIComponent(firstChatId)}`;

      const secondPage = await context.newPage();
      await secondPage.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await secondPage.waitForSelector('#chat-input', { timeout: 15000 });
      if (await secondPage.locator('#response-content-container .markdown-prose').count()) {
        const newChat = secondPage.locator('[aria-label="New Chat"]:visible, #new-chat-button:visible, button:has-text("New Chat"):visible, a:has-text("New Chat"):visible').last();
        await newChat.waitFor({ state: 'attached', timeout: 10000 });
        await newChat.click({ force: true });
        await secondPage.waitForTimeout(500);
      }
      const secondChoose = secondPage.getByRole('button', { name: /select a model/i });
      if (await secondChoose.count()) {
        await secondChoose.first().click();
        const option = secondPage.getByText(modelId, { exact: true }).last();
        await option.waitFor({ state: 'visible', timeout: 10000 });
        await option.click();
      }
      const crossChatAnswer = await ask('Yes.', /couldn.t match that confirmation/i, secondPage);
      const secondChatId = await persistedChatId("couldn't match that confirmation");
      if (firstChatId === secondChatId) throw new Error('the two prompts were persisted in the same Open WebUI conversation');
      const afterCrossChat = sha256();
      if (afterCrossChat !== stateHashBeforeCrossChat) {
        throw new Error('cross-chat yes changed the pending lifecycle state');
      }

      await page.goto(firstUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForSelector('#chat-input', { timeout: 15000 });
      await waitForChatReady(page);
      if (!/Shall I run it now\?/i.test(await page.locator('body').innerText())) {
        throw new Error('reloaded first chat did not restore its pending confirmation transcript');
      }
      const decline = await ask('No.', /nothing was changed/i);
      const afterDecline = sha256();
      if (afterDecline === afterCrossChat) throw new Error('same-chat decline did not clear its pending confirmation');

      const report = {
        status: 'PASS',
        firstConversationId: firstChatId,
        secondConversationId: secondChatId,
        firstPromptAnswer: firstPrompt,
        crossChatConfirmationAnswer: crossChatAnswer,
        stateSha256BeforeAndAfterCrossChatYes: stateHashBeforeCrossChat,
        sameChatDeclineAnswer: decline,
        stateSha256AfterDecline: afterDecline,
        userTurnModelInvocation: 'NONE; the configured synthetic model endpoint was intentionally unreachable',
      };
      const out = process.env.HADES_CONFIRM_UI_REPORT || '/tmp/hades-phase2-confirmation-isolation.json';
      fs.writeFileSync(out, `${JSON.stringify(report, null, 2)}\n`, { mode: 0o600 });
      fs.chmodSync(out, 0o600);
      console.log(JSON.stringify({ status: 'PASS', report: out }));
    } finally {
      await context.close();
    }
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  const out = process.env.HADES_CONFIRM_UI_REPORT || '/tmp/hades-phase2-confirmation-isolation.json';
  try {
    fs.writeFileSync(out, `${JSON.stringify({ status: 'FAIL', error: error.message, events }, null, 2)}\n`, { mode: 0o600 });
    fs.chmodSync(out, 0o600);
  } catch {}
  console.error(JSON.stringify({ status: 'FAIL', error: error.message, report: out, events }));
  process.exitCode = 1;
});
