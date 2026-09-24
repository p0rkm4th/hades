"""Current-state, read-only Grocy summary semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
import json
import hashlib
import sqlite3
from pathlib import Path
import urllib.error
import urllib.request


@dataclass(frozen=True)
class InventoryObservation:
    state: str
    low: tuple[str, ...] = ()
    out: tuple[str, ...] = ()
    no_minimum: tuple[str, ...] = ()
    reason: str = ""


def summarize_grocy(rows: Sequence[Mapping[str, Any]]) -> InventoryObservation:
    """Use Grocy's returned stock/minimum fields; never guess from names."""
    low: list[str] = []
    out: list[str] = []
    no_minimum: list[str] = []
    for row in rows:
        product = row.get("product") if isinstance(row.get("product"), Mapping) else {}
        name = str(product.get("name") or row.get("product_id") or row.get("name") or "").strip()
        if not name:
            continue
        amount = row.get("amount_aggregated", row.get("amount"))
        minimum = row.get(
            "amount_aggregated_min_stock",
            row.get("min_stock_amount", row.get("minimum", product.get("min_stock_amount"))),
        )
        try:
            if amount is None:
                continue
            if float(amount) <= 0:
                out.append(name)
            elif minimum is None:
                no_minimum.append(name)
            elif float(amount) < float(minimum):
                low.append(name)
        except (TypeError, ValueError):
            continue
    return InventoryObservation("READY", tuple(low), tuple(out), tuple(no_minimum))


def render_summary(observation: InventoryObservation) -> str:
    if observation.state != "READY":
        return "I couldn't read the household inventory right now; no stock conclusion was made."
    lines = ["You're low on:"]
    lines.extend(f"- {item}" for item in observation.low)
    if not observation.low:
        lines.append("- Nothing below Grocy's minimum-stock rule")
    if observation.no_minimum:
        lines.append("")
        lines.append("No minimum configured: " + ", ".join(observation.no_minimum) + ".")
    if observation.out:
        lines.append("")
        lines.append("Out of stock: " + ", ".join(observation.out) + ".")
    return "\n".join(lines)


class GrocyReadUnavailable(RuntimeError):
    """The canonical Grocy source could not be read."""


def read_current_grocy_stock(base_url: str, api_key: str, *, timeout: float = 5.0) -> InventoryObservation:
    """Read only Grocy's current stock endpoint; URL is deployment-owned."""
    if not base_url or not api_key:
        raise GrocyReadUnavailable("Grocy credentials are unavailable")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/stock",
        headers={"GROCY-API-KEY": api_key, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            rows = json.loads(response.read())
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise GrocyReadUnavailable("Grocy source is unavailable") from exc
    if not isinstance(rows, list):
        raise GrocyReadUnavailable("Grocy returned no canonical stock list")
    return summarize_grocy(rows)


class InventorySummaryService:
    """Retains only the last bounded result hash and notification decision."""

    def __init__(self, state_file: str, automation_id: str, owner: str):
        if not automation_id or not owner:
            raise ValueError("inventory summary identity is required")
        self.path = Path(state_file)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.automation_id = automation_id
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS inventory_summary_state (automation_id TEXT PRIMARY KEY, result_hash TEXT NOT NULL, rendered TEXT NOT NULL, state TEXT NOT NULL, observed_at TEXT NOT NULL, notifications INTEGER NOT NULL DEFAULT 0)")
        self.path.chmod(0o600)

    def record(self, observation: InventoryObservation, rendered: str, observed_at: str) -> dict[str, object]:
        result_hash = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
        with sqlite3.connect(self.path) as db:
            old = db.execute("SELECT result_hash, notifications FROM inventory_summary_state WHERE automation_id = ?", (self.automation_id,)).fetchone()
            changed = old is None or old[0] != result_hash
            count = (old[1] if old else 0) + (1 if changed else 0)
            db.execute("INSERT INTO inventory_summary_state(automation_id,result_hash,rendered,state,observed_at,notifications) VALUES(?,?,?,?,?,?) ON CONFLICT(automation_id) DO UPDATE SET result_hash=excluded.result_hash, rendered=excluded.rendered, state=excluded.state, observed_at=excluded.observed_at, notifications=excluded.notifications", (self.automation_id, result_hash, rendered, observation.state, observed_at, count))
        return {"state": observation.state, "changed": changed, "notify": changed, "notifications": count}


def build_n8n_workflow(automation_id: str, interval_days: int = 7, *, template_path: str | None = None) -> dict[str, Any]:
    """Instantiate the fixed Grocy read graph; its source is never caller-controlled."""
    if not 1 <= interval_days <= 14:
        raise ValueError("inventory schedule is outside the bounded interval")
    path = Path(template_path) if template_path else Path(__file__).resolve().parents[2] / "config" / "epsilon-workflows" / "low-inventory-n8n.json"
    try:
        workflow = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("typed inventory workflow template is unavailable") from exc
    if workflow.get("id") != "low-inventory-summary":
        raise ValueError("typed inventory workflow template is invalid")
    workflow["id"] = automation_id
    workflow["active"] = False
    workflow["tags"] = [{"name": "hades-template:inv"}, {"name": "hades-owner:owner"}, {"name": "hades-approved:true"}, {"name": "hades-trigger:schedule"}]
    for node in workflow.get("nodes", []):
        if node.get("name") == "HADES-local run-now trigger":
            node.setdefault("parameters", {})["path"] = automation_id
            node["webhookId"] = automation_id
        if node.get("name") == "Bounded weekly schedule":
            node.setdefault("parameters", {}).setdefault("rule", {}).setdefault("interval", [{}])[0]["daysInterval"] = interval_days
    return workflow
