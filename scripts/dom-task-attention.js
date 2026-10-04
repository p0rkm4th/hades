#!/usr/bin/env node

/* Authenticated disposable UI acceptance for actor-scoped Task attention. */
const fs = require('node:fs');
const { execFileSync } = require('node:child_process');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');

const base = (process.env.HADES_TASK_ATTENTION_DOM_BASE_URL || '').replace(/\/$/, '');
const report = process.env.HADES_TASK_ATTENTION_REPORT || '/tmp/hades-task-attention-dom.json';
const password = process.env.HADES_TASK_ATTENTION_PASSWORD;
const modelId = process.env.HADES_TASK_ATTENTION_MODEL_ID;
const users = {
  alpha: { email: process.env.HADES_TASK_ATTENTION_ALPHA_EMAIL, own: 'Alpha synthetic dinner plan', foreign: ['Beta private synthetic plan', 'Gamma private synthetic plan'] },
  beta: { email: process.env.HADES_TASK_ATTENTION_BETA_EMAIL, own: 'Beta private synthetic plan', foreign: ['Alpha synthetic dinner plan', 'Gamma private synthetic plan'] },
  gamma: { email: process.env.HADES_TASK_ATTENTION_GAMMA_EMAIL, own: 'Gamma private synthetic plan', foreign: ['Alpha synthetic dinner plan', 'Beta private synthetic plan'] },
};
const authTokens = new Map();

async function tokenFor(account) {
  if (authTokens.has(account)) return authTokens.get(account);
  const user = users[account];
  const auth = await fetch(`${base}/api/v1/auths/signin`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ email: user.email, password }),
  });
  if (!auth.ok) throw new Error(`${account} login failed: HTTP ${auth.status}`);
  const { token } = await auth.json();
  if (!token) throw new Error(`${account} login returned no token`);
  authTokens.set(account, token);
  return token;
}
if (!base || !password || !modelId || Object.values(users).some(user => !user.email)) {
  throw new Error('disposable UI URL, advertised model ID, and synthetic Alpha/Beta/Gamma credentials are required');
}

async function installTaskNotificationFetchControl(page) {
  await page.addInitScript(() => {
    const nativeFetch = window.fetch.bind(window);
    window.__hadesTaskNotificationStatus = 200;
    window.__hadesTaskNotificationRequests = 0;
    window.__hadesTaskNotificationRelease401 = null;
    window.__hadesTaskNotificationRelease200 = null;
    window.fetch = (input, init) => {
      const url = typeof input === 'string' ? input : input?.url || '';
      if (!url.includes('/api/v1/hades/tasks/notifications')) return nativeFetch(input, init);
      window.__hadesTaskNotificationRequests += 1;
      const status = window.__hadesTaskNotificationStatus;
      if (status === 'deferred401') {
        return new Promise(resolve => {
          window.__hadesTaskNotificationRelease401 = () => resolve(new Response('', { status: 401 }));
        });
      }
      if (status === 'deferred200') {
        return new Promise(resolve => {
          window.__hadesTaskNotificationRelease200 = () => resolve(new Response(JSON.stringify({
            version: 1,
            tasks: [{ task_id: 'task-alpha-approval', revision: 99, status: 'FAILED', goal: 'Alpha synthetic dinner plan' }],
          }), { status: 200, headers: { 'content-type': 'application/json' } }));
        });
      }
      if (status !== 200) return Promise.resolve(new Response('', { status }));
      return nativeFetch(input, init);
    };
  });
}

async function installDesktopNotificationFixture(page) {
  await page.addInitScript(() => {
    window.__hadesSyntheticDocumentHidden = false;
    window.__hadesSyntheticDesktopNotifications = [];
    Object.defineProperty(document, 'hidden', {
      configurable: true,
      get: () => window.__hadesSyntheticDocumentHidden,
    });
    class SyntheticNotification {
      constructor(title, options = {}) {
        this.title = title;
        this.body = options.body || '';
        this.closed = false;
        window.__hadesSyntheticDesktopNotifications.push(this);
      }
      close() {
        this.closed = true;
        if (typeof this.onclose === 'function') this.onclose();
      }
    }
    Object.defineProperty(SyntheticNotification, 'permission', { value: 'granted' });
    window.Notification = SyntheticNotification;
    const nativeSetInterval = window.setInterval.bind(window);
    window.setInterval = (callback, delay, ...args) => {
      if (delay === 30000) window.__hadesTaskNotificationPollNow = callback;
      return nativeSetInterval(callback, delay, ...args);
    };
  });
}

