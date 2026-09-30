#!/usr/bin/env node

/* Credential-free real-DOM check for the unauthenticated responsive shell. */
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const baseUrl = process.env.HADES_DOM_BASE_URL || 'http://127.0.0.1:3000/';
const viewports = [
  { width: 320, height: 568 },
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const results = [];
  try {
    for (const viewport of viewports) {
      const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForTimeout(800);
      const emailButton = page.getByRole('button', { name: 'Continue with Email', exact: true });
      if (await emailButton.count()) {
        await emailButton.click();
        await page.waitForTimeout(250);
      }
      const state = await page.evaluate(() => ({
        email: Boolean(document.querySelector('input[type="email"]')),
        password: Boolean(document.querySelector('input[type="password"]')),
        emailPath: Boolean(document.querySelector('input[type="email"]')),
        globalFinance: /Financial CSV|hades-finance-csv-button/i.test(document.body.innerText),
        globalReceipt: /hades-receipt-ocr-button/i.test(document.body.innerText),
      }));
      if (!state.email || !state.password || !state.emailPath) throw new Error(`login shell incomplete at ${viewport.width}x${viewport.height}`);
      if (state.globalFinance || state.globalReceipt) throw new Error(`global integration clutter visible at ${viewport.width}x${viewport.height}`);
      if (errors.length) throw new Error(`browser error at ${viewport.width}x${viewport.height}: ${errors[0]}`);
      results.push({ viewport, status: 'PASS', state });
      await context.close();
    }
    console.log(JSON.stringify({ status: 'PASS', results }));
  } finally {
    await browser.close().catch(() => {});
  }
})().catch(error => { console.error(String(error.message || error)); process.exitCode = 1; });
