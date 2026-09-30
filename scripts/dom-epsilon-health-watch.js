#!/usr/bin/env node

/* Fresh authenticated DOM acceptance for the typed Server Health Watch lane. */
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const base = process.env.HADES_DOM_BASE_URL || 'http://127.0.0.1:3000/';
const root = process.env.HADES_DOM_CREDENTIAL_DIR || require('path').join(require('os').homedir(), '.config', 'hades-dom');
const waitMs = Number(process.env.HADES_EPSILON_DOM_WAIT_MS || 45000);
const credentials = name => {
  const override = name === 'acceptance-owner-email' ? process.env.HADES_EPSILON_OWNER_EMAIL
    : name === 'acceptance-owner-password' ? process.env.HADES_EPSILON_OWNER_PASSWORD
      : name === 'household-a-email' ? process.env.HADES_EPSILON_HOUSEHOLD_EMAIL
        : name === 'household-a-password' ? process.env.HADES_EPSILON_HOUSEHOLD_PASSWORD : '';
  return override || fs.readFileSync(path.join(root, name), 'utf8').trim();
};

async function login(page, emailName, passwordName) {
  await page.goto(`${base}/`, { waitUntil: 'commit', timeout: 30000 });
  await page.waitForSelector('#username, input[type="email"], #chat-input, button:has-text("Continue with Email")', { timeout: 30000 });
  // Prefer the configured LDAP form when it is present. The page also
  // advertises a generic email path, but selecting it would bypass the
  // authenticated acceptance route used by the other live DOM harnesses.
  if (await page.locator('#username').count()) {
    await page.locator('#username').fill(credentials(emailName));
    await page.locator('#password').fill(credentials(passwordName));
    await page.getByRole('button', { name: /authenticate/i }).click();
  } else {
    const emailPath = page.getByRole('button', { name: 'Continue with Email', exact: true });
    if (await emailPath.count()) {
    await emailPath.click();
    await page.waitForSelector('input[type="email"]', { timeout: 10000 });
    await page.locator('input[type="email"]').fill(credentials(emailName));
    await page.locator('input[type="password"]').fill(credentials(passwordName));
    await page.locator('button[type="submit"], button:has-text("Sign in")').first().click();
    } else if (await page.locator('input[type="email"]').count()) {
    await page.locator('input[type="email"]').fill(credentials(emailName));
    await page.locator('input[type="password"]').fill(credentials(passwordName));
    await page.locator('button[type="submit"], button:has-text("Sign in")').first().click();
    }
  }
  await page.waitForSelector('#chat-input', { timeout: 30000 });
}

async function newChat(page) {
  const hiddenButton = page.locator('#new-chat-button');
  const buttons = page.locator('[aria-label="New Chat"]:visible, button:has-text("New Chat"):visible, a:has-text("New Chat"):visible');
  const target = await hiddenButton.count() ? hiddenButton : buttons;
  if (await target.count()) await target.last().click({ force: true }).catch(() => {});
  await page.waitForTimeout(300);
}

async function send(page, prompt) {
  const before = await page.locator('#response-content-container .markdown-prose').count();
  const input = page.locator('#chat-input');
  await input.waitFor({ state: 'visible', timeout: 15000 });
  await input.fill(prompt);
  if (before === 0) await input.press('Enter');
  else {
    const submit = page.locator('#send-message-button:visible');
    if (await submit.count()) await submit.click({ force: true });
    else await input.press('Enter');
  }
  const deadline = Date.now() + waitMs;
  while (Date.now() < deadline) {
    const nodes = page.locator('#response-content-container .markdown-prose');
    const count = await nodes.count();
    const stop = await page.locator('#message-input-container button[aria-label="Stop"]').count();
    if (count > before && !stop) return (await nodes.last().innerText()).trim();
    await page.waitForTimeout(350);
  }
  throw new Error(`turn did not settle: ${prompt}; tail=${(await page.locator('body').innerText()).slice(-1800)}`);
}

function requireText(text, pattern, label) {
  if (!pattern.test(text)) throw new Error(`${label}: ${JSON.stringify(text.slice(-1200))}`);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const results = [];
  try {
    for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }, { width: 768, height: 1024 }]) {
      const ownerContext = await browser.newContext({ ignoreHTTPSErrors: true, viewport });
      const owner = await ownerContext.newPage();
      const errors = [];
      owner.on('pageerror', e => errors.push(e.message));
      await login(owner, 'acceptance-owner-email', 'acceptance-owner-password');
      await newChat(owner);

      if (viewport.width === 1440 && process.env.HADES_EPSILON_SKIP_CREATE !== '1') {
        // Reuse the canonical 15-minute owner watch; the test must not create
        // a second interval merely to exercise the lifecycle.
        const preview = await send(owner, 'watch HADES Core health every 15 minutes');
        requireText(preview, /Server Health Watch/i, `preview ${viewport.width}`);
        requireText(preview, /Create it\?/i, `confirmation ${viewport.width}`);
        const created = await send(owner, 'yes, create it');
        requireText(created, /Created.*HADES Core Watch|already active.*no duplicate/i, `create ${viewport.width}`);
      }
      const inventory = await send(owner, 'what am I monitoring?');
      requireText(inventory, /HADES Core Watch/i, `inventory ${viewport.width}`);
      const checked = await send(owner, 'run HADES Core check');
      requireText(checked, /Shall I run/i, `run confirmation ${viewport.width}`);
      const checkResult = await send(owner, 'yes');
      requireText(checkResult, /check ran.*up/i, `run result ${viewport.width}`);
      results.push({ viewport, owner: 'PASS', errors });
      await ownerContext.close();
    }

    const ownerContext = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1440, height: 900 } });
    const owner = await ownerContext.newPage();
    await login(owner, 'acceptance-owner-email', 'acceptance-owner-password');
    await newChat(owner);
    const sharePrompt = await send(owner, 'share HADES Core Watch with household-a');
    requireText(sharePrompt, /Shall I share/i, 'share confirmation');
    const shared = await send(owner, 'yes');
    requireText(shared, /Updated sharing|already active.*no duplicate/i, 'share result');
    await ownerContext.close();

    const householdContext = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 390, height: 844 } });
    const household = await householdContext.newPage();
    await login(household, 'household-a-email', 'household-a-password');
    await newChat(household);
    const sharedInventory = await send(household, 'what am I monitoring?');
    requireText(sharedInventory, /HADES Core Watch/i, 'household shared inventory');
    const denied = await send(household, 'run HADES Core check');
    requireText(denied, /view-only|did not change|not available/i, 'household view-only denial');
    await householdContext.close();

    const revokeContext = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1440, height: 900 } });
    const revokeOwner = await revokeContext.newPage();
    await login(revokeOwner, 'acceptance-owner-email', 'acceptance-owner-password');
    await newChat(revokeOwner);
    const revokePrompt = await send(revokeOwner, 'revoke HADES Core Watch from household-a');
    requireText(revokePrompt, /Shall I revoke/i, 'revoke confirmation');
    const revoked = await send(revokeOwner, 'yes');
    requireText(revoked, /Revoked/i, 'revoke result');
    await revokeContext.close();

    console.log(JSON.stringify({ status: 'PASS', results, sharing: 'PASS', viewOnly: 'PASS', revocation: 'PASS' }));
  } finally {
    await browser.close().catch(() => {});
  }
})().catch(error => { console.error(String(error.stack || error)); process.exitCode = 1; });