async function ask(browser, account, prompt = 'What needs my attention?') {
  const user = users[account];
  const token = await tokenFor(account);

  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  try {
    await context.addCookies([{ name: 'token', value: token, url: `${base}/` }]);
    const page = await context.newPage();
    await installTaskNotificationFetchControl(page);
    await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForSelector('#chat-input', { timeout: 30000 });
    const welcome = page.getByRole('button', { name: /okay,\s*let.s go/i });
    if (await welcome.count()) await welcome.first().click({ force: true });
    const selectModel = page.getByRole('button', { name: /select a model/i });
    if (await selectModel.count()) {
      await selectModel.first().click();
      const option = page.getByText(modelId, { exact: true }).last();
      await option.waitFor({ state: 'visible', timeout: 10000 });
      await option.click();
    }
    await page.locator('#chat-input').fill(prompt);
    await page.locator('#send-message-button').click({ force: true });

    const selector = '#response-content-container .markdown-prose';
    const deadline = Date.now() + 45000;
    let response = '';
    while (Date.now() < deadline) {
      const items = page.locator(selector);
      const count = await items.count();
      response = count ? (await items.last().innerText()).trim() : '';
      const streaming = await page.locator('#message-input-container button[aria-label="Stop"]').count();
      if (response && !streaming) break;
      await page.waitForTimeout(250);
    }
    if (!response) throw new Error(`${account} attention turn returned no response; page=${(await page.locator('body').innerText()).slice(-1400)}`);
    const isMediaHelp = prompt === "The thing we watch movies on isn't working.";
    const isMinecraftProvisioning = prompt === 'Can you spin up a Minecraft server for me and let me know the server port/ip so I can add it to the firewall?';
    const isGenericProvisioning = prompt === 'Can you spin up a server?';
    const isUnsupportedProvisioning = prompt === 'Can you spin up a Factorio server?';
    const isAmbiguousProvisioning = prompt === 'Make a Minecraft server and a website';
    const isWeeklyPartial = prompt === 'Show the latest weekly household summary.';
    const isComputerStatus = prompt === 'Are all the computers okay?';
    const isNamedNodeStatus = prompt === 'whats deep-inference-node doing rn';
    const isCompoundServerBackupStatus = prompt === 'Are all the servers okay, and what backup coverage do I have?';
    const isFinanceComparison = prompt === 'How much am I spending eating out compared with groceries?';
    const isFinanceMonthOverMonth = prompt === 'Why was spending higher this month?';
    const isMinecraftHealth = prompt === 'Is Minecraft healthy enough for tonight?';
    const isJellyfinHealth = prompt === 'Is Jellyfin healthy enough for tonight?';
    const isNetworkDiagnosis = prompt === 'Something feels slow on the network; check node status, network health, recent resource usage, and services, then tell me what looks abnormal.';
    const isDetailedHomelab = prompt === 'Give me a detailed homelab status.' ||
      prompt === 'Is everything okay with the servers?';
    const isMorningBriefing = prompt === 'Can I have my morning briefing?';
    const isFreshBriefingRecap = prompt === 'What did we learn from my morning briefing, and what needs attention first?';
    if (isMinecraftProvisioning) {
      for (const expected of [
        'no approved minecraft template and placement are configured',
        'Nothing was prepared or created',
        "I won't start a generic VM or change the firewall.",
      ]) {
        if (!response.includes(expected)) throw new Error(`${account} Minecraft preflight omitted ${expected}: ${response}`);
      }
    } else if (isGenericProvisioning) {
      if (!response.includes('What kind of server do you want to run?') || !response.includes("I haven't prepared anything")) {
        throw new Error(`${account} generic server request did not clarify without preparing a VM: ${response}`);
      }
    } else if (isUnsupportedProvisioning) {
      for (const expected of [
        "don't have an approved factorio server template",
        "I won't substitute a different VM",
        'nothing was prepared',
      ]) {
        if (!response.includes(expected)) throw new Error(`${account} unsupported workload response omitted ${expected}: ${response}`);
      }
    } else if (isAmbiguousProvisioning) {
      if (!response.includes('more than one possible server type') || !response.includes('nothing was prepared or created')) {
        throw new Error(`${account} mixed workload request was not clarified safely: ${response}`);
      }
    } else if (isNetworkDiagnosis) {
      for (const expected of [
        'Fresh configured-probe response-time samples: Router ping: 84 ms.',
        'These are individual configured-check samples, not a network-wide measure.',
        'Packet-loss, throughput, and historical comparison data are unavailable',
        'cannot identify a network bottleneck or trend from this evidence',
      ]) {
        if (!response.includes(expected)) throw new Error(`${account} network diagnosis omitted ${expected}: ${response}`);
      }
    } else if (isCompoundServerBackupStatus) {
      for (const expected of [
        'SERVER STATUS:',
        'Live Proxmox currently reports: synthetic-core-node.',
        'BACKUP COVERAGE:',
        'Your Backup Checks:',
        'Backup Check (HADES repository) — enabled',
        'Verified coverage currently exists only for: HADES repository.',
      ]) {
        if (!response.includes(expected)) throw new Error(`${account} compound server/backup answer omitted ${expected}: ${response}`);
      }
    } else if (isDetailedHomelab) {
      for (const expected of [
        'Live Proxmox currently reports: synthetic-core-node.',
        "Uptime Kuma's configured probes failed: Search",
        'Jellyfin (last reported down; stale)',
        "Uptime Kuma's configured probes responded for: Minecraft Server",
        'does not prove application login, session, or workload readiness',
        'Inference-worker health was not independently verified by this read.',
        'Repository backup freshness: HADES repository backup: healthy; last successful check',
      ]) {
        if (!response.includes(expected)) throw new Error(`${account} detailed homelab status omitted ${expected}: ${response}`);
      }
      if (/configured probes failed: Jellyfin(?:[.]|,)/i.test(response)) {
        throw new Error(`${account} detailed homelab status reported a stale monitor as currently down: ${response}`);
      }
    } else if (isMinecraftHealth) {
      for (const expected of [
        "Uptime Kuma's configured check for Minecraft Server is up.",
        'does not verify an application login, usable session, or workload state',
        "can't guarantee it is ready for use",
      ]) {
        if (!response.includes(expected)) throw new Error(`${account} Minecraft health answer omitted ${expected}: ${response}`);
      }
    } else if (isJellyfinHealth) {
      if (!response.includes("couldn't verify a current Uptime Kuma service monitor matching jellyfin") ||
          !response.includes('Proxmox host or VM being online does not show')) {
        throw new Error(`${account} Jellyfin health answer inferred service health without a monitor: ${response}`);
      }
    } else if (isFinanceComparison) {
      for (const expected of [
        'CSV finance comparison (owner-only, read-only)',
        '$52.00 for dining out across 2 transactions',
        '$180.00 for groceries across 2 transactions',
        '$26.00 dining out and $90.00 groceries',
        'not a live balance or forecast',
      ]) {
        if (!response.includes(expected)) throw new Error(`${account} finance comparison omitted ${expected}: ${response}`);
      }
    } else if (isFinanceMonthOverMonth) {
      if (account === 'alpha') {
        for (const expected of [
          'CSV finance comparison (owner-only, read-only)',
          '$100.00 higher',
          '$300.00 across 3 expense rows',
          '$200.00',
          'Restaurants $60.00',
          'Groceries $40.00',
          'matching calendar days',
          'Pending rows included: 1 this month and 0 last month',
          'Historical statement data only',
          'no live balance or forecast is available',
        ]) {
          if (!response.includes(expected)) throw new Error(`Alpha month-over-month finance answer omitted ${expected}: ${response}`);
        }
        if (response.includes('$2,500.00')) throw new Error(`month-over-month finance answer included income: ${response}`);
      } else if (!response.includes("I can't access the owner's finances. That information is owner-only")) {
        throw new Error(`${account} month-over-month finance request was not denied as owner-only: ${response}`);
      }
    } else if (isComputerStatus) {
      if (!response.includes('Live Proxmox currently reports: synthetic-core-node.') ||
          !response.includes('Repository backup freshness: HADES repository backup: healthy; last successful check') ||
          /memory update/i.test(response)) {
        throw new Error(`${account} low-tech computer status did not use the safe live homelab route: ${response}`);
      }
    } else if (isNamedNodeStatus) {
      for (const expected of [
        'I found deep-inference-node in the hardware inventory.',
        'The recorded address is 192.0.2.69.',
        'It is listed as synthetic inference node.',
        "I don't have a current runtime check for it, so I can't say whether it's online.",
      ]) {
        if (!response.includes(expected)) throw new Error(`Alpha named-node status omitted ${expected}: ${response}`);
      }
    } else if (prompt === 'whats specialized-inference-node doing rn') {
      for (const expected of [
        'the specialized-inference-node check is responding (fresh observation).',
        "That confirms only that this check responded; I don't have a current host workload or operating-system status.",
      ]) {
        if (!response.includes(expected)) throw new Error(`Alpha monitor-only fresh-up answer omitted ${expected}: ${response}`);
      }
      if (/Proxmox runtime status is|GPU health|workload is healthy/i.test(response)) {
        throw new Error(`Alpha monitor-only fresh-up answer overstated host health: ${response}`);
      }
    } else if (prompt === 'whats management-node doing rn') {
      for (const expected of [
        'the management-node check is failing (fresh observation).',
        'That confirms the check failed, but not why or whether the host is powered off.',
      ]) {
        if (!response.includes(expected)) throw new Error(`Alpha monitor-only fresh-down answer omitted ${expected}: ${response}`);
      }
      if (/Proxmox runtime status is|management-node is (?:offline|powered off)/i.test(response)) {
        throw new Error(`Alpha monitor-only fresh-down answer inferred host status: ${response}`);
      }
    } else if (prompt === 'whats hermes doing rn') {
      for (const expected of [
        'the Hermes check last reported up, but that observation is stale.',
        "I can't verify current reachability or workload status.",
      ]) {
        if (!response.includes(expected)) throw new Error(`Alpha monitor-only stale answer omitted ${expected}: ${response}`);
      }
      if (/Proxmox runtime status is|currently online|currently responding/i.test(response)) {
        throw new Error(`Alpha monitor-only stale answer presented stale status as current: ${response}`);
      }
    } else if (isMediaHelp) {
      if (!response.includes('Do you mean the TV, a streaming box, or an app?')) {
        throw new Error(`${account} media-help turn did not ask a plain-language clarification: ${response}`);
      }
    } else if (isMorningBriefing) {
      if (!response.includes('HADES morning briefing (bounded live sources):') ||
          !response.includes('Live Proxmox currently reports: synthetic-core-node.')) {
        throw new Error(`${account} morning briefing omitted the synthetic live source: ${response}`);
      }
    } else if (isFreshBriefingRecap) {
      for (const expected of [
        'HADES morning briefing refresh (bounded live sources):',
        'I refreshed the live sources instead of relying on a stale prior conversation',
        'Live Proxmox currently reports: synthetic-core-node.',
        'Alpha synthetic dinner plan is waiting for your approval.',
      ]) {
        if (!response.includes(expected)) {
          throw new Error(`${account} fresh-session recap omitted ${expected}: ${response}`);
        }
      }
    } else if (isWeeklyPartial) {
      if (account === 'gamma') {
        if (!response.includes('No shared Weekly Household Summary is available') ||
            response.includes('All servers look okay.') || response.includes('Last verified backup')) {
          throw new Error(`${account} received a partial summary without an active share: ${response}`);
        }
      } else {
        for (const expected of [
          'Unavailable this week: Groceries.',
          'All servers look okay.',
          'Last verified backup is healthy.',
        ]) {
          if (!response.includes(expected)) throw new Error(`${account} partial weekly result omitted ${expected}: ${response}`);
        }
      }
    } else if (!isCompoundServerBackupStatus && !response.includes(user.own)) {
      throw new Error(`${account} response omitted its own task: ${response}`);
    }
    for (const text of user.foreign) if (response.includes(text)) throw new Error(`${account} response disclosed another user's task`);
    if (/task-(?:alpha|beta|gamma)-/i.test(response)) throw new Error(`${account} response disclosed an internal task ID`);

    // Confirm the authenticated chat history API stores the turn, including
    // the assistant summary, under this user's account.
    let persisted = false;
    const persistenceDeadline = Date.now() + 12000;
    while (Date.now() < persistenceDeadline) {
      const chatsResponse = await fetch(`${base}/api/v1/chats/?page=1`, {
        headers: { authorization: `Bearer ${token}` },
      });
      if (chatsResponse.ok) {
        const payload = await chatsResponse.json();
        const chats = Array.isArray(payload) ? payload : (payload.items || payload.chats || []);
        for (const chat of chats.slice(0, 30)) {
          const id = chat.id || chat.chat_id;
          if (!id) continue;
          const storedResponse = await fetch(`${base}/api/v1/chats/${encodeURIComponent(id)}`, {
            headers: { authorization: `Bearer ${token}` },
          });
          const expected = isDetailedHomelab
            ? "Uptime Kuma's configured probes failed: Search"
            : isMinecraftProvisioning
              ? 'no approved `minecraft` template and placement are configured'
            : isGenericProvisioning
              ? 'What kind of server do you want to run?'
            : isUnsupportedProvisioning
              ? "don't have an approved `factorio` server template"
            : isAmbiguousProvisioning
              ? 'more than one possible server type'
            : isNetworkDiagnosis
              ? 'Fresh configured-probe response-time samples: Router ping: 84 ms.'
            : isMinecraftHealth
            ? "Uptime Kuma's configured check for Minecraft Server is up."
            : isJellyfinHealth
              ? "couldn't verify a current Uptime Kuma service monitor matching jellyfin"
              : isFinanceComparison
            ? 'CSV finance comparison (owner-only, read-only)'
            : isFinanceMonthOverMonth
              ? account === 'alpha'
                ? 'CSV finance comparison (owner-only, read-only)'
                : "I can't access the owner's finances. That information is owner-only"
            : isComputerStatus
            ? 'Repository backup freshness: HADES repository backup: healthy'
            : isNamedNodeStatus
            ? 'I found deep-inference-node in the hardware inventory.'
            : isCompoundServerBackupStatus
              ? 'SERVER STATUS:'
            : prompt === 'whats specialized-inference-node doing rn'
              ? 'the specialized-inference-node check is responding (fresh observation).'
              : prompt === 'whats management-node doing rn'
                ? 'the management-node check is failing (fresh observation).'
                : prompt === 'whats hermes doing rn'
                  ? 'the Hermes check last reported up, but that observation is stale.'
            : isMediaHelp
            ? 'Do you mean the TV, a streaming box, or an app?'
            : isMorningBriefing
              ? 'HADES morning briefing (bounded live sources):'
                : isFreshBriefingRecap
                  ? 'HADES morning briefing refresh (bounded live sources):'
                  : isWeeklyPartial
                    ? account === 'gamma'
                      ? 'No shared Weekly Household Summary is available'
                      : 'Unavailable this week: Groceries.'
                : user.own;
          if (storedResponse.ok && JSON.stringify(await storedResponse.json()).includes(expected)) {
            persisted = true;
            break;
          }
        }
      }
      if (persisted) break;
      await page.waitForTimeout(500);
    }
    if (!persisted) throw new Error(`${account} response to ${JSON.stringify(prompt)} did not persist in authenticated chat history`);
    return response;
  } finally {
    await context.close();
  }
}

