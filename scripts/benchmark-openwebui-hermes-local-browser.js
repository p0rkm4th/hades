#!/usr/bin/env node

/* Authenticated browser turn for benchmark-openwebui-hermes-browser.py. */
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const base = process.env.WEBUI_URL;
const modelId = 'hermes-agent';
const password = 'Synthetic-Only-123!';
const email = 'local-browser@example.invalid';
const prompt = 'What is 18% of 250? Reply with just the number.';

async function api(path, token, body) {
  const response = await fetch(`${base}${path}`, {
    method: body ? 'POST' : 'GET',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(body ? { 'content-type': 'application/json' } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await response.text();
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return text ? JSON.parse(text) : null;
}

async function main() {
  if (!base || !process.env.HERMES_URL) throw new Error('probe service URLs are required');
  const owner = await api('/api/v1/auths/signup', null, {
    name: 'Synthetic UI Owner', email, password,
  });
  const token = owner.token;
  await api('/openai/config/update', token, {
    ENABLE_OPENAI_API: true,
    OPENAI_API_BASE_URLS: [`${process.env.HERMES_URL}/v1`],
    OPENAI_API_KEYS: ['synthetic-local-browser-key-2026'],
    OPENAI_API_CONFIGS: {
      '0': { headers: { 'X-Hermes-Session-Key': 'hades-user-synthetic' } },
    },
  });

  const taskConfig = await api('/api/v1/tasks/config', token);
  const tasksEnabled = process.env.METADATA_TASKS === 'on';
  for (const key of [
    'ENABLE_TITLE_GENERATION',
    'ENABLE_FOLLOW_UP_GENERATION',
    'ENABLE_TAGS_GENERATION',
  ]) taskConfig[key] = tasksEnabled;
  const updatedConfig = await api('/api/v1/tasks/config/update', token, taskConfig);
  for (const key of [
    'ENABLE_TITLE_GENERATION',
    'ENABLE_FOLLOW_UP_GENERATION',
    'ENABLE_TAGS_GENERATION',
  ]) {
    if (updatedConfig[key] !== tasksEnabled) throw new Error(`task setting did not apply: ${key}`);
  }

  let models;
  for (let attempt = 0; attempt < 10; attempt += 1) {
    models = await api('/api/models', token);
    if (models.data?.some(model => model.id === modelId)) break;
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  if (!models.data?.some(model => model.id === modelId)) {
    throw new Error(`configured Hermes model is missing from Open WebUI: ${JSON.stringify(models)}`);
  }

  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1365, height: 850 } });
    await context.addCookies([{ name: 'token', value: token, url: `${base}/` }]);
    const page = await context.newPage();
    const taskRequests = [];
    const trackedRequests = new Map();
    page.on('request', request => {
      const path = new URL(request.url()).pathname;
      if (path.includes('/tasks/') || path.endsWith('/api/chat/completions')) {
        const row = { method: request.method(), path, startedAt: Date.now() };
        taskRequests.push(row);
        trackedRequests.set(request, row);
      }
    });
    page.on('response', response => {
      const row = trackedRequests.get(response.request());
      if (row) row.status = response.status();
    });
    page.on('requestfinished', request => {
      const row = trackedRequests.get(request);
      if (row) row.finishedAt = Date.now();
    });
    page.on('requestfailed', request => {
      const row = trackedRequests.get(request);
      if (row) row.failure = request.failure()?.errorText || 'unknown';
    });

    await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForSelector('#chat-input', { timeout: 30000 });
    const welcome = page.getByRole('button', { name: /okay,\s*let.s go/i });
    if (await welcome.count()) await welcome.first().click({ force: true });

    const modelSelector = page.getByRole('button', { name: /select a model/i });
    if (await modelSelector.count()) {
      await modelSelector.first().click();
      const modelOption = page.getByText(modelId, { exact: true }).last();
      await modelOption.waitFor({ state: 'visible', timeout: 15000 });
      await modelOption.click();
    }

    const input = page.locator('#chat-input');
    await input.fill(prompt);
    const submittedAt = Date.now();
    await input.press('Enter');
    await page.waitForFunction(
      () => /\/c\/[0-9a-f-]{36}/i.test(location.pathname),
      null,
      { timeout: 60000 },
    );
    const chatId = page.url().match(/\/c\/([^/?#]+)/)?.[1];
    await page.getByText('45', { exact: true }).last().waitFor({
      state: 'visible', timeout: 180000,
    });
    const answerVisibleMs = Date.now() - submittedAt;
    let followup = null;
    if (process.env.SEND_FOLLOWUP === 'on') {
      // Open WebUI can render the completed text before its stream/task state
      // is committed. Give the HADES composer settlement window time to run;
      // the earlier immediate-send probe was intercepted while still busy.
      await page.waitForTimeout(6000);
      const composerReadyStartedAt = Date.now();
      let composerReady = false;
      try {
        await page.waitForFunction(
          () => !document.querySelector('#message-input-container button[aria-label="Stop"]'),
          null,
          { timeout: 15000 },
        );
        composerReady = true;
      } catch (_) {
        // Preserve the measured busy state in the result instead of losing
        // provider and request diagnostics to a browser timeout.
      }
      const followupInput = page.locator('#chat-input');
      followup = { prompt: 'Why?', composer_ready: composerReady,
        composer_ready_delay_ms: Date.now() - composerReadyStartedAt };
      if (composerReady) {
        await followupInput.fill('Why?');
        const followupSubmittedAt = Date.now();
        await followupInput.press('Enter');
        followup.input_after_submit = await followupInput.evaluate(
          element => ({ tag: element.tagName, text: element.innerText, value: element.value }),
        );
        followup.busy_notice_after_submit = await page.locator('#hades-composer-busy-notice').count() > 0;
        try {
          await page.waitForFunction(
            () => [...document.querySelectorAll('#response-content-container .markdown-prose')]
              .filter(node => node.innerText?.trim()).length >= 2,
            null,
            { timeout: 90000 },
          );
          const answers = await page.locator('#response-content-container .markdown-prose').allInnerTexts();
          followup.answer_visible_ms = Date.now() - followupSubmittedAt;
          followup.rendered_assistant_answers = answers.map(text => text.trim()).filter(Boolean);
        } catch (_) {
          followup.rendered_assistant_answers = await page.locator(
            '#response-content-container .markdown-prose',
          ).allInnerTexts();
          followup.rendered_assistant_answers = followup.rendered_assistant_answers
            .map(text => text.trim()).filter(Boolean);
          followup.answer_timeout = true;
        }
      } else {
        followup.stop_control_still_present = await page.locator(
          '#message-input-container button[aria-label="Stop"]',
        ).count() > 0;
      }
    }

    // Let Open WebUI's asynchronous metadata requests finish before reload.
    await page.waitForTimeout(process.env.SEND_FOLLOWUP === 'on' ? 5000 : 45000);
    const titleBeforeReload = (await api(`/api/v1/chats/${chatId}`, token)).title;
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForSelector('#chat-input', { timeout: 30000 });
    await page.getByText('45', { exact: true }).last().waitFor({
      state: 'visible', timeout: 30000,
    });
    const titleAfterReload = (await api(`/api/v1/chats/${chatId}`, token)).title;
    console.log(JSON.stringify({
      chat_id: chatId,
      metadata_tasks: tasksEnabled ? 'on' : 'off',
      model_id: modelId,
      visible_answer_after_reload: true,
      answer_visible_ms: answerVisibleMs,
      followup,
      title_before_reload: titleBeforeReload,
      title_after_reload: titleAfterReload,
      browser_task_and_chat_requests: taskRequests,
    }));
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
});
