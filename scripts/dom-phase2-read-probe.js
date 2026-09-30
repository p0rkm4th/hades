#!/usr/bin/env node

/* Read-only authenticated DOM probe for the Phase 2 summary surfaces. */
const fs = require('node:fs');
const crypto = require('node:crypto');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const base = process.env.HADES_DOM_BASE_URL || 'http://127.0.0.1:3000/';
const root = process.env.HADES_DOM_CREDENTIAL_DIR || require('path').join(require('os').homedir(), '.config', 'hades-dom');
const waitMs = Number(process.env.HADES_PHASE2_DOM_WAIT_MS || 60000);
const users = {
  owner: ['acceptance-owner-email', 'acceptance-owner-password'],
  householdA: ['household-a-email', 'household-a-password'],
  householdB: ['household-b-email', 'household-b-password'],
};
const requestedUsers = (process.env.HADES_PHASE2_USER_FILTER || '')
  .split(',').map(value => value.trim()).filter(Boolean);
const unknownUsers = requestedUsers.filter(user => !Object.hasOwn(users, user));
if (unknownUsers.length) throw new Error(`unknown HADES_PHASE2_USER_FILTER value: ${unknownUsers.join(', ')}`);
const selectedUsers = Object.entries(users).filter(([user]) => !requestedUsers.length || requestedUsers.includes(user));
const prompts = {
  backup: 'what backup checks do I have?',
  low: 'what low grocery summaries do I have?',
  weekly: 'what weekly household summaries do I have?',
};

function secret(name) { return fs.readFileSync(`${root}/${name}`, 'utf8').trim(); }
function digest(value) { return crypto.createHash('sha256').update(value).digest('hex').slice(0, 12); }

async function attachCompletionTelemetry(page) {
  const session = await page.context().newCDPSession(page);
  const requests = new Map();
  await session.send('Network.enable');
  session.on('Network.requestWillBeSent', event => {
    let pathname = '';
    try { pathname = new URL(event.request.url).pathname; } catch (_) {}
    if (pathname !== '/api/chat/completions' || event.request.method !== 'POST') return;
    const telemetry = page.__turnTelemetry;
    if (!telemetry) return;
    const record = { started_at: Date.now(), first_byte_ms: null, status: null, tool_names: new Set() };
    requests.set(event.requestId, record);
    telemetry.completions.push(record);
  });
  session.on('Network.responseReceived', event => {
    const record = requests.get(event.requestId);
    if (record) record.status = event.response.status;
  });
  session.on('Network.dataReceived', event => {
    const record = requests.get(event.requestId);
    const telemetry = page.__turnTelemetry;
    if (record && telemetry && record.first_byte_ms === null) {
      record.first_byte_ms = Date.now() - telemetry.startedAt;
    }
  });
  session.on('Network.loadingFinished', async event => {
    const record = requests.get(event.requestId);
    if (!record) return;
    try {
      const body = await session.send('Network.getResponseBody', { requestId: event.requestId });
      const text = body.base64Encoded ? Buffer.from(body.body, 'base64').toString('utf8') : body.body;
      const addNames = value => {
        if (!value || typeof value !== 'object') return;
        if (Array.isArray(value)) { for (const item of value) addNames(item); return; }
        if (value.function && typeof value.function.name === 'string') record.tool_names.add(value.function.name);
        for (const child of Object.values(value)) addNames(child);
      };
      for (const line of text.split(/\r?\n/)) {
        if (!line.startsWith('data:')) continue;
        const payload = line.slice(5).trim();
        if (!payload || payload === '[DONE]') continue;
        try { addNames(JSON.parse(payload)); } catch (_) {}
      }
    } catch (_) { /* Keep only timing/status when the browser discards a streamed body. */ }
  });
  return session;
}

async function login(context, emailName, passwordName) {
  const response = await fetch(`${base}/api/v1/auths/ldap`, {
    method: 'POST', headers: {'content-type': 'application/json'},
    body: JSON.stringify({ user: secret(emailName), password: secret(passwordName) }),
  });
  if (!response.ok) throw new Error(`login HTTP ${response.status}`);
  const body = await response.json();
  if (!body.token) throw new Error('login returned no token');
  await context.addCookies([{ name: 'token', value: body.token, domain: new URL(base).hostname, path: '/' }]);
  return body.token;
}

