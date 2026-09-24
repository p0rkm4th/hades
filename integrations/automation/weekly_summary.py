"""Per-domain authorization and partial-failure composition for summaries."""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from pathlib import Path
from typing import Callable, Mapping
import json


@dataclass(frozen=True)
class SummarySection:
    key: str
    title: str
    text: str | None
    available: bool
    reason: str = ""


def compose_summary(sections: Mapping[str, tuple[str, Callable[[], str]]], authorize: Callable[[str], bool]) -> str:
    """Evaluate each source after its own authorization check.

    A source failure becomes an unavailable section; it cannot erase healthy
    authorized sections or turn an empty response into a success claim.
    """
    rendered: list[str] = ["Household summary", ""]
    unavailable: list[str] = []
    for key, (title, reader) in sections.items():
        if not authorize(key):
            continue
        try:
            text = reader()
        except Exception:  # source failure must remain local to this section
            text = ""
        if text:
            rendered.extend([f"{title}:", text, ""])
        else:
            unavailable.append(title)
    if unavailable:
        rendered.append("Unavailable this week: " + ", ".join(unavailable) + ".")
    return "\n".join(rendered).rstrip()


class SummaryHistory:
    """Bounded history for explaining the last summary, not a household DB."""

    def __init__(self, state_file: str, limit: int = 12):
        self.path = Path(state_file)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.limit = max(1, min(limit, 52))
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS weekly_summary_history (summary_id INTEGER PRIMARY KEY AUTOINCREMENT, recipient TEXT NOT NULL, ran_at TEXT NOT NULL, text TEXT NOT NULL, omitted TEXT NOT NULL)")
        self.path.chmod(0o600)

    def record(self, recipient: str, ran_at: str, text: str, omitted: str = "") -> None:
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO weekly_summary_history(recipient,ran_at,text,omitted) VALUES(?,?,?,?)", (recipient, ran_at, text, omitted))
            db.execute("DELETE FROM weekly_summary_history WHERE summary_id NOT IN (SELECT summary_id FROM weekly_summary_history ORDER BY summary_id DESC LIMIT ?)", (self.limit,))

    def latest(self, recipient: str) -> dict[str, str] | None:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT ran_at, text, omitted FROM weekly_summary_history WHERE recipient = ? ORDER BY summary_id DESC LIMIT 1", (recipient,)).fetchone()
        return {"ran_at": row[0], "text": row[1], "omitted": row[2]} if row else None


def build_n8n_workflow(automation_id: str, *, template_path: str | None = None) -> dict[str, object]:
    """Instantiate the fixed three-source collection graph."""
    path = Path(template_path) if template_path else Path(__file__).resolve().parents[2] / "config" / "epsilon-workflows" / "weekly-household-summary-n8n.json"
    workflow = json.loads(path.read_text(encoding="utf-8"))
    if workflow.get("id") != "weekly-household-summary":
        raise ValueError("typed weekly workflow template is invalid")
    workflow["id"] = automation_id
    workflow["active"] = False
    workflow["tags"] = [{"name": "hades-template:weekly"}, {"name": "hades-owner:owner"}, {"name": "hades-approved:true"}, {"name": "hades-trigger:schedule"}]
    for node in workflow.get("nodes", []):
        if node.get("name") == "HADES-local run-now trigger":
            node.setdefault("parameters", {})["path"] = automation_id
            node["webhookId"] = automation_id
    return workflow
