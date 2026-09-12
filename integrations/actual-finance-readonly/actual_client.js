/* Read-only bridge around the official @actual-app/api package. */
const fs = require("fs");
const path = require("path");

const modulePath = process.env.ACTUAL_API_MODULE;
if (!modulePath) throw new Error("ACTUAL_API_MODULE is not configured");
const api = require(modulePath);

function readSecret() {
  if (process.env.ACTUAL_PASSWORD_FILE) {
    return fs.readFileSync(process.env.ACTUAL_PASSWORD_FILE, "utf8").trim();
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
    const budget = budgets.find((item) =>
      (requestedGroup && item.groupId === requestedGroup) ||
      (requestedName && item.name === requestedName)
    ) || budgets[0];
    if (!budget) return { ok: false, error: "No Actual Budget is available." };

    let local = localBudget(root, budget.groupId);
    if (!local) {
      await api.downloadBudget(budget.groupId);
      local = localBudget(root, budget.groupId);
    }
    if (!local) return { ok: false, error: "Actual Budget could not be cached locally." };
    await api.loadBudget(local.id);

    const serverVersion = await api.getServerVersion();
    if (request.action === "status") {
      return {
        ok: true,
        budget: budget.name,
        group_id: budget.groupId,
        server_version: serverVersion.version || serverVersion.error,
        last_synced: local.metadata.lastSyncedTimestamp || null,
        read_only: true,
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
        budget: budget.name,
        server_version: serverVersion.version || serverVersion.error,
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
          amount: row.amount,
          payee: row.payee_name || payees.get(row.payee) || row.payee || null,
          amount_cents: row.amount,
          amount: row.amount / 100,
          notes: row.notes || null,
          imported_id: row.imported_id || null,
          transfer_id: row.transfer_id || null,
        });
      }
      transactions.sort((a, b) => a.date.localeCompare(b.date) || a.id.localeCompare(b.id));
      return {
        ok: true,
        budget: budget.name,
        server_version: serverVersion.version || serverVersion.error,
        transactions: transactions.slice(0, Math.max(1, Number(request.limit) || 100)),
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
