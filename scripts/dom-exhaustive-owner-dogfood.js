#!/usr/bin/env node

/* Evidence collector for the exhaustive owner dogfood campaign.
 * It records real authenticated UI turns; it does not assert canned answers
 * or mutate data beyond what the product itself requests confirmation for.
 */
const fs = require('node:fs');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const base = process.env.HADES_DOM_BASE_URL || 'http://127.0.0.1:3000/';
const root = process.env.HADES_DOM_CREDENTIAL_DIR || require('path').join(require('os').homedir(), '.config', 'hades-dom');
const read = name => fs.readFileSync(`${root}/${name}`, 'utf8').trim();
const report = process.env.HADES_DOM_REPORT || '/tmp/hades-exhaustive-owner-dogfood.json';
const prompts = [
  ['recipes_available', 'List my recipes, and tell me which ones I can make right now without buying anything.'],
  ['expiring_food', 'What food in the pantry or fridge is going to expire in the next 7 days? Give me some meals that would use as much of it as possible.'],
  ['spaghetti_grocery', 'I wanna make spaghetti tonight. Check what I already have, tell me what I’m missing, and add the missing stuff to my grocery list.'],
  ['homelab_status', 'What’s running on my homelab right now? Give me each node, its OS, major services, CPU/RAM/storage utilization, and anything that looks unhealthy.'],
  ['network_diagnosis', 'Something feels slow on the network. Check the HADES nodes, network health, recent resource usage, and services, then tell me what looks abnormal.'],
  ['model_placement', 'Which of my servers would be the best place to deploy another local AI model without interfering with what’s already running?'],
  ['backup_coverage', 'Are all my important services actually backed up? Tell me when each one was last backed up, whether the backup succeeded, and anything that currently has no verified backup.'],
  ['utilities', 'How much did I spend on utilities on average per month over the past 8 months? Break it down by electric, internet, phone, and anything else you classify as a utility.'],
  ['eating_out', 'How much have I spent on restaurants, DoorDash, coffee, and convenience food since January? Break it down by month and tell me which places I spend the most at.'],
  ['subscriptions', 'Show me all of my recurring charges and subscriptions. Flag anything that increased in price, looks duplicated, or I barely use.'],
  ['weekend_spend', 'Based on my current balances, upcoming bills, paychecks, and normal spending, how much money can I safely spend this weekend without screwing up my rent plan?'],
  ['rent_goal', 'How am I doing on my goal to have the rest of my current lease prepaid? Show me where I should be by now, where I actually am, and what I need to set aside from each remaining paycheck.'],
  ['restock', 'Give me a household restock report. What are we low on, what do we normally consume quickly, and what should probably go on the grocery list before we run out?'],
  ['save_300', 'I want to cut my spending by $300 a month without making my life miserable. Look at my actual spending, subscriptions, groceries, takeout, phone bill, and other recurring costs and find realistic places to cut it.'],
  ['morning_briefing', 'Give me my HADES morning briefing: anything down in the homelab, failed backups, low or expiring groceries, unusual spending, bills coming up, and anything else that needs my attention.'],
];

async function openPage(browser, viewport) {
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport });
  const page = await context.newPage();
  // Deterministic bounded routes can legitimately return the same text on
  // consecutive turns (for example weekend affordability and rent-plan
  // refusal).  Keep the websocket completion event as the authoritative
  // new-turn signal when DOM text/node identity is unchanged.
  page.__hadesCompletionSeen = false;
  page.on('websocket', socket => {
    socket.on('framereceived', data => {
      const frame = String(data);
      if (frame.includes('chat:completion') && (frame.includes('"done":true') || frame.includes('"finish_reason":"stop"'))) {
        page.__hadesCompletionSeen = true;
      }
    });
  });
  const auth = await fetch(`${base}/api/v1/auths/ldap`, {
    method: 'POST', headers: {'content-type': 'application/json'},
    body: JSON.stringify({user: read('acceptance-owner-email'), password: read('acceptance-owner-password')}),
  });
  if (!auth.ok) throw new Error(`login failed: HTTP ${auth.status}`);
  const body = await auth.json();
  await context.addCookies([{name: 'token', value: body.token, domain: new URL(base).hostname, path: '/'}]);
  await page.goto(`${base}/`, {waitUntil: 'commit', timeout: 30000});
  await page.waitForSelector('#chat-input', {timeout: 30000});
  let newChat = page.locator('#new-chat-button');
  if (!await newChat.count()) newChat = page.locator('[aria-label="New Chat"]:visible, button:has-text("New Chat"):visible, a:has-text("New Chat"):visible').last();
  if (await newChat.count()) await newChat.click({force: true}).catch(() => {});
  await page.waitForTimeout(500);
  return {context, page};
}

