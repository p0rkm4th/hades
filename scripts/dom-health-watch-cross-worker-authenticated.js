#!/usr/bin/env node

/* Exercise Health Watch stale-worker confirmation precedence in one real UI chat. */
const fs = require('node:fs');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const base = process.env.HADES_HW_UI_BASE_URL;
const reportPath = process.env.HADES_HW_UI_REPORT;
const email = process.env.HADES_HW_UI_EMAIL;
const password = process.env.HADES_HW_UI_PASSWORD;
const workerA = process.env.HADES_HW_UI_MODEL_A;
const workerB = process.env.HADES_HW_UI_MODEL_B;
if (![base, reportPath, email, password, workerA, workerB].every(Boolean)) {
  throw new Error('synthetic Health Watch UI inputs are required');
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const result = { status: 'PASS', checks: {} };
  try {
    const login = await fetch(`${base}/api/v1/auths/signin`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!login.ok) throw new Error(`synthetic Alpha login failed: HTTP ${login.status}`);
    const { token } = await login.json();
    const context = await browser.newContext({ viewport: { width: 1365, height: 850 } });
    try {
      await context.addCookies([{ name: 'token', value: token, url: `${base}/` }]);
      const page = await context.newPage();
      await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForSelector('#chat-input', { timeout: 30000 });
      const welcome = page.getByRole('button', { name: /okay,\s*let.s go/i });
      if (await welcome.count()) await welcome.first().click({ force: true });
      const dismiss = page.getByRole('button', { name: /dismiss|close/i });
      if (await dismiss.count()) await dismiss.last().click({ force: true }).catch(() => {});

      async function selectModel(modelId) {
        if (workerA === workerB && await page.getByRole('button', { name: new RegExp(workerA.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i') }).count()) return;
        const selector = page.getByRole('button', {
          name: new RegExp(`select a model|${[workerA, workerB].map(value => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')}`, 'i'),
        }).first();
        await selector.waitFor({ state: 'visible', timeout: 15000 });
        await selector.click({ force: true });
        const option = page.getByText(new RegExp(modelId.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i')).last();
        await option.waitFor({ state: 'visible', timeout: 10000 });
        await option.click();
        await page.waitForTimeout(250);
      }

      async function ask(prompt) {
        const selector = '#response-content-container .markdown-prose';
        const before = await page.locator(selector).count();
        await page.locator('#chat-input').fill(prompt);
        const submit = page.locator('#send-message-button:visible').last();
        await submit.waitFor({ state: 'visible', timeout: 10000 });
        await submit.evaluate(element => element.click());
        const deadline = Date.now() + 60000;
        while (Date.now() < deadline) {
          const messages = page.locator(selector);
          if (await messages.count() > before) {
            const text = (await messages.last().innerText()).trim();
            const streaming = await page.locator('#message-input-container button[aria-label="Stop"]').count();
            if (text && !streaming) {
              await page.waitForTimeout(1000);
              return text;
            }
          }
          await page.waitForTimeout(200);
        }
        throw new Error(`no settled answer for ${JSON.stringify(prompt)}; page=${(await page.locator('body').innerText()).slice(-1000)}`);
      }

      await selectModel(workerA);
      const first = await ask('Monitor HADES Core if it goes offline every 10 minutes.');
      if (!/create it\?/i.test(first) || !/cannot restart or modify the server/i.test(first)) {
        throw new Error(`worker A did not return the bounded create preview: ${first}`);
      }
      const chatUrl = page.url();
      result.checks.workerACreatePreview = 'PASS; authenticated UI received explicit, read-only preview';

      await selectModel(workerB);
      const second = await ask('Share HADES Core Watch with household-a.');
      if (!/shall i share it with `?household-a`?/i.test(second)) {
        throw new Error(`worker B did not return the current share preview: ${second}`);
      }
      if (page.url() !== chatUrl) throw new Error('Open WebUI changed conversations while switching Hermes workers');
      result.checks.workerBSharePreview = 'PASS; second Hermes process persisted share preview in the same chat';

      await selectModel(workerA);
      const confirmation = await ask('Yes.');
      if (!/updated sharing/i.test(confirmation) || !/household-a/i.test(confirmation)) {
        throw new Error(`worker A did not apply the persisted current share action: ${confirmation}`);
      }
      if (page.url() !== chatUrl) throw new Error('confirmation left the original WebUI conversation');
      result.checks.workerAConfirmation = 'PASS; persisted share action beat worker A stale create cache';
      result.checks.sameAuthenticatedConversation = 'PASS';

      const chatsResponse = await fetch(`${base}/api/v1/chats/${encodeURIComponent(chatUrl.split('/').filter(Boolean).at(-1))}`, {
        headers: { authorization: `Bearer ${token}` },
      });
      if (!chatsResponse.ok) throw new Error(`authenticated chat persistence lookup failed: HTTP ${chatsResponse.status}`);
      const persisted = JSON.stringify(await chatsResponse.json());
      for (const phrase of ['Monitor HADES Core if it goes offline every 10 minutes.', 'Share HADES Core Watch with household-a.', 'Yes.']) {
        if (!persisted.includes(phrase)) throw new Error(`chat history did not persist ${JSON.stringify(phrase)}`);
      }
      result.checks.chatPersistence = 'PASS; all three user turns persisted in the same authenticated chat';

      await page.goto(`${base}/`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForSelector('#chat-input', { timeout: 15000 });
      if (await page.locator('#response-content-container .markdown-prose').count()) {
        throw new Error('root navigation did not open a fresh chat composer');
      }
      await selectModel(workerA);
      const endpointAsk = 'Can you spin up a Minecraft server for me and lemme know the server port/ip so I can add it to the firewall?';
      const endpointAnswer = await ask(endpointAsk);
      for (const expected of [
        'Plan only', 'minecraft', 'gamma-minecraft', '4 CPU cores', '8 GiB RAM',
        '40 GiB disk', 'SyntheticNode', 'owner only', 'TCP 25565',
        'does not confirm Minecraft is installed or running',
        'cannot read back the guest IP', 'No firewall rule will be changed', 'reply Create it',
      ]) {
        if (!endpointAnswer.includes(expected)) throw new Error(`exact Minecraft dogfood omitted ${expected}: ${endpointAnswer}`);
      }
      if (/^Created\b|VMID\s+\d+/im.test(endpointAnswer)) {
        throw new Error(`exact Minecraft dogfood created a server before confirmation: ${endpointAnswer}`);
      }
      result.checks.minecraftDogfoodPreview = 'PASS; explicit spin-up intent received a bounded plan despite also asking for an endpoint';
      await selectModel(workerB);
      const endpointContinuation = await ask('Perfect, continue');
      for (const expected of [
        'Plan only', 'minecraft', 'gamma-minecraft', '4 CPU cores', '8 GiB RAM',
        '40 GiB disk', 'SyntheticNode', 'owner only', 'TCP 25565',
        'does not confirm Minecraft is installed or running',
        'cannot read back the guest IP', 'No firewall rule will be changed', 'reply Create it',
      ]) {
        if (!endpointContinuation.includes(expected)) throw new Error(`exact dogfood continuation omitted ${expected}: ${endpointContinuation}`);
      }
      if (/^Created\b|VMID\s+\d+/im.test(endpointContinuation)) {
        throw new Error(`exact dogfood continuation created a server before confirmation: ${endpointContinuation}`);
      }
      result.checks.minecraftDogfoodContinuation = 'PASS; cross-worker acknowledgement recovered the same plan without writes';
      await selectModel(workerA);
      const provisioningResult = await ask('Create it');
      for (const expected of [
        'Created the minecraft VM gamma-minecraft',
        'Proxmox reports the VM running',
        "haven't confirmed that Minecraft itself is running",
        "can't give you a firewall-ready endpoint",
        'No firewall rule was changed',
      ]) {
        if (!provisioningResult.includes(expected)) throw new Error(`authenticated create result omitted ${expected}: ${provisioningResult}`);
      }
      if (/192\.168\.|25565/.test(provisioningResult)) throw new Error(`create result invented a game endpoint: ${provisioningResult}`);
      result.checks.minecraftProvisioningResultHonesty = 'PASS; authenticated owner saw VM-only status, unverified game/IP state, and no-firewall statement after synthetic Proxmox success';
      const provisionChatId = page.url().split('/').filter(Boolean).at(-1);
      const provisionChatResponse = await fetch(`${base}/api/v1/chats/${encodeURIComponent(provisionChatId)}`, {
        headers: { authorization: `Bearer ${token}` },
      });
      if (!provisionChatResponse.ok) throw new Error(`provisioning chat persistence lookup failed: HTTP ${provisionChatResponse.status}`);
      const provisionHistory = JSON.stringify(await provisionChatResponse.json());
      for (const phrase of [endpointAsk, 'Perfect, continue', 'Create it']) {
        if (!provisionHistory.includes(phrase)) throw new Error(`provisioning chat history omitted ${JSON.stringify(phrase)}`);
      }
      result.checks.provisioningChatPersistence = 'PASS; request, continuation, and confirmation persisted in one authenticated Open WebUI chat';

      fs.writeFileSync(reportPath, `${JSON.stringify(result, null, 2)}\n`, { mode: 0o600 });
      fs.chmodSync(reportPath, 0o600);
      console.log(JSON.stringify({ status: 'PASS', report: reportPath }));
    } finally {
      await context.close();
    }
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  console.error(JSON.stringify({ status: 'FAIL', error: error.message }));
  process.exitCode = 1;
});
