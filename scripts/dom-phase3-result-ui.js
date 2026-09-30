#!/usr/bin/env node

/* Authenticated disposable Open WebUI acceptance for Phase 3 result delivery. */
const fs = require('node:fs');
const playwrightModule = process.env.HADES_PHASE3_PLAYWRIGHT_MODULE || 'playwright';
const { chromium } = require(playwrightModule);

const base = (process.env.HADES_PHASE3_UI_BASE_URL || '').replace(/\/$/, '');
const modelId = process.env.HADES_PHASE3_UI_MODEL_ID || '';
const password = process.env.HADES_PHASE3_UI_PASSWORD || '';
const report = process.env.HADES_PHASE3_UI_REPORT || '/tmp/hades-phase3-result-ui.json';
const users = {
  alpha: process.env.HADES_PHASE3_UI_ALPHA_EMAIL || '',
  beta: process.env.HADES_PHASE3_UI_BETA_EMAIL || '',
  gamma: process.env.HADES_PHASE3_UI_GAMMA_EMAIL || '',
};
const mode = process.env.HADES_PHASE3_UI_MODE || 'initial';
let alphaNotificationVerified = false;
if (!base || !modelId || !password || Object.values(users).some(value => !value)) {
  throw new Error('disposable URL, model ID, and synthetic Alpha/Beta/Gamma accounts are required');
}

