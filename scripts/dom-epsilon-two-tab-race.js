#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.HADES_DOM_BASE_URL || 'http://127.0.0.1:3000/';
const root = process.env.HADES_DOM_CREDENTIAL_DIR || require('path').join(require('os').homedir(), '.config', 'hades-dom');
const email = process.env.HADES_EPSILON_ACCEPTANCE_OWNER_EMAIL || fs.readFileSync(path.join(root, 'acceptance-owner-email'), 'utf8').trim();
const password = process.env.HADES_EPSILON_ACCEPTANCE_OWNER_PASSWORD || fs.readFileSync(path.join(root, 'acceptance-owner-password'), 'utf8').trim();
const target = process.env.HADES_EPSILON_BACKUP_TARGET || 'Infrastructure';

async function openTab(browser) {
  const context = await browser.newContext({ignoreHTTPSErrors: true, viewport: {width: 390, height: 844}});
  const page = await context.newPage();
  const signed = await fetch(`${base}/api/v1/auths/ldap`, {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({user: email, password})});
  if (!signed.ok) throw new Error(`signin ${signed.status}`);
  const auth = await signed.json();
  await context.addCookies([{name: 'token', value: auth.token, domain: new URL(base).hostname, path: '/'}]);
  await page.goto(`${base}/`, {waitUntil: 'commit', timeout: 30000});
  await page.waitForSelector('#chat-input', {timeout: 30000});
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
  const a = await openTab(browser); const b = await openTab(browser);
  try {
    const prompts = await Promise.all([
      send(a.page, `resume ${target} backup`),
      send(b.page, `pause ${target} backup`),
    ]);
    if (process.env.HADES_RACE_PAUSE_MS) {
      console.log(JSON.stringify({prompts}, null, 2));
      await new Promise(resolve => setTimeout(resolve, Number(process.env.HADES_RACE_PAUSE_MS)));
    }
    const confirmations = await Promise.all([send(a.page, 'yes'), send(b.page, 'yes')]);
    console.log(JSON.stringify({prompts, confirmations}, null, 2));
  } finally { await a.context.close(); await b.context.close(); await browser.close(); }
})().catch(error => { console.error(error.stack || error); process.exit(1); });
