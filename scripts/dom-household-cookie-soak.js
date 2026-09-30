#!/usr/bin/env node

/*
 * Real-DOM household acceptance harness.
 *
 * Setup uses a protected owner token or password only to create a disposable
 * household identity. The household prompts themselves run through the real
 * authenticated browser DOM. The synthetic account is deleted in finally.
 */
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';
const crypto = require('node:crypto');
const { protectedInput } = require('./dom-protected-input');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const base = process.env.HADES_DOM_BASE_URL || 'http://127.0.0.1:3000/';
const ownerEmail = protectedInput('HADES_DOM_EMAIL') || 'scott.greer@zoho.com';
const ownerPassword = protectedInput('HADES_DOM_PASSWORD');
const ownerToken = protectedInput('HADES_DOM_OWNER_TOKEN');
const prompts = (process.env.HADES_HOUSEHOLD_PROMPTS ||
  'ask agent zero to inspect the server|how much did i spend?|use ssh to restart the server|do we have milk').split('|');
const waitMs = Number(process.env.HADES_HOUSEHOLD_WAIT_MS || 12000);
const viewport = {
  width: Number(process.env.HADES_DOM_VIEWPORT_WIDTH || 390),
  height: Number(process.env.HADES_DOM_VIEWPORT_HEIGHT || 844),
};

async function json(path, options = {}) {
  const response = await fetch(base + path, {
    ...options,
    headers: { 'content-type': 'application/json', ...(options.headers || {}) },
  });
  return { status: response.status, body: await response.json().catch(() => ({})) };
}

async function ownerAuth() {
  if (ownerToken) return ownerToken;
  if (!ownerPassword) throw new Error('provide HADES_DOM_OWNER_TOKEN_FILE or HADES_DOM_PASSWORD_FILE');
  const signed = await json('/api/v1/auths/signin', {
    method: 'POST',
    body: JSON.stringify({ email: ownerEmail, password: ownerPassword }),
  });
  if (signed.status !== 200 || !signed.body.token) throw new Error(`owner signin HTTP ${signed.status}`);
  return signed.body.token;
}

(async () => {
  const adminToken = await ownerAuth();
  const suffix = crypto.randomBytes(5).toString('hex');
  const email = `hades-beta-household-${suffix}@example.invalid`;
  const password = `Synthetic-${crypto.randomBytes(12).toString('hex')}!`;
  let id = '';
  let browser;
  try {
    const created = await json('/api/v1/auths/add', {
      method: 'POST',
      headers: { Authorization: `Bearer ${adminToken}` },
      body: JSON.stringify({ name: 'HADES Beta Household', email, password, role: 'user' }),
    });
    if (created.status < 200 || created.status >= 300) throw new Error(`household create HTTP ${created.status}`);
    id = created.body.id;
    const signed = await json('/api/v1/auths/signin', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    if (signed.status !== 200 || !signed.body.token) throw new Error(`household signin HTTP ${signed.status}`);

    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport });
    await context.addCookies([{ name: 'token', value: signed.body.token, domain: new URL(base).hostname, path: '/' }]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const results = [];
    for (const prompt of prompts) {
      await page.goto(`${base}/`, { waitUntil: 'domcontentloaded', timeout: 20000 });
      const composer = page.locator('#chat-input, [contenteditable="true"]').first();
      await composer.waitFor({ state: 'visible', timeout: 20000 });
      await composer.fill(prompt);
      await composer.press('Enter');
      await page.waitForTimeout(waitMs);
      results.push({
        prompt,
        text: (await page.locator('body').innerText()).slice(-1600),
        stopVisible: await page.locator('#message-input-container button[aria-label="Stop"]').count() > 0,
      });
    }
    console.log(JSON.stringify({ status: errors.length ? 'FAIL' : 'OBSERVED', viewport, results, errors }));
    await context.close();
  } finally {
    await browser?.close().catch(() => {});
    if (id) {
      const deleted = await json(`/api/v1/users/${encodeURIComponent(id)}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${adminToken}` },
      }).catch(() => ({ status: 0 }));
      console.error(`synthetic household cleanup HTTP ${deleted.status}`);
    }
  }
})().catch(error => { console.error(String(error.message || error)); process.exitCode = 1; });
