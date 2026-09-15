"""Preview-only service boundary for local Actual Budget file intake."""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any

from file_boundary import MAX_FILE_BYTES, build_native_handoff
from import_csv import ImportFormatError, build_apply_request, build_preview


MAX_BASE64_CHARS = ((MAX_FILE_BYTES + 2) // 3) * 4
MAX_JSON_CHARS = 256 * 1024


def _decode_file(file_base64: str) -> bytes:
    if not isinstance(file_base64, str) or not file_base64.strip():
        raise ImportFormatError("file_base64 must be a non-empty base64 string")
    encoded = file_base64.strip()
    if len(encoded) > MAX_BASE64_CHARS:
        raise ImportFormatError("encoded financial file exceeds the 10 MiB limit")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ImportFormatError("file_base64 is not valid base64") from exc
    if not data or len(data) > MAX_FILE_BYTES:
        raise ImportFormatError("financial file is empty or exceeds the 10 MiB limit")
    return data


def _json_object(value: str, label: str) -> dict[str, Any]:
    if not isinstance(value, str) or len(value) > MAX_JSON_CHARS:
        raise ImportFormatError(f"{label} must be bounded JSON text")
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise ImportFormatError(f"{label} must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ImportFormatError(f"{label} must be a JSON object")
    return parsed


def _json_list(value: str, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, str) or len(value) > MAX_JSON_CHARS:
        raise ImportFormatError(f"{label} must be bounded JSON text")
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise ImportFormatError(f"{label} must be valid JSON") from exc
    if not isinstance(parsed, list) or any(not isinstance(row, dict) for row in parsed):
        raise ImportFormatError(f"{label} must be a JSON list of objects")
    return parsed


def preview_file(
    file_base64: str,
    filename: str,
    mapping_json: str = "{}",
    existing_transactions_json: str = "[]",
) -> dict[str, Any]:
    """Build a review preview without retaining or sending the file anywhere."""
    try:
        data = _decode_file(file_base64)
        handoff = build_native_handoff(data, filename)
        if handoff["format"] != "CSV":
            return handoff
        mapping = _json_object(mapping_json, "mapping_json")
        existing = _json_list(existing_transactions_json, "existing_transactions_json")
        return build_preview(data, mapping, existing_transactions=existing)
    except (ImportFormatError, ValueError) as exc:
        return {"status": "FAILED", "error": str(exc), "writes_performed": False}


def preview_apply_request(preview_json: str, *, confirm: bool = False) -> dict[str, Any]:
    """Build the CSV import request; this remains a write-free handoff."""
    try:
        preview = _json_object(preview_json, "preview_json")
        return build_apply_request(preview, confirm=confirm)
    except (ImportFormatError, ValueError) as exc:
        return {"status": "FAILED", "error": str(exc), "writes_performed": False}