async function persistedRouteSignals(page, token) {
  const chatId = decodeURIComponent(page.url().split('/c/')[1] || '').split(/[/?#]/)[0];
  if (!chatId) return { history_status: 'NO_CHAT_ID' };
  const response = await fetch(`${base}/api/v1/chats/${encodeURIComponent(chatId)}`, {
    headers: { authorization: `Bearer ${token}` },
  });
  if (!response.ok) return { history_status: response.status };
  const payload = await response.json();
  const history = payload.chat?.history || payload.history || {};
  const messages = Object.values(history.messages || {}).filter(message => message?.role === 'assistant');
  const toolNames = new Set();
  const modelIds = new Set();
  const collectTools = value => {
    if (!value || typeof value !== 'object') return;
    if (Array.isArray(value)) { for (const item of value) collectTools(item); return; }
    if (value.function && typeof value.function.name === 'string') toolNames.add(value.function.name);
    for (const child of Object.values(value)) collectTools(child);
  };
  for (const message of messages) {
    for (const candidate of [message.model, message.modelName, message.info?.model]) {
      if (typeof candidate === 'string' && candidate.length < 120) modelIds.add(candidate);
    }
    collectTools(message.tool_calls);
    collectTools(message.info?.meta?.tool_calls);
    collectTools(message.info?.tool_calls);
  }
  return {
    history_status: 'READ',
    assistant_messages: messages.length,
    model_ids: [...modelIds].sort(),
    tool_names: [...toolNames].sort(),
  };
}

async function send(page, prompt) {
  const nodes = page.locator('#response-content-container .markdown-prose');
  const before = await nodes.count();
  const baseline = ((await nodes.allTextContents()).at(-1) || '').trim();
  const startedAt = Date.now();
  let firstVisibleMs = null;
  page.__turnTelemetry = { startedAt, completions: [] };
  page.__completion = false;
  const submit = page.locator('button[type="submit"]:visible');
  await page.locator('#chat-input').fill(prompt);
  if (await submit.count()) await submit.last().click(); else await page.locator('#chat-input').press('Enter');
  const deadline = Date.now() + waitMs;
  while (Date.now() < deadline) {
    const current = page.locator('#response-content-container .markdown-prose');
    const texts = await current.allTextContents();
    const last = (texts.at(-1) || '').trim();
    if (last && (texts.length > before || last !== baseline) && firstVisibleMs === null) {
      firstVisibleMs = Date.now() - startedAt;
    }
    const stop = await page.locator('#message-input-container button[aria-label="Stop"]').count();
    if (last && (texts.length > before || last !== baseline || page.__completion) && !stop) {
      await page.waitForTimeout(600);
      const answer = (await current.last().innerText()).trim();
      page.__lastTurnTelemetry = {
        elapsed_ms: Date.now() - startedAt,
        first_visible_text_ms: firstVisibleMs,
        completion_requests: page.__turnTelemetry.completions.length,
        first_response_byte_ms: page.__turnTelemetry.completions.find(item => item.first_byte_ms !== null)?.first_byte_ms ?? null,
        completion_statuses: page.__turnTelemetry.completions.map(item => item.status),
        tool_names: [...new Set(page.__turnTelemetry.completions.flatMap(item => [...item.tool_names]))].sort(),
      };
      return answer;
    }
    await page.waitForTimeout(300);
  }
  throw new Error('settlement timeout; response content omitted from diagnostic output');
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const result = { started_at: new Date().toISOString(), viewport: { width: 390, height: 844 }, users: {} };
  try {
    for (const [user, [email, password]] of selectedUsers) {
      const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: result.viewport });
      const page = await context.newPage();
      const telemetrySession = await attachCompletionTelemetry(page);
      const token = await login(context, email, password);
      await page.goto(`${base}/`, { waitUntil: 'commit', timeout: 30000 });
      await page.waitForSelector('#chat-input', { timeout: 30000 });
      const fresh = page.locator('[aria-label="New Chat"]:visible, #new-chat-button:visible, button:has-text("New Chat"):visible');
      if (await fresh.count()) await fresh.last().click().catch(() => {});
      const turns = {};
      if (process.env.HADES_PHASE2_REVOKE_ONLY === '1') {
        if (user === 'owner') {
          const verb = process.env.HADES_PHASE2_RESHARE_ONLY === '1' ? 'share' : 'revoke sharing';
          const revokePreview = await send(page, `${verb} the weekly household summary with household-a`);
          const revokeConfirmation = await send(page, 'yes');
          turns.revocation = { preview: revokePreview.replace(/\s+/g, ' ').slice(0, 300), confirmation: revokeConfirmation.replace(/\s+/g, ' ').slice(0, 300) };
        }
        result.users[user] = turns;
        await telemetrySession.detach();
        await context.close();
        continue;
      }
      if (process.env.HADES_PHASE2_HISTORY_ONLY === '1') {
        const historyOnly = await send(page, 'show the latest weekly household summary');
        turns.history_only = { digest: digest(historyOnly), chars: historyOnly.length, excerpt: historyOnly.replace(/\s+/g, ' ').slice(0, 500) };
        result.users[user] = turns;
        await telemetrySession.detach();
        await context.close();
        continue;
      }
      if (process.env.HADES_PHASE2_RECIPE_ONLY === '1') {
        const customPrompt = String(process.env.HADES_PHASE2_RECIPE_PROMPT || '').trim();
        const variants = customPrompt ? [customPrompt] : [
          'List my recipes, and tell me which ones I can make right now without buying anything.',
          'List my recipes and tell me which ones I can make right now.',
          'Which recipes can we make right now?',
        ];
        for (const variant of variants) {
          const turnStartedAt = Date.now();
          const text = await send(page, variant);
          const turn = {
            digest: digest(text),
            chars: text.length,
            elapsed_ms: Date.now() - turnStartedAt,
            ...(page.__lastTurnTelemetry || {}),
            persisted_route: await persistedRouteSignals(page, token),
          };
          if (process.env.HADES_PHASE2_REDACT_RESPONSE !== '1') {
            turn.excerpt = text.replace(/\s+/g, ' ').slice(0, 500);
          }
          turns[customPrompt ? 'custom_read' : variant] = turn;
        }
        result.users[user] = turns;
        await telemetrySession.detach();
        await context.close();
        continue;
      }
      for (const [key, prompt] of Object.entries(prompts)) {
        const text = await send(page, prompt);
        turns[key] = { digest: digest(text), chars: text.length, excerpt: text.replace(/\s+/g, ' ').slice(0, 240) };
      }
      if (user === 'owner' && process.env.HADES_PHASE2_EXECUTE === '1') {
        const preview = await send(page, 'run my weekly household summary');
        const confirmation = await send(page, 'yes');
        const history = await send(page, 'show the latest weekly household summary');
        const lowPreview = await send(page, 'run my low grocery summary');
        const lowConfirmation = await send(page, 'yes');
        const backupPreview = await send(page, 'run my backup check');
        const backupConfirmation = await send(page, 'yes');
        turns.execution = {
          preview: preview.replace(/\s+/g, ' ').slice(0, 240),
          confirmation: confirmation.replace(/\s+/g, ' ').slice(0, 360),
          history: history.replace(/\s+/g, ' ').slice(0, 500),
          low_preview: lowPreview.replace(/\s+/g, ' ').slice(0, 240),
          low_confirmation: lowConfirmation.replace(/\s+/g, ' ').slice(0, 360),
          backup_preview: backupPreview.replace(/\s+/g, ' ').slice(0, 240),
          backup_confirmation: backupConfirmation.replace(/\s+/g, ' ').slice(0, 360),
        };
      }
      if (user !== 'owner' && process.env.HADES_PHASE2_EXECUTE === '1') {
        const sharedHistory = await send(page, 'show the latest weekly household summary');
        turns.shared_history = { digest: digest(sharedHistory), chars: sharedHistory.length, excerpt: sharedHistory.replace(/\s+/g, ' ').slice(0, 500) };
      }
      if (user === 'owner' && process.env.HADES_PHASE2_REVOKE === '1') {
        const revokePreview = await send(page, 'revoke sharing for the weekly household summary from household-a');
        const revokeConfirmation = await send(page, 'yes');
        turns.revocation = {
          preview: revokePreview.replace(/\s+/g, ' ').slice(0, 300),
          confirmation: revokeConfirmation.replace(/\s+/g, ' ').slice(0, 300),
        };
      }
      result.users[user] = turns;
      await telemetrySession.detach();
      await context.close();
    }
  } finally { await browser.close(); }
  console.log(JSON.stringify(result, null, 2));
})().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
