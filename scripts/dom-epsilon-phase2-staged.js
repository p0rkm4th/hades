#!/usr/bin/env node

/* Reusable authenticated Phase 2 DOM matrix. It is intentionally staged:
 * no flow in this harness is allowed to enable a production schedule. */
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const base = process.env.HADES_DOM_BASE_URL || 'http://127.0.0.1:3000/';
const root = process.env.HADES_DOM_CREDENTIAL_DIR || require('path').join(require('os').homedir(), '.config', 'hades-dom');
const users = {
  owner: ['acceptance-owner-email', 'acceptance-owner-password'],
  householdA: ['household-a-email', 'household-a-password'],
  householdB: ['household-b-email', 'household-b-password'],
};
const viewports = [
  ['desktop', 1440, 900], ['tablet', 768, 1024],
  ['mobile390', 390, 844], ['mobile320', 320, 568],
];
const flows = ['preview', 'confirm', 'list', 'inspect', 'run-now', 'pause', 'resume', 'edit', 'delete', 'history', 'sharing', 'revocation'];

function credential(name) {
  return process.env[`HADES_EPSILON_${name.replaceAll('-', '_').toUpperCase()}`]
    || fs.readFileSync(path.join(root, name), 'utf8').trim();
}
async function login(page, emailName, passwordName) {
  const response = await fetch(`${base}/api/v1/auths/ldap`, { method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({user: credential(emailName), password: credential(passwordName)}) });
  if (!response.ok) throw new Error(`authenticated session setup failed: HTTP ${response.status}`);
  const body = await response.json();
  if (!body.token) throw new Error('authenticated session setup returned no token');
  await page.context().addCookies([{name: 'token', value: body.token, domain: new URL(base).hostname, path: '/'}]);
  await page.goto(`${base}/`, { waitUntil: 'commit', timeout: 30000 });
  await page.waitForSelector('#chat-input', { timeout: 30000 });
}
async function send(page, prompt) {
  const before = await page.locator('#response-content-container .markdown-prose').count();
  await page.locator('#chat-input').fill(prompt);
  const submit = page.locator('button[type="submit"]:visible');
  if (await submit.count()) await submit.last().click();
  else await page.locator('#chat-input').press('Enter');
  const deadline = Date.now() + Number(process.env.HADES_EPSILON_DOM_WAIT_MS || 45000);
  while (Date.now() < deadline) {
    const nodes = page.locator('#response-content-container .markdown-prose');
    if (await nodes.count() > before && !(await page.locator('#message-input-container button[aria-label="Stop"]').count())) { await page.waitForTimeout(900); return (await nodes.last().innerText()).trim(); }
    await page.waitForTimeout(350);
  }
  throw new Error(`turn did not settle: ${prompt}; tail=${(await page.locator('body').innerText()).slice(-1800)}`);
}
async function newChat(page) {
  const buttons = page.locator('[aria-label="New Chat"]:visible, button:has-text("New Chat"):visible, a:has-text("New Chat"):visible');
  if (await buttons.count()) await buttons.last().click().catch(() => {});
  await page.waitForTimeout(500);
}

async function main() {
  if (process.argv.includes('--plan')) {
    console.log(JSON.stringify({ production_enablement: false, users: Object.keys(users), viewports, flows, fixtures: require('../config/epsilon-phase2-fixtures.json') }, null, 2));
    return;
  }
  const browser = await chromium.launch({ headless: true });
  const results = [];
  try {
    for (const [user, [email, password]] of Object.entries(users)) {
      for (const [viewport, width, height] of viewports) {
        const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width, height } });
        const page = await context.newPage();
        await login(page, email, password);
        await newChat(page);
        let discovery = await send(page, user === 'owner' ? 'what backup checks do I have?' : 'show shared backup checks');
        if (/external email|sms|shell|agent zero|automatic remediation/i.test(discovery)) throw new Error(`${user}/${viewport}: unauthorized capability advertised`);
        if (!process.env.HADES_EPSILON_DOM_DISCOVERY_ONLY && user === 'owner' && viewport === 'desktop') {
          const preview = await send(page, 'verify my HADES backup every morning');
          if (!/Backup Check|Create it/i.test(preview)) throw new Error('backup preview did not render');
          const confirmed = await send(page, 'yes');
          if (!/Created.*Backup Check|already exists|enabled/i.test(confirmed)) throw new Error('backup confirmation did not settle');
          discovery = await send(page, 'what backup checks do I have?');
        }
        results.push({ user, viewport, discovery: discovery.slice(0, 500), production_enablement: false });
        await context.close();
      }
    }
  } finally { await browser.close(); }
  console.log(JSON.stringify(results, null, 2));
}
main().catch(error => { console.error(error.stack || error); process.exit(1); });
