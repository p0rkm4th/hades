"""Strict CSV-to-Actual import preview.

This module does not connect to Actual and does not maintain a second ledger.
It turns a local file into an explicit preview that a future adapter can pass
to Actual's own reconciliation/import API after owner confirmation.
"""

from __future__ import annotations

import csv
import hashlib
import io
from decimal import Decimal, InvalidOperation
from typing import Any


class ImportFormatError(ValueError):
    pass


def _required(mapping: dict[str, str], key: str) -> str:
    value = mapping.get(key, "").strip()
    if not value:
        raise ImportFormatError(f"mapping must specify {key}")
    return value


def _money(value: str, row_number: int) -> str:
    text = value.strip().replace(",", "")
    if not text:
        raise ImportFormatError(f"row {row_number}: amount is empty")
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise ImportFormatError(f"row {row_number}: amount is invalid") from exc
    if not amount.is_finite() or amount == 0:
        raise ImportFormatError(f"row {row_number}: amount must be finite and non-zero")
    return format(amount.quantize(Decimal("0.01")), "f")


def _amount(row: dict[str, str], mapping: dict[str, str], row_number: int) -> str:
    amount_column = mapping.get("amount", "").strip()
    if amount_column:
        return _money(row.get(amount_column, ""), row_number)
    inflow_column = _required(mapping, "inflow")
    outflow_column = _required(mapping, "outflow")
    inflow = row.get(inflow_column, "").strip().replace(",", "")
    outflow = row.get(outflow_column, "").strip().replace(",", "")
    if bool(inflow) == bool(outflow):
        raise ImportFormatError(
            f"row {row_number}: exactly one of inflow or outflow must be populated"
        )
    return _money(inflow or f"-{outflow}", row_number)


def build_preview(
    file_bytes: bytes,
    mapping: dict[str, str],
    *,
    existing_transactions: list[dict[str, Any]] | None = None,
    delimiter: str = ",",
    encoding: str = "utf-8-sig",
) -> dict[str, Any]:
    """Return a deterministic preview; never writes to Actual.

    ``mapping`` must explicitly name ``date`` and ``payee`` plus either
    ``amount`` or both ``inflow`` and ``outflow``. Dates are intentionally
    left as source strings until the caller selects a known format for Actual.
    """
    if not file_bytes:
        raise ImportFormatError("CSV file is empty")
    if len(file_bytes) > 10 * 1024 * 1024:
        raise ImportFormatError("CSV file exceeds the 10 MiB preview limit")
    if len(delimiter) != 1:
        raise ImportFormatError("delimiter must be one character")
    date_column = _required(mapping, "date")
    payee_column = _required(mapping, "payee")
    if not mapping.get("amount", "").strip() and not (
        mapping.get("inflow", "").strip() and mapping.get("outflow", "").strip()
    ):
        raise ImportFormatError("mapping must specify amount or inflow and outflow")
    try:
        text = file_bytes.decode(encoding)
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ImportFormatError("CSV cannot be decoded or parsed") from exc
    if not reader.fieldnames or any(not field for field in reader.fieldnames):
        raise ImportFormatError("CSV must contain named columns")
    missing = {
        column
        for column in (
            date_column,
            payee_column,
            mapping.get("amount", "").strip(),
            mapping.get("inflow", "").strip(),
            mapping.get("outflow", "").strip(),
        )
        if column and column not in reader.fieldnames
    }
    if missing:
        raise ImportFormatError(f"CSV mapping names missing columns: {sorted(missing)}")

    digest = hashlib.sha256(file_bytes).hexdigest()
    existing = existing_transactions or []
    existing_ids = {str(row.get("imported_id")) for row in existing if row.get("imported_id")}
    existing_signatures = {
        (str(row.get("date", "")), str(row.get("amount", "")), str(row.get("payee", "")).casefold())
        for row in existing
    }
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row_number, row in enumerate(reader, start=2):
        date = row.get(date_column, "").strip()
        payee = row.get(payee_column, "").strip()
        if not date or not payee:
            raise ImportFormatError(f"row {row_number}: date and payee are required")
        amount = _amount(row, mapping, row_number)
        imported_id = hashlib.sha256(
            f"{digest}:{row_number}:{date}:{payee}:{amount}".encode()
        ).hexdigest()
        signature = (date, amount, payee.casefold())
        duplicate = imported_id in existing_ids or signature in existing_signatures
        if imported_id in seen_ids:
            raise ImportFormatError(f"row {row_number}: duplicate row identity")
        seen_ids.add(imported_id)
        rows.append(
            {
                "date": date,
                "payee": payee,
                "amount": amount,
                "imported_id": imported_id,
                "disposition": "DUPLICATE" if duplicate else "NEW",
                "source_row": row_number,
            }
        )
    if not rows:
        raise ImportFormatError("CSV contains no transactions")
    return {
        "status": "PREVIEW",
        "source": "local-csv",
        "file_sha256": digest,
        "transaction_count": len(rows),
        "new_count": sum(row["disposition"] == "NEW" for row in rows),
        "duplicate_count": sum(row["disposition"] == "DUPLICATE" for row in rows),
        "transactions": rows,
        "requires_confirmation": True,
        "writes_performed": False,
        "canonical_target": "Actual Budget importTransactions",
    }

