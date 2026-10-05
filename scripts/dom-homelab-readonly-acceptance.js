#!/usr/bin/env node

/* Bounded, read-only owner/household acceptance for live homelab answers. */
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const { chromium } = require(process.env.HADES_PLAYWRIGHT_MODULE || 'playwright');
const {
  createPrivateLabelPatterns,
  containsPrivateTopology,
  validatePrivateLabelDetectors,
} = require('./homelab-household-redaction');

const baseValue = process.env.HADES_DOM_BASE_URL;
if (!baseValue) throw new Error('HADES_DOM_BASE_URL is required');
const base = new URL(baseValue);
if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password || base.search || base.hash) {
  throw new Error('HADES_DOM_BASE_URL must be a plain HTTP(S) origin/path without embedded credentials or query');
}
if (!['127.0.0.1', 'localhost', '[::1]'].includes(base.hostname)) {
  throw new Error('HADES_DOM_BASE_URL must use a loopback-only SSH tunnel');
}
if (!base.pathname.endsWith('/')) base.pathname += '/';

const credentialDir = path.resolve(process.env.HADES_DOM_CREDENTIAL_DIR || path.join(os.homedir(), '.config', 'hades-dom'));
const waitMs = Math.max(30000, Math.min(Number(process.env.HADES_HOMELAB_TURN_TIMEOUT_MS || 120000), 240000));
const users = [
  { id: 'owner', email: 'acceptance-owner-email', password: 'acceptance-owner-password', prompts: [
    'Is everything okay with the homelab?',
    "What's the deep inference node doing right now?",
    'Are my backups current?',
    'Why does the network feel slow?',
  ] },
  { id: 'householdA', email: 'household-a-email', password: 'household-a-password', prompts: [
    'Are all the computers okay?',
    'Is the game server working?',
  ] },
  { id: 'householdB', email: 'household-b-email', password: 'household-b-password', prompts: [
    'Why is everything slow?',
    'Can we use the AI thing right now?',
  ] },
];
const requestedUser = process.env.HADES_HOMELAB_USER_FILTER || '';
const requestedPrompt = process.env.HADES_HOMELAB_PROMPT_FILTER || '';
if (requestedUser && !users.some(user => user.id === requestedUser)) {
  throw new Error('HADES_HOMELAB_USER_FILTER must be owner, householdA, or householdB');
}
if (requestedPrompt && !users.some(user => user.prompts.includes(requestedPrompt))) {
  throw new Error('HADES_HOMELAB_PROMPT_FILTER must exactly match a bounded built-in prompt');
}
const selectedUsers = users.filter(user => !requestedUser || user.id === requestedUser)
  .map(user => ({ ...user, prompts: user.prompts.filter(prompt => !requestedPrompt || prompt === requestedPrompt) }));
const expectedTurns = selectedUsers.reduce((count, user) => count + user.prompts.length, 0);

const privateLabelsFile = process.env.HADES_HOMELAB_PRIVATE_LABELS_FILE;
if (!privateLabelsFile) throw new Error('HADES_HOMELAB_PRIVATE_LABELS_FILE is required');
const labelsPath = path.resolve(privateLabelsFile);
const labelsStat = fs.lstatSync(labelsPath);
if (!labelsStat.isFile() || labelsStat.isSymbolicLink() || (labelsStat.mode & 0o077) !== 0) {
  throw new Error('private-label input must be a regular mode-0600-or-stricter file');
}
const labelsRealPath = fs.realpathSync(labelsPath);
const repoRealPath = fs.realpathSync(path.resolve(__dirname, '..')) + path.sep;
if (labelsRealPath.startsWith(repoRealPath)) throw new Error('private-label input must stay outside the repository');
const configuredPrivateLabels = fs.readFileSync(labelsRealPath, 'utf8')
  .split(/\r?\n/).map(value => value.trim()).filter(value => value && !value.startsWith('#'));
