#!/usr/bin/env node

/* Authenticated synthetic Hindsight memory UI acceptance (never production). */
const fs = require('node:fs');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');
const credentialsPath = process.env.HADES_HINDSIGHT_UI_CREDENTIALS_FILE || '';
let fixtureUsers = {};
if (credentialsPath) {
  const metadata = fs.lstatSync(credentialsPath);
  if (!metadata.isFile() || metadata.isSymbolicLink() || (metadata.mode & 0o077) !== 0) {
    throw new Error('HADES_HINDSIGHT_UI_CREDENTIALS_FILE must be a private regular file');
  }
  const fixture = JSON.parse(fs.readFileSync(credentialsPath, 'utf8'));
  if (fixture.synthetic_only !== true || !fixture.users || typeof fixture.users !== 'object') {
    throw new Error('HADES_HINDSIGHT_UI_CREDENTIALS_FILE must contain a synthetic household fixture');
  }
  fixtureUsers = fixture.users;
}

const base = (process.env.HADES_HINDSIGHT_UI_BASE_URL || '').replace(/\/$/, '');
const password = process.env.HADES_HINDSIGHT_UI_PASSWORD;
const modelId = process.env.HADES_HINDSIGHT_UI_MODEL_ID;
const report = process.env.HADES_HINDSIGHT_UI_REPORT || '/tmp/hades-hindsight-explicit-ui.json';
const identityNames = {
  alpha: 'hades-reconstruction-alpha',
  beta: 'hades-reconstruction-beta',
  gamma: 'hades-reconstruction-gamma',
};
const users = {
  alpha: { own: 'pear', foreign: ['mango'] },
  beta: { own: '', foreign: ['mango', 'pear'] },
  gamma: { own: '', foreign: ['mango', 'pear'] },
};
for (const [account, user] of Object.entries(users)) {
  const identity = identityNames[account];
  const fixtureUser = fixtureUsers[identity] || {};
  user.username = identity;
  user.email = process.env[`HADES_HINDSIGHT_UI_${account.toUpperCase()}_EMAIL`] || fixtureUser.email || '';
  user.password = process.env[`HADES_HINDSIGHT_UI_${account.toUpperCase()}_PASSWORD`] || fixtureUser.password || password || '';
  user.useLdap = Boolean(credentialsPath && fixtureUser.password);
}
if (!base || !modelId || Object.values(users).some(user => !user.email || !user.password)) {
  throw new Error('disposable UI URL, model ID, and synthetic Alpha/Beta/Gamma credentials are required');
}

async function login(browser, account) {
  const user = users[account];
  const auth = await fetch(`${base}/api/v1/auths/${user.useLdap ? 'ldap' : 'signin'}`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify(user.useLdap
      ? { user: user.username, password: user.password }
      : { email: user.email, password: user.password }),
  });
  if (!auth.ok) throw new Error(`${account} login failed: HTTP ${auth.status}`);
  const { token } = await auth.json();
  if (!token) throw new Error(`${account} login returned no token`);
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addCookies([{ name: 'token', value: token, url: `${base}/` }]);
  const page = await context.newPage();
  await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
  const welcome = page.getByRole('button', { name: /okay,\s*let.s go/i });
  if (user.useLdap) {
    if (await welcome.count()) await welcome.first().click({ force: true });
    await page.locator('#chat-input, [contenteditable="true"]').first().waitFor({ state: 'visible', timeout: 30000 });
  } else {
    // Preserve the known-good fresh-volume fixture sequence; LDAP-backed
    // existing accounts may instead land on the welcome screen first.
    await page.waitForSelector('#chat-input', { timeout: 30000 });
    if (await welcome.count()) await welcome.first().click({ force: true });
  }
  const selectModel = page.getByRole('button', { name: /select a model/i });
  if (await selectModel.count()) {
    await selectModel.first().click();
    const option = page.getByText(modelId, { exact: true }).last();
    await option.waitFor({ state: 'visible', timeout: 10000 });
    await option.click();
  }
  return { context, page, token };
}

async function newChat(page) {
  await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.locator('#chat-input, [contenteditable="true"]').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.waitForTimeout(300);
}