async function verifyMinecraftLostStateRecovery(browser) {
  const account = 'alpha';
  const user = users[account];
  const token = await tokenFor(account);
  const tokenPayload = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString('utf8'));
  const actor = String(tokenPayload.id || '');
  if (!actor) throw new Error('synthetic Alpha token has no stable subject ID');
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  try {
    await context.addCookies([{ name: 'token', value: token, url: `${base}/` }]);
    let page = await context.newPage();
    const chatCompletionRequests = [];
    page.on('request', request => {
      if (/\/api\/chat\/completions(?:\?|$)/.test(request.url())) chatCompletionRequests.push(request.url());
    });
    await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForSelector('#chat-input', { timeout: 30000 });
    const welcome = page.getByRole('button', { name: /okay,\s*let.s go/i });
    if (await welcome.count()) await welcome.first().click({ force: true });
    const selectModel = page.getByRole('button', { name: /select a model/i });
    if (await selectModel.count()) {
      await selectModel.first().click();
      const option = page.getByText(modelId, { exact: true }).last();
      await option.waitFor({ state: 'visible', timeout: 10000 });
      await option.click();
    }
    const sendTurn = async prompt => {
      const selector = '#response-content-container .markdown-prose';
      const previousText = await page.locator('#response-content-container').innerText().catch(() => '');
      const requestsBefore = chatCompletionRequests.length;
      await page.locator('#chat-input').fill(prompt);
      const submit = page.locator('#send-message-button:visible').last();
      await submit.waitFor({ state: 'visible', timeout: 10000 });
      await submit.evaluate(element => element.click());
      const requestDeadline = Date.now() + 10000;
      while (chatCompletionRequests.length === requestsBefore && Date.now() < requestDeadline) {
        await page.waitForTimeout(100);
      }
      if (chatCompletionRequests.length === requestsBefore) {
        throw new Error(`Open WebUI sent no chat completion for ${JSON.stringify(prompt)}; page=${(await page.locator('body').innerText()).slice(-1000)}`);
      }
      const deadline = Date.now() + 45000;
      while (Date.now() < deadline) {
        const items = page.locator(selector);
        const count = await items.count();
        const conversationText = await page.locator('#response-content-container').innerText().catch(() => '');
        const response = count && conversationText !== previousText ? (await items.last().innerText()).trim() : '';
        const streaming = await page.locator('#message-input-container button[aria-label="Stop"]').count();
        if (response && !streaming) return response;
        await page.waitForTimeout(250);
      }
      throw new Error(`authenticated Minecraft recovery turn timed out: ${prompt}; url=${page.url()}; page=${(await page.locator('body').innerText()).slice(-1400)}`);
    };
    const originalRequest = 'Can you spin up a Minecraft server for me and lemme know the server port/ip so I can add it to the firewall?';
    const offer = await sendTurn(originalRequest);
    const expectedPlan = [
      'Plan only', 'minecraft', 'gamma-minecraft', '4 CPU cores', '8 GiB RAM',
      '40 GiB disk', 'SyntheticNode', 'owner only', 'TCP 25565',
      'does not confirm Minecraft is installed or running',
      'cannot read back the guest IP', 'No firewall rule will be changed', 'reply Create it',
    ];
    const missingPlanDetails = expectedPlan.filter(expected => !offer.includes(expected));
    if (/^Created\b|VMID\s+\d+/im.test(offer)) throw new Error(`configured synthetic catalog unexpectedly created a server: ${offer}`);
    const chatId = page.url().split('/').filter(Boolean).at(-1);
    if (!chatId) throw new Error('Open WebUI did not expose the current chat ID in its URL');
    if (process.env.HADES_TASK_ATTENTION_ACTIVE_ARTIFACT_DIAGNOSTIC === '1') {
      const pendingState = execFileSync('python3', ['-c', [
        'import json, sys',
        'sys.path.insert(0, sys.argv[1])',
        'from integrations.automation import LifecycleStore',
        'actor, state_path, origin = sys.argv[2:]',
        'store = LifecycleStore(state_path)',
        'rows = [row for row in store.pending_for_actor(actor) if row.get("payload", {}).get("origin") == origin and row.get("payload", {}).get("template") == "minecraft"]',
        'print(json.dumps({"count": len(rows), "statuses": [row.get("status") for row in rows]}))',
      ].join('\n'), process.env.HADES_TASK_ATTENTION_REPO_DIR,
      actor, process.env.HADES_TASK_ATTENTION_EPSILON_DB, originalRequest], { encoding: 'utf8', stdio: 'pipe' });
      let continuation;
      try {
        continuation = { response: await sendTurn('Perfect, continue') };
      } catch (error) {
        continuation = { error: error.message };
      }
      await page.close();
      page = await context.newPage();
      page.on('request', request => {
        if (/\/api\/chat\/completions(?:\?|$)/.test(request.url())) chatCompletionRequests.push(request.url());
      });
      await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForSelector('#chat-input', { timeout: 10000 });
      const freshModel = page.getByRole('button', { name: /select a model/i });
      if (await freshModel.count()) {
        await freshModel.first().click();
        const option = page.getByText(modelId, { exact: true }).last();
        await option.waitFor({ state: 'visible', timeout: 10000 });
        await option.click();
      }
      let crossChatConfirmation;
      try {
        crossChatConfirmation = { response: await sendTurn('Yes') };
      } catch (error) {
        crossChatConfirmation = { error: error.message };
      }
      const syntheticControlCalls = (() => {
        const path = process.env.HADES_TASK_ATTENTION_SYNTHETIC_CONTROL_CALLS;
        if (!path || !fs.existsSync(path)) return [];
        return fs.readFileSync(path, 'utf8').split(/\r?\n/).filter(Boolean).map(line => JSON.parse(line));
      })();
      return {
        status: 'DIAGNOSTIC',
        initial_response: offer,
        plan_details_missing: missingPlanDetails,
        synthetic_pending_state: JSON.parse(pendingState),
        same_chat_continuation: continuation,
        fresh_chat_confirmation: crossChatConfirmation,
        synthetic_provision_calls_from_fresh_chat: syntheticControlCalls,
        side_effect_boundary: 'disposable synthetic identities and registry; Proxmox URL and credentials are unset; no production infrastructure is reachable from this harness',
      };
    }
    for (const expected of expectedPlan) {
      if (!offer.includes(expected)) throw new Error(`configured synthetic catalog first response omitted ${expected}: ${offer}`);
    }
    const removal = [
      'import sys',
      'sys.path.insert(0, sys.argv[1])',
      'from integrations.automation import LifecycleStore',
      'actor, state_path, origin = sys.argv[2:]',
      'store = LifecycleStore(state_path)',
      'matches = [row for row in store.pending_for_actor(actor) if row.get("payload", {}).get("origin") == origin and row.get("payload", {}).get("template") == "minecraft"]',
      'assert len(matches) == 1, "expected exactly this synthetic Alpha chat pending record"',
      'key = matches[0]["pending_key"]',
      'store.pending_delete(key, actor)',
      'assert store.pending_get(key, actor) is None, "pending record was not removed"',
      'print("SYNTHETIC_PENDING_REMOVED")',
    ].join('\n');
    const removed = execFileSync('python3', ['-c', removal, process.env.HADES_TASK_ATTENTION_REPO_DIR,
      actor, process.env.HADES_TASK_ATTENTION_EPSILON_DB, originalRequest], { encoding: 'utf8', stdio: 'pipe' });
    if (!removed.includes('SYNTHETIC_PENDING_REMOVED')) throw new Error('could not confirm deletion of the isolated synthetic pending record');
    const recovery = await sendTurn('Perfect, continue');
    for (const expected of [
      'Plan only', 'minecraft', 'gamma-minecraft', '4 CPU cores', '8 GiB RAM',
      '40 GiB disk', 'SyntheticNode', 'owner only', 'TCP 25565',
      'does not confirm Minecraft is installed or running',
      'cannot read back the guest IP', 'No firewall rule will be changed', 'reply Create it',
    ]) {
      if (!recovery.includes(expected)) throw new Error(`recovered authenticated plan omitted ${expected}: ${recovery}`);
    }
    if (/^Created\b|VMID\s+\d+/im.test(recovery)) throw new Error(`recovery unexpectedly created a server: ${recovery}`);
    const chats = await fetch(`${base}/api/v1/chats/${encodeURIComponent(chatId)}`, {
      headers: { authorization: `Bearer ${token}` },
    });
    if (!chats.ok || !JSON.stringify(await chats.json()).includes('Perfect, continue')) {
      throw new Error(`recovered continuation did not persist in authenticated chat ${chatId}`);
    }
    await page.close();
    page = await context.newPage();
    page.on('request', request => {
      if (/\/api\/chat\/completions(?:\?|$)/.test(request.url())) chatCompletionRequests.push(request.url());
    });
    await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForSelector('#chat-input', { timeout: 10000 });
    const freshSelectModel = page.getByRole('button', { name: /select a model/i });
    if (await freshSelectModel.count()) {
      await freshSelectModel.first().click();
      const option = page.getByText(modelId, { exact: true }).last();
      await option.waitFor({ state: 'visible', timeout: 10000 });
      await option.click();
    }
    const contextFree = await sendTurn('Perfect, continue');
    for (const expected of ["don't have enough context", 'Nothing was created', 'repeat which server']) {
      if (!contextFree.toLowerCase().includes(expected.toLowerCase())) {
        throw new Error(`context-free new-chat continuation did not fail closed for ${expected}: ${contextFree}`);
      }
    }
    return {
      status: 'PASS',
      state_loss_injection: 'removed exactly the pending Minecraft record for this synthetic Alpha chat',
      offer: offer.slice(0, 260),
      recovered_response: recovery,
      context_free_response: contextFree,
      side_effects: 'zero model calls, Proxmox calls, VM creations, or firewall changes; pending state remained scoped to its original chat',
    };
  } finally {
    await context.close();
  }
}

