#!/usr/bin/env node

/*
 * Real-browser daily-use smoke/soak harness.
 *
 * Credentials are supplied only through the environment. This file never
 * prints them and is intentionally limited to the production UI contract.
 * Use HADES_DOM_PASSWORD from a protected input mechanism, not a committed
 * file or command history.
 */

const fs = require('node:fs');
const path = require('node:path');
const { protectedInput } = require('./dom-protected-input');

let playwright;
try {
  playwright = require('playwright');
} catch (_) {
  playwright = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');
}

const baseUrl = process.env.HADES_DOM_BASE_URL || 'http://127.0.0.1:3000/';
const email = protectedInput('HADES_DOM_EMAIL');
const password = protectedInput('HADES_DOM_PASSWORD');
const storageStateText = protectedInput('HADES_DOM_STORAGE_STATE');
let storageState = null;
if (storageStateText) {
  try { storageState = JSON.parse(storageStateText); }
  catch (_) { console.error('FAIL invalid protected HADES_DOM_STORAGE_STATE_FILE JSON'); process.exit(2); }
}
const timeoutMs = Number(process.env.HADES_DOM_TIMEOUT_MS || 30000);
const artifactDir = process.env.HADES_DOM_ARTIFACT_DIR || '/tmp/hades-dom-soak';
const viewport = {
  width: Number(process.env.HADES_DOM_VIEWPORT_WIDTH || 1440),
  height: Number(process.env.HADES_DOM_VIEWPORT_HEIGHT || 900),
};

if (!storageState && (!email || !password)) {
  console.error('FAIL missing protected owner password or storage state input');
  process.exit(2);
}

fs.mkdirSync(artifactDir, { recursive: true, mode: 0o700 });
const results = [];
const started = Date.now();
let activeBrowser = null;

async function closeOnSignal(signal) {
  await activeBrowser?.close().catch(() => {});
  process.exit(signal === 'SIGINT' ? 130 : 143);
}

process.once('SIGINT', () => { void closeOnSignal('SIGINT'); });
process.once('SIGTERM', () => { void closeOnSignal('SIGTERM'); });

function safeUrl(url) {
  try {
    const parsed = new URL(url);
    return `${parsed.origin}${parsed.pathname}`;
  } catch (_) {
    return '<invalid-url>';
  }
}

async function withTimeout(name, fn) {
  const begin = Date.now();
  try {
    const value = await Promise.race([
      fn(),
      new Promise((_, reject) => setTimeout(() => reject(new Error(`stage timeout after ${timeoutMs}ms`)), timeoutMs)),
    ]);
    results.push({ name, status: 'PASS', ms: Date.now() - begin });
    return value;
  } catch (error) {
    results.push({ name, status: 'FAIL', ms: Date.now() - begin, error: String(error.message || error) });
    throw error;
  }
}