if (!configuredPrivateLabels.length || configuredPrivateLabels.some(value => value.length < 3)) {
  throw new Error('private-label input must contain the complete private labels, one per line');
}
const privateLabelPatterns = createPrivateLabelPatterns(configuredPrivateLabels);
function readSecret(name) {
  const filename = path.join(credentialDir, name);
  const stat = fs.lstatSync(filename);
  if (!stat.isFile() || stat.isSymbolicLink() || (stat.mode & 0o077) !== 0) {
    throw new Error(`credential file permissions are not private: ${name}`);
  }
  const value = fs.readFileSync(filename, 'utf8').trim();
  if (!value) throw new Error(`credential file is empty: ${name}`);
  return value;
}
function digest(value) { return crypto.createHash('sha256').update(value).digest('hex'); }
function leakDetected(text) { return containsPrivateTopology(text, privateLabelPatterns); }
if (!validatePrivateLabelDetectors(configuredPrivateLabels, privateLabelPatterns)) {
  throw new Error('private-label detector positive-control self-test failed');
}
async function authenticate(context, user) {
  const response = await fetch(new URL('api/v1/auths/ldap', base), {
    method: 'POST',
    redirect: 'error',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ user: readSecret(user.email), password: readSecret(user.password) }),
  });
  if (!response.ok) throw new Error(`${user.id} login failed with HTTP ${response.status}`);
  const body = await response.json();
  if (typeof body.token !== 'string' || !body.token) throw new Error(`${user.id} login response did not include a session token`);
  await context.addCookies([{ name: 'token', value: body.token, url: base.origin }]);
  return body.token;
}

async function sendTurn(page, prompt) {
  const messages = page.locator('#response-content-container .markdown-prose');
  const oldCount = await messages.count();
  const box = page.locator('#chat-input');
  await box.fill(prompt);
  const submit = page.locator('button[type="submit"]:visible');
  if (await submit.count()) await submit.last().click();
  else await box.press('Enter');

  const deadline = Date.now() + waitMs;
  let answer = '';
  while (Date.now() < deadline) {
    const current = page.locator('#response-content-container .markdown-prose');
    const count = await current.count();
    if (count > oldCount) {
      const stopVisible = await page.locator('#message-input-container button[aria-label="Stop"]:visible').count();
      const candidate = (await current.last().innerText()).trim();
      if (candidate && !stopVisible) {
        await page.waitForTimeout(900);
        answer = (await current.last().innerText()).trim();
        if (answer) return answer;
      }
    }
    await page.waitForTimeout(300);
  }
  throw new Error('turn did not settle before the bounded timeout; response omitted');
}

