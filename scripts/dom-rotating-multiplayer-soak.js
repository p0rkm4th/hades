#!/usr/bin/env node
const { protectedInput } = require('./dom-protected-input');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const base = process.env.HADES_DOM_BASE_URL || 'http://127.0.0.1:3000/';
const users = [
  ['owner', 'HADES_DOM_OWNER_EMAIL', 'HADES_DOM_OWNER_PASSWORD', process.env.HADES_DOM_OWNER_PROMPT || 'check deep-inference-node status'],
  ['owner-tab-b', 'HADES_DOM_OWNER_EMAIL', 'HADES_DOM_OWNER_PASSWORD', process.env.HADES_DOM_OWNER_TAB_B_PROMPT || 'do we have milk'],
  ['household-a', 'HADES_DOM_HOUSEHOLD_A_EMAIL', 'HADES_DOM_HOUSEHOLD_A_PASSWORD', process.env.HADES_DOM_MUTATION_PROMPT || 'add HADES beta test oat milk to the grocery list'],
  ['household-b', 'HADES_DOM_HOUSEHOLD_B_EMAIL', 'HADES_DOM_HOUSEHOLD_B_PASSWORD', process.env.HADES_DOM_HOUSEHOLD_B_PROMPT || 'ask Agent Zero to inspect the server'],
];
const maxWaitMs = Number(process.env.HADES_DOM_MULTI_WAIT_MS || 90000);
const viewport = {
  width: Number(process.env.HADES_DOM_VIEWPORT_WIDTH || 390),
  height: Number(process.env.HADES_DOM_VIEWPORT_HEIGHT || 844),
};
const results = [];

