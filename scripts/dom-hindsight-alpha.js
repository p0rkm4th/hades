#!/usr/bin/env node

/* Fresh authenticated Hindsight retain/recall proof; marker is harmless. */
const fs = require('node:fs');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.HADES_DOM_BASE_URL || 'http://127.0.0.1:3000/';
const root = process.env.HADES_DOM_CREDENTIAL_DIR || require('path').join(require('os').homedir(), '.config', 'hades-dom');
const modelId = process.env.HADES_DOM_MODEL_ID || '';
const marker = process.env.HADES_HINDSIGHT_MARKER || `alpha-memory-marker-${Date.now()}`;
const expectAbsent = process.env.HADES_HINDSIGHT_EXPECT_ABSENT === '1';
const recallOnly = process.env.HADES_HINDSIGHT_RECALL_ONLY === '1';
const read = name => fs.readFileSync(`${root}/${name}`, 'utf8').trim();

if (expectAbsent && !recallOnly) {
  throw new Error('expected-absence checks must use HADES_HINDSIGHT_RECALL_ONLY=1 to avoid writing test memory');
}

async function login(page, context) {
  const user = process.env.HADES_DOM_AUTH_USER || read('acceptance-owner-email');
  const result = await fetch(`${base}/api/v1/auths/ldap`, {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({user, password: read('acceptance-owner-password')})});
  if (!result.ok) throw new Error(`login failed: HTTP ${result.status}`);
  const body = await result.json();
  await context.addCookies([{name: 'token', value: body.token, domain: new URL(base).hostname, path: '/'}]);
  await page.goto(`${base}/`, {waitUntil: 'commit', timeout: 30000});
  await page.waitForSelector('#chat-input', {timeout: 30000});
  const welcome = page.getByRole('button', {name: /okay,\s*let.s go/i});
  if (await welcome.count()) await welcome.first().click({force: true});
  const updateToast = page.locator('.absolute.bottom-8.right-8.z-50');
  try {
    await updateToast.waitFor({state: 'visible', timeout: 2000});
    await updateToast.getByRole('button').click({force: true});
  } catch (_) {}
  if (modelId) {
    const selector = page.getByRole('button', {name: /select a model/i});
    if (await selector.count()) {
      await selector.first().click();
      const option = page.getByText(modelId, {exact: true}).last();
      await option.waitFor({state: 'visible', timeout: 10000});
      await option.click();
    } else if (!(await page.getByText(modelId, {exact: true}).count())) {
      throw new Error(`requested model is not selectable: ${modelId}`);
    }
  }
}
async function newChat(page) {
  const buttons = page.locator('[aria-label="New Chat"]:visible, button:has-text("New Chat"):visible, a:has-text("New Chat"):visible');
  if (await buttons.count()) await buttons.last().click().catch(() => {});
  await page.waitForTimeout(800);
}
async function send(page, prompt) {
  const before = await page.locator('#response-content-container .markdown-prose').count();
  await page.locator('#chat-input').fill(prompt);
  const submit = page.locator('button[type="submit"]:visible');
  if (await submit.count()) await submit.last().click(); else await page.locator('#chat-input').press('Enter');
  const deadline = Date.now() + Number(process.env.HADES_EPSILON_DOM_WAIT_MS || 90000);
  while (Date.now() < deadline) {
    const nodes = page.locator('#response-content-container .markdown-prose');
    if (await nodes.count() > before && !(await page.locator('#message-input-container button[aria-label="Stop"]').count())) { await page.waitForTimeout(700); return (await nodes.last().innerText()).trim(); }
    await page.waitForTimeout(500);
  }
  const diagnostic = process.env.HADES_DOM_DEBUG === '1'
    ? `; page=${(await page.locator('body').innerText()).slice(-1600)}`
    : '';
  throw new Error(`turn did not settle: ${prompt}${diagnostic}`);
}
(async () => {
  const browser = await chromium.launch({headless: true});
  const context = await browser.newContext({ignoreHTTPSErrors: true, viewport: {width: 1440, height: 900}});
  const page = await context.newPage();
  try {
    await login(page, context);
    let retain = 'reused existing marker';
    const measurementStarted = Date.now();
    let retainSettledAt = measurementStarted;
    if (!recallOnly) {
      await newChat(page);
      retain = await send(page, `Remember that my harmless Alpha test fruit is ${marker}. This is a disposable acceptance fact.`);
      retainSettledAt = Date.now();
    }
    await newChat(page);
    const recallStartedAt = Date.now();
    const recall = await send(page, process.env.HADES_HINDSIGHT_RECALL_QUERY || `What is the Alpha test fruit?`);
    const matched = recall.includes(marker);
    const result = {
      status: (expectAbsent ? !matched : matched) ? 'PASS' : 'FAIL',
      marker,
      retain,
      recall,
      expected_absent: expectAbsent,
      fresh_conversation: true,
      retain_to_recall_start_ms: Math.max(0, recallStartedAt - retainSettledAt),
      retain_to_recall_success_ms: matched ? Date.now() - retainSettledAt : null,
      total_elapsed_ms: Date.now() - measurementStarted,
    };
    console.log(JSON.stringify(result));
    if (result.status !== 'PASS') process.exitCode = 1;
  } finally { await context.close(); await browser.close(); }
})().catch(error => { console.error(JSON.stringify({status: 'FAIL', error: error.message, marker})); process.exitCode = 1; });