async function send(page, prompt, timeoutMs = 90000) {
  const nodes = page.locator('#response-content-container .markdown-prose');
  const before = await nodes.count();
  const beforeTexts = await nodes.allTextContents();
  const baseline = beforeTexts.at(-1)?.trim() || '';
  await page.locator('#chat-input').fill(prompt);
  page.__hadesCompletionSeen = false;
  const submit = page.locator('button[type="submit"]:visible');
  if (await submit.count()) await submit.last().click(); else await page.locator('#chat-input').press('Enter');
  const end = Date.now() + timeoutMs;
  while (Date.now() < end) {
    const current = page.locator('#response-content-container .markdown-prose');
    const count = await current.count();
    const stop = await page.locator('#message-input-container button[aria-label="Stop"]').count();
    const texts = await current.allTextContents();
    const last = texts.at(-1)?.trim() || '';
    // Open WebUI can reuse the last markdown node for a deterministic task
    // response.  Text change is therefore a valid new-turn signal; relying
    // only on node count creates false timeouts in persistent chats.
    if (last && (count > before || last !== baseline || page.__hadesCompletionSeen) && !stop) {
      await page.waitForTimeout(800);
      return (await current.last().innerText()).trim();
    }
    await page.waitForTimeout(500);
  }
  return `TIMEOUT: stop=${await page.locator('#message-input-container button[aria-label="Stop"]').count()} tail=${(await page.locator('body').innerText()).slice(-900)}`;
}

(async () => {
  const browser = await chromium.launch({headless: true});
  const result = {started_at: new Date().toISOString(), owner: {}, fresh: {}, mobile: {}, turns: []};
  let owner;
  try {
    owner = await openPage(browser, {width: 1440, height: 900});
    for (const [key, prompt] of prompts) {
      if (process.env.HADES_DOM_FRESH_EACH === '1' && owner) {
        await owner.context.close();
        owner = await openPage(browser, {width: 1440, height: 900});
      }
      const started = Date.now();
      const response = await send(owner.page, prompt, Number(process.env.HADES_DOM_TURN_TIMEOUT_MS || 45000));
      result.turns.push({key, prompt, response, ms: Date.now() - started, viewport: '1440x900'});
    }
    result.owner = {viewport: '1440x900', turns: result.turns.length};
    result.followup = await send(owner.page, 'That briefing is too broad. What should I handle first, and why?');
    result.correction = await send(owner.page, 'Actually, forget the spending advice for now. Just give me the grocery items that need attention.');
    await owner.page.setViewportSize({width: 390, height: 844});
    result.mobile_continuation = await send(owner.page, 'Give me the short version of those grocery items on this phone.');
    const fresh = await openPage(browser, {width: 1440, height: 900});
    result.fresh.response = await send(fresh.page, 'What did we learn from my morning briefing, and what needs attention first?');
    result.fresh.viewport = '1440x900';
    await fresh.context.close();
    const mobile = await openPage(browser, {width: 390, height: 844});
    result.mobile.response = await send(mobile.page, 'What can I cook tonight, and what is most urgent to use up?');
    result.mobile.viewport = '390x844';
    await mobile.context.close();
    result.status = 'COLLECTED';
  } catch (error) {
    result.status = 'PARTIAL'; result.error = error.message;
  } finally {
    await owner?.context.close().catch(() => {});
    await browser.close();
    fs.writeFileSync(report, `${JSON.stringify(result, null, 2)}\n`, {mode: 0o600});
    console.log(JSON.stringify({status: result.status, turns: result.turns.length, report}));
  }
})().catch(error => { console.error(JSON.stringify({status: 'FAIL', error: error.message})); process.exitCode = 1; });
