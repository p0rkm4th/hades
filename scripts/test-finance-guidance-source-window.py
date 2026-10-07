#!/usr/bin/env python3
"""Keep local finance answers explicit about statement coverage and source age."""
from __future__ import annotations

import importlib.util
import os
from datetime import datetime, timezone
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hades_finance_window", ROOT / "hermes/sitecustomize.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


with tempfile.TemporaryDirectory(prefix="hades-finance-window-") as temporary:
    path = Path(temporary) / "statement.csv"
    path.write_text(
        "Date,Description,Amount,Category,Status\n"
        "2026-01-15,Electric Utility,-90.00,Utilities,Posted\n"
        "2026-09-10,Electric Utility,-45.00,Utilities,Pending\n",
        encoding="utf-8",
    )
    expected_mtime = datetime(2026, 9, 20, 12, 30, tzinfo=timezone.utc).timestamp()
    os.utime(path, (expected_mtime, expected_mtime))
    os.environ["HADES_FINANCE_CSV_PATH"] = str(path)
    assert module._hades_direct_finance_guidance(
        "I'm lactose intolerant. What would be a good coffee order for me?"
    ) is None, "a coffee recommendation must not expose owner finance history"
    assert module._hades_direct_finance_guidance(
        "How much did I spend on coffee?"
    ) is not None, "an explicit coffee-spending question should retain finance support"
    result = module._hades_direct_finance_guidance("How much did I spend on utilities?")
    assert "Statement dates: 2026-01-15 through 2026-09-10" in result, result
    assert "span crosses 9 calendar months; rows appear in 2 months; first month is partial, last month is partial" in result, result
    assert "latest transaction date: 2026-09-10" in result, result
    assert "CSV file last modified: 2026-09-20 12:30 UTC" in result, result
    assert "Simple average across the 2 calendar months with statement rows" in result, result
    assert "partial months are included" in result, result
    assert "1 pending" in result, result
    assert str(path) not in result, "local private path leaked"

    path.write_text(
        "Date,Description,Amount,Category,Status\n"
        "2026-08-01,Electric Utility,-90.00,Utilities,Posted\n"
        "2026-08-31,Electric Utility,-45.00,Utilities,Posted\n",
        encoding="utf-8",
    )
    result = module._hades_direct_finance_guidance("Review this")
    assert "Statement dates: 2026-08-01 through 2026-08-31 (span crosses 1 calendar month; rows appear in 1 month)" in result, result
    assert "first month is partial" not in result, result
    assert "last month is partial" not in result, result
    assert "nothing was imported" in result, result

    path.write_text(
        "Date,Description,Amount,Category,Status\n"
        "2026-01-05,Main Street Market,-100.00,Groceries,Posted\n"
        "2026-01-06,Joe's Coffee,-12.00,Coffee,Posted\n"
        "2026-02-03,Northside Restaurant,-40.00,Restaurants,Posted\n"
        "2026-02-28,Market,-80.00,Grocery,Posted\n",
        encoding="utf-8",
    )
    result = module._hades_direct_finance_guidance(
        "How much am I spending eating out compared with groceries?"
    )
    for expected in (
        "CSV finance comparison (owner-only, read-only)",
        "$52.00 for dining out across 2 transactions",
        "$180.00 for groceries across 2 transactions",
        "$26.00 dining out and $90.00 groceries",
        "0 statement rows are pending",
        "Rows are matched from statement categories/descriptions",
        "not a live balance or forecast",
    ):
        assert expected in result, result
    assert str(path) not in result, "synthetic statement path leaked"

print("PASS finance guidance distinguishes transaction coverage from export-file modification time")
print("PASS partial calendar months and pending rows are explicit without exposing the local file path")
print("PASS ordinary dining-out versus grocery comparison reports matched totals and comparable statement-month averages")
