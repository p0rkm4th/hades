#!/usr/bin/env node

/* One bounded, read-only multi-user/device soak. Consequential actions are
 * intentionally covered by the dedicated authorized Phase 2 probe instead. */
const fs = require('node:fs');
const crypto = require('node:crypto');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const base = process.env.HADES_DOM_BASE_URL || 'http://127.0.0.1:3000/';
const root = process.env.HADES_DOM_CREDENTIAL_DIR || require('path').join(require('os').homedir(), '.config', 'hades-dom');
const waitMs = Number(process.env.HADES_COMBINED_SOAK_WAIT_MS || 60000);
const users = {
  owner: ['acceptance-owner-email', 'acceptance-owner-password'],
  householdA: ['household-a-email', 'household-a-password'],
  householdB: ['household-b-email', 'household-b-password'],
};
const ownerPrompts = [
  'Give me my HADES morning briefing.',
  'What should I handle first, and why?',
  'What is running on my homelab right now?',
  'Something feels slow on the network; what looks abnormal?',
  'List my recipes and tell me which ones I can make right now.',
  'What food is going to expire in the next 7 days?',
  'Give me a household restock report.',
  'Show me subscriptions and recurring charges from my uploaded statement.',
];

function secret(name) { return fs.readFileSync(`${root}/${name}`, 'utf8').trim(); }
function digest(value) { return crypto.createHash('sha256').update(value).digest('hex').slice(0, 10); }

async function login(context, emailName, passwordName) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  const response = await fetch(`${base}/api/v1/auths/ldap`, {
    method: 'POST', headers: {'content-type': 'application/json'},
    body: JSON.stringify({ user: secret(emailName), password: secret(passwordName) }),
    signal: controller.signal,
  });
  clearTimeout(timeout);
  if (!response.ok) throw new Error(`login HTTP ${response.status}`);
  const body = await response.json();
  await context.addCookies([{ name: 'token', value: body.token, domain: new URL(base).hostname, path: '/' }]);
}

async function fresh(page) {
  await page.goto(`${base}/`, { waitUntil: 'commit', timeout: 30000 });
  await page.waitForSelector('#chat-input', { timeout: 30000 });
  const button = page.locator('[aria-label="New Chat"]:visible, #new-chat-button:visible, button:has-text("New Chat"):visible');
  if (await button.count()) await button.last().click().catch(() => {});
  const deadline = Date.now() + 5000;
  while (Date.now() < deadline && await page.locator('#response-content-container .markdown-prose').count()) await page.waitForTimeout(250);
  if (await page.locator('#response-content-container .markdown-prose').count()) {
    const retry = page.locator('[aria-label="New Chat"], #new-chat-button, button:has-text("New Chat")').last();
    if (await retry.count()) await retry.click({ force: true }).catch(() => {});
    await page.waitForTimeout(700);
  }
}

async function turn(page, prompt, doubleSubmit = false) {
  const nodes = page.locator('#response-content-container .markdown-prose');
  const before = await nodes.count();
  const baseline = ((await nodes.allTextContents()).at(-1) || '').trim();
  page.__done = false;
  await page.locator('#chat-input').fill(prompt);
  const submit = page.locator('button[type="submit"]:visible, #send-message-button:visible');
  if (!await submit.count()) await page.locator('#chat-input').press('Enter');
  else {
    await submit.last().click();
    if (doubleSubmit) await submit.last().click().catch(() => {});
  }
  const end = Date.now() + waitMs;
  while (Date.now() < end) {
    const current = page.locator('#response-content-container .markdown-prose');
    const texts = await current.allTextContents();
    const last = (texts.at(-1) || '').trim();
    const stop = await page.locator('#message-input-container button[aria-label="Stop"]').count();
    if (last && (texts.length > before || last !== baseline) && !stop) {
      await page.waitForTimeout(800);
      return { status: 'SETTLED', digest: digest(last), chars: last.length, excerpt: last.replace(/\s+/g, ' ').slice(0, 180) };
    }
    await page.waitForTimeout(300);
  }
  throw new Error(`timeout for ${prompt}`);
}

const results = [];
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    for (const [label, width, height] of [['desktop', 1440, 900], ['mobile390', 390, 844], ['mobile320', 320, 568]]) {
      const contexts = {};
      const pages = {};
      for (const [user, [email, password]] of Object.entries(users)) {
        contexts[user] = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width, height } });
        pages[user] = await contexts[user].newPage();
        pages[user].on('websocket', socket => socket.on('framereceived', data => {
          const frame = String(data);
          if (frame.includes('chat:completion') && (frame.includes('"done":true') || frame.includes('"finish_reason":"stop"'))) pages[user].__done = true;
        }));
        await login(contexts[user], email, password);
        await fresh(pages[user]);
      }
      const ownerCases = label === 'desktop' ? ownerPrompts : [
        'What should I handle first from my HADES morning briefing?',
        'Show the latest weekly household summary.',
      ];
      for (const prompt of ownerCases) results.push({ viewport: label, user: 'owner', prompt, ...(await turn(pages.owner, prompt)) });
      if (label === 'desktop') {
        results.push({ viewport: label, user: 'owner', prompt: 'what backup checks do I have?', double_submit: true, ...(await turn(pages.owner, 'what backup checks do I have?', true)) });
        const stale = pages.owner;
        const recovery = await contexts.owner.newPage();
        await fresh(recovery);
        const abandoned = turn(stale, 'Which server is the best place for another local AI model?').catch(() => ({ status: 'ABANDONED' }));
        await stale.waitForTimeout(1200);
        await stale.close().catch(() => {});
        results.push({ viewport: label, user: 'owner', prompt: 'hello after stale-tab abandonment', ...(await turn(recovery, 'hello')) });
        await abandoned;
        await recovery.close();
      }
      results.push({ viewport: label, user: 'householdA', prompt: 'show the latest weekly household summary', ...(await turn(pages.householdA, 'show the latest weekly household summary')) });
      results.push({ viewport: label, user: 'householdB', prompt: 'show the latest weekly household summary', ...(await turn(pages.householdB, 'show the latest weekly household summary')) });
      for (const context of Object.values(contexts)) await context.close();
    }
  } finally { await browser.close(); }
  const denied = results.filter(row => row.user === 'householdB').every(row => /no shared|not available|owner can create/i.test(row.excerpt));
  const settled = results.filter(row => row.status === 'SETTLED').length;
  console.log(JSON.stringify({ status: denied && settled === results.length ? 'PASS' : 'FAIL', total: results.length, settled, householdB_denied: denied, results }, null, 2));
})().catch(error => { console.error(JSON.stringify({ status: 'FAIL', error: error.message, results })); process.exitCode = 1; });