(async () => {
  const browser = await playwright.chromium.launch({ headless: true });
  activeBrowser = browser;
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport, ...(storageState ? { storageState } : {}) });
  const page = await context.newPage();
  const network = [];
  const browserErrors = [];
  const browserErrorDetails = [];
  let completionRequests = 0;
  const browserEvents = [];

  page.on('console', message => {
    if (message.type() === 'error') browserErrors.push(`console: ${message.text()}`);
  });
  page.on('pageerror', error => {
    const message = `page: ${error.message}`;
    browserErrors.push(message);
    browserErrorDetails.push({ type: 'pageerror', message: error.message, stack: error.stack || '' });
  });
  page.on('requestfailed', request => network.push({ type: 'failed', url: safeUrl(request.url()), error: request.failure()?.errorText }));
  page.on('request', request => {
    if (request.url().includes('/api/chat/completions')) {
      completionRequests += 1;
      network.push({ type: 'completion-request', url: safeUrl(request.url()) });
    }
  });
  page.on('response', response => {
    if (response.status() >= 400) network.push({ type: 'http-error', status: response.status(), url: safeUrl(response.url()) });
  });

  try {
    await withTimeout('navigate', async () => {
      const deadline = Date.now() + timeoutMs;
      let lastError;
      while (Date.now() < deadline) {
        try {
          await page.goto(baseUrl, { waitUntil: 'commit', timeout: Math.min(5000, Math.max(1000, deadline - Date.now())) });
          await page.waitForURL(/\/auth(?:\?|$)/, { timeout: Math.min(5000, Math.max(1000, deadline - Date.now())) }).catch(() => {});
          if (page.url().includes('/auth')) return;
        } catch (error) {
          lastError = error;
          if (page.url().includes('/auth') || await page.locator('input[type="email"]').count()) return;
        }
        await page.waitForTimeout(500);
      }
      throw lastError || new Error('HADES UI did not become ready');
    });
    await page.exposeFunction('__hadesRecordDomEvent', event => browserEvents.push(event));
    await page.evaluate(() => {
      window.addEventListener('error', event => window.__hadesRecordDomEvent?.({
        type: 'window-error',
        message: event.message || 'window error',
        filename: event.filename || '',
        line: event.lineno || 0,
        column: event.colno || 0,
        stack: event.error?.stack || '',
      }), true);
      window.addEventListener('unhandledrejection', event => window.__hadesRecordDomEvent?.({
        type: 'unhandled-rejection',
        reason: String(event.reason?.message || event.reason || 'unhandled rejection'),
        stack: event.reason?.stack || '',
      }), true);
    });
    if (storageState) {
      await withTimeout('restore protected browser session', async () => {
        await page.waitForSelector('#chat-input', { timeout: timeoutMs });
      });
    } else {
      const ldapUsernameField = page.locator('#username');
      if (await ldapUsernameField.count()) {
        await withTimeout('authenticate via LDAP', async () => {
          await ldapUsernameField.fill(email);
          await page.locator('#password').fill(password);
          await page.getByRole('button', { name: /authenticate/i }).click();
          await page.waitForSelector('#chat-input', { timeout: timeoutMs });
        });
      } else {
      const emailField = page.locator('input[type="email"]');
      if (!await emailField.count()) {
        const emailOption = page.getByText('Continue with Email', { exact: true });
        await withTimeout('show email login', async () => {
          await emailOption.waitFor({ state: 'visible', timeout: timeoutMs });
          await emailOption.click();
          await emailField.waitFor({ state: 'visible', timeout: timeoutMs });
        });
      }
      await withTimeout('authenticate', async () => {
        await emailField.fill(email);
        await page.locator('input[type="password"]').fill(password);
        await page.locator('button[type="submit"]').click();
        await page.waitForSelector('#chat-input', { timeout: timeoutMs });
      });
      }
    }
    await page.evaluate(() => {
      window.addEventListener('keydown', event => window.__hadesRecordDomEvent?.({
        type: 'keydown', key: event.key, target: event.target?.id || event.target?.tagName,
        defaultPrevented: event.defaultPrevented,
      }), true);
      window.addEventListener('submit', event => window.__hadesRecordDomEvent?.({
        type: 'submit', target: event.target?.id || event.target?.tagName,
        defaultPrevented: event.defaultPrevented,
      }), true);
    });

    await withTimeout('global UI clutter absent', async () => {
      const text = await page.locator('body').innerText();
      if (/Financial CSV|hades-finance-csv-button|hades-receipt-ocr-button/i.test(text)) {
        throw new Error('global finance/receipt action is visible');
      }
      const unattachedReceiptAction = await page.evaluate(() => {
        const action = document.querySelector('#hades-receipt-ocr-contextual-button');
        if (!action) return false;
        const attachedChip = [...document.querySelectorAll('button')].some(button =>
          /\.(?:png|jpe?g|webp)(?:\s|$)/i.test(button.textContent || '') && !button.matches('[aria-label="Remove File"]')
        );
        return !attachedChip && !(window.__hadesUploadedFileIds?.size);
      });
      if (unattachedReceiptAction) throw new Error('contextual receipt action is visible without an attached image');
    });

    if (process.env.HADES_DOM_RECEIPT_ROTATION === '1') {
      await withTimeout('receipt attachment rotation', async () => {
        const receiptFiles = (process.env.HADES_RECEIPT_FILES || '/tmp/receipt-partial.png,/tmp/receipt-rotated.png')
          .split(',').map(value => value.trim()).filter(Boolean);
        for (const receiptFile of receiptFiles) {
          const fileInputs = page.locator('input[type="file"]');
          if (!await fileInputs.count()) throw new Error(`no file input for ${receiptFile}`);
          await fileInputs.last().setInputFiles(receiptFile);
          await page.waitForTimeout(1200);
          const review = page.locator('#hades-receipt-ocr-contextual-button');
          if (!await review.count()) throw new Error(`contextual receipt review did not appear for ${receiptFile}`);
          await review.click();
          await page.waitForTimeout(500);
          if (!await page.locator('#hades-receipt-ocr-modal').count()) {
            throw new Error(`contextual receipt review button did not open its modal for ${receiptFile}`);
          }
          await page.getByRole('button', { name: 'Preview OCR', exact: true }).click();
          // OCR is local CPU work; allow a bounded completion window so a slow
          // image is distinguished from an actually eternal spinner.
          await page.waitForTimeout(30000);
          const modalText = await page.locator('#hades-receipt-ocr-modal').innerText();
          if (!/Receipt review|couldn't read that receipt|could not identify|receipt reader is unavailable|nothing was added/i.test(modalText)) {
            throw new Error(`receipt preview did not render review/error state for ${receiptFile}`);
          }
          await page.locator('#hades-receipt-ocr-modal').getByRole('button', { name: 'Close', exact: true }).click({ force: true });
          const removeFile = page.locator('button[aria-label="Remove File"]:visible');
          if (await removeFile.count()) {
            await removeFile.last().click();
            await page.waitForTimeout(300);
          }
        }
      });
    }

    if (process.env.HADES_DOM_DEPENDENCY_PROBE === 'searxng') {
      await withTimeout('SearXNG outage recovery', async () => {
        const probeInput = page.locator('#chat-input');
        await probeInput.fill('look this up for me: what is the latest Linux kernel version');
        await probeInput.press('Enter');
        await page.waitForTimeout(40000);
        const failedState = await page.evaluate(() => ({
          stop: Boolean(document.querySelector('#message-input-container button[aria-label="Stop"]')),
          composer: document.querySelector('#chat-input')?.value || '',
          body: document.body.innerText.slice(-1400),
        }));
        if (failedState.stop) throw new Error('SearXNG outage left the composer in a stale Stop state');
        await probeInput.fill('hello, unrelated question');
        await probeInput.press('Enter');
        await page.waitForTimeout(5000);
        const recoveredState = await page.evaluate(() => ({
          stop: Boolean(document.querySelector('#message-input-container button[aria-label="Stop"]')),
          composer: document.querySelector('#chat-input')?.value || '',
          body: document.body.innerText.slice(-1400),
        }));
        if (recoveredState.stop) throw new Error('unrelated follow-up remained blocked after SearXNG failure');
      });
    }

    if (process.env.HADES_DOM_FINANCE_ROTATION === '1') {
      await withTimeout('finance CSV contextual preview', async () => {
        const financeFile = process.env.HADES_FINANCE_FILE || '/tmp/hades-synthetic-checking.csv';
        const fileInputs = page.locator('input[type="file"]');
        if (!await fileInputs.count()) throw new Error(`no file input for ${financeFile}`);
        await fileInputs.last().setInputFiles(financeFile);
        await page.waitForTimeout(1200);
        const review = page.locator('#hades-finance-csv-contextual-button');
        if (!await review.count()) throw new Error('contextual CSV review action did not appear');
        await review.click();
        const modal = page.locator('#hades-finance-csv-modal');
        await modal.waitFor({ state: 'visible', timeout: timeoutMs });
        await modal.getByRole('button', { name: 'Review statement', exact: true }).click();
        await page.waitForTimeout(5000);
        const text = await modal.innerText();
        if (process.env.HADES_DOM_FINANCE_EXPECT_AMBIGUOUS === '1') {
          if (!/Date range: not detected|I need help matching the columns|Which account should receive/i.test(text)) {
            throw new Error('ambiguous finance statement did not produce a human-readable review request');
          }
        } else if (!/transaction rows|Which account should receive/i.test(text)) {
          throw new Error('finance CSV preview did not show row/account review state');
        }
        await modal.getByRole('button', { name: 'Close', exact: true }).click({ force: true });
      });
    }

    if (process.env.HADES_DOM_NOVICE_ROTATION === '1') {
      await withTimeout('novice language rotation', async () => {
        const prompts = [
          'milk?',
          'whats runing on tartarus',
          'what can i cook with what we have',
          'can u check the server thing',
        ];
        const noviceInput = page.locator('#chat-input');
        const observations = [];
        for (const prompt of prompts) {
          const started = Date.now();
          await noviceInput.fill(prompt);
          await noviceInput.press('Enter');
          await page.waitForTimeout(30000);
          const observation = await page.evaluate((value) => ({
            prompt: value,
            elapsedMs: Date.now(),
            stop: Boolean(document.querySelector('#message-input-container button[aria-label="Stop"]')),
            composer: document.querySelector('#chat-input')?.value || '',
            assistantText: [...document.querySelectorAll('#response-content-container .markdown-prose')]
              .at(-1)?.innerText?.trim() || '',
            tail: document.body.innerText.slice(-900),
          }), prompt);
          observation.elapsedMs = Date.now() - started;
          observations.push(observation);
          if (!observation.assistantText) {
            throw new Error(`novice prompt produced a blank assistant response: ${prompt}`);
          }
          const prior = observations.slice(0, -1).find(item => item.assistantText === observation.assistantText);
          if (prior) {
            throw new Error(`novice prompt repeated a prior assistant response (${prior.prompt} -> ${prompt})`);
          }
          if (/Connection error|There was an issue with the response/i.test(observation.tail)) {
            throw new Error(`novice prompt produced a visible provider failure: ${prompt}`);
          }
        }
        results.push({ name: 'novice-language-observations', status: 'INFO', observations });
        if (browserErrors.length) throw new Error(`novice rotation browser error: ${browserErrors[0]}`);
      });
    }

    const input = page.locator('#chat-input');
    await withTimeout('rapid-send lifecycle', async () => {
      await input.fill('Give me a useful but detailed explanation of how refrigerators work.');
      await input.press('Enter');
      await page.waitForTimeout(100);
      await input.fill('whats in the pantry');
      await input.press('Enter');
      await page.waitForTimeout(300);
      const rapidState = await page.evaluate(() => {
        const inputElement = document.querySelector('#chat-input');
        const notice = document.querySelector('#hades-composer-busy-notice');
        const stop = document.querySelector('#message-input-container button[aria-label="Stop"]');
        return {
          notice: Boolean(notice), noticeText: notice?.textContent || '',
          composer: inputElement?.value || inputElement?.textContent || '',
          stop: Boolean(stop), guard: Boolean(window.__hadesCompletionFetchGuard),
        };
      });
      rapidState.events = browserEvents;
      results.push({ name: 'rapid-send-state', status: 'INFO', ...rapidState });
      if (!rapidState.notice && rapidState.stop && !rapidState.composer.trim()) {
        throw new Error('rapid follow-up was silently discarded while Stop remained active');
      }
    });

    await withTimeout('reload and re-entry', async () => {
      await page.reload({ waitUntil: 'commit', timeout: timeoutMs });
      await page.waitForSelector('#chat-input', { timeout: timeoutMs });
      await page.locator('#chat-input').fill('hello after reload');
      await page.locator('#chat-input').press('Enter');
    });

    await withTimeout('abandonment and re-entry', async () => {
      const reentryInput = page.locator('#chat-input');
      await reentryInput.fill('give me a deliberately slow, detailed answer about household network safety');
      await reentryInput.press('Enter');
      await page.waitForTimeout(100);
      await page.reload({ waitUntil: 'commit', timeout: timeoutMs });
      await page.waitForSelector('#chat-input', { timeout: timeoutMs });
      await reentryInput.fill('after reconnect can you answer a simple question');
      await reentryInput.press('Enter');
      await page.waitForTimeout(500);
      const reentryState = await page.evaluate(() => ({
        url: location.href,
        composerPresent: Boolean(document.querySelector('#chat-input')),
        composerValue: document.querySelector('#chat-input')?.value || '',
        stopVisible: Boolean(document.querySelector('#message-input-container button[aria-label="Stop"]')),
        assistantSlots: document.querySelectorAll('#response-content-container .markdown-prose').length,
        bodyTail: document.body.innerText.slice(-1200),
      }));
      browserEvents.push({ type: 'abandonment-reentry-state', ...reentryState });
      const nullState = browserErrors.find(error => /null.*length|length.*null/i.test(error))
        || browserEvents.find(event => /null.*length|length.*null/i.test(JSON.stringify(event)));
      if (nullState) throw new Error(`abandonment re-entry null-state error: ${nullState}`);
      if (!reentryState.composerPresent) throw new Error('composer missing after abandonment re-entry');
    });

    await withTimeout('same-user multi-tab concurrency', async () => {
      const secondPage = await context.newPage();
      const secondErrors = [];
      secondPage.on('pageerror', error => secondErrors.push(error.message));
      try {
        await secondPage.goto(baseUrl, { waitUntil: 'commit', timeout: timeoutMs });
        await secondPage.waitForSelector('#chat-input', { timeout: timeoutMs });
        await secondPage.locator('#chat-input').fill('what is the simplest way to check my server health');
        await secondPage.locator('#chat-input').press('Enter');
        await page.locator('#chat-input').fill('write a short note about keeping backups');
        await page.locator('#chat-input').press('Enter');
        await page.waitForTimeout(500);
        await secondPage.reload({ waitUntil: 'commit', timeout: timeoutMs });
        await secondPage.waitForSelector('#chat-input', { timeout: timeoutMs });
        if (secondErrors.length) throw new Error(`second tab browser error: ${secondErrors[0]}`);
      } finally {
        await secondPage.close().catch(() => {});
      }
    });

    const report = {
      status: 'PASS',
      baseUrl: safeUrl(baseUrl),
      elapsedMs: Date.now() - started,
      completionRequests,
      browserErrors,
      browserErrorDetails,
      network,
      browserEvents,
      stages: results,
      conversationUrl: safeUrl(page.url()),
      viewport,
    };
    fs.writeFileSync(path.join(artifactDir, 'report.json'), `${JSON.stringify(report, null, 2)}\n`, { mode: 0o600 });
    console.log(JSON.stringify(report));
  } catch (error) {
    const screenshot = path.join(artifactDir, 'failure.png');
    await page.screenshot({ path: screenshot, fullPage: true }).catch(() => {});
    const report = {
      status: 'FAIL',
      baseUrl: safeUrl(baseUrl),
      elapsedMs: Date.now() - started,
      error: String(error.message || error),
      completionRequests,
      browserErrors,
      browserErrorDetails,
      network,
      browserEvents,
      stages: results,
      conversationUrl: safeUrl(page.url()),
      viewport,
      screenshot,
    };
    fs.writeFileSync(path.join(artifactDir, 'report.json'), `${JSON.stringify(report, null, 2)}\n`, { mode: 0o600 });
    console.error(JSON.stringify(report));
    process.exitCode = 1;
  } finally {
    await browser.close().catch(() => {});
    activeBrowser = null;
  }
})();
