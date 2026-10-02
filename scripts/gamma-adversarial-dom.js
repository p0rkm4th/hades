#!/usr/bin/env node

/*
 * Bounded Gamma adversarial browser pass.
 *
 * This intentionally uses only the production login page and rendered DOM.
 * Credentials are read from protected 0600 files and are never included in
 * results.  The runner keeps contexts alive so conversation/session state,
 * navigation, and cross-user behavior are part of the evidence.
 */
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const base = process.env.HADES_DOM_BASE_URL || 'http://127.0.0.1:3000/';
const outDir = process.env.HADES_GAMMA_ARTIFACT_DIR || '/tmp/hades-gamma-adversarial';
const waitMs = Number(process.env.HADES_GAMMA_WAIT_MS || 15000);
fs.mkdirSync(outDir, { recursive: true, mode: 0o700 });

const users = {
  ownerA: ['acceptance-owner-email', 'acceptance-owner-password', { width: 1440, height: 900 }],
  ownerB: ['acceptance-owner-email', 'acceptance-owner-password', { width: 1440, height: 900 }],
  householdA: ['household-a-email', 'household-a-password', { width: 1440, height: 900 }],
  householdB: ['household-b-email', 'household-b-password', { width: 1440, height: 900 }],
  householdMobile: ['household-a-email', 'household-a-password', { width: 390, height: 844 }],
};

function credential(name) {
  const file = require('path').join(process.env.HADES_DOM_CREDENTIAL_DIR || require('path').join(require('os').homedir(), '.config', 'hades-dom'), name);
  const stat = fs.statSync(file);
  if ((stat.mode & 0o077) !== 0) throw new Error(`credential permissions too broad: ${name}`);
  return fs.readFileSync(file, 'utf8').trim();
}

function cleanText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim().slice(-3000);
}

async function login(page, email, password) {
  await page.goto(`${base}/`, { waitUntil: 'commit', timeout: 30000 });
  await page.waitForSelector('#username, input[type="email"], #chat-input', { timeout: 30000 });
  if (await page.locator('#username').count()) {
    await page.locator('#username').fill(email);
    await page.locator('#password').fill(password);
    await page.getByRole('button', { name: /authenticate/i }).click();
  } else if (await page.locator('input[type="email"]').count()) {
    await page.locator('input[type="email"]').fill(email);
    await page.locator('input[type="password"]').fill(password);
    await page.locator('button[type="submit"], button:has-text("Sign in")').first().click();
  }
  await page.waitForSelector('#chat-input', { timeout: 30000 });
}

async function newConversation(page) {
  const candidates = page.locator('[aria-label="New Chat"]:visible, button:has-text("New Chat"):visible, a:has-text("New Chat"):visible');
  if (await candidates.count()) await candidates.last().click({ timeout: 3000 }).catch(() => {});
  await page.waitForTimeout(400);
}

async function domState(page) {
  return page.evaluate(() => {
    const nodes = [...document.querySelectorAll('#response-content-container .markdown-prose')];
    const body = document.body.innerText || '';
    return {
      url: location.pathname,
      stop: Boolean(document.querySelector('#message-input-container button[aria-label="Stop"]')),
      composer: document.querySelector('#chat-input')?.innerText || document.querySelector('#chat-input')?.value || '',
      assistantCount: nodes.length,
      lastAssistant: nodes.at(-1)?.innerText?.trim() || '',
      tail: body.slice(-1600),
    };
  });
}

