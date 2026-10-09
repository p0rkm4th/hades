#!/usr/bin/env node
'use strict';

const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const baseUrl = process.env.HADES_CANDIDATE_BROWSER_URL;
const email = process.env.HADES_CANDIDATE_BROWSER_EMAIL;
const username = process.env.HADES_CANDIDATE_BROWSER_USERNAME || email;
const password = process.env.HADES_CANDIDATE_BROWSER_PASSWORD;
const fixtureFile = process.env.HADES_CANDIDATE_BROWSER_FILE;
const expectedReply = process.env.HADES_CANDIDATE_BROWSER_EXPECTED_REPLY || 'Alpha-private-fact-confirmed';
const forbiddenText = process.env.HADES_CANDIDATE_BROWSER_FORBIDDEN_TEXT || '';
const prompt = process.env.HADES_CANDIDATE_BROWSER_PROMPT || 'Please confirm the Alpha browser conversation.';
if (!baseUrl || !email || !password) {
  console.error('FAIL candidate browser test requires its disposable URL and synthetic login');
  process.exit(2);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const pageErrors = [];
  const networkEvents = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  context.on('request', request => {
    const url = new URL(request.url());
    if (/\/api\/(chat\/completions|models|v1\/files)/.test(url.pathname)) networkEvents.push({ kind: 'request', path: url.pathname });
  });
  context.on('response', response => {
    const url = new URL(response.url());
    if (/\/api\/(chat\/completions|models|v1\/files)/.test(url.pathname)) networkEvents.push({ kind: 'response', status: response.status(), path: url.pathname });
  });
  const checks = [];
  const timed = async (name, action) => {
    const started = Date.now();
    await action();
    checks.push({ name, elapsed_ms: Date.now() - started });
  };
  try {
    await timed('login page and owner authentication', async () => {
      await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
      const usernameInput = page.locator('input[name="username"], #username');
      await page.locator('input[name="username"], #username, input[type="email"]').first()
        .waitFor({ state: 'visible', timeout: 15000 });
      if (await usernameInput.count()) {
        await usernameInput.fill(username);
        await page.locator('input[type="password"]').fill(password);
        const authenticate = page.getByRole('button', { name: /authenticate|sign in|log in/i });
        if (await authenticate.count()) await authenticate.first().click();
        else await page.locator('button[type="submit"]').click();
        await page.waitForSelector('#chat-input', { timeout: 30000 });
        if (forbiddenText && (await page.locator('body').innerText()).includes(forbiddenText)) {
          throw new Error('account landing page displayed another account\'s private response marker');
        }
        return;
      }
      const emailInput = page.locator('input[type="email"]');
      if (!await emailInput.count()) {
        const continueWithEmail = page.getByText('Continue with Email', { exact: true });
        if (await continueWithEmail.count()) await continueWithEmail.click({ timeout: 10000 });
      }
      try {
        await emailInput.waitFor({ state: 'visible', timeout: 15000 });
      } catch (error) {
        const state = await page.evaluate(() => ({
          url: location.pathname,
          title: document.title,
          text: document.body.innerText.slice(0, 300),
          inputs: [...document.querySelectorAll('input')].map(node => ({ type: node.type, name: node.name, id: node.id, placeholder: node.placeholder })),
        }));
        throw new Error(`email login control unavailable: ${JSON.stringify(state)}`);
      }
      await emailInput.fill(email);
      await page.locator('input[type="password"]').fill(password);
      await page.locator('button[type="submit"]').click();
      await page.waitForSelector('#chat-input', { timeout: 30000 });
      if (forbiddenText && (await page.locator('body').innerText()).includes(forbiddenText)) {
        throw new Error('account landing page displayed another account\'s private response marker');
      }
    });

    await timed('HADES theme and upload controls render', async () => {
      const css = await page.request.get(`${baseUrl}/static/hades-theme.css`);
      if (css.status() !== 200) throw new Error(`HADES theme CSS returned HTTP ${css.status()}`);
      const js = await page.request.get(`${baseUrl}/static/hades-theme.js`);
      if (js.status() !== 200) throw new Error(`HADES theme JS returned HTTP ${js.status()}`);
      if (!await page.locator('input[type="file"]').count()) throw new Error('file upload control is missing');
      const themeScript = await page.locator('script[src*="hades-theme.js"]').count();
      if (!themeScript) throw new Error('HADES theme script is not included in the page');
    });

    await timed('release-notes overlay can be dismissed', async () => {
      const dialog = page.getByRole('dialog');
      if (!await dialog.count()) return;
      const close = dialog.getByRole('button', { name: /close|dismiss|later|got it|not now/i });
      if (!await close.count()) {
        const buttons = await dialog.locator('button').evaluateAll(nodes => nodes.map(node => ({
          text: node.innerText.trim(), aria: node.getAttribute('aria-label'), title: node.getAttribute('title'),
        })));
        throw new Error(`release-notes dialog has no recognizable dismiss control: ${JSON.stringify(buttons)}`);
      }
      await close.first().click();
      await dialog.waitFor({ state: 'hidden', timeout: 5000 });
    });

    if (fixtureFile) {
      await timed('file picker uploads a synthetic text attachment', async () => {
        await page.locator('input[type="file"]').last().setInputFiles(fixtureFile);
        await page.getByText('candidate-usability.txt', { exact: false }).waitFor({ state: 'visible', timeout: 15000 });
        const upload = networkEvents.find(item => item.kind === 'response' && item.path.startsWith('/api/v1/files'));
        if (!upload || upload.status < 200 || upload.status >= 300) throw new Error('file upload did not return a successful API response');
      });
    }

    await timed('model response through the visible chat composer', async () => {
      const input = page.locator('#chat-input');
      await input.fill(prompt);
      await page.locator('#send-message-button').click();
      try {
        await page.waitForFunction(
          expected => document.querySelector('#response-content-container')?.innerText.includes(expected),
          expectedReply,
          { timeout: 10000 },
        );
      } catch (_) {
        const state = await page.evaluate(() => ({
          text: document.body.innerText.slice(-900),
          composer: document.querySelector('#chat-input')?.value || '',
          composer_html: document.querySelector('#chat-input')?.outerHTML.slice(0, 1200) || '',
          parent_html: document.querySelector('#chat-input')?.parentElement?.parentElement?.outerHTML.slice(0, 1800) || '',
          input_container_html: document.querySelector('#message-input-container')?.outerHTML.slice(-2500) || '',
          stop_visible: Boolean(document.querySelector('#message-input-container button[aria-label="Stop"]')),
          buttons: [...document.querySelectorAll('button')].map(node => node.getAttribute('aria-label') || node.getAttribute('title') || node.innerText.trim()).filter(Boolean).slice(0, 30),
          assistant: document.querySelector('#response-content-container')?.innerText.slice(-500) || '',
        }));
        throw new Error(`browser chat did not complete: ${JSON.stringify({ state, networkEvents })}`);
      }
    });

    await timed('conversation survives browser reload', async () => {
      await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForSelector('#chat-input', { timeout: 30000 });
      await page.waitForFunction(
        expected => document.querySelector('#response-content-container')?.innerText.includes(expected),
        expectedReply,
        { timeout: 30000 },
      );
      if (fixtureFile && !(await page.locator('body').innerText()).includes('candidate-usability.txt')) {
        throw new Error('uploaded file reference did not persist with the reloaded conversation');
      }
    });

    if (pageErrors.length) throw new Error(`browser reported ${pageErrors.length} page error(s)`);
    console.log(JSON.stringify({ status: 'PASS', checks, browser_errors: 0 }));
  } catch (error) {
    console.error(JSON.stringify({ status: 'FAIL', checks, browser_errors: pageErrors.length, network_events: networkEvents, error: String(error.message || error) }));
    process.exitCode = 1;
  } finally {
    await browser.close().catch(() => {});
  }
})();