async function send(page, prompt) {
  const selector = '#response-content-container .markdown-prose';
  const before = await page.locator(selector).count();
  const started = Date.now();
  const composer = page.locator('#chat-input, [contenteditable="true"]').first();
  await composer.fill(prompt);
  const submit = page.locator('button[type="submit"]:visible');
  if (await submit.count()) await submit.last().click({ force: true });
  else await composer.press('Enter');
  const deadline = Date.now() + 90000;
  let response = '';
  while (Date.now() < deadline) {
    const items = page.locator(selector);
    const count = await items.count();
    response = count > before ? (await items.last().innerText()).trim() : '';
    const streaming = await page.locator('#message-input-container button[aria-label="Stop"]').count();
    if (response && !streaming) break;
    await page.waitForTimeout(250);
  }
  if (!response) throw new Error(`turn returned no settled response for ${JSON.stringify(prompt)}; page=${(await page.locator('body').innerText()).slice(-1200)}`);
  return { response, elapsedMs: Date.now() - started };
}

async function verifyChatHistory(baseUrl, token, expected, forbidden) {
  const chatsResponse = await fetch(`${baseUrl}/api/v1/chats/?page=1`, {
    headers: { authorization: `Bearer ${token}` },
  });
  if (!chatsResponse.ok) throw new Error(`chat history request failed: HTTP ${chatsResponse.status}`);
  const payload = await chatsResponse.json();
  const chats = Array.isArray(payload) ? payload : (payload.items || payload.chats || []);
  let found = false;
  for (const chat of chats.slice(0, 15)) {
    const id = chat.id || chat.chat_id;
    if (!id) continue;
    const detail = await fetch(`${baseUrl}/api/v1/chats/${encodeURIComponent(id)}`, {
      headers: { authorization: `Bearer ${token}` },
    });
    if (!detail.ok) continue;
    const serialized = JSON.stringify(await detail.json()).toLowerCase();
    if (expected && serialized.includes(expected.toLowerCase())) found = true;
    for (const value of forbidden) {
      if (serialized.includes(value.toLowerCase())) throw new Error(`authenticated chat history disclosed foreign memory value ${value}`);
    }
  }
  if (expected && !found) throw new Error(`authenticated chat history did not persist the expected response: ${expected}`);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const result = { status: 'PASS', accounts: {} };
  try {
    const alpha = await login(browser, 'alpha');
    try {
      const retainedMango = await send(alpha.page, 'Remember that my favorite fruit is mango.');
      if (!/(?:stored that as private memory|remember that privately)/i.test(retainedMango.response) || !/mango/i.test(retainedMango.response)) {
        throw new Error(`Alpha retain did not confirm the synthetic fact: ${retainedMango.response}`);
      }
      await newChat(alpha.page);
      const correctedPear = await send(alpha.page, 'Remember that my favorite fruit is pear.');
      if (!/(?:stored that as private memory|remember that privately)/i.test(correctedPear.response) || !/pear/i.test(correctedPear.response)) {
        throw new Error(`Alpha correction retain did not confirm the synthetic fact: ${correctedPear.response}`);
      }
      await newChat(alpha.page);
      const freshTypoRecall = await send(alpha.page, 'What is my favrite frut?');
      if (!/pear/i.test(freshTypoRecall.response) || /mango/i.test(freshTypoRecall.response)) {
        throw new Error(`Alpha fresh typo recall did not return only the corrected value: ${freshTypoRecall.response}`);
      }
      await verifyChatHistory(base, alpha.token, 'pear', []);
      result.accounts.alpha = {
        retain: 'PASS', correction: 'PASS', freshConversationTypoRecall: 'PASS',
        recallMs: freshTypoRecall.elapsedMs,
      };
    } finally {
      await alpha.context.close();
    }

    for (const account of ['beta', 'gamma']) {
      const session = await login(browser, account);
      try {
        const response = await send(session.page, 'What is my favorite fruit?');
        if (/mango|pear/i.test(response.response)) {
          throw new Error(`${account} received Alpha's private memory: ${response.response}`);
        }
        await verifyChatHistory(base, session.token, '', ['mango', 'pear']);
        result.accounts[account] = {
          crossUserIsolation: 'PASS',
          response: response.response,
          elapsedMs: response.elapsedMs,
        };
      } finally {
        await session.context.close();
      }
    }

    fs.writeFileSync(report, `${JSON.stringify(result, null, 2)}\n`, { mode: 0o600 });
    fs.chmodSync(report, 0o600);
    console.log(JSON.stringify({ status: result.status, report }));
  } finally {
    await browser.close();
  }
})().catch(error => {
  const debugDir = process.env.HADES_HINDSIGHT_UI_DEBUG_DIR;
  if (debugDir) {
    fs.mkdirSync(debugDir, { recursive: true, mode: 0o700 });
    fs.writeFileSync(`${debugDir}/browser-failure.txt`, `${error.stack || error.message}\n`, { mode: 0o600 });
  }
  console.error(JSON.stringify({ status: 'FAIL', error: error.message }));
  process.exitCode = 1;
});