async function verifyTaskNotification(browser) {
  const token = await tokenFor('alpha');
  const payload = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString('utf8'));
    const userId = String(payload.id || '');
  if (!userId) throw new Error('Alpha notification login returned no stable user id');
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  try {
    await context.addCookies([{ name: 'token', value: token, url: `${base}/` }]);
    const page = await context.newPage();
    await installTaskNotificationFetchControl(page);
    await installDesktopNotificationFixture(page);
    await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForSelector('#chat-input', { timeout: 30000 });
    await page.waitForFunction(id => localStorage.getItem(`hades-task-notification-state:${id}`) !== null, userId, { timeout: 15000 });
    console.log('Task notification: Alpha baseline loaded');
    if (await page.locator('#hades-task-notification').count()) throw new Error('existing Task state generated a notification during initial baseline');

    execFileSync('python3', ['-c', [
      'import sys',
      'sys.path.insert(0, sys.argv[1])',
      'from integrations.task import TaskStatus, TaskStore',
      'store = TaskStore(sys.argv[2])',
      'task = store.get("task-alpha-approval", sys.argv[3])',
      'store.transition(task["task_id"], sys.argv[3], task["task_revision"], TaskStatus.AWAITING_APPROVAL, event_type="NOTIFICATION_ACCEPTANCE")',
    ].join('\n'), process.env.HADES_TASK_ATTENTION_REPO_DIR, process.env.HADES_TASK_ATTENTION_TASK_DB, userId], { stdio: 'pipe' });
    await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
    const notice = page.locator('#hades-task-notification');
    await notice.waitFor({ state: 'visible', timeout: 15000 });
    console.log('Task notification: Alpha alert shown');
    const noticeText = await notice.innerText();
    if (!noticeText.includes('Alpha synthetic dinner plan') || !noticeText.includes('needs your approval')) {
      throw new Error(`Task notification omitted its actor-scoped status: ${noticeText}`);
    }
    await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
    await page.waitForTimeout(400);
    if (await page.locator('#hades-task-notification').count() !== 1) throw new Error('duplicate task notification surface was rendered');
    await notice.getByRole('button', { name: 'Review in HADES' }).click();
    const reviewPrompt = await page.locator('#chat-input').innerText();
    if (reviewPrompt !== 'Show me the status of my task: Alpha synthetic dinner plan') {
      throw new Error(`Task notification did not navigate to its own review context: ${reviewPrompt}`);
    }
    if (reviewPrompt.includes('task-alpha-approval')) {
      throw new Error('Task notification exposed an internal task identifier');
    }
    await page.locator('#chat-input').fill('');
    await page.evaluate(id => localStorage.setItem(`hades-task-notification-state:${id}`, JSON.stringify({ 'task-alpha-approval': '1:AWAITING_APPROVAL' })), userId);
    await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
    await notice.waitFor({ state: 'visible', timeout: 10000 });

    execFileSync('python3', ['-c', [
      'import sys',
      'sys.path.insert(0, sys.argv[1])',
      'from integrations.task import TaskStatus, TaskStore',
      'store = TaskStore(sys.argv[2])',
      'task = store.get("task-alpha-approval", sys.argv[3])',
      'store.transition(task["task_id"], sys.argv[3], task["task_revision"], TaskStatus.FAILED, event_type="DESKTOP_NOTIFICATION_ACCEPTANCE")',
    ].join('\n'), process.env.HADES_TASK_ATTENTION_REPO_DIR, process.env.HADES_TASK_ATTENTION_TASK_DB, userId], { stdio: 'pipe' });
    await page.evaluate(() => {
      window.__hadesSyntheticDocumentHidden = true;
      window.__hadesTaskNotificationPollNow?.();
    });
    await page.waitForFunction(() => window.__hadesSyntheticDesktopNotifications.some(item => item.body.includes('Alpha synthetic dinner plan')), null, { timeout: 5000 });
    console.log('Task notification: synthetic desktop alert shown');

    await page.waitForTimeout(150);
    const requestCount = await page.evaluate(id => {
      localStorage.setItem(`hades-task-notification-review:${id}`, 'Show me the status of my task: Alpha synthetic dinner plan');
      window.__hadesSyntheticDocumentHidden = false;
      window.__hadesTaskNotificationStatus = 503;
      const before = window.__hadesTaskNotificationRequests;
      document.dispatchEvent(new Event('visibilitychange'));
      return before;
    }, userId);
    await page.waitForFunction(before => window.__hadesTaskNotificationRequests > before, requestCount, { timeout: 5000 });
    console.log('Task notification: transient 503 received');
    await page.waitForTimeout(150);
    const transientState = await page.evaluate(id => ({
      noticeVisible: !!document.getElementById('hades-task-notification'),
      state: localStorage.getItem(`hades-task-notification-state:${id}`),
      review: localStorage.getItem(`hades-task-notification-review:${id}`),
    }), userId);
    if (!transientState.noticeVisible || !transientState.state || !transientState.review) {
      throw new Error(`transient 503 cleared private Task notification state: ${JSON.stringify(transientState)}`);
    }

    const staleSuccessRequestCount = await page.evaluate(() => {
      window.__hadesTaskNotificationStatus = 'deferred200';
      const before = window.__hadesTaskNotificationRequests;
      document.dispatchEvent(new Event('visibilitychange'));
      return before;
    });
    await page.waitForFunction(before =>
      window.__hadesTaskNotificationRequests > before &&
      typeof window.__hadesTaskNotificationRelease200 === 'function',
      staleSuccessRequestCount, { timeout: 5000 }
    );

    const unauthorizedRequestCount = await page.evaluate(() => {
      window.__hadesTaskNotificationStatus = 401;
      const before = window.__hadesTaskNotificationRequests;
      document.dispatchEvent(new Event('visibilitychange'));
      return before;
    });
    await page.waitForFunction(before => window.__hadesTaskNotificationRequests > before, unauthorizedRequestCount, { timeout: 5000 });
    console.log('Task notification: 401 response received');
    await page.waitForFunction(id =>
      !document.getElementById('hades-task-notification') &&
      localStorage.getItem(`hades-task-notification-state:${id}`) === null &&
      localStorage.getItem(`hades-task-notification-review:${id}`) === null &&
      window.__hadesSyntheticDesktopNotifications.length > 0 &&
      window.__hadesSyntheticDesktopNotifications.every(item => item.closed),
      userId, { timeout: 5000 }
    );
    console.log('Task notification: current-recipient 401 cleared state');
    await page.evaluate(async () => {
      window.__hadesTaskNotificationRelease200?.();
      await new Promise(resolve => window.setTimeout(resolve, 200));
    });
    const staleSuccessState = await page.evaluate(id => ({
      noticeVisible: !!document.getElementById('hades-task-notification'),
      state: localStorage.getItem(`hades-task-notification-state:${id}`),
      review: localStorage.getItem(`hades-task-notification-review:${id}`),
    }), userId);
    if (staleSuccessState.noticeVisible || staleSuccessState.state !== null || staleSuccessState.review !== null) {
      throw new Error(`in-flight authorized response restored state after 401: ${JSON.stringify(staleSuccessState)}`);
    }

    const deferredRequestCount = await page.evaluate(id => {
      localStorage.setItem(`hades-task-notification-review:${id}`, 'Show me the status of my task: Alpha synthetic dinner plan');
      window.__hadesTaskNotificationStatus = 'deferred401';
      const before = window.__hadesTaskNotificationRequests;
      document.dispatchEvent(new Event('visibilitychange'));
      return before;
    }, userId);
    await page.waitForFunction(before =>
      window.__hadesTaskNotificationRequests > before &&
      typeof window.__hadesTaskNotificationRelease401 === 'function',
      deferredRequestCount, { timeout: 5000 }
    );
    console.log('Task notification: Alpha 401 held pending');

    const betaToken = await tokenFor('beta');
    const betaPayload = JSON.parse(Buffer.from(betaToken.split('.')[1], 'base64url').toString('utf8'));
    const betaId = String(betaPayload.id || '');
    if (!betaId || betaId === userId) throw new Error('Beta account switch did not produce a distinct user identity');
    await context.addCookies([{ name: 'token', value: betaToken, url: `${base}/` }]);
    await page.evaluate(token => {
      localStorage.setItem('token', token);
      window.__hadesTaskNotificationStatus = 200;
    }, betaToken);
    await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
    await page.waitForFunction(id => localStorage.getItem(`hades-task-notification-state:${id}`) !== null, betaId, { timeout: 15000 });
    console.log('Task notification: Beta baseline loaded');
    await page.evaluate(id => {
      const key = `hades-task-notification-state:${id}`;
      const current = JSON.parse(localStorage.getItem(key) || '{}');
      const entry = current['task-beta-private'];
      if (typeof entry === 'string') {
        const [revision, status] = entry.split(':');
        current['task-beta-private'] = `${Math.max(0, Number(revision) - 1)}:${status}`;
        localStorage.setItem(key, JSON.stringify(current));
      }
      document.dispatchEvent(new Event('visibilitychange'));
    }, betaId);
    await page.waitForFunction(() => document.getElementById('hades-task-notification')?.innerText.includes('Beta private synthetic plan'), null, { timeout: 5000 });
    console.log('Task notification: Beta alert shown');
    await page.evaluate(() => window.__hadesTaskNotificationRelease401?.());
    await page.waitForFunction(id => localStorage.getItem(`hades-task-notification-review:${id}`) === null, userId, { timeout: 5000 });
    if (!(await page.locator('#hades-task-notification').innerText()).includes('Beta private synthetic plan')) {
      throw new Error('stale Alpha 401 response dismissed Beta notification after the account switch');
    }
    await page.waitForTimeout(250);
    if ((await page.locator('body').innerText()).includes('Alpha synthetic dinner plan')) throw new Error('Alpha Task text remained visible after switching the same browser to Beta');
    execFileSync('python3', ['-c', [
      'import sys',
      'sys.path.insert(0, sys.argv[1])',
      'from integrations.task import TaskStatus, TaskStore',
      'store = TaskStore(sys.argv[2])',
      'task = store.get("task-alpha-approval", sys.argv[3])',
      'store.transition(task["task_id"], sys.argv[3], task["task_revision"], TaskStatus.AWAITING_APPROVAL, event_type="RESTORE_NOTIFICATION_FIXTURE")',
    ].join('\n'), process.env.HADES_TASK_ATTENTION_REPO_DIR, process.env.HADES_TASK_ATTENTION_TASK_DB, userId], { stdio: 'pipe' });
    console.log('Task notification: Alpha synthetic task restored to acceptance baseline');
    return { status: 'PASS', recipient: 'Alpha and Beta scoped', notification: noticeText, review_prompt_prefilled: true, chat_not_submitted: true, synthetic_desktop_notification_closed_on_401: true, transient_503_preserves_alert_and_cursor: true, unauthorized_401_clears_current_recipient_state: true, stale_success_after_401_does_not_restore_cursor: true, stale_alpha_401_preserves_beta_alert: true, same_browser_beta_switch_clears_alpha_alert: true };
  } finally {
    await context.close();
  }
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    let results;
    if (process.env.HADES_TASK_ATTENTION_NOTIFICATION_ONLY === '1') {
      results = { notification: await verifyTaskNotification(browser) };
    } else if (process.env.HADES_TASK_ATTENTION_MINECRAFT_RECOVERY === '1') {
      results = { minecraft_lost_state_recovery_alpha: await verifyMinecraftLostStateRecovery(browser) };
    } else if (process.env.HADES_TASK_ATTENTION_MINECRAFT_PREFLIGHT === '1') {
      results = {
        minecraft_preflight_alpha: await ask(
          browser, 'alpha', 'Can you spin up a Minecraft server for me and let me know the server port/ip so I can add it to the firewall?'),
        generic_server_alpha: await ask(browser, 'alpha', 'Can you spin up a server?'),
        unsupported_factorio_alpha: await ask(browser, 'alpha', 'Can you spin up a Factorio server?'),
        mixed_workloads_alpha: await ask(browser, 'alpha', 'Make a Minecraft server and a website'),
      };
    } else if (process.env.HADES_TASK_ATTENTION_NETWORK_DIAGNOSIS === '1') {
      results = {
        network_diagnosis_alpha: await ask(
          browser, 'alpha', 'Something feels slow on the network; check node status, network health, recent resource usage, and services, then tell me what looks abnormal.'
        ),
      };
    } else if (process.env.HADES_TASK_ATTENTION_COMPOUND_STATUS === '1') {
      results = {
        compound_server_backup_status_alpha: await ask(
          browser, 'alpha', 'Are all the servers okay, and what backup coverage do I have?'
        ),
      };
    } else if (process.env.HADES_TASK_ATTENTION_FINANCE_MONTHLY === '1') {
      results = {
        finance_month_over_month_alpha: await ask(browser, 'alpha', 'Why was spending higher this month?'),
        finance_denial_beta: await ask(browser, 'beta', 'Why was spending higher this month?'),
      };
    } else if (process.env.HADES_TASK_ATTENTION_WEEKLY_PARTIAL === '1') {
      results = { weekly_partial: {} };
      for (const account of Object.keys(users)) {
        results.weekly_partial[account] = await ask(
          browser, account, 'Show the latest weekly household summary.'
        );
      }
    } else {
      results = { attention: {}, media_help: {}, notification: await verifyTaskNotification(browser) };
      results.computer_status_alpha = await ask(browser, 'alpha', 'Are all the computers okay?');
      results.named_node_status_alpha = await ask(browser, 'alpha', 'whats deep-inference-node doing rn');
      results.compound_server_backup_status_alpha = await ask(
        browser, 'alpha', 'Are all the servers okay, and what backup coverage do I have?'
      );
      results.monitor_only_fresh_up_alpha = await ask(browser, 'alpha', 'whats specialized-inference-node doing rn');
      results.monitor_only_fresh_down_alpha = await ask(browser, 'alpha', 'whats management-node doing rn');
      results.monitor_only_stale_alpha = await ask(browser, 'alpha', 'whats hermes doing rn');
      results.finance_comparison_alpha = await ask(
        browser, 'alpha', 'How much am I spending eating out compared with groceries?'
      );
      results.minecraft_health_alpha = await ask(browser, 'alpha', 'Is Minecraft healthy enough for tonight?');
      results.homelab_detailed_alpha = await ask(browser, 'alpha', 'Give me a detailed homelab status.');
      results.homelab_broad_alpha = await ask(browser, 'alpha', 'Is everything okay with the servers?');
      results.jellyfin_health_alpha = await ask(browser, 'alpha', 'Is Jellyfin healthy enough for tonight?');
      for (const account of Object.keys(users)) {
        results.attention[account] = await ask(browser, account);
        results.media_help[account] = await ask(
          browser, account, "The thing we watch movies on isn't working."
        );
      }
      results.briefing_alpha = await ask(
        browser, 'alpha', 'Can I have my morning briefing?'
      );
      results.fresh_session_recap_alpha = await ask(
        browser, 'alpha',
        'What did we learn from my morning briefing, and what needs attention first?'
      );
    }
    const diagnostic = process.env.HADES_TASK_ATTENTION_ACTIVE_ARTIFACT_DIAGNOSTIC === '1';
    const result = { status: diagnostic ? 'DIAGNOSTIC' : 'PASS', checks: results };
    fs.writeFileSync(report, `${JSON.stringify(result, null, 2)}\n`, { mode: 0o600 });
    fs.chmodSync(report, 0o600);
    console.log(JSON.stringify({ status: result.status, report }));
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(JSON.stringify({ status: 'FAIL', error: error.message }));
  process.exitCode = 1;
});
