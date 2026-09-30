#!/usr/bin/env node

/* Authenticated read-only Grocy + public-research composition acceptance. */
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');
const base = (process.env.HADES_GROCY_UI_BASE_URL || '').replace(/\/$/, '');
const modelId = process.env.HADES_GROCY_UI_MODEL_ID;
const password = process.env.HADES_GROCY_UI_PASSWORD;
const email = process.env.HADES_GROCY_UI_OWNER_EMAIL || 'alpha-grocy@example.invalid';
if (!base || !modelId || !password) throw new Error('authenticated Grocy web-composition inputs are required');

async function main() {
  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1365, height: 850 } });
    try {
      const auth = await fetch(`${base}/api/v1/auths/signin`, {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!auth.ok) throw new Error(`Alpha login failed: HTTP ${auth.status}`);
      const { token } = await auth.json();
      await context.addCookies([{ name: 'token', value: token, url: `${base}/` }]);
      const page = await context.newPage();
      await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForSelector('#chat-input', { timeout: 30000 });
      const welcome = page.getByRole('button', { name: /okay,\s*let.s go/i });
      if (await welcome.count()) await welcome.first().click({ force: true });
      const choose = page.getByRole('button', { name: /select a model/i });
      if (await choose.count()) {
        await choose.first().click();
        const option = page.getByText(modelId, { exact: true }).last();
        await option.waitFor({ state: 'visible', timeout: 10000 });
        await option.click();
      }
      const prompt = 'Research an online recipe that uses the household pantry. Check what we actually have first, then use public_research for a source.';
      await page.locator('#chat-input').fill(prompt);
      await page.locator('#send-message-button:visible').last().click({ force: true });
      const selector = '#response-content-container .markdown-prose';
      const deadline = Date.now() + 60000;
      let answer = '';
      while (Date.now() < deadline) {
        const rows = page.locator(selector);
        if (await rows.count()) answer = (await rows.last().innerText()).trim();
        if (answer && !(await page.locator('#message-input-container button[aria-label="Stop"]').count())) break;
        await page.waitForTimeout(250);
      }
      for (const value of ['milk', 'rice', 'Synthetic Milk and Rice Pudding', '2026-09-27T12:00:00Z', 'static-page']) {
        if (!answer.toLowerCase().includes(value.toLowerCase())) throw new Error(`composed answer omitted ${value}: ${answer}`);
      }
      const citation = page.locator(`${selector} a[href="https://recipes.synthetic.example/milk-rice-pudding"]`).last();
      if (!(await citation.count())) throw new Error(`composed answer omitted exact source link: ${answer}`);
      if (!/did not change|didn't change|no pantry|no shopping-list change/i.test(answer)) throw new Error(`composed answer omitted its no-mutation statement: ${answer}`);
      const chatId = new URL(page.url()).pathname.split('/').filter(Boolean).pop();
      const history = await fetch(`${base}/api/v1/chats/${encodeURIComponent(chatId)}`, { headers: { authorization: `Bearer ${token}` } });
      if (!history.ok || !(await history.text()).includes(prompt)) throw new Error('composed research did not persist in Alpha chat history');
      console.log('PASS authenticated Alpha combines canonical synthetic Grocy HTTP reads with cited public-research evidence; no mutation');
    } finally { await context.close(); }
  } finally { await browser.close(); }
}
main().catch(error => { console.error(`FAIL ${error.message}`); process.exitCode = 1; });