async function query(browser, account) {
  const response = await fetch(`${base}/api/v1/auths/signin`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ email: users[account], password }),
  });
  if (!response.ok) throw new Error(`${account} sign-in failed: HTTP ${response.status}`);
  const { token } = await response.json();
  if (!token) throw new Error(`${account} sign-in returned no token`);
  const tokenPayload = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString('utf8'));
  const userId = String(tokenPayload.id || '');
  if (!userId) throw new Error(`${account} sign-in returned no stable subject`);
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  try {
    await context.addCookies([{ name: 'token', value: token, url: `${base}/` }]);
    const page = await context.newPage();
    await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForSelector('#chat-input', { timeout: 30000 });
    if (mode === 'revoked-beta') {
      const stateKey = `hades-automation-notification-state:${userId}`;
      await page.evaluate(key => localStorage.setItem(key, JSON.stringify({ ['a'.repeat(64)]: 'b'.repeat(64) })), stateKey);
      await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
      try {
        await page.waitForFunction(key => {
          try { return Object.keys(JSON.parse(localStorage.getItem(key) || '{}')).length === 0; } catch (_) { return false; }
        }, stateKey, { timeout: 15000 });
      } catch (error) {
        const debug = await page.evaluate(key => ({
          installed: Boolean(window.__hadesAutomationNotificationsInstalled),
          state: localStorage.getItem(key),
          currentUserId: (() => { try { return JSON.parse(atob(localStorage.getItem('token').split('.')[1])).id || ''; } catch (_) { return ''; } })(),
          responseText: document.getElementById('hades-automation-notification')?.innerText || '',
        }), stateKey);
        throw new Error(`revoked Beta notification state did not clear (${JSON.stringify(debug)}): ${error.message}`);
      }
      if (await page.locator('#hades-automation-notification').count()) {
        throw new Error('revoked Beta retained a Phase 3 notification after access was withdrawn');
      }
    }
    const welcome = page.getByRole('button', { name: /okay,\s*let.s go/i });
    if (await welcome.count()) await welcome.first().click({ force: true });
    if (account === 'alpha' && mode === 'initial') {
      const stateKey = `hades-automation-notification-state:${userId}`;
      const routeProbe = await page.evaluate(async () => {
        const response = await fetch('/api/v1/hades/automations/notifications', {
          credentials: 'same-origin', headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }, cache: 'no-store'
        });
        let body;
        try { body = await response.json(); } catch (_) { body = { invalid: true }; }
        return { status: response.status, body };
      });
      if (routeProbe.status !== 200 || routeProbe.body?.error) {
        throw new Error(`Alpha Phase 3 notification route returned HTTP ${routeProbe.status}: ${JSON.stringify(routeProbe.body)}`);
      }
      await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
      try {
        await page.waitForFunction(key => localStorage.getItem(key) !== null, stateKey, { timeout: 15000 });
      } catch (error) {
        const debug = await page.evaluate(key => ({
          installed: Boolean(window.__hadesAutomationNotificationsInstalled),
          state: localStorage.getItem(key),
          currentUserId: (() => { try { return JSON.parse(atob(localStorage.getItem('token').split('.')[1])).id || ''; } catch (_) { return ''; } })(),
          responseText: document.getElementById('hades-automation-notification')?.innerText || '',
        }), stateKey);
        throw new Error(`Alpha notification baseline was not stored (${JSON.stringify(debug)}): ${error.message}`);
      }
      const feedResponse = await page.evaluate(async () => fetch('/api/v1/hades/automations/notifications', {
        credentials: 'same-origin', headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }, cache: 'no-store'
      }).then(response => response.json()));
      if (feedResponse.notifications?.filter(row => row.title === 'Grocery Summary').length !== 1) {
        throw new Error(`Alpha received duplicate historical states for the same Grocery Summary: ${JSON.stringify(feedResponse)}`);
      }
      const item = feedResponse.notifications?.find(row => row.actionable && row.title === 'Grocery Summary');
      if (!item || !item.message.includes('1 item(s) below minimum')) {
        throw new Error(`Alpha did not receive its requester-scoped actionable Phase 3 result: ${JSON.stringify(feedResponse)}`);
      }
      await page.evaluate(({ key, sourceKey }) => {
        const current = JSON.parse(localStorage.getItem(key) || '{}');
        current[sourceKey] = '0'.repeat(64);
        localStorage.setItem(key, JSON.stringify(current));
        document.dispatchEvent(new Event('visibilitychange'));
      }, { key: stateKey, sourceKey: item.source_key });
      const notice = page.locator('#hades-automation-notification');
      await notice.waitFor({ state: 'visible', timeout: 15000 });
      const noticeText = await notice.innerText();
      if (!noticeText.includes('Grocery Summary: Grocy found 1 item(s) below minimum')) {
        throw new Error(`Alpha automation alert omitted its safe result summary: ${noticeText}`);
      }
      await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
      await page.waitForTimeout(300);
      if (await page.locator('#hades-automation-notification').count() !== 1) {
        throw new Error('repeated Phase 3 notification poll created a duplicate alert');
      }
      await notice.getByRole('button', { name: 'Review in HADES' }).click();
      if ((await page.locator('#chat-input').innerText()).trim() !== 'Show me my latest automation results') {
        throw new Error('Phase 3 notification did not prefill the safe results review prompt');
      }
      await page.evaluate(() => {
        const nativeFetch = window.fetch.bind(window);
        let held = false;
        window.__hadesReleaseStaleAutomation403 = null;
        window.fetch = (input, init) => {
          const url = typeof input === 'string' ? input : input?.url || '';
          if (!held && url.includes('/api/v1/hades/automations/notifications')) {
            held = true;
            return new Promise(resolve => {
              window.__hadesReleaseStaleAutomation403 = () => resolve(new Response('', { status: 403 }));
            });
          }
          return nativeFetch(input, init);
        };
        document.dispatchEvent(new Event('visibilitychange'));
      });
      await page.waitForFunction(() => typeof window.__hadesReleaseStaleAutomation403 === 'function', null, { timeout: 5000 });
      const betaSignin = await fetch(`${base}/api/v1/auths/signin`, {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ email: users.beta, password }),
      });
      if (!betaSignin.ok) throw new Error(`Beta sign-in for account-switch check failed: HTTP ${betaSignin.status}`);
      const betaToken = (await betaSignin.json()).token;
      if (!betaToken) throw new Error('Beta sign-in for account-switch check returned no token');
      const betaUserId = String(JSON.parse(Buffer.from(betaToken.split('.')[1], 'base64url').toString('utf8')).id || '');
      if (!betaUserId || betaUserId === userId) throw new Error('Alpha/Beta account-switch check requires distinct stable subjects');
      await page.evaluate(token => {
        localStorage.setItem('token', token);
        document.dispatchEvent(new Event('visibilitychange'));
      }, betaToken);
      const betaStateKey = `hades-automation-notification-state:${betaUserId}`;
      await page.waitForFunction(key => localStorage.getItem(key) !== null, betaStateKey, { timeout: 15000 });
      if (await page.locator('#hades-automation-notification').count()) {
        const leaked = await page.locator('#hades-automation-notification').innerText();
        if (/Grocy found 1 item\(s\) below minimum/.test(leaked)) {
          throw new Error('Alpha notification content survived switching the browser session to Beta');
        }
        throw new Error(`a stale notification remained visible after switching to Beta: ${leaked}`);
      }
      await page.evaluate(({ key, sourceKey }) => {
        const current = JSON.parse(localStorage.getItem(key) || '{}');
        current[sourceKey] = '0'.repeat(64);
        localStorage.setItem(key, JSON.stringify(current));
        document.dispatchEvent(new Event('visibilitychange'));
      }, { key: betaStateKey, sourceKey: item.source_key });
      const betaNotice = page.locator('#hades-automation-notification');
      await betaNotice.waitFor({ state: 'visible', timeout: 15000 });
      await page.evaluate(() => window.__hadesReleaseStaleAutomation403?.());
      await page.waitForTimeout(300);
      const afterStaleAlpha403 = await page.evaluate(() => ({
        notice: document.getElementById('hades-automation-notification')?.innerText || '',
        tokenUserId: (() => { try { return JSON.parse(atob(localStorage.getItem('token').split('.')[1])).id || ''; } catch (_) { return ''; } })(),
      }));
      if (afterStaleAlpha403.tokenUserId !== betaUserId || !afterStaleAlpha403.notice.includes('Grocery Summary: Grocy found 1 item(s) below minimum')) {
        throw new Error(`late Alpha authorization failure cleared Beta's Phase 3 alert: ${JSON.stringify(afterStaleAlpha403)}`);
      }
      await page.evaluate(sourceKey => {
        const nativeFetch = window.fetch.bind(window);
        let intercepted = false;
        window.fetch = (input, init) => {
          const url = typeof input === 'string' ? input : input?.url || '';
          if (!intercepted && url.includes('/api/v1/hades/automations/notifications')) {
            intercepted = true;
            return Promise.resolve(new Response(JSON.stringify({ version: 1, notifications: [{
              source_key: sourceKey,
              state_key: 'c'.repeat(64),
              actionable: false,
              title: 'Grocery Summary',
              message: '',
            }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
          }
          return nativeFetch(input, init);
        };
        document.dispatchEvent(new Event('visibilitychange'));
      }, item.source_key);
      await page.waitForFunction(({ key, sourceKey }) => {
        try { return JSON.parse(localStorage.getItem(key) || '{}')[sourceKey] === 'c'.repeat(64); }
        catch (_) { return false; }
      }, { key: betaStateKey, sourceKey: item.source_key }, { timeout: 5000 });
      if (await page.locator('#hades-automation-notification').count()) {
        const staleRecoveryNotice = await page.locator('#hades-automation-notification').innerText();
        throw new Error(`recovered Phase 3 source left a stale Beta alert visible: ${staleRecoveryNotice}`);
      }
      await page.evaluate(token => {
        localStorage.setItem('token', token);
        document.dispatchEvent(new Event('visibilitychange'));
      }, token);
      alphaNotificationVerified = true;
    }
    const chooseModel = page.getByRole('button', { name: /select a model/i });
    if (await chooseModel.count()) {
      await chooseModel.first().click();
      const option = page.getByText(modelId, { exact: true }).last();
      await option.waitFor({ state: 'visible', timeout: 10000 });
      await option.click();
    }
    const newChat = page.locator('[aria-label="New Chat"]:visible, button:has-text("New Chat"):visible');
    if (await newChat.count()) await newChat.last().click({ force: true });
    await page.locator('#chat-input').fill('Show my latest automation results');
    await page.locator('#send-message-button').click({ force: true });
    const selector = '#response-content-container .markdown-prose';
    const deadline = Date.now() + 45000;
    let answer = '';
    while (Date.now() < deadline) {
      const bubbles = page.locator(selector);
      const count = await bubbles.count();
      answer = count ? (await bubbles.last().innerText()).trim() : '';
      const streaming = await page.locator('#message-input-container button[aria-label="Stop"]').count();
      if (answer && !streaming) break;
      await page.waitForTimeout(250);
    }
    if (!answer) throw new Error(`${account} result query did not settle`);
    return answer;
  } finally {
    await context.close();
  }
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    if (mode === 'revoked-beta') {
      const beta = await query(browser, 'beta');
      if (!/no completed automation results/i.test(beta) || beta.includes('Synthetic Rice')) {
        throw new Error('revoked Beta still received the previously shared result');
      }
      fs.writeFileSync(report, `${JSON.stringify({ status: 'PASS', betaNoLongerSeesSharedResult: true }, null, 2)}\n`, { mode: 0o600 });
    } else if (mode === 'initial') {
      const results = {
        alpha: await query(browser, 'alpha'),
        beta: await query(browser, 'beta'),
        gamma: await query(browser, 'gamma'),
      };
      for (const account of ['alpha', 'beta']) {
        if (!results[account].includes('Synthetic Rice') || !results[account].includes('1 item(s) below minimum')) {
          throw new Error(`${account} did not receive the permitted synthetic result`);
        }
      }
      if (!/no completed automation results/i.test(results.gamma) || results.gamma.includes('Synthetic Rice')) {
        throw new Error('unshared Gamma received a protected result');
      }
      if (/run_id|automation_id/.test(JSON.stringify(results))) {
        throw new Error('internal run identifiers appeared in the user interface');
      }
      if (!alphaNotificationVerified) throw new Error('Phase 3 result notification was not verified in Alpha UI');
      fs.writeFileSync(report, `${JSON.stringify({ status: 'PASS', checks: results, phase3Notification: 'fresh actionable result appears once; opens an unsent review prompt; late Alpha 403 preserves Beta alert; recovered source clears stale alert' }, null, 2)}\n`, { mode: 0o600 });
    } else {
      throw new Error('HADES_PHASE3_UI_MODE must be initial or revoked-beta');
    }
    fs.chmodSync(report, 0o600);
    console.log(JSON.stringify({ status: 'PASS', mode, report }));
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(JSON.stringify({ status: 'FAIL', error: error.message }));
  process.exitCode = 1;
});
