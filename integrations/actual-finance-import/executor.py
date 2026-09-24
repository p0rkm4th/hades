"""Canonical reconciliation contract for the future authorized Actual writer.

This module contains no Actual client and performs no I/O by itself. The
injected client must expose ``read_imported(account_id, imported_ids)`` and
``import_transactions(account_id, rows, options)``. The latter is the only
write call, and every attempted call is reconciled before an outcome is
reported.
"""

from __future__ import annotations

from typing import Any, Protocol


class ImportRejected(Exception):
    """A definitive pre-write rejection from the canonical client."""


class ActualImportClient(Protocol):
    def read_imported(self, account_id: str, imported_ids: list[str]) -> list[dict[str, Any]]: ...

    def import_transactions(
        self, account_id: str, rows: list[dict[str, Any]], options: dict[str, Any]
    ) -> dict[str, Any]: ...


def _valid_rows(rows: Any) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(rows, list) or not rows:
        raise ValueError("finance import requires a non-empty transaction list")
    normalized: list[dict[str, Any]] = []
    ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("imported_id"), str) or not row["imported_id"].strip():
            raise ValueError("every finance transaction requires a non-empty imported_id")
        if any(key not in row for key in ("date", "payee", "amount")):
            raise ValueError("every finance transaction requires date, payee, and amount")
        imported_id = row["imported_id"].strip()
        if imported_id in ids:
            raise ValueError("duplicate imported_id in one finance request")
        ids.append(imported_id)
        normalized.append(dict(row, imported_id=imported_id))
    return normalized, ids


def _readback(client: ActualImportClient, account_id: str, ids: list[str]) -> tuple[str, list[dict[str, Any]]]:
    try:
        rows = client.read_imported(account_id, ids)
    except Exception:
        return "UNAVAILABLE", []
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        return "MALFORMED", []
    for row in rows:
        row_account = row.get("account_id", row.get("account"))
        if row_account is not None and str(row_account) != account_id:
            return "MISMATCH", rows
    return "OK", rows


def execute_import(client: ActualImportClient, account_id: str, rows: Any) -> dict[str, Any]:
    """Execute one confirmed import and reconcile it through canonical Actual."""
    if not isinstance(account_id, str) or not account_id.strip() or len(account_id.strip()) > 128:
        return {"status": "FAILED", "error": "An explicit bounded Actual account ID is required.", "writes_performed": False}
    account_id = account_id.strip()
    try:
        normalized, ids = _valid_rows(rows)
    except ValueError as exc:
        return {"status": "FAILED", "error": str(exc), "writes_performed": False}

    state, existing = _readback(client, account_id, ids)
    if state != "OK":
        return {"status": "FAILED", "error": "Canonical finance preflight could not verify the target account.", "writes_performed": False}
    existing_ids = {str(row.get("imported_id")) for row in existing}
    pending = [row for row in normalized if row["imported_id"] not in existing_ids]
    if not pending:
        return {
            "status": "NOOP_DUPLICATES", "account_id": account_id, "transactions": [],
            "writes_performed": False, "canonical_source": "Actual Budget",
        }

    attempted = False
    api_result: Any = None
    try:
        attempted = True
        api_result = client.import_transactions(
            account_id, pending, {"reimportDeleted": False, "defaultCleared": False}
        )
    except ImportRejected as exc:
        return {"status": "FAILED", "account_id": account_id, "error": str(exc), "writes_performed": False}
    except Exception:
        api_result = None

    state, reconciled = _readback(client, account_id, [row["imported_id"] for row in pending])
    reconciled_ids = {str(row.get("imported_id")) for row in reconciled}
    complete = all(row["imported_id"] in reconciled_ids for row in pending)
    if complete:
        return {
            "status": "SUCCEEDED", "account_id": account_id,
            "transactions": reconciled, "canonical_source": "Actual Budget",
            "reconciled": True, "writes_performed": attempted,
            "api_result": api_result if isinstance(api_result, dict) else None,
        }
    if isinstance(api_result, dict) and api_result.get("errors") and not api_result.get("added") and not api_result.get("updated"):
        return {"status": "FAILED", "account_id": account_id, "error": "Actual rejected the finance import.", "writes_performed": attempted}
    return {
        "status": "OUTCOME UNKNOWN", "account_id": account_id,
        "error": "Actual import was attempted but canonical read-back is incomplete.",
        "writes_performed": attempted, "reconcile_before_retry": True,
        "readback_state": state,
    }