function secret(name, fallbackFile) { return protectedInput(name) || (fallbackFile ? protectedInput(fallbackFile) : ''); }
function errorsFor(page) {
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(`console: ${m.text()}`); });
  page.on('pageerror', e => errors.push(`page: ${e.message}`));
  return errors;
}
async function login(page, email, password) {
  await page.goto(`${base}/`, { waitUntil: 'commit', timeout: 30000 });
  await page.waitForSelector('#username, #chat-input', { timeout: 30000 });
  if (await page.locator('#username').count()) {
    await page.locator('#username').fill(email);
    await page.locator('#password').fill(password);
    await page.getByRole('button', { name: /authenticate/i }).click();
  }
  await page.waitForSelector('#chat-input', { timeout: 30000 });
}
async function sendAndWait(page, prompt, maxMs = maxWaitMs) {
  const input = page.locator('#chat-input');
  const before = await page.locator('#response-content-container .markdown-prose').count();
  await input.fill(prompt);
  // Open WebUI's composer can leave Enter as a newline after the first
  // completed turn, even though the input remains enabled. Prefer the
  // visible composer submit control so stale-tab/follow-up checks exercise
  // an actual second request; retain Enter only for responsive layouts that
  // do not expose that control.
  // The first fresh turn uses the contenteditable submit path. Once a
  // transcript exists, use the actual composer send control; Enter can become
  // a literal newline after hydration on mobile.
  if (before === 0) await input.press('Enter');
  else {
    const submit = page.locator('#send-message-button:visible');
    if (await submit.count()) await submit.click({ force: true });
    else await input.press('Enter');
  }
  const deadline = Date.now() + maxMs;
  let snapshot = null;
  while (Date.now() < deadline) {
    snapshot = await page.evaluate((beforeCount) => {
      const nodes = [...document.querySelectorAll('#response-content-container .markdown-prose')];
      const text = nodes.slice(beforeCount).map(n => n.innerText?.trim() || '').filter(Boolean);
      return {
        beforeCount,
        text: text.at(-1) || '',
        texts: nodes.slice(beforeCount).map(n => n.innerText?.trim() || ''),
        stop: Boolean(document.querySelector('#message-input-container button[aria-label="Stop"]')),
        composer: document.querySelector('#chat-input')?.value || '',
        assistantCount: nodes.length,
      };
    }, before);
    if (snapshot.text && !snapshot.stop) return { status: 'PASS', ...snapshot, elapsedMs: maxMs - (deadline - Date.now()) };
    await page.waitForTimeout(500);
  }
  return { status: 'FAIL', ...snapshot, elapsedMs: maxMs, reason: 'turn did not settle with visible assistant text and no Stop control' };
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const contexts = [];
  try {
    const pages = [];
    for (const [label, emailName, passwordName] of users) {
      const emailFile = require('path').join(process.env.HADES_DOM_CREDENTIAL_DIR || require('path').join(require('os').homedir(), '.config', 'hades-dom'), emailName === 'HADES_DOM_OWNER_EMAIL' ? 'acceptance-owner-email' : emailName === 'HADES_DOM_HOUSEHOLD_A_EMAIL' ? 'household-a-email' : 'household-b-email');
      const passwordFile = require('path').join(process.env.HADES_DOM_CREDENTIAL_DIR || require('path').join(require('os').homedir(), '.config', 'hades-dom'), passwordName === 'HADES_DOM_OWNER_PASSWORD' ? 'acceptance-owner-password' : passwordName === 'HADES_DOM_HOUSEHOLD_A_PASSWORD' ? 'household-a-password' : 'household-b-password');
    const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport });
      contexts.push(context);
      const page = await context.newPage();
      const errors = errorsFor(page);
      await login(page, protectedInput(emailName) || require('node:fs').readFileSync(emailFile, 'utf8').trim(), protectedInput(passwordName) || require('node:fs').readFileSync(passwordFile, 'utf8').trim());
      // Each browser context must exercise a distinct durable conversation.
      // Without this, two tabs opened on the user's last chat intentionally
      // share Hermes' per-session lease and the soak would misclassify valid
      // same-session serialization as cross-conversation isolation failure.
      let newChat = page.locator('#new-chat-button');
      if (!await newChat.count()) newChat = page.locator(
        '[aria-label="New Chat"]:visible, button:has-text("New Chat"):visible, a:has-text("New Chat"):visible'
      ).last();
      if (!await newChat.count()) {
        const sidebar = page.locator('#sidebar-toggle-button');
        if (await sidebar.count()) await sidebar.click();
        newChat = page.locator(
          '[aria-label="New Chat"]:visible, button:has-text("New Chat"):visible, a:has-text("New Chat"):visible'
        ).last();
      }
      await newChat.waitFor({ state: 'attached', timeout: 5000 });
      await newChat.click({ timeout: 5000, force: true }).catch(() => {
        // Root navigation is already a fresh composer in some responsive
        // layouts; if the sidebar link is visually occluded, retain that
        // fresh conversation instead of turning harness setup into a failure.
      });
      // On narrow layouts New Chat can leave the mobile drawer mounted above
      // the composer. Close it before filling the next turn; otherwise a
      // forced submit can click through the drawer and produce a false
      // cross-user/lease failure.
      await page.keyboard.press('Escape').catch(() => {});
      const sidebarToggle = page.locator('#sidebar-toggle-button:visible');
      if (await sidebarToggle.count()) {
        await sidebarToggle.click({ force: true }).catch(() => {});
      }
      const freshDeadline = Date.now() + 5000;
      while (Date.now() < freshDeadline && await page.locator('#response-content-container .markdown-prose').count()) {
        await page.waitForTimeout(250);
      }
      // A responsive drawer can swallow the first navigation click while it
      // is closing. If the old transcript remains, retry the semantic New
      // Chat control once, even when its animation reports no visible box.
      if (await page.locator('#response-content-container .markdown-prose').count()) {
        const retryNewChat = page.locator('[aria-label="New Chat"], button:has-text("New Chat"), a:has-text("New Chat")').last();
        if (await retryNewChat.count()) {
          await retryNewChat.click({ force: true }).catch(() => {});
          await page.waitForTimeout(500);
        }
      }
      await page.waitForTimeout(250);
      pages.push({ label, page, errors, prompt: users.find(x => x[0] === label)[3] });
    }
    // Start all four contexts together. The owner Deep request is deliberately
    // abandoned after admission; the other users must still complete.
    const owner = pages[0];
    const ownerRun = sendAndWait(owner.page, owner.prompt, maxWaitMs);
    ownerRun.catch(() => {});
    const concurrentOthers = process.env.HADES_DOM_CONCURRENT_DEEP === '1'
      ? pages.slice(1).map(item => ({ item, run: sendAndWait(item.page, item.prompt) }))
      : null;
    await owner.page.waitForTimeout(2500);
    await owner.page.close();
    results.push({ label: owner.label, prompt: owner.prompt, status: 'ABANDONED', errors: owner.errors });
    const others = concurrentOthers
      ? await Promise.all(concurrentOthers.map(async ({ item, run }) => ({ label: item.label, prompt: item.prompt, ...(await run), errors: item.errors })))
      : await Promise.all(pages.slice(1).map(async item => ({ label: item.label, prompt: item.prompt, ...(await sendAndWait(item.page, item.prompt)), errors: item.errors })));
    results.push(...others);
    // Owner's second tab remains live and must recover independently.
    const ownerB = pages[1];
    // Rehydrate the tab before the recovery turn so this explicitly covers a
    // stale browser document, not only a still-mounted composer component.
    await ownerB.page.reload({ waitUntil: 'commit', timeout: 30000 });
    await ownerB.page.waitForSelector('#chat-input', { timeout: 30000 });
    const follow = await sendAndWait(ownerB.page, 'hello', 60000);
    results.push({ label: ownerB.label, prompt: 'follow-up after concurrent abandonment', ...follow, errors: ownerB.errors });
    const denial = results.find(r => r.label === 'household-b');
    if (!denial?.text || !/owner-only|can.?t|cannot|not available|not allowed|denied/i.test(denial.text)) {
      throw new Error('household Agent Zero denial was not plain and visible');
    }
    if (results.some(r => r.status === 'FAIL')) throw new Error('one or more concurrent browser turns failed to settle');
    console.log(JSON.stringify({ status: 'PASS', viewport, results }));
  } finally {
    for (const context of contexts) await context.close().catch(() => {});
    await browser.close();
  }
})().catch(error => { console.error(JSON.stringify({ status: 'FAIL', error: error.message, results })); process.exitCode = 1; });
