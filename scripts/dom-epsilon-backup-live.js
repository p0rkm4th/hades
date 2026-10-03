#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');
// The API calls below append absolute-looking paths, so keep one canonical
// base form even when operators provide a trailing slash.
const base = (process.env.HADES_DOM_BASE_URL || 'http://127.0.0.1:3000/').replace(/\/$/, '');
const root = process.env.HADES_DOM_CREDENTIAL_DIR || require('path').join(require('os').homedir(), '.config', 'hades-dom');
const user = (process.env.HADES_EPSILON_DOM_USER || 'owner').toLowerCase();
const userFiles = user === 'householda' || user === 'household-a'
  ? ['HADES_EPSILON_HOUSEHOLD_A_EMAIL', 'HADES_EPSILON_HOUSEHOLD_A_PASSWORD', 'household-a-email', 'household-a-password']
  : user === 'householdb' || user === 'household-b'
    ? ['HADES_EPSILON_HOUSEHOLD_B_EMAIL', 'HADES_EPSILON_HOUSEHOLD_B_PASSWORD', 'household-b-email', 'household-b-password']
    : ['HADES_EPSILON_ACCEPTANCE_OWNER_EMAIL', 'HADES_EPSILON_ACCEPTANCE_OWNER_PASSWORD', 'acceptance-owner-email', 'acceptance-owner-password'];
const get = (name, fallback) => process.env[name] || fs.readFileSync(path.join(root, fallback), 'utf8').trim();
const target = process.env.HADES_EPSILON_BACKUP_TARGET || 'HADES';
(async () => {
  const browser = await chromium.launch({headless: true});
  const context = await browser.newContext({ignoreHTTPSErrors: true, viewport: {width: Number(process.env.HADES_DOM_WIDTH || 1440), height: Number(process.env.HADES_DOM_HEIGHT || 900)}});
  const page = await context.newPage();
  let activeChatRequests = 0;
  const debug = process.env.HADES_DOM_DEBUG === '1';
  page.on('console', message => { if (debug) console.error('BROWSER', message.type(), message.text()); });
  page.on('pageerror', error => { if (debug) console.error('PAGEERROR', error.message); });
  page.on('request', request => { if (/chat\/completions/i.test(request.url())) activeChatRequests++; if (debug && /chat|completion|auth|socket/i.test(request.url())) console.error('REQ', request.method(), request.url()); });
  page.on('response', response => { if (/chat\/completions/i.test(response.url())) activeChatRequests = Math.max(0, activeChatRequests - 1); if (debug && /chat|completion|auth|socket/i.test(response.url())) console.error('RESP', response.status(), response.url()); });
  const signed = await fetch(`${base}/api/v1/auths/ldap`, {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({user: process.env[userFiles[0]] || fs.readFileSync(path.join(root, userFiles[2]), 'utf8').trim(), password: process.env[userFiles[1]] || fs.readFileSync(path.join(root, userFiles[3]), 'utf8').trim()})});
  if (!signed.ok) throw new Error(`sign-in HTTP ${signed.status}`);
  const auth = await signed.json();
  await context.addCookies([{name: 'token', value: auth.token, domain: new URL(base).hostname, path: '/'}]);
  await page.goto(`${base}/`, {waitUntil: 'commit', timeout: 30000});
  await page.waitForSelector('#chat-input', {timeout: 30000});
  const newChat = page.locator('[aria-label="New Chat"]:visible, button:has-text("New Chat"):visible, a:has-text("New Chat"):visible');
  if (await newChat.count()) await newChat.last().click().catch(() => {});
  await page.waitForTimeout(500);
  async function send(prompt) {
    const before = await page.locator('#response-content-container .markdown-prose').count();
    if (debug) console.error('SEND', prompt, 'before', before);
    await page.locator('#chat-input').fill(prompt);
    const submit = page.locator('button[type="submit"]:visible');
    if (await submit.count()) await submit.last().click();
    else await page.locator('#chat-input').press('Enter');
    await page.waitForTimeout(500);
    if (prompt.includes('verify')) {
      const buttons = await page.locator('button:visible').evaluateAll(items => items.map(item => ({text: item.innerText, aria: item.getAttribute('aria-label'), type: item.getAttribute('type')})).slice(-15));
      if (debug) console.error('BUTTONS', JSON.stringify(buttons));
    }
    const end = Date.now() + Number(process.env.HADES_EPSILON_DOM_WAIT_MS || 60000);
    while (Date.now() < end) {
      const nodes = page.locator('#response-content-container .markdown-prose');
      if (await nodes.count() > before && !(await page.locator('#message-input-container button[aria-label="Stop"]').count()) && activeChatRequests === 0) {
        await page.waitForTimeout(1800);
        if (activeChatRequests === 0 && !(await page.locator('#message-input-container button[aria-label="Stop"]').count())) return (await nodes.last().innerText()).trim();
      }
      await page.waitForTimeout(300);
    }
    throw new Error(`timeout for ${prompt}; body=${(await page.locator('body').innerText()).slice(-2200)}`);
  }
  const prompts = process.env.HADES_EPSILON_DOM_PROMPTS ? JSON.parse(process.env.HADES_EPSILON_DOM_PROMPTS) : [`what ${target} backup checks do I have?`, `verify my ${target} backup every morning`, 'yes', `inspect ${target} backup`, `run ${target} backup`, 'yes', `pause ${target} backup`, 'yes', `resume ${target} backup`, 'yes', `change ${target} backup to every 2 days`, 'yes', `what did ${target} backup history say?`, `delete ${target} backup`, 'yes'];
  for (const prompt of prompts) console.log(prompt, JSON.stringify((await send(prompt)).slice(-1000)));
  await browser.close();
})().catch(error => { console.error(error.stack || error); process.exit(1); });
