/* Read-only bridge around the official @actual-app/api package. */
const fs = require("fs");
const path = require("path");
const MAX_SECRET_BYTES = 8192;

const modulePath = process.env.ACTUAL_API_MODULE;
if (!modulePath) throw new Error("ACTUAL_API_MODULE is not configured");
const api = require(modulePath);

function readSecret() {
  if (process.env.ACTUAL_PASSWORD_FILE) {
    const secretPath = process.env.ACTUAL_PASSWORD_FILE;
    const stat = fs.lstatSync(secretPath);
    if (!stat.isFile() || stat.isSymbolicLink()) {
      throw new Error("Actual password file must be a regular non-symlink file");
    }
    const mode = stat.mode & 0o777;
    if (mode !== 0o600 && mode !== 0o640) {
      throw new Error("Actual password file must be mode 0600 or 0640");
    }
    const raw = fs.readFileSync(secretPath);
    if (raw.length === 0 || raw.length > MAX_SECRET_BYTES) {
      throw new Error("Actual password file is empty or exceeds the bounded size");
    }
    return raw.toString("utf8").trim();
  }
  return process.env.ACTUAL_PASSWORD || "";
}

function configuredRoot() {
  return process.env.ACTUAL_DATA_DIR || path.join(process.cwd(), ".actual-readonly");
}

function localBudget(root, groupId) {
  if (!fs.existsSync(root)) return null;
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const metadataPath = path.join(root, entry.name, "metadata.json");
    if (!fs.existsSync(metadataPath)) continue;
    try {
      const metadata = JSON.parse(fs.readFileSync(metadataPath, "utf8"));
      if (metadata.groupId === groupId) return { id: entry.name, metadata };
    } catch (_) {
      // Ignore incomplete cache entries and let the caller re-download.
    }
  }
  return null;
}

function freshnessMetadata(local) {
  const lastSynced = local.metadata.lastSyncedTimestamp || null;
  let syncedMs = Number.NaN;
  if (typeof lastSynced === "number") {
    syncedMs = lastSynced < 1e12 ? lastSynced * 1000 : lastSynced;
  } else if (typeof lastSynced === "string" && lastSynced.trim()) {
    syncedMs = Date.parse(lastSynced);
  }
  return {
    retrieved_at: new Date().toISOString(),
    last_synced: lastSynced,
    freshness_seconds: Number.isFinite(syncedMs)
      ? Math.max(0, Math.floor((Date.now() - syncedMs) / 1000))
      : null,
    freshness_known: Number.isFinite(syncedMs),
  };
}

async function main(request) {
  const root = configuredRoot();
  fs.mkdirSync(root, { recursive: true });
  await api.init({
    dataDir: root,
    serverURL: (process.env.ACTUAL_SERVER_URL || "http://127.0.0.1:5006").replace(/\/+$/, ""),
    password: readSecret(),
    verbose: false,
  });
  try {
    const budgets = await api.getBudgets();
    const requestedGroup = process.env.ACTUAL_BUDGET_GROUP_ID || "";
    const requestedName = process.env.ACTUAL_BUDGET_NAME || "";
    if (!requestedGroup && !requestedName) {
      return { ok: false, error: "An explicit Actual Budget selection is required." };
    }
    const budget = budgets.find((item) =>
      (requestedGroup && item.groupId === requestedGroup) ||
      (requestedName && item.name === requestedName)
    );
    if (!budget) return { ok: false, error: "No Actual Budget is available." };

    let local = localBudget(root, budget.groupId);
    if (!local) {
      await api.downloadBudget(budget.groupId);
      local = localBudget(root, budget.groupId);
    }
    if (!local) return { ok: false, error: "Actual Budget could not be cached locally." };
    await api.loadBudget(local.id);

    const serverVersion = await api.getServerVersion();
    const metadata = {
      source: "Actual Budget canonical",
      budget: budget.name,
      group_id: budget.groupId,
      server_version: serverVersion.version || serverVersion.error,
      ...freshnessMetadata(local),
      read_only: true,
    };
    if (!metadata.freshness_known) {
      return {
        ok: false,
        error: "Actual Budget freshness is unknown; live finance data is unavailable.",
        ...metadata,
      };
    }
    if (request.action === "status") {
      return {
        ok: true,
        ...metadata,
        coverage: ["budget", "server_status", "sync_freshness"],
      };
    }
    if (request.action === "accounts") {
      const accounts = await api.getAccounts();
      const withBalances = [];
      for (const item of accounts) {
        withBalances.push({
          id: item.id,
          name: item.name,
          balance_cents: await api.getAccountBalance(item.id),
          off_budget: item.offbudget,
          closed: item.closed,
        });
      }
      return {
        ok: true,
        ...metadata,
        coverage: ["accounts", "account_balances"],
        account_count: withBalances.length,
        accounts: withBalances.map((item) => ({
          ...item,
          balance: item.balance_cents / 100,
        })),
        read_only: true,
      };
    }
    if (request.action === "transactions") {
      const accounts = await api.getAccounts();
      const payees = new Map((await api.getPayees()).map((item) => [item.id, item.name]));
      const selected = request.account
        ? accounts.filter((item) => item.name === request.account || item.id === request.account)
        : accounts;
      const transactions = [];
      for (const account of selected) {
        const rows = await api.getTransactions(account.id, request.startDate, request.endDate);
        for (const row of rows) transactions.push({
          id: row.id,
          account: account.name,
          date: row.date,
          payee: row.payee_name || payees.get(row.payee) || row.payee || null,
          amount_cents: row.amount,
          amount: row.amount / 100,
          notes: row.notes || null,
          imported_id: row.imported_id || null,
          transfer_id: row.transfer_id || null,
        });
      }
      transactions.sort((a, b) => a.date.localeCompare(b.date) || a.id.localeCompare(b.id));
      const requestedLimit = Math.max(1, Number(request.limit) || 100);
      return {
        ok: true,
        ...metadata,
        coverage: ["transactions"],
        date_range: { start: request.startDate, end: request.endDate },
        account_filter: request.account || null,
        total_matching: transactions.length,
        returned_count: Math.min(transactions.length, requestedLimit),
        pagination_complete: transactions.length <= requestedLimit,
        transactions: transactions.slice(0, requestedLimit),
        read_only: true,
      };
    }
    return { ok: false, error: "Unsupported read action." };
  } finally {
    await api.shutdown();
  }
}

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => { input += chunk; });
process.stdin.on("end", async () => {
  try {
    process.stdout.write(JSON.stringify(await main(JSON.parse(input))));
  } catch (error) {
    process.stderr.write(String(error?.message || error));
    process.exitCode = 1;
  }
});
