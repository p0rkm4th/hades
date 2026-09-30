#!/usr/bin/env node

/* Bounded real-DOM receipt rotation. Credentials are environment-only. */
const fs = require('node:fs');
const { protectedInput } = require('./dom-protected-input');
let playwright;
try { playwright = require('playwright'); } catch (_) {
  playwright = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');
}

const baseUrl = process.env.HADES_DOM_BASE_URL || 'http://127.0.0.1:3000/';
const email = protectedInput('HADES_DOM_EMAIL');
const password = protectedInput('HADES_DOM_PASSWORD');
const storageStateText = protectedInput('HADES_DOM_STORAGE_STATE');
let storageState = null;
if (storageStateText) {
  try { storageState = JSON.parse(storageStateText); }
  catch (_) { throw new Error('invalid protected HADES_DOM_STORAGE_STATE_FILE JSON'); }
}
const files = (process.env.HADES_RECEIPT_FILES || '/tmp/receipt-partial.png,/tmp/receipt-rotated.png')
  .split(',').map(value => value.trim()).filter(Boolean);
if (!storageState && (!email || !password)) throw new Error('protected owner password or storage state input is required');

(async () => {
  const browser = await playwright.chromium.launch({ headless: true });
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 390, height: 844 }, ...(storageState ? { storageState } : {}) });
  const page = await context.newPage();
  const errors = [];
  const expectedResourceFailures = [];
  const isExpectedServerFailure = text => /Failed to load resource.*status of 5\d\d/i.test(text);
  page.on('pageerror', error => {
    if (isExpectedServerFailure(error.message)) expectedResourceFailures.push(error.message);
    else errors.push(error.message);
  });
  page.on('console', message => {
    if (message.type() !== 'error') return;
    const text = message.text();
    if (isExpectedServerFailure(text)) {
      expectedResourceFailures.push(text);
      return;
    }
    errors.push(text);
  });
  const result = { files: [], errors, expectedResourceFailures };
  try {
    await page.goto(baseUrl, { waitUntil: 'commit', timeout: 30000 });
    await page.waitForURL(/\/auth(?:\?|$)/, { timeout: 5000 }).catch(() => {});
    let emailField = page.locator('input[type="email"]:visible, #username:visible');
    if (page.url().includes('/auth') && !storageState) {
      if (!await emailField.count()) {
        await page.getByText('Continue with Email', { exact: true }).click();
        emailField = page.locator('input[type="email"]:visible, #username:visible');
        await emailField.waitFor({ state: 'visible', timeout: 30000 });
      }
      await emailField.fill(email);
      await page.locator('input[type="password"]:visible, #password:visible').fill(password);
      await page.locator('button[type="submit"]:visible, button:has-text("Sign in"):visible, button:has-text("Authenticate"):visible').first().click();
    }
    await page.waitForSelector('#chat-input', { timeout: 30000 });
    for (const file of files) {
      const inputs = page.locator('input[type="file"]');
      if (!await inputs.count()) throw new Error(`no file input for ${file}`);
      await inputs.last().setInputFiles(file);
      await page.waitForTimeout(1500);
      const review = page.getByRole('button', { name: 'Review receipt', exact: true });
      const entry = { file, reviewVisible: await review.count() > 0 };
      if (process.env.HADES_RECEIPT_EXPECT_NO_REVIEW === '1' && entry.reviewVisible) {
        throw new Error(`unsupported attachment incorrectly exposed receipt review for ${file}`);
      }
      if (entry.reviewVisible) {
        await review.click();
        const preview = page.getByRole('button', { name: 'Preview OCR', exact: true });
        await preview.click();
        await page.waitForFunction(() => {
          const text = document.querySelector('#hades-receipt-ocr-modal')?.innerText || '';
          return !/Running local OCR preview…|Running local OCR preview\.\.\./i.test(text);
        }, { timeout: 30000 });
        entry.reviewText = (await page.locator('#hades-receipt-ocr-modal').innerText()).slice(0, 2000);
        entry.ocrTerminal = /Receipt review|couldn.t read that receipt|could not identify|preview failed|receipt reader is unavailable|nothing was added/i.test(entry.reviewText);
        if (!entry.ocrTerminal) throw new Error(`receipt OCR did not reach a terminal review/error state for ${file}`);
        entry.confirmVisible = await page.getByRole('button', { name: /Confirm and add to pantry/ }).count() > 0;
        if (process.env.HADES_RECEIPT_APPLY === '1' && entry.confirmVisible) {
          const modal = page.locator('#hades-receipt-ocr-modal');
          const selects = modal.locator('select');
          for (let index = 0; index < await selects.count(); index += 1) {
            const select = selects.nth(index);
            if (await select.isEnabled() && await select.locator('option').count()) {
              const value = await select.locator('option').first().getAttribute('value');
              if (value) await select.selectOption(value);
            }
          }
          await page.getByRole('button', { name: /Confirm and add to pantry/ }).click();
          await page.waitForTimeout(2500);
          entry.applyText = (await modal.innerText()).slice(-800);
          entry.applyStatus = /Grocy confirmed the update|already added|needs reconciliation/i.test(entry.applyText)
            ? 'PASS' : 'FAIL';
          if (entry.applyStatus === 'FAIL') throw new Error(`receipt apply did not show a canonical outcome for ${file}`);
        }
        await page.getByRole('button', { name: 'Close', exact: true }).click();
      }
      result.files.push(entry);
    }
    result.errors = errors.filter(error => !isExpectedServerFailure(error));
    result.status = result.errors.length ? 'FAIL' : 'PASS';
    console.log(JSON.stringify(result));
    process.exitCode = result.status === 'PASS' ? 0 : 1;
  } catch (error) {
    result.status = 'FAIL';
    result.error = String(error.message || error);
    result.url = page.url();
    result.bodyTail = (await page.locator('body').innerText().catch(() => '')).slice(-1200);
    await page.screenshot({ path: '/tmp/hades-dom-receipt-rotation-failure.png', fullPage: true }).catch(() => {});
    console.log(JSON.stringify(result));
    process.exitCode = 1;
  } finally { await browser.close(); }
})();
