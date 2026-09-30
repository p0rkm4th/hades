#!/usr/bin/env node

/* Authenticated household UI proof for staged automation creation and transparency. */
const fs = require('node:fs');
const crypto = require('node:crypto');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const base = (process.env.HADES_PHASE3_UI_BASE_URL || '').replace(/\/$/, '');
const email = process.env.HADES_PHASE3_UI_EMAIL;
const password = process.env.HADES_PHASE3_UI_PASSWORD;
const gammaEmail = process.env.HADES_PHASE3_UI_GAMMA_EMAIL;
const gammaPassword = process.env.HADES_PHASE3_UI_GAMMA_PASSWORD;
const modelId = process.env.HADES_PHASE3_UI_MODEL_ID;
const stateFile = process.env.HADES_PHASE3_UI_STATE_FILE;
if (!base || !email || !password || !gammaEmail || !gammaPassword || !modelId || !stateFile) throw new Error('synthetic Phase 3 UI inputs are required');
const sha256 = () => crypto.createHash('sha256').update(fs.readFileSync(stateFile)).digest('hex');

async function main() {
  const browser = await chromium.launch({ headless: true });
  try {
    const login = await fetch(`${base}/api/v1/auths/signin`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!login.ok) throw new Error(`synthetic household login failed: HTTP ${login.status}`);
    const { token } = await login.json();
    const gammaLogin = await fetch(`${base}/api/v1/auths/signin`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ email: gammaEmail, password: gammaPassword }),
    });
    if (!gammaLogin.ok) throw new Error(`synthetic Gamma login failed: HTTP ${gammaLogin.status}`);
    const { token: gammaToken } = await gammaLogin.json();
    const context = await browser.newContext({ viewport: { width: 1365, height: 850 } });
    const gammaContext = await browser.newContext({ viewport: { width: 1365, height: 850 } });
    try {
      async function openPageIn(target, authToken) {
        const page = await target.newPage();
        await target.addCookies([{ name: 'token', value: authToken, url: `${base}/` }]);
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
        if (await page.locator('#response-content-container .markdown-prose').count()) {
          const newChat = page.locator('[aria-label="New Chat"]:visible, #new-chat-button:visible, button:has-text("New Chat"):visible').last();
          await newChat.waitFor({ state: 'attached', timeout: 10000 });
          await newChat.click({ force: true });
          const deadline = Date.now() + 5000;
          while (Date.now() < deadline && await page.locator('#response-content-container .markdown-prose').count()) await page.waitForTimeout(200);
        }
        return page;
      }
      const openPage = () => openPageIn(context, token);
      const openGammaPage = () => openPageIn(gammaContext, gammaToken);

      async function ask(page, prompt, pattern) {
        const selector = '#response-content-container .markdown-prose';
        const before = await page.locator(selector).count();
        await page.locator('#chat-input').fill(prompt);
        const send = page.locator('#send-message-button:visible');
        if (await send.count()) await send.last().click({ force: true });
        else await page.locator('#chat-input').press('Enter');
        const deadline = Date.now() + 30000;
        while (Date.now() < deadline) {
          const messages = page.locator(selector);
          if (await messages.count() > before) {
            const text = (await messages.last().innerText()).trim();
            const streaming = await page.locator('#message-input-container button[aria-label="Stop"]').count();
            if (text && !streaming) {
              if (!pattern.test(text)) throw new Error(`unexpected answer to ${JSON.stringify(prompt)}: ${text}`);
              if (/private-synthetic|synthetic-household-subject|[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}/i.test(text)) {
                throw new Error(`internal identity or automation ID leaked in answer: ${text}`);
              }
              return text;
            }
          }
          await page.waitForTimeout(200);
        }
        throw new Error(`no settled answer for ${JSON.stringify(prompt)}`);
      }

      const createPage = await openPage();
      const preview = await ask(
        createPage,
        'Create a low inventory summary',
        /Low Grocery Summary[\s\S]*Schedule: weekly[\s\S]*saves a draft only[\s\S]*does not create or activate a schedule[\s\S]*Create it\?/i,
      );
      const pendingBeforeForeignYes = sha256();
      const foreignYesPage = await openPage();
      const foreignYes = await ask(
        foreignYesPage,
        'Yes',
        /couldn't match that confirmation to this conversation[\s\S]*nothing was changed/i,
      );
      const pendingAfterForeignYes = sha256();
      if (pendingAfterForeignYes !== pendingBeforeForeignYes) {
        throw new Error('confirmation from a different chat changed the pending draft state');
      }
      const created = await ask(
        createPage,
        'Yes',
        /Created your Low Inventory Summary draft[\s\S]*not running because it has not been connected to the HADES automation runner/i,
      );
      await ask(
        createPage,
        'Create a low inventory summary',
        /Low Grocery Summary[\s\S]*saves a draft only[\s\S]*Create it\?/i,
      );
      const duplicate = await ask(
        createPage,
        'Yes',
        /already have this automation saved[\s\S]*did not create a duplicate/i,
      );
      const weeklyPage = await openPage();
      const weeklyPreview = await ask(
        weeklyPage,
        'Create a weekly household summary',
        /Weekly Household Summary[\s\S]*Resources: Groceries[\s\S]*saves a draft only[\s\S]*does not create or activate a schedule[\s\S]*Create it\?/i,
      );
      const weeklyCreated = await ask(
        weeklyPage,
        'Yes',
        /Created your Weekly Household Summary draft[\s\S]*not running because it has not been connected to the HADES automation runner/i,
      );

      const sharePage = await openPage();
      const sharePrompt = await ask(
        sharePage,
        'Share my low inventory summary draft with Gamma',
        /Shall I share it\?/i,
      );
      const shared = await ask(sharePage, 'Yes', /Sharing is now enabled for that household member/i);
      const gammaSharedPage = await openGammaPage();
      const gammaSharedInventory = await ask(
        gammaSharedPage,
        'What automations do I have?',
        /not running[\s\S]*Low Inventory Summary[\s\S]*shared with you/i,
      );
      if (/private-synthetic|synthetic-household-subject|beta-phase3|[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}/i.test(gammaSharedInventory)) {
        throw new Error(`Gamma's shared inventory disclosed an internal identity: ${gammaSharedInventory}`);
      }
      const revokePage = await openPage();
      const revokePrompt = await ask(
        revokePage,
        'Revoke sharing of my low inventory summary draft from Gamma',
        /Shall I revoke sharing\?/i,
      );
      const revoked = await ask(revokePage, 'Yes', /Sharing is now revoked/i);
      const gammaRevokedPage = await openGammaPage();
      const gammaRevokedInventory = await ask(
        gammaRevokedPage,
        'What automations do I have?',
        /do not have any staged household automations yet/i,
      );

      const inventoryPage = await openPage();
      const inventory = await ask(inventoryPage, 'What automations do I have?', /draft automations[\s\S]*not running/i);
      if (!/Low Inventory Summary/i.test(inventory) || !/Weekly Household Summary/i.test(inventory) || !/Groceries/i.test(inventory)) {
        throw new Error(`household inventory omitted the useful automation description: ${inventory}`);
      }
      if (/low-inventory-summary|weekly-household-summary|STAGED|automation_id|resource_scope/i.test(inventory)) {
        throw new Error(`household inventory exposed internal draft machinery: ${inventory}`);
      }

      const stateBefore = sha256();
      const runPage = await openPage();
      const runResponse = await ask(
        runPage,
        'Can you run my low inventory summary draft?',
        /not connected to the HADES runner yet.*not run it or changed anything/i,
      );
      const stateAfter = sha256();
      if (stateAfter !== stateBefore) throw new Error('plain-language run request changed staged automation state');

      const chats = await fetch(`${base}/api/v1/chats/?page=1`, { headers: { authorization: `Bearer ${token}` } });
      if (!chats.ok) throw new Error(`authenticated chat history failed: HTTP ${chats.status}`);
      const payload = await chats.json();
      const rows = Array.isArray(payload) ? payload : (payload.items || payload.chats || []);
      let inventoryPersisted = false;
      let runPersisted = false;
      let createPersisted = false;
      let duplicatePersisted = false;
      let weeklyPersisted = false;
      let foreignYesPersisted = false;
      let sharePersisted = false;
      let revokePersisted = false;
      for (const chat of rows.slice(0, 12)) {
        const id = chat.id || chat.chat_id;
        if (!id) continue;
        const detail = await fetch(`${base}/api/v1/chats/${encodeURIComponent(id)}`, { headers: { authorization: `Bearer ${token}` } });
        if (!detail.ok) continue;
        const serialized = JSON.stringify(await detail.json());
        if (serialized.includes('Low Inventory Summary') && serialized.includes('not running')) inventoryPersisted = true;
        if (serialized.includes('not connected to the HADES runner yet') && serialized.includes('not run it')) runPersisted = true;
        if (serialized.includes('Create a low inventory summary') && serialized.includes('Created your Low Inventory Summary draft')) createPersisted = true;
        if (serialized.includes('already have this automation saved') && serialized.includes('did not create a duplicate')) duplicatePersisted = true;
        if (serialized.includes('Create a weekly household summary') && serialized.includes('Created your Weekly Household Summary draft')) weeklyPersisted = true;
        if (serialized.includes("couldn't match that confirmation to this conversation") && serialized.includes('nothing was changed')) foreignYesPersisted = true;
        if (serialized.includes('Sharing is now enabled for that household member')) sharePersisted = true;
        if (serialized.includes('Sharing is now revoked')) revokePersisted = true;
      }
      const gammaChats = await fetch(`${base}/api/v1/chats/?page=1`, { headers: { authorization: `Bearer ${gammaToken}` } });
      if (!gammaChats.ok) throw new Error(`Gamma chat history failed: HTTP ${gammaChats.status}`);
      const gammaPayload = await gammaChats.json();
      const gammaRows = Array.isArray(gammaPayload) ? gammaPayload : (gammaPayload.items || gammaPayload.chats || []);
      let gammaSharePersisted = false;
      let gammaRevokePersisted = false;
      for (const chat of gammaRows.slice(0, 12)) {
        const id = chat.id || chat.chat_id;
        if (!id) continue;
        const detail = await fetch(`${base}/api/v1/chats/${encodeURIComponent(id)}`, { headers: { authorization: `Bearer ${gammaToken}` } });
        if (!detail.ok) continue;
        const serialized = JSON.stringify(await detail.json());
        if (serialized.includes('Low Inventory Summary') && serialized.includes('shared with you')) gammaSharePersisted = true;
        if (serialized.includes('do not have any staged household automations yet')) gammaRevokePersisted = true;
      }
      if (!inventoryPersisted || !runPersisted || !createPersisted || !duplicatePersisted || !weeklyPersisted || !foreignYesPersisted || !sharePersisted || !revokePersisted || !gammaSharePersisted || !gammaRevokePersisted) throw new Error('household authorization and draft answers did not persist in authenticated chat history');

      const report = {
        status: 'PASS',
        ownerFacingInternalIds: 'NONE',
        creationPreview: preview,
        foreignChatConfirmation: foreignYes,
        creationConfirmation: created,
        weeklyCreationPreview: weeklyPreview,
        weeklyCreationConfirmation: weeklyCreated,
        sharePrompt,
        shareConfirmation: shared,
        gammaSharedInventory,
        revokePrompt,
        revokeConfirmation: revoked,
        gammaRevokedInventory,
        duplicateConfirmation: duplicate,
        inventoryAnswer: inventory,
        runAnswer: runResponse,
        userTurnModelInvocation: 'NONE; synthetic provider endpoint was intentionally unreachable',
        stateSha256BeforeAndAfter: stateBefore,
        authenticatedChatPersistence: 'PASS for both users: creation, cross-chat denial, sharing, revocation, duplicate protection, inventory, and run response',
      };
      const out = process.env.HADES_PHASE3_UI_REPORT || '/tmp/hades-phase3-draft-transparency.json';
      fs.writeFileSync(out, `${JSON.stringify(report, null, 2)}\n`, { mode: 0o600 });
      fs.chmodSync(out, 0o600);
      console.log(JSON.stringify({ status: 'PASS', report: out }));
      await inventoryPage.close();
      await runPage.close();
      await weeklyPage.close();
      await foreignYesPage.close();
      await createPage.close();
      await sharePage.close();
      await gammaSharedPage.close();
      await revokePage.close();
      await gammaRevokedPage.close();
    } finally {
      await context.close();
      await gammaContext.close();
    }
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  console.error(JSON.stringify({ status: 'FAIL', error: error.message }));
  process.exitCode = 1;
});
