#!/usr/bin/env node

/* Real authenticated owner DOM proof for the first durable Task goal. */
const fs = require('node:fs');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const base = process.env.HADES_DOM_BASE_URL || 'http://127.0.0.1:3000/';
const root = process.env.HADES_DOM_CREDENTIAL_DIR || require('path').join(require('os').homedir(), '.config', 'hades-dom');
const read = name => fs.readFileSync(`${root}/${name}`, 'utf8').trim();
const report = process.env.HADES_DOM_REPORT || '/tmp/hades-alpha-task-dom.json';

async function login(page, context) {
  const result = await fetch(`${base}/api/v1/auths/ldap`, {
    method: 'POST', headers: {'content-type': 'application/json'},
    body: JSON.stringify({user: read('acceptance-owner-email'), password: read('acceptance-owner-password')}),
  });
  if (!result.ok) throw new Error(`login failed: HTTP ${result.status}`);
  const body = await result.json();
  if (!body.token) throw new Error('login returned no session token');
  await context.addCookies([{name: 'token', value: body.token, domain: new URL(base).hostname, path: '/'}]);
  await page.goto(`${base}/`, {waitUntil: 'commit', timeout: 30000});
  await page.waitForSelector('#chat-input', {timeout: 30000});
}

async function send(page, prompt) {
  const before = await page.locator('#response-content-container .markdown-prose').count();
  const beforeText = before ? (await page.locator('#response-content-container .markdown-prose').last().innerText()).trim() : '';
  await page.locator('#chat-input').fill(prompt);
  const submit = page.locator('button[type="submit"]:visible');
  if (await submit.count()) await submit.last().click(); else await page.locator('#chat-input').press('Enter');
  const deadline = Date.now() + Number(process.env.HADES_EPSILON_DOM_WAIT_MS || 45000);
  while (Date.now() < deadline) {
    const nodes = page.locator('#response-content-container .markdown-prose');
    const latest = await nodes.count() ? (await nodes.last().innerText()).trim() : '';
    if ((await nodes.count() > before || latest !== beforeText) && !(await page.locator('#message-input-container button[aria-label="Stop"]').count())) {
      await page.waitForTimeout(600);
      return (await nodes.last().innerText()).trim();
    }
    await page.waitForTimeout(350);
  }
  throw new Error(`turn did not settle: ${prompt}; responses=${await page.locator('#response-content-container .markdown-prose').count()}; stop=${await page.locator('#message-input-container button[aria-label="Stop"]').count()}; tail=${(await page.locator('body').innerText()).slice(-1200)}`);
}

async function newChat(page) {
  const buttons = page.locator('#new-chat-button:visible, [aria-label="New Chat"]:visible, button:has-text("New Chat"):visible, a:has-text("New Chat"):visible');
  if (await buttons.count()) await buttons.last().click({force: true}).catch(() => {});
  await page.waitForTimeout(500);
}

(async () => {
  const browser = await chromium.launch({headless: true});
  const context = await browser.newContext({ignoreHTTPSErrors: true, viewport: {width: 1440, height: 900}});
  const page = await context.newPage();
  try {
    await login(page, context);
    await newChat(page);
    const first = [
      'Help me get ready to make spaghetti Friday.',
      'Create it.',
    ];
    const turns = [];
    for (const prompt of first) turns.push({prompt, response: await send(page, prompt)});
    await newChat(page);
    for (const prompt of [
      "What's happening with the spaghetti thing?",
      'Approve the spaghetti task.',
      'Approve the exact task revision.',
    ]) turns.push({prompt, response: await send(page, prompt)});
    await newChat(page);
    for (const prompt of [
      'Continue the spaghetti task.',
      "What's happening with the spaghetti thing?",
    ]) turns.push({prompt, response: await send(page, prompt)});
    const text = turns.map(item => item.response).join('\n');
    if (!/Create it\?|already tracking.*proposed/i.test(turns[0].response)) throw new Error('task preview/idempotency result missing');
    if (!/Created the task|already created.*no duplicate/i.test(turns[1].response)) throw new Error('task creation/idempotency result missing');
    if (!/WAITING/i.test(turns[2].response)) throw new Error('waiting inspection missing');
    if (!/Approval is required/i.test(turns[3].response)) throw new Error('approval request missing');
    if (!/Approved the current task revision/i.test(turns[4].response)) throw new Error('approval missing');
    if (!/Completed the bounded task/i.test(turns[5].response)) throw new Error('resume/completion missing');
    if (!/COMPLETED|completed/i.test(turns[6].response)) throw new Error('fresh-session completion inspection missing');
    const output = {status: 'PASS', viewport: {width: 1440, height: 900}, turns};
    fs.writeFileSync(report, `${JSON.stringify(output, null, 2)}\n`, {mode: 0o600});
    console.log(JSON.stringify(output));
  } finally { await context.close(); await browser.close(); }
})().catch(error => { console.error(JSON.stringify({status: 'FAIL', error: error.message})); process.exitCode = 1; });
