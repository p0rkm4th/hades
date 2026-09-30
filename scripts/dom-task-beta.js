#!/usr/bin/env node

/* Authenticated DOM acceptance for Beta task history and explicit task IDs.
 * This script deliberately has no production URL or credential defaults. */
const fs = require('node:fs');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const base = (process.env.HADES_BETA_DOM_BASE_URL || '').replace(/\/$/, '');
const report = process.env.HADES_BETA_DOM_REPORT || '/tmp/hades-task-beta-dom.json';
const accounts = {
  alpha: [process.env.HADES_BETA_ALPHA_EMAIL, process.env.HADES_BETA_ALPHA_PASSWORD],
  beta: [process.env.HADES_BETA_BETA_EMAIL, process.env.HADES_BETA_BETA_PASSWORD],
  gamma: [process.env.HADES_BETA_GAMMA_EMAIL, process.env.HADES_BETA_GAMMA_PASSWORD],
};

for (const [name, [email, password]] of Object.entries(accounts)) {
  if (!email || !password) throw new Error(`missing synthetic ${name} credentials`);
}
if (!base || !/^https?:\/\//.test(base)) {
  throw new Error('HADES_BETA_DOM_BASE_URL must name the disposable Open WebUI endpoint');
}

async function login(browser, accountName) {
  const [email, password] = accounts[accountName];
  const response = await fetch(`${base}/api/v1/auths/signin`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw new Error(`${accountName} login failed: HTTP ${response.status}`);
  const body = await response.json();
  if (!body.token) throw new Error(`${accountName} login returned no session token`);

  const context = await browser.newContext({
    ignoreHTTPSErrors: base.startsWith('https://'),
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();
  await context.addCookies([{ name: 'token', value: body.token, url: `${base}/` }]);
  await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForSelector('#chat-input', { timeout: 30000 });
  const welcome = page.getByRole('button', { name: /okay,\s*let.s go/i });
  if (await welcome.count()) {
    await welcome.first().click({ force: true });
    await page.waitForTimeout(300);
  }
  return { context, page };
}

async function ask(browser, accountName, prompt) {
  const { context, page } = await login(browser, accountName);
  try {
    const selector = '#response-content-container .markdown-prose';
    const before = await page.locator(selector).count();
    const beforeText = before ? (await page.locator(selector).last().innerText()).trim() : '';
    await page.locator('#chat-input').fill(prompt);
    await page.locator('#send-message-button').click({ force: true });

    const deadline = Date.now() + Number(process.env.HADES_BETA_DOM_WAIT_MS || 45000);
    while (Date.now() < deadline) {
      const responses = page.locator(selector);
      const count = await responses.count();
      const latest = count ? (await responses.last().innerText()).trim() : '';
      const stop = await page.locator('#message-input-container button[aria-label="Stop"]').count();
      if ((count > before || latest !== beforeText) && latest && !stop) {
        await page.waitForTimeout(400);
        return (await responses.last().innerText()).trim();
      }
      await page.waitForTimeout(300);
    }
    throw new Error(`turn did not settle for ${accountName}: ${prompt}; tail=${(await page.locator('body').innerText()).slice(-900)}`);
  } finally {
    await context.close();
  }
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const alpha = {};
    alpha.recent = await ask(browser, 'alpha', 'list my tasks');
    alpha.completed = await ask(browser, 'alpha', 'show completed tasks');
    alpha.inspect = await ask(browser, 'alpha', 'show task task-alpha-completed01');
    alpha.foreignId = await ask(browser, 'alpha', 'show task task-beta-private001');
    alpha.ambiguousCancel = await ask(browser, 'alpha', 'cancel task');
    alpha.cancel = await ask(browser, 'alpha', 'cancel task task-alpha-cancel003');
    alpha.cancelledStatus = await ask(browser, 'alpha', 'show task task-alpha-cancel003');
    const beta = await ask(browser, 'beta', 'list my tasks');
    const gamma = await ask(browser, 'gamma', 'list my tasks');

    if (!alpha.recent.includes('task-alpha-completed01') || !alpha.recent.includes('task-alpha-active002') || !alpha.recent.includes('task-alpha-cancel003') || alpha.recent.includes('task-beta-private001')) {
      throw new Error('Alpha recent task history is missing or crosses actor scope');
    }
    if (!alpha.completed.includes('task-alpha-completed01') || alpha.completed.includes('task-alpha-active001')) {
      throw new Error('completed-task filter did not isolate completed Alpha tasks');
    }
    if (!/status: completed/i.test(alpha.inspect)) throw new Error('explicit task-ID inspection did not show status');
    if (!/couldn.t find a task/i.test(alpha.foreignId) || alpha.foreignId.includes('task-beta-private001')) {
      throw new Error('foreign task-ID lookup disclosed task existence');
    }
    if (!/which task should i cancel/i.test(alpha.ambiguousCancel)) throw new Error('ambiguous cancellation did not ask for a task ID');
    if (!/(cancelled the task|already cancelled)/i.test(alpha.cancel) || !/status: cancelled/i.test(alpha.cancelledStatus)) {
      throw new Error('explicit cancellation or fresh-session status read failed');
    }
    if (!beta.includes('task-beta-private001') || beta.includes('task-alpha-completed01') || beta.includes('task-gamma-private001')) {
      throw new Error('Beta task history is missing or crosses actor scope');
    }
    if (!gamma.includes('task-gamma-private001') || gamma.includes('task-alpha-completed01') || gamma.includes('task-beta-private001')) {
      throw new Error('Gamma task history is missing or crosses actor scope');
    }

    const result = { status: 'PASS', checks: alpha, beta, gamma };
    fs.writeFileSync(report, `${JSON.stringify(result, null, 2)}\n`, { mode: 0o600 });
    fs.chmodSync(report, 0o600);
    console.log(JSON.stringify({ status: result.status, report }));
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(JSON.stringify({ status: 'FAIL', error: error.message }));
  process.exitCode = 1;
});