async function send(page, prompt, label, timeout = waitMs) {
  const started = Date.now();
  const before = await page.locator('#response-content-container .markdown-prose').count();
  const input = page.locator('#chat-input');
  await input.waitFor({ state: 'visible', timeout: 15000 });
  await input.click();
  await input.fill(prompt);
  await input.press('Enter');
  let last = await domState(page);
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    last = await domState(page);
    const fresh = last.assistantCount > before && last.lastAssistant;
    if (fresh && !last.stop) {
      return { label, prompt, status: 'PASS', elapsedMs: Date.now() - started, state: last };
    }
    await page.waitForTimeout(400);
  }
  return { label, prompt, status: 'FAIL', elapsedMs: Date.now() - started, reason: 'turn did not settle', state: last };
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const contexts = [];
  const results = [];
  try {
    const pages = {};
    for (const [label, [emailName, passwordName, viewport]] of Object.entries(users)) {
      console.error(`SETUP ${label}`);
      const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport });
      contexts.push(context);
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', e => errors.push({ type: 'pageerror', message: e.message, stack: e.stack || '' }));
      page.on('console', m => { if (m.type() === 'error') errors.push({ type: 'console', message: m.text() }); });
      await login(page, credential(emailName), credential(passwordName));
      await newConversation(page);
      pages[label] = { page, errors };
      console.error(`READY ${label}`);
    }

    const cases = [
      ['ownerA', 'hey'],
      ['ownerA', 'what can I do here?'],
      ['householdA', 'grocry?'],
      ['householdB', 'we got eggs?'],
      ['ownerB', 'what food do we have'],
      ['householdA', 'add milk'],
      ['householdA', 'actually dont'],
      ['householdB', 'what did we add?'],
      ['ownerB', 'remember my test color is cobalt'],
      ['ownerB', 'what was the thing i said'],
      ['householdB', 'ask Agent Zero to inspect the server'],
      ['householdA', "show me the owner's private checking"],
      ['ownerA', 'show my servers'],
      ['householdMobile', 'is the server thing working'],
    ];
    for (const [label, prompt] of cases) {
      const result = await send(pages[label].page, prompt, `${label}:${prompt}`);
      result.browserErrors = pages[label].errors.splice(0);
      results.push(result);
      fs.writeFileSync(path.join(outDir, 'gamma-adversarial-progress.json'), JSON.stringify(results, null, 2), { mode: 0o600 });
      console.error(`${result.status} ${result.label} ${result.elapsedMs}ms`);
    }

    // Navigation/re-entry on a live household context, then an unrelated turn.
    const reentry = pages.householdA.page;
    await reentry.reload({ waitUntil: 'commit', timeout: 30000 });
    await reentry.waitForSelector('#chat-input', { timeout: 30000 });
    const reentryResult = { ...(await send(reentry, 'did that actually work?', 'householdA:reload-follow-up')), browserErrors: pages.householdA.errors.splice(0) };
    results.push(reentryResult);
    fs.writeFileSync(path.join(outDir, 'gamma-adversarial-progress.json'), JSON.stringify(results, null, 2), { mode: 0o600 });
    console.error(`${reentryResult.status} ${reentryResult.label} ${reentryResult.elapsedMs}ms`);

    // Cross-user turns are concurrent but bounded; no API shortcuts are used.
    const concurrentCases = [
      ['ownerA', 'explain DNS simply', 'ownerA:concurrent-fast'],
      ['householdA', 'what is on the grocery list', 'householdA:concurrent-grocy'],
      ['householdB', 'hello?', 'householdB:concurrent-chat'],
      ['householdMobile', 'what can we cook tonight?', 'householdMobile:concurrent-recipe'],
    ];
    const concurrent = await Promise.all(concurrentCases.map(([label, prompt, resultLabel]) =>
      send(pages[label].page, prompt, resultLabel).then(result => ({
        ...result,
        browserErrors: pages[label].errors.splice(0),
      }))
    ));
    results.push(...concurrent);
    fs.writeFileSync(path.join(outDir, 'gamma-adversarial-progress.json'), JSON.stringify(results, null, 2), { mode: 0o600 });

    const summary = {
      status: results.some(r => r.status === 'FAIL') ? 'FAIL' : 'PASS',
      base,
      sessions: Object.fromEntries(Object.entries(pages).map(([k, v]) => [k, { errors: v.errors.length }])),
      results,
    };
    fs.writeFileSync(path.join(outDir, 'gamma-adversarial-dom.json'), JSON.stringify(summary, null, 2), { mode: 0o600 });
    console.log(JSON.stringify({ status: summary.status, resultCount: results.length, failures: results.filter(r => r.status === 'FAIL').map(r => ({ label: r.label, reason: r.reason, tail: r.state?.tail })) }));
    return summary.status === 'PASS' ? 0 : 1;
  } finally {
    for (const context of contexts) await context.close().catch(() => {});
    await browser.close();
  }
}

run().then(code => { process.exitCode = code; }).catch(error => {
  console.error(JSON.stringify({ status: 'ERROR', error: error.message }));
  process.exitCode = 1;
});