async function persisted(page, token, prompt, answer) {
  const tokens = value => String(value || '').toLowerCase().match(/[a-z0-9]+/g) || [];
  const tokenSimilarity = (left, right) => {
    const a = tokens(left);
    const b = tokens(right);
    if (!a.length || !b.length) return 0;
    let previous = Array.from({ length: b.length + 1 }, (_, index) => index);
    for (let i = 1; i <= a.length; i++) {
      const current = [i];
      for (let j = 1; j <= b.length; j++) {
        current[j] = Math.min(
          current[j - 1] + 1,
          previous[j] + 1,
          previous[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1),
        );
      }
      previous = current;
    }
    return 1 - previous[b.length] / Math.max(a.length, b.length);
  };
  const promptTokens = tokens(prompt);
  const collectStrings = (value, rows) => {
    if (typeof value === 'string') { rows.push(value); return; }
    if (Array.isArray(value)) { for (const child of value) collectStrings(child, rows); return; }
    if (value && typeof value === 'object') {
      for (const child of Object.values(value)) collectStrings(child, rows);
    }
  };
  const chatId = new URL(page.url()).pathname.match(/\/c\/([^/]+)/)?.[1];
  if (!chatId) return false;
  const deadline = Date.now() + 12000;
  while (Date.now() < deadline) {
    const detail = await fetch(new URL(`api/v1/chats/${encodeURIComponent(chatId)}`, base), {
      headers: { authorization: `Bearer ${token}` },
    });
    if (detail.ok) {
      const history = await detail.json();
      const messages = Object.values(history.chat?.history?.messages || history.history?.messages || {});
      let latestUserIndex = -1;
      for (let index = 0; index < messages.length; index++) {
        if (messages[index]?.role === 'user') latestUserIndex = index;
      }
      if (latestUserIndex < 0) continue;
      const userParts = [];
      collectStrings(messages[latestUserIndex].content, userParts);
      if (tokens(userParts.join(' ')).join(' ') !== promptTokens.join(' ')) continue;
      for (let next = latestUserIndex + 1; next < messages.length && messages[next]?.role !== 'user'; next++) {
        if (messages[next]?.role !== 'assistant') continue;
        const answerParts = [];
        collectStrings(messages[next].content, answerParts);
        if (tokenSimilarity(answer, answerParts.join(' ')) >= 0.98) return true;
      }
    }
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  return false;
}

function safeReportPath() {
  const filename = path.resolve(process.env.HADES_HOMELAB_REPORT ||
    path.join(os.tmpdir(), `hades-homelab-readonly-${new Date().toISOString().replace(/[:.]/g, '-')}.json`));
  const parent = fs.realpathSync(path.dirname(filename));
  const canonicalRepo = fs.realpathSync(path.resolve(__dirname, '..')) + path.sep;
  const canonicalFilename = path.join(parent, path.basename(filename));
  const parentMode = fs.statSync(parent).mode;
  if (canonicalFilename.startsWith(canonicalRepo)) throw new Error('acceptance report must be outside the repository');
  if ((parentMode & 0o022) !== 0 && (parentMode & 0o1000) === 0) {
    throw new Error('report parent must not be group/world-writable without sticky-bit protection');
  }
  return canonicalFilename;
}

async function main() {
  const reportPath = safeReportPath();
  const report = { started_at: new Date().toISOString(), base_origin: base.origin, users: {}, errors: [] };
  const browser = await chromium.launch({ headless: true });
  try {
    for (const user of selectedUsers) {
      const context = await browser.newContext({ ignoreHTTPSErrors: false, viewport: { width: 1280, height: 900 } });
      try {
        const token = await authenticate(context, user);
        const entry = { turns: [] };
        report.users[user.id] = entry;
        for (const prompt of user.prompts) {
          const page = await context.newPage();
          await page.goto(base.href, { waitUntil: 'domcontentloaded', timeout: 30000 });
          await page.waitForSelector('#chat-input', { timeout: 30000 });
          const answer = await sendTurn(page, prompt);
          const turn = {
            prompt,
            answer,
            answer_sha256: digest(answer),
            characters: answer.length,
            persisted: await persisted(page, token, prompt, answer),
            private_topology_leak: user.id === 'owner' ? false : leakDetected(answer),
          };
          entry.turns.push(turn);
          await page.close();
        }
      } catch (error) {
        report.errors.push({ user: user.id, error: String(error.message || error) });
      } finally {
        await context.close();
      }
    }
  } finally {
    await browser.close();
    report.finished_at = new Date().toISOString();
    const fd = fs.openSync(reportPath, 'wx', 0o600);
    try {
      fs.writeFileSync(fd, `${JSON.stringify(report, null, 2)}\n`);
      fs.fchmodSync(fd, 0o600);
    } finally { fs.closeSync(fd); }
    const turns = Object.values(report.users).flatMap(user => user.turns || []);
    const leaks = turns.filter(turn => turn.private_topology_leak).length;
    const unpersisted = turns.filter(turn => !turn.persisted).length;
    console.log(JSON.stringify({
      result: report.errors.length || leaks || unpersisted || turns.length !== expectedTurns ? 'FAIL' : 'PASS',
      expected_turns: expectedTurns,
      authenticated_users: Object.keys(report.users),
      turns: turns.length,
      persisted: turns.length - unpersisted,
      household_topology_leaks: leaks,
      errors: report.errors.length,
      protected_report: reportPath,
    }));
    if (report.errors.length || leaks || unpersisted || turns.length !== expectedTurns) process.exitCode = 1;
  }
}

main().catch(error => {
  console.error(`FAIL ${String(error.message || error)}`);
  process.exitCode = 1;
});
