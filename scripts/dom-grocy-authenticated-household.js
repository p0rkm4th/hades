#!/usr/bin/env node

/* Synthetic low-tech household flows through authenticated Open WebUI. */
const fs = require('node:fs');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const base = (process.env.HADES_GROCY_UI_BASE_URL || '').replace(/\/$/, '');
const email = process.env.HADES_GROCY_UI_EMAIL;
const password = process.env.HADES_GROCY_UI_PASSWORD;
const modelId = process.env.HADES_GROCY_UI_MODEL_ID;
const report = process.env.HADES_GROCY_UI_REPORT || '/tmp/hades-grocy-household-ui.json';
const failureFile = process.env.HADES_GROCY_UI_FAILURE_FILE;
if (!base || !email || !password || !modelId || !failureFile) throw new Error('synthetic Grocy UI inputs are required');

async function main() {
  const ownerServingOnly = process.env.HADES_GROCY_UI_OWNER_SERVING_ONLY === '1';
  const recipeScopeProbe = process.env.HADES_GROCY_UI_RECIPE_SCOPE_PROBE === '1';
  const recipeScopeOnly = process.env.HADES_GROCY_UI_RECIPE_SCOPE_ONLY === '1';
  const recipeAuthoring = process.env.HADES_GROCY_UI_RECIPE_AUTHORING === '1';
  const browser = await chromium.launch({ headless: true });
  const result = { status: 'PASS', checks: {} };
  try {
    const login = await fetch(`${base}/api/v1/auths/signin`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!login.ok) throw new Error(`synthetic household login failed: HTTP ${login.status}`);
    const { token } = await login.json();
    const context = await browser.newContext({ viewport: { width: 1365, height: 850 } });
    try {
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

      async function ask(prompt, targetPage = page, waitForSubmitReady = false) {
        if (!targetPage._hadesChatTransport) {
          targetPage._hadesChatTransport = [];
          targetPage._hadesBrowserErrors = [];
          targetPage.on('pageerror', error => targetPage._hadesBrowserErrors.push(error.message));
          targetPage.on('console', message => {
            const text = message.text();
            if (message.type() === 'error') targetPage._hadesBrowserErrors.push(text);
            else if (text.startsWith('submitHandler')) targetPage._hadesBrowserErrors.push(`debug ${text}`);
          });
          targetPage.on('requestfailed', request => {
            targetPage._hadesBrowserErrors.push(`requestfailed ${request.url()} ${request.failure()?.errorText || ''}`);
          });
          targetPage.on('response', response => {
            if (response.status() >= 400) {
              targetPage._hadesBrowserErrors.push(`HTTP ${response.status()} ${response.url()}`);
            }
          });
          targetPage.on('request', request => {
            if (request.url().includes('/api/chat/completions')) {
              targetPage._hadesChatTransport.push(`request ${request.method()} ${request.url()}`);
            }
          });
          targetPage.on('response', response => {
            if (response.url().includes('/api/chat/completions')) {
              targetPage._hadesChatTransport.push(`response ${response.status()} ${response.url()}`);
            }
          });
          targetPage.on('requestfailed', request => {
            if (request.url().includes('/api/chat/completions')) {
              targetPage._hadesChatTransport.push(`failed ${request.url()} ${request.failure()?.errorText || ''}`);
            }
          });
        }
        if (!targetPage._hadesUpdateToastChecked) {
          targetPage._hadesUpdateToastChecked = true;
          const updateToast = targetPage.locator('.absolute.bottom-8.right-8.z-50');
          try {
            await updateToast.waitFor({ state: 'visible', timeout: 2500 });
            await updateToast.getByRole('button').click();
            targetPage._hadesUpdateToastDismissed = true;
          } catch (_) {
            targetPage._hadesUpdateToastDismissed = false;
          }
        }
        const selector = '#response-content-container .markdown-prose';
        const priorMessages = targetPage.locator(selector);
        const before = await priorMessages.count();
        const beforeLastText = before ? (await priorMessages.last().innerText()).trim() : '';
        const composer = targetPage.locator('#chat-input');
        await composer.fill(prompt);
        if (ownerServingOnly && prompt === 'Yes, do it.' && !targetPage._hadesFormProbeDone) {
          targetPage._hadesFormProbeDone = true;
          await composer.fill('');
          await targetPage.waitForTimeout(100);
          await targetPage.evaluate(() => {
            const form = document.querySelector('#chat-input')?.closest('form');
            if (!form) {
              window.__hadesFormSubmitProbe = { formPresent: false };
              return;
            }
            const event = new Event('submit', { bubbles: true, cancelable: true });
            const dispatched = form.dispatchEvent(event);
            window.__hadesFormSubmitProbe = {
              formPresent: true, dispatched, defaultPrevented: event.defaultPrevented,
              childCount: form.children.length,
            };
          });
          await composer.fill(prompt);
        }
        const submit = targetPage.locator('#send-message-button:visible');
        if (await submit.count()) {
          if (waitForSubmitReady) {
            await targetPage.waitForFunction(() => {
              const buttons = [...document.querySelectorAll('#send-message-button')];
              const button = buttons.filter(item => item.offsetParent !== null).at(-1);
              return button && !button.disabled && button.getAttribute('aria-disabled') !== 'true';
            }, null, { timeout: 15000 });
            await submit.last().click();
          } else {
            await submit.last().click();
          }
        } else await targetPage.locator('#chat-input').press('Enter');
        const deadline = Date.now() + Number(process.env.HADES_GROCY_UI_TURN_TIMEOUT_MS || 60000);
        while (Date.now() < deadline) {
          const messages = targetPage.locator(selector);
          const currentCount = await messages.count();
          const currentText = currentCount ? (await messages.last().innerText()).trim() : '';
          // Some Open WebUI versions reuse the trailing markdown node while
          // advancing a conversation turn. Detect that replacement as well as
          // the usual appended node, while still requiring a completed stream.
          if (currentCount > before || (currentCount === before && currentText && currentText !== beforeLastText)) {
            const text = currentText;
            const streaming = await targetPage.locator('#message-input-container button[aria-label="Stop"]').count();
            if (text && !streaming) {
              // Hermes releases the per-user turn lease immediately after the
              // UI stops streaming; allow that final lifecycle event to land
              // before issuing the next synthetic turn.
              await targetPage.waitForTimeout(900);
              return text;
            }
          }
          await page.waitForTimeout(200);
        }
        const sendState = await targetPage.locator('#send-message-button').evaluateAll(buttons => buttons.map(button => ({
          visible: button.offsetParent !== null,
          disabled: button.disabled,
          ariaDisabled: button.getAttribute('aria-disabled'),
          text: button.innerText,
        })));
        const inputState = await targetPage.locator('#chat-input').evaluate(input => ({
          value: input.value,
          focused: document.activeElement === input,
          form: input.form?.outerHTML?.slice(0, 500) || null,
        }));
        const buttonMarkup = await targetPage.locator('#send-message-button').evaluateAll(buttons => buttons.map(button => button.outerHTML));
        const submitTrace = await targetPage.evaluate(async () => {
          const composer = document.querySelector('#message-input-container');
          const queuedPromptNodes = [...(composer?.querySelectorAll('*') || [])]
            .filter(node => node.children.length === 0
              && !node.closest('#chat-input')
              && node.innerText?.trim() === 'Yes, do it.')
            .map(node => ({
              tag: node.tagName,
              classes: String(node.className || '').slice(0, 160),
              parentMarkup: node.parentElement?.parentElement?.outerHTML?.slice(0, 900) || '',
            }));
          const row = {
            events: window.__hadesSubmitTrace || [],
            formProbe: window.__hadesFormSubmitProbe || null,
            stopVisible: Boolean(document.querySelector('#message-input-container button[aria-label="Stop"]')),
            busyNotice: document.getElementById('hades-composer-busy-notice')?.textContent || '',
            composerButtons: [...(composer?.querySelectorAll('button') || [])]
              .filter(button => button.offsetParent !== null)
              .map(button => ({ text: button.innerText.trim(), title: button.title, label: button.getAttribute('aria-label') })),
            queuedPromptNodes,
            queuedPromptVisibleOutsideInput: queuedPromptNodes.length > 0,
            assistantText: [...document.querySelectorAll('#response-content-container .markdown-prose')].map(node => node.innerText),
          };
          const chatId = decodeURIComponent(location.pathname.split('/c/')[1] || '');
          if (!chatId) return row;
          try {
            const response = await fetch(`/api/v1/chats/${encodeURIComponent(chatId)}`, {
              headers: { authorization: `Bearer ${localStorage.getItem('token') || ''}` },
            });
            if (!response.ok) return { ...row, persistedHttpStatus: response.status };
            const payload = await response.json();
            const history = payload.chat?.history || payload.history || {};
            const messages = history.messages || {};
            const current = messages[history.currentId];
            return {
              ...row,
              currentRole: current?.role || null,
              currentDone: current?.done ?? null,
              messageStates: Object.values(messages).map(message => ({
                role: message.role, done: message.done ?? null, contentLength: String(message.content || '').length,
              })),
            };
          } catch (_) { return { ...row, persistedRead: 'failed' }; }
        });
        throw new Error(`no settled answer for ${JSON.stringify(prompt)}; transport=${JSON.stringify(targetPage._hadesChatTransport)}; browserErrors=${JSON.stringify(targetPage._hadesBrowserErrors)}; input=${JSON.stringify(inputState)}; buttons=${JSON.stringify(buttonMarkup)}; send=${JSON.stringify(sendState)}; submitTrace=${JSON.stringify(submitTrace)}; lifecycle=${JSON.stringify(targetPage._hadesChatLifecycle || null)}; page=${(await targetPage.locator('body').innerText()).slice(-1000)}`);
      }

      if (!ownerServingOnly && !recipeScopeOnly && !recipeAuthoring) {
      const pantry = await ask('Do we have milk?');
      if (!/milk\s*\(2 units\)/i.test(pantry)) throw new Error(`canonical pantry answer was missing or incorrect: ${pantry}`);
      if (/unavailable|couldn't check|did not use another/i.test(pantry)) throw new Error(`pantry read failed honestly: ${pantry}`);
      result.checks.plainLanguagePantryRead = 'PASS';
      result.checks.pantryAnswer = pantry;

      const makeAgain = await ask('Can I make Synthetic Pancakes again?');
      if (!/not quite yet: synthetic pancakes still needs eggs \(1 more\)/i.test(makeAgain)
          || !/canonical grocy stock/i.test(makeAgain)
          || !/didn't change anything/i.test(makeAgain)
          || !/can add only the missing items to the shared shopping list if you'd like/i.test(makeAgain)) {
        throw new Error(`specific saved-recipe make-again question did not use canonical stock safely: ${makeAgain}`);
      }
      result.checks.specificRecipeMakeAgain = 'PASS; exact saved recipe checked against canonical stock, one optional read-only shopping-list offer stated, no mutation';
      result.checks.specificRecipeMakeAgainAnswer = makeAgain;

      const declinedOffer = await ask('No thanks.');
      if (!/okay, i won't add anything to the shopping list/i.test(declinedOffer)) {
        throw new Error(`declining the optional shopping-list offer was not acknowledged without action: ${declinedOffer}`);
      }
      result.checks.preemptiveOfferDecline = 'PASS; explicit refusal acknowledged, no Grocy mutation';
      result.checks.preemptiveOfferDeclineAnswer = declinedOffer;

      const secondRecipeOffer = await ask('Can I make Synthetic Pancakes again?');
      if (!/can add only the missing items to the shared shopping list if you'd like/i.test(secondRecipeOffer)) {
        throw new Error(`second missing-item offer was not presented before affirmative acceptance: ${secondRecipeOffer}`);
      }
      const acceptedRecipeOffer = await ask('Yes, please');
      if (!/for Synthetic Pancakes, added and verified eggs/i.test(acceptedRecipeOffer)
          || !/did not change pantry quantities/i.test(acceptedRecipeOffer)) {
        throw new Error(`same-chat acceptance did not add and canonically verify only missing recipe items: ${acceptedRecipeOffer}`);
      }
      result.checks.preemptiveOfferAffirmative = 'PASS; same-chat yes rechecked the exact canonical offer, added only the missing shared-list item, and verified it';
      result.checks.preemptiveOfferAffirmativeAnswer = acceptedRecipeOffer;

      const recipe = await ask('Which recipes can we make right now?');
      if (!/Saved Grocy recipes:[\s\S]*Synthetic Pancakes — missing: eggs \(1 more\)/i.test(recipe) || !/did not change anything/i.test(recipe)) {
        throw new Error(`recipe feasibility did not use canonical shared stock or implied an unsafe change: ${recipe}`);
      }
      if (!/Unit Mismatch Bread — can't compare stock units for: bananas/i.test(recipe)
          || /Unit Mismatch Bread — missing: bananas/i.test(recipe)) {
        throw new Error(`recipe feasibility guessed across incompatible units: ${recipe}`);
      }
      if (!/Converted Unit Rice — missing: rice \(0\.5 more\)/i.test(recipe)) {
        throw new Error(`recipe feasibility did not apply Grocy's canonical resolved unit conversion: ${recipe}`);
      }
      if (!/Expired Toast — missing: bread \(1 more; only known stock is past its best-before date\)/i.test(recipe)) {
        throw new Error(`recipe feasibility counted known-expired stock as usable: ${recipe}`);
      }
      result.checks.canonicalHouseholdRecipeFeasibility = 'PASS; one ingredient stocked, one missing, no state change';
      result.checks.expiredStockExcludedFromRecipeFeasibility = 'PASS; known past-date stock is not counted as usable';
      result.checks.recipeUnitMismatchFailsClosed = 'PASS; incompatible recipe/stock units are unknown, not guessed';
      result.checks.recipeResolvedUnitConversion = 'PASS; canonical Grocy conversion factor applied before comparing stock';
      result.checks.recipeAnswer = recipe;

      const naturalMeal = await ask('Are there any meals we can make tonight without going shopping?');
      if (!/Milk Soup/i.test(naturalMeal)
          || !/Grocy lists|current stock|shared pantry/i.test(naturalMeal)
          || /can't help investigate a private person/i.test(naturalMeal)
          || !/did not change anything|did not change stock/i.test(naturalMeal)) {
        throw new Error(`natural meal question did not return a privacy-safe canonical stock answer: ${naturalMeal}`);
      }
      result.checks.naturalMealPlanning = 'PASS; natural “Are there any meals…” wording cleared the privacy guard and returned synthetic canonical recipe/stock evidence without mutation';

      const budgetMeal = await ask('What can we cook tonight without spending much?');
      if (!/To keep extra spending down, start with Milk Soup/i.test(budgetMeal)
          || !/can't compare total meal prices/i.test(budgetMeal)
          || /Expired Toast|Synthetic Pancakes/i.test(budgetMeal)
          || !/did not change anything/i.test(budgetMeal)) {
        throw new Error(`low-spend meal advice failed pantry, price-honesty, or expired-food checks: ${budgetMeal}`);
      }
      result.checks.lowSpendMeal = 'PASS; recommends a saved recipe fully covered by usable stock, states prices are unavailable, no mutation';
      result.checks.lowSpendMealAnswer = budgetMeal;

      await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForSelector('#chat-input', { timeout: 15000 });
      const expiry = await ask("What's going bad soon?");
      if (!/known expired:[\s\S]*bread/i.test(expiry) || !/known to expire within 7 days:[\s\S]*eggs/i.test(expiry)) {
        throw new Error(`expiry answer omitted canonical dated stock: ${expiry}`);
      }
      if (!/saved recipes using food that expires within 7 days:[\s\S]*Synthetic Pancakes/i.test(expiry)
          || /Milk Soup|Expired Toast/i.test(expiry)) {
        throw new Error(`expiry recipe overlap included nonexpiring or already-expired food: ${expiry}`);
      }
      result.checks.expiryRecipeOverlap = 'PASS; only recipes using within-seven-day nonexpired ingredients are suggested';
      result.checks.expiryAnswer = expiry;

      const compoundDinner = await ask('Can we make Synthetic Pancakes for dinner, and what food is going to expire?');
      if (!/Not quite yet: Synthetic Pancakes still needs eggs \(1 more\)/i.test(compoundDinner)
          || !/known expired:[\s\S]*bread/i.test(compoundDinner)
          || !/known to expire within 7 days:[\s\S]*eggs/i.test(compoundDinner)) {
        throw new Error(`compound dinner and expiry question did not answer both parts from canonical Grocy data: ${compoundDinner}`);
      }
      result.checks.compoundDinnerAndExpiry = 'PASS; named recipe feasibility and dated pantry status both answered from canonical Grocy without mutation';
      result.checks.compoundDinnerAndExpiryAnswer = compoundDinner;

      await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForSelector('#chat-input', { timeout: 15000 });
      const recipeAdd = await ask("Could you add what we're missing for Synthetic Pancakes?");
      if (!/for Synthetic Pancakes, already listed eggs/i.test(recipeAdd) || !/did not change pantry quantities/i.test(recipeAdd)) {
        throw new Error(`recipe shortage retry did not preserve the prior confirmed list add: ${recipeAdd}`);
      }
      result.checks.explicitRecipeShortageAdd = 'PASS; exact saved recipe shortage was already present from the immediately confirmed offer; no duplicate or pantry mutation';
      result.checks.recipeAddAnswer = recipeAdd;

      await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForSelector('#chat-input', { timeout: 15000 });
      const convertedRecipeAdd = await ask("Could you add what's missing for Converted Unit Rice?");
      if (!/for Converted Unit Rice, added and verified rice/i.test(convertedRecipeAdd)) {
        throw new Error(`converted recipe shortage was not added with canonical confirmation: ${convertedRecipeAdd}`);
      }
      result.checks.convertedRecipeShortageAdd = 'PASS; recipe quantity converted to stock units, then purchase units before shared-list write';

      await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForSelector('#chat-input', { timeout: 15000 });
      const repeatedConvertedRecipeAdd = await ask('Add what we still need for Converted Unit Rice to the grocery list.');
      if (!/already listed rice/i.test(repeatedConvertedRecipeAdd)) {
        throw new Error(`converted recipe retry did not recognize the existing canonical row: ${repeatedConvertedRecipeAdd}`);
      }
      result.checks.convertedRecipeAddIdempotency = 'PASS; retry did not duplicate the converted purchase quantity';

      await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForSelector('#chat-input', { timeout: 15000 });
      const unsafeRecipeAdd = await ask("Could you add what's missing for Unit Mismatch Bread?");
      if (!/can't safely compare this recipe with stock and purchase units yet/i.test(unsafeRecipeAdd)
          || !/nothing was changed/i.test(unsafeRecipeAdd)) {
        throw new Error(`unresolved recipe units were not refused before list mutation: ${unsafeRecipeAdd}`);
      }
      result.checks.unresolvedRecipeUnitMutationFailsClosed = 'PASS; no shopping-list write when a required unit conversion is absent';

      await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForSelector('#chat-input', { timeout: 15000 });
      const repeatRecipeAdd = await ask('Put the ingredients we still need for Synthetic Pancakes on the groceries list.');
      if (!/already listed eggs/i.test(repeatRecipeAdd)) {
        throw new Error(`repeated recipe request did not recognize the existing list row: ${repeatRecipeAdd}`);
      }
      result.checks.recipeShortageAddIdempotency = 'PASS; existing canonical row reused, no duplicate';

      await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForSelector('#chat-input', { timeout: 15000 });
      const ambiguousRecipeAdd = await ask("Add what we're missing for dinner.");
      if (!/which saved recipe should i check/i.test(ambiguousRecipeAdd) || !/haven't changed the shopping list/i.test(ambiguousRecipeAdd)) {
        throw new Error(`ambiguous recipe add did not ask before changing shared state: ${ambiguousRecipeAdd}`);
      }
      result.checks.ambiguousRecipeAddClarification = 'PASS; asks which saved recipe and leaves the list unchanged';

      await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForSelector('#chat-input', { timeout: 15000 });
      const add = await ask('Add milk to the shopping list.');
      if (!/added milk to the shared shopping list and verified it/i.test(add)) {
        throw new Error(`shopping-list action lacked a clear verified result: ${add}`);
      }
      result.checks.explicitSharedListMutation = 'PASS';
      result.checks.mutationAnswer = add;

      const mutationCorrection = await ask(
        'No, I meant put the milk in the recipe instead.', page,
      );
      if (!/already added milk to the shared shopping list and verified it/i.test(mutationCorrection)
          || !/haven't changed any recipe/i.test(mutationCorrection)
          || !/only the owner can change saved recipes/i.test(mutationCorrection)
          || !/remove milk from the list if you'd like/i.test(mutationCorrection)) {
        throw new Error(`post-mutation correction did not state what happened and offer a safe correction: ${mutationCorrection}`);
      }
      result.checks.postMutationCorrectionRecovery = 'PASS; states the completed list add, confirms no recipe change, preserves owner-only authoring, offers an explicit removal choice without acting';
      result.checks.postMutationCorrectionAnswer = mutationCorrection;

      await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForSelector('#chat-input', { timeout: 15000 });
      const list = await ask("What's on the shopping list?");
      if (!/milk/i.test(list) || !/eggs/i.test(list)) throw new Error(`fresh canonical list read missed recipe or explicit item: ${list}`);
      result.checks.canonicalReadBack = 'PASS';
      result.checks.readBackAnswer = list;

      fs.writeFileSync(failureFile, 'synthetic outage injection\n', { mode: 0o600, flag: 'wx' });
      await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForSelector('#chat-input', { timeout: 15000 });
      const outage = await ask('Do we have milk?');
      if (!/couldn't check|service is unavailable/i.test(outage) || /pantry is empty|no stocked pantry items/i.test(outage)) {
        throw new Error(`canonical Grocy outage was not reported honestly: ${outage}`);
      }
      result.checks.canonicalOutageHonesty = 'PASS';
      result.checks.outageAnswer = outage;

      fs.unlinkSync(failureFile);
      await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForSelector('#chat-input', { timeout: 15000 });
      const chickenAgain = await ask('Can I make that chicken thing again?');
      if (!/not quite yet: lemon chicken still needs chicken \(1 more\)/i.test(chickenAgain)
          || !/canonical grocy stock/i.test(chickenAgain)
          || !/didn't change anything/i.test(chickenAgain)) {
        throw new Error(`vague saved-recipe reference did not resolve safely from canonical ingredients: ${chickenAgain}`);
      }
      result.checks.grandmaChickenRecipeReference = 'PASS; unique saved recipe matched by canonical ingredient, exact shortage returned, no mutation';
      result.checks.grandmaChickenRecipeReferenceAnswer = chickenAgain;

      const chats = await fetch(`${base}/api/v1/chats/?page=1`, { headers: { authorization: `Bearer ${token}` } });
      if (!chats.ok) throw new Error(`authenticated chat history failed: HTTP ${chats.status}`);
      const payload = await chats.json();
      const rows = Array.isArray(payload) ? payload : (payload.items || payload.chats || []);
      let persisted = false;
      let persistedChatId = '';
      for (const chat of rows.slice(0, 10)) {
        const id = chat.id || chat.chat_id;
        if (!id) continue;
        const detail = await fetch(`${base}/api/v1/chats/${encodeURIComponent(id)}`, {
          headers: { authorization: `Bearer ${token}` },
        });
        if (detail.ok && /added milk to the shared shopping list/i.test(JSON.stringify(await detail.json()))) {
          persisted = true;
          persistedChatId = id;
          break;
        }
      }
      if (!persisted) throw new Error('verified household action did not persist in authenticated chat history');
      result.checks.chatPersistence = 'PASS';

      if (recipeScopeProbe) {
        const scopeProbe = await ask(
          'Please preview this recipe from https://recipes.example.test/beta-scope-probe.',
        );
        if (!/no canonical change was made/i.test(scopeProbe)) {
          throw new Error(`household recipe-scope probe did not complete safely: ${scopeProbe}`);
        }
        result.checks.householdRecipeToolScope = 'PASS; authenticated Beta prompt reached the synthetic model with its scoped catalog';
      }

      const gammaEmail = process.env.HADES_GROCY_UI_GAMMA_EMAIL;
      if (gammaEmail) {
        const gammaLogin = await fetch(`${base}/api/v1/auths/signin`, {
          method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ email: gammaEmail, password }),
        });
        if (!gammaLogin.ok) throw new Error(`synthetic Gamma login failed: HTTP ${gammaLogin.status}`);
        const { token: gammaToken } = await gammaLogin.json();
        const gammaContext = await browser.newContext({ viewport: { width: 1365, height: 850 } });
        try {
          await gammaContext.addCookies([{ name: 'token', value: gammaToken, url: `${base}/` }]);
          const gammaPage = await gammaContext.newPage();
          await gammaPage.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
          await gammaPage.waitForSelector('#chat-input', { timeout: 30000 });
          const gammaWelcome = gammaPage.getByRole('button', { name: /okay,\s*let.s go/i });
          if (await gammaWelcome.count()) await gammaWelcome.first().click({ force: true });
          const gammaChoose = gammaPage.getByRole('button', { name: /select a model/i });
          if (await gammaChoose.count()) {
            await gammaChoose.first().click();
            const option = gammaPage.getByText(modelId, { exact: true }).last();
            await option.waitFor({ state: 'visible', timeout: 10000 });
            await option.click();
          }
          const gammaPantry = await ask('Do we have milk?', gammaPage);
          if (!/milk\s*\(2 units\)/i.test(gammaPantry)) {
            throw new Error(`Gamma could not read shared canonical pantry: ${gammaPantry}`);
          }
          const gammaList = await ask("What's on the shopping list?", gammaPage);
          if (!/milk/i.test(gammaList) || !/eggs/i.test(gammaList) || !/rice/i.test(gammaList)) {
            throw new Error(`Gamma could not read Beta's shared canonical shopping list: ${gammaList}`);
          }
          const foreignChat = await fetch(`${base}/api/v1/chats/${encodeURIComponent(persistedChatId)}`, {
            headers: { authorization: `Bearer ${gammaToken}` },
          });
          if (foreignChat.status !== 401 && foreignChat.status !== 403) {
            throw new Error(`Gamma accessed Beta's private chat: HTTP ${foreignChat.status}`);
          }
          result.checks.gammaSharedPantryAndList = 'PASS; independent household identity read Alpha/Beta shared Grocy state';
          result.checks.gammaCannotReadBetaPrivateChat = 'PASS';
        } finally {
          await gammaContext.close();
        }
      }

      } else if (recipeScopeOnly && recipeScopeProbe) {
        const scopeProbe = await ask(
          'Please preview this recipe from https://recipes.example.test/beta-scope-probe.',
        );
        if (!/no canonical change was made/i.test(scopeProbe)) {
          throw new Error(`household recipe-scope probe did not complete safely: ${scopeProbe}`);
        }
        result.checks.householdRecipeToolScope = 'PASS; authenticated Beta prompt reached the synthetic model with its scoped catalog';
      }

      if (recipeAuthoring) {
        const householdRecipeAttempt = await ask('Please create a new recipe Beta Unauthorized Soup.');
        if (!/only the owner can create or change saved recipes/i.test(householdRecipeAttempt)
            || !/didn't change anything/i.test(householdRecipeAttempt)) {
          throw new Error(`Beta recipe authoring attempt was not clearly denied: ${householdRecipeAttempt}`);
        }
        result.checks.householdRecipeAuthoringDenied = 'PASS; authenticated Beta received a clear owner-only denial before any recipe write';
      }

      const ownerEmail = process.env.HADES_GROCY_UI_OWNER_EMAIL;
      if (ownerEmail && (process.env.HADES_GROCY_UI_INCLUDE_OWNER_SERVING === '1' || recipeScopeProbe || recipeAuthoring)) {
        const ownerLogin = await fetch(`${base}/api/v1/auths/signin`, {
          method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ email: ownerEmail, password }),
        });
        if (!ownerLogin.ok) throw new Error(`synthetic Alpha login failed: HTTP ${ownerLogin.status}`);
        const { token: ownerToken } = await ownerLogin.json();
        const ownerContext = await browser.newContext({ viewport: { width: 1365, height: 850 } });
        await ownerContext.addInitScript(() => {
          window.__hadesSubmitTrace = [];
          const nativeDispatchEvent = EventTarget.prototype.dispatchEvent;
          EventTarget.prototype.dispatchEvent = function (event) {
            if (event?.type === 'submit') {
              window.__hadesSubmitTrace.push({
                event: 'dispatchEvent',
                target: this?.tagName || this?.constructor?.name || '',
                targetId: this?.id || '',
                bubbles: Boolean(event.bubbles),
                cancelable: Boolean(event.cancelable),
                detailType: typeof event.detail,
                detailLength: typeof event.detail === 'string' ? event.detail.length : null,
              });
            }
            return nativeDispatchEvent.call(this, event);
          };
          window.addEventListener('click', event => {
            if (!event.target.closest?.('#send-message-button')) return;
            const button = event.target.closest('#send-message-button');
            const row = {
              event: 'send-click', before: event.defaultPrevented,
              buttonFormId: button.form?.id || null,
              closestFormId: button.closest('form')?.id || null,
              formContainsComposer: Boolean(button.form?.querySelector('#chat-input')),
            };
            window.__hadesSubmitTrace.push(row);
            queueMicrotask(() => {
              row.after = event.defaultPrevented;
              row.busyNotice = document.getElementById('hades-composer-busy-notice')?.textContent || '';
            });
          }, true);
          window.addEventListener('submit', event => {
            const row = {
              event: 'submit', target: event.target?.tagName || '', before: event.defaultPrevented,
              targetId: event.target?.id || '', targetClass: String(event.target?.className || '').slice(0, 120),
              containsComposer: Boolean(event.target?.querySelector?.('#chat-input')),
              containsVisibleSend: Boolean([...event.target?.querySelectorAll?.('#send-message-button') || []].some(button => button.offsetParent !== null)),
            };
            window.__hadesSubmitTrace.push(row);
            queueMicrotask(() => {
              row.after = event.defaultPrevented;
              row.stopped = event.cancelBubble;
              row.busyNotice = document.getElementById('hades-composer-busy-notice')?.textContent || '';
            });
          }, true);
        });
        try {
          await ownerContext.addCookies([{ name: 'token', value: ownerToken, url: `${base}/` }]);
          const ownerPage = await ownerContext.newPage();
          await ownerPage.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
          await ownerPage.waitForSelector('#chat-input', { timeout: 30000 });
          const ownerWelcome = ownerPage.getByRole('button', { name: /okay,\s*let.s go/i });
          if (await ownerWelcome.count()) await ownerWelcome.first().click({ force: true });
          const ownerChoose = ownerPage.getByRole('button', { name: /select a model/i });
          if (await ownerChoose.count()) {
            await ownerChoose.first().click();
            const option = ownerPage.getByText(modelId, { exact: true }).last();
            await option.waitFor({ state: 'visible', timeout: 10000 });
            await option.click();
          }
          if (!ownerServingOnly && !recipeScopeOnly && !recipeAuthoring) {
            const ownerPantry = await ask('Do we have milk?', ownerPage);
            if (!/milk\s*\(2 units\)/i.test(ownerPantry)) {
              throw new Error(`Alpha could not read canonical household pantry: ${ownerPantry}`);
            }
            await ownerPage.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
            await ownerPage.waitForSelector('#chat-input', { timeout: 15000 });
            const ownerList = await ask("What's on the shopping list?", ownerPage);
            if (!/milk/i.test(ownerList) || !/eggs/i.test(ownerList) || !/rice/i.test(ownerList)) {
              throw new Error(`Alpha could not read the household's canonical shopping list: ${ownerList}`);
            }
            result.checks.alphaOwnerSharedPantryAndList = 'PASS; owner identity read canonical state after Beta writes';
          }

          if (recipeScopeProbe) {
            await ownerPage.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
            await ownerPage.waitForSelector('#chat-input', { timeout: 15000 });
            const ownerRecipeProbe = await ask(
              'Please preview this recipe from https://recipes.example.test/alpha-scope-probe.', ownerPage,
            );
            if (!/no canonical change was made/i.test(ownerRecipeProbe)) {
              throw new Error(`owner recipe-scope probe did not complete safely: ${ownerRecipeProbe}`);
            }
            result.checks.ownerRecipeToolScope = 'PASS; authenticated Alpha prompt reached the synthetic model with its owner catalog';
          }

          if (recipeAuthoring) {
            await ownerPage.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
            await ownerPage.waitForSelector('#chat-input', { timeout: 15000 });
            const createdRecipe = await ask(
              'Please add my new recipe HADES Synthetic Authoring Soup. It needs 1 milk and 2 eggs.', ownerPage,
            );
            if (!/added HADES Synthetic Authoring Soup/i.test(createdRecipe)) {
              throw new Error(`Alpha recipe creation did not complete: ${createdRecipe}`);
            }
            const removedIngredient = await ask(
              'For HADES Synthetic Authoring Soup, remove the eggs ingredient.', ownerPage,
            );
            if (!/removed the eggs/i.test(removedIngredient)) {
              throw new Error(`Alpha ingredient removal did not complete: ${removedIngredient}`);
            }
            const restoredIngredient = await ask(
              'Restore 2 eggs in the recipe HADES Synthetic Authoring Soup.', ownerPage,
            );
            if (!/restored eggs/i.test(restoredIngredient)) {
              throw new Error(`Alpha ingredient restoration did not complete: ${restoredIngredient}`);
            }
            const shortage = await ask(
              'Can I make HADES Synthetic Authoring Soup with what we have?', ownerPage,
            );
            if (!/still needs eggs \(1 more\)/i.test(shortage)) {
              throw new Error(`Alpha recipe feasibility did not report the canonical shortage: ${shortage}`);
            }
            const addMissing = await ask(
              "Add only what's missing for HADES Synthetic Authoring Soup to my shopping list.", ownerPage,
            );
            if (!/added and verified eggs/i.test(addMissing)) {
              throw new Error(`Alpha add-missing action did not complete: ${addMissing}`);
            }
            result.checks.ownerRecipeAuthoring = 'PASS; create, remove/restore ingredient, canonical shortage, and add-missing went through authenticated Alpha UI';
          }

          if (process.env.HADES_GROCY_UI_INCLUDE_OWNER_SERVING === '1') {
          await ownerPage.close();
          const servingPage = await ownerContext.newPage();
          await servingPage.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
          await servingPage.waitForSelector('#chat-input', { timeout: 30000 });
          const servingWelcome = servingPage.getByRole('button', { name: /okay,\s*let.s go/i });
          if (await servingWelcome.count()) await servingWelcome.first().click({ force: true });
          const servingChoose = servingPage.getByRole('button', { name: /select a model/i });
          if (await servingChoose.count()) {
            await servingChoose.first().click();
            const option = servingPage.getByText(modelId, { exact: true }).last();
            await option.waitFor({ state: 'visible', timeout: 10000 });
            await option.click();
          }
          const servingPreview = await ask(
            'Change the servings for Synthetic Pancakes to six.', servingPage, true,
          );
          const servingChatId = decodeURIComponent(servingPage.url().split('/c/')[1] || '');
          const servingHistoryResponse = await fetch(`${base}/api/v1/chats/${encodeURIComponent(servingChatId)}`, {
            headers: { authorization: `Bearer ${ownerToken}` },
          });
          const servingHistoryPayload = servingHistoryResponse.ok ? await servingHistoryResponse.json() : {};
          const servingHistory = servingHistoryPayload.chat?.history || servingHistoryPayload.history || {};
          const servingMessages = servingHistory.messages || {};
          const servingCompletionState = Object.values(servingMessages).map(message => ({
            role: message.role, done: message.done, contentLength: String(message.content || '').length,
          }));
          servingPage._hadesChatLifecycle = {
            currentId: servingHistory.currentId || null,
            currentRole: servingMessages[servingHistory.currentId]?.role || null,
            currentDone: servingMessages[servingHistory.currentId]?.done ?? null,
            messages: servingCompletionState,
          };
          if (!/Synthetic Pancakes currently serves 4/i.test(servingPreview)
              || !/Change it to serve 6\?/i.test(servingPreview)
              || !/Reply yes to confirm or no to cancel/i.test(servingPreview)
              || !/Nothing has changed yet/i.test(servingPreview)) {
            throw new Error(`serving resize did not present a write-free canonical preview: ${servingPreview}`);
          }

          // A same-user bare confirmation in another Open WebUI chat must
          // not consume or apply this preview. Verify the canonical Grocy
          // value before returning to the originating chat.
          const unrelatedOwnerContext = await browser.newContext({ viewport: { width: 1365, height: 850 } });
          try {
            await unrelatedOwnerContext.addCookies([{ name: 'token', value: ownerToken, url: `${base}/` }]);
            const unrelatedServingPage = await unrelatedOwnerContext.newPage();
            await unrelatedServingPage.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
            await unrelatedServingPage.waitForSelector('#chat-input', { timeout: 30000 });
            const unrelatedServingChoose = unrelatedServingPage.getByRole('button', { name: /select a model/i });
            if (await unrelatedServingChoose.count()) {
              await unrelatedServingChoose.first().click();
              const option = unrelatedServingPage.getByText(modelId, { exact: true }).last();
              await option.waitFor({ state: 'visible', timeout: 10000 });
              await option.click();
            }
            // The form-submit diagnostic was already exercised in the
            // originating chat; skip its duplicate browser-only probe here.
            unrelatedServingPage._hadesFormProbeDone = true;
            const unrelatedConfirmation = await ask('Yes, do it.', unrelatedServingPage, true);
            const unrelatedChatId = decodeURIComponent(unrelatedServingPage.url().split('/c/')[1] || '');
            if (!unrelatedChatId || unrelatedChatId === servingChatId) {
              throw new Error('cross-chat serving probe did not create a distinct authenticated chat');
            }
            if (!/couldn't match that confirmation to this chat's recipe change/i.test(unrelatedConfirmation)
                || !/nothing was changed/i.test(unrelatedConfirmation)) {
              throw new Error(`cross-chat serving confirmation was not rejected clearly: ${unrelatedConfirmation}`);
            }
            const canonicalBeforeSameChatConfirmation = await fetch(
              `${process.env.GROCY_URL}/api/objects/recipes/21`,
              { headers: { 'GROCY-API-KEY': process.env.GROCY_API_KEY } },
            );
            if (!canonicalBeforeSameChatConfirmation.ok) {
              throw new Error(`canonical recipe check failed after cross-chat confirmation: HTTP ${canonicalBeforeSameChatConfirmation.status}`);
            }
            const unchangedRecipe = await canonicalBeforeSameChatConfirmation.json();
            if (Number(unchangedRecipe.base_servings) !== 4) {
              throw new Error(`cross-chat confirmation changed canonical servings to ${unchangedRecipe.base_servings}`);
            }
          } finally {
            await unrelatedOwnerContext.close();
          }
          result.checks.ownerServingCrossChatIsolation = 'PASS; same-user confirmation from a separate chat was rejected, canonical servings stayed at 4, and the original preview remained usable';

          const householdContext = await browser.newContext({ viewport: { width: 1365, height: 850 } });
          try {
            await householdContext.addCookies([{ name: 'token', value: token, url: `${base}/` }]);
            const householdServingPage = await householdContext.newPage();
            await householdServingPage.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
            await householdServingPage.waitForSelector('#chat-input', { timeout: 30000 });
            const householdServingChoose = householdServingPage.getByRole('button', { name: /select a model/i });
            if (await householdServingChoose.count()) {
              await householdServingChoose.first().click();
              const option = householdServingPage.getByText(modelId, { exact: true }).last();
              await option.waitFor({ state: 'visible', timeout: 10000 });
              await option.click();
            }
            householdServingPage._hadesFormProbeDone = true;
            const householdAttempt = await ask(
              'Change the servings for Synthetic Pancakes to eight.', householdServingPage, true,
            );
            if (!/only the owner can change a saved recipe/i.test(householdAttempt)
                || !/household recipe reads and shopping-list actions are still available/i.test(householdAttempt)) {
              throw new Error(`household serving mutation was not denied with the right scope: ${householdAttempt}`);
            }
          } finally {
            await householdContext.close();
          }
          result.checks.householdServingMutationDenied = 'PASS; separate household account was denied before Grocy access while the owner preview remained pending';

          const servingApplied = await ask('Yes, do it.', servingPage, true);
          if (!/Updated Synthetic Pancakes to serve 6/i.test(servingApplied)
              || !/Grocy confirmed the saved recipe/i.test(servingApplied)) {
            throw new Error(`owner confirmation lacked canonical serving read-back: ${servingApplied}`);
          }
          const cancellationPreview = await ask(
            'Set Synthetic Pancakes to 7 servings.', servingPage, true,
          );
          if (!/currently serves 6/i.test(cancellationPreview)
              || !/Reply yes to confirm or no to cancel/i.test(cancellationPreview)) {
            throw new Error(`second serving preview did not use current canonical state: ${cancellationPreview}`);
          }
          const servingCancelled = await ask('No thanks.', servingPage, true);
          if (!/left the saved recipe unchanged/i.test(servingCancelled)) {
            throw new Error(`serving cancellation was not acknowledged safely: ${servingCancelled}`);
          }
          result.checks.alphaServingResizeConfirmation = 'PASS; owner preview, same-chat confirmation, canonical read-back, and cancellation without a second write';
          result.checks.updateToast = servingPage._hadesUpdateToastDismissed
            ? 'PASS; dismissed the first-run update notice that overlaps the composer send button'
            : 'PASS; no overlapping update notice was present';
          }
        } finally {
          await ownerContext.close();
        }
      }
      fs.writeFileSync(report, `${JSON.stringify(result, null, 2)}\n`, { mode: 0o600 });
      fs.chmodSync(report, 0o600);
      console.log(JSON.stringify({ status: 'PASS', report }));
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
