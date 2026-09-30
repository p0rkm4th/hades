#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const base = process.env.HADES_DOM_BASE_URL || 'http://127.0.0.1:3000/';
const root = process.env.HADES_DOM_CREDENTIAL_DIR || require('path').join(require('os').homedir(), '.config', 'hades-dom');
const target = process.env.HADES_EPSILON_BACKUP_TARGET || 'Infrastructure';
const email = process.env.HADES_EPSILON_ACCEPTANCE_OWNER_EMAIL || fs.readFileSync(path.join(root, 'acceptance-owner-email'), 'utf8').trim();
const password = process.env.HADES_EPSILON_ACCEPTANCE_OWNER_PASSWORD || fs.readFileSync(path.join(root, 'acceptance-owner-password'), 'utf8').trim();

async function openTab(browser) {
  const context = await browser.newContext({ignoreHTTPSErrors: true, viewport: {width: 390, height: 844}});
  const page = await context.newPage();
  const signed = await fetch(`${base}/api/v1/auths/ldap`, {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({user: email, password})});
  if (!signed.ok) throw new Error(`signin ${signed.status}`);
  const auth = await signed.json();
  await context.addCookies([{name: 'token', value: auth.token, domain: new URL(base).hostname, path: '/'}]);
  await page.goto(`${base}/`, {waitUntil: 'commit', timeout: 30000});
  await page.waitForSelector('#chat-input', {timeout: 30000});
  const newChat = page.locator('[aria-label="New Chat"]:visible, button:has-text("New Chat"):visible, a:has-text("New Chat"):visible');
  if (await newChat.count()) await newChat.last().click().catch(() => {});
  await page.waitForTimeout(500);
  return {context, page};
}

async function send(page, prompt) {
  const before = await page.locator('#response-content-container .markdown-prose').count();
  await page.locator('#chat-input').fill(prompt);
  const submit = page.locator('button[type="submit"]:visible');
  if (await submit.count()) await submit.last().click(); else await page.locator('#chat-input').press('Enter');
  const end = Date.now() + 60000;
  while (Date.now() < end) {
    const nodes = page.locator('#response-content-container .markdown-prose');
    if (await nodes.count() > before && !(await page.locator('#message-input-container button[aria-label="Stop"]').count())) {
      await page.waitForTimeout(1800);
      if (!(await page.locator('#message-input-container button[aria-label="Stop"]').count())) return (await nodes.last().innerText()).trim();
    }
    await page.waitForTimeout(300);
  }
  throw new Error(`timeout ${prompt}`);
}

(async () => {
  const browser = await chromium.launch({headless: true});
  const stale = await openTab(browser);
  const mutator = await openTab(browser);
  try {
    const stalePreview = await send(stale.page, `pause ${target} backup`);
    const deletedPreview = await send(mutator.page, `remove ${target} backup`);
    const deleted = await send(mutator.page, `yes, delete ${target} backup`);
    const staleConfirmation = await send(stale.page, 'yes');
    console.error(JSON.stringify({stalePreview, deletedPreview, deleted, staleConfirmation}, null, 2));
    if (!/no longer exists|old confirmation|current HADES state/i.test(staleConfirmation)) {
      throw new Error(`stale confirmation was not rejected: ${staleConfirmation}`);
    }
    console.log(JSON.stringify({stalePreview, deletedPreview, deleted, staleConfirmation}, null, 2));
  } finally {
    await stale.context.close(); await mutator.context.close(); await browser.close();
  }
})().catch(error => { console.error(error.stack || error); process.exit(1); });
