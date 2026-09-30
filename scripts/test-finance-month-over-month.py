#!/usr/bin/env python3
"""Synthetic read-only coverage for ordinary month-over-month spending questions."""
from __future__ import annotations

import importlib.util
import calendar
import os
from datetime import date
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hades_finance_monthly", ROOT / "hermes/sitecustomize.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

today = date.today()
previous_year, previous_month = ((today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1))
current_early = today.replace(day=min(5, today.day))
current_late = today.replace(day=min(15, today.day))
previous_early = date(previous_year, previous_month, min(5, current_late.day))
previous_late = date(previous_year, previous_month, min(15, current_late.day))

with tempfile.TemporaryDirectory(prefix="hades-finance-monthly-") as temporary:
    path = Path(temporary) / "statement.csv"
    path.write_text(
        "Date,Description,Amount,Category,Status\n"
        f"{previous_early},Food Market,-80.00,Groceries,Posted\n"
        f"{previous_late},Town Cafe,-20.00,Restaurants,Posted\n"
        f"{previous_late},Power Company,-100.00,Utilities,Posted\n"
        f"{current_early},Food Market,-120.00,Groceries,Posted\n"
        f"{current_late},Town Cafe,-80.00,Restaurants,Pending\n"
        f"{current_late},Power Company,-100.00,Utilities,Posted\n"
        f"{current_late},Paycheck,2500.00,Income,Posted\n",
        encoding="utf-8",
    )
    os.environ["HADES_FINANCE_CSV_PATH"] = str(path)
    result = module._hades_direct_finance_guidance("Why was spending higher this month?")
    for expected in (
        "CSV finance comparison (owner-only, read-only)",
        "$100.00 higher",
        "$300.00 across 3 expense rows",
        "$200.00",
        "Restaurants $60.00",
        "Groceries $40.00",
        "not why it happened",
        "matching calendar days",
        "1 this month and 0 last month",
        "Historical statement data only",
    ):
        assert expected in result, result
    assert "$2,500.00" not in result, "income must not be included in expenses"
    assert str(path) not in result, "synthetic statement path leaked"

    # Old exports must not be relabeled as this month's activity.
    path.write_text(
        "Date,Description,Amount,Category,Status\n"
        f"{previous_early},Food Market,-80.00,Groceries,Posted\n"
        f"{previous_late},Town Cafe,-20.00,Restaurants,Posted\n",
        encoding="utf-8",
    )
    result = module._hades_direct_finance_guidance("What changed in my spending this month?")
    assert "can't compare this month with last month" in result, result
    assert "won't treat older statement months as current spending" in result, result
    assert "Spending is" not in result, result

    # A current-month export without the immediately preceding month cannot
    # fabricate a comparison from a non-adjacent period.
    path.write_text(
        "Date,Description,Amount,Category,Status\n"
        f"{current_late},Food Market,-80.00,Groceries,Posted\n",
        encoding="utf-8",
    )
    result = module._hades_direct_finance_guidance("How did my spending change month over month?")
    assert "transactions during" in result and "to compare" in result, result
    assert "Spending is" not in result, result

    after_window_day = min(current_late.day + 1, calendar.monthrange(previous_year, previous_month)[1])
    after_window = date(previous_year, previous_month, after_window_day)
    path.write_text(
        "Date,Description,Amount,Category,Status\n"
        f"{after_window},Food Market,-80.00,Groceries,Posted\n"
        f"{current_late},Food Market,-80.00,Groceries,Posted\n",
        encoding="utf-8",
    )
    result = module._hades_direct_finance_guidance("How did my spending change month over month?")
    assert "transactions during" in result and "to compare" in result, result
    assert "Spending is" not in result, result

    path.write_text(
        "Date,Description,Amount,Category,Status\n"
        f"{previous_early},Paycheck,2500.00,Income,Posted\n"
        f"{current_late},Food Market,-80.00,Groceries,Posted\n",
        encoding="utf-8",
    )
    result = module._hades_direct_finance_guidance("Why was spending higher this month?")
    assert "no expense rows" in result and "to compare" in result, result
    assert "Spending is" not in result, result

    path.write_text(
        "Date,Description,Amount,Category,Status\n"
        f"{previous_early},Food Market,-80.00,Groceries,Posted\n"
        f"{current_late},Paycheck,2500.00,Income,Posted\n",
        encoding="utf-8",
    )
    result = module._hades_direct_finance_guidance("Why was spending higher this month?")
    assert "no expense rows to compare" in result, result
    assert "Spending is" not in result, result

print("PASS owner-only finance comparison explains month-to-date changes from synthetic statement rows")
print("PASS stale exports and missing expense baselines do not produce a guessed comparison")
