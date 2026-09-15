"""Classify local Actual-supported financial files without owning a ledger.

Actual itself is the parser and canonical importer for QIF, OFX, QFX, and
CAMT. This boundary only validates a bounded local file, records a digest, and
selects the native handoff. CSV may use the deterministic preview module;
other formats must remain opaque until Actual's native import path previews
them.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import PurePath
from typing import Any


MAX_FILE_BYTES = 10 * 1024 * 1024
SUPPORTED = {"csv", "qif", "ofx", "qfx", "camt"}


class FinanceFileError(ValueError):
    pass


def _extension(filename: str) -> str:
    suffix = PurePath(filename).suffix.lower().lstrip(".")
    if suffix not in SUPPORTED:
        raise FinanceFileError("financial file must use CSV, QIF, OFX, QFX, or CAMT format")
    return suffix


def _looks_like(file_bytes: bytes, extension: str) -> bool:
    sample = file_bytes[:8192].decode("utf-8-sig", errors="ignore").lstrip()
    if extension == "csv":
        return bool(sample and "\n" in sample)
    if extension == "qif":
        return sample.startswith("!Type:") or sample.startswith("!Account")
    if extension in {"ofx", "qfx"}:
        return "<OFX" in sample.upper() or "OFXHEADER:" in sample.upper()
    # CAMT is XML and commonly carries a camt namespace or document element.
    return sample.startswith("<") and bool(re.search(r"camt\.|<Document(?:\s|>)", sample, re.I))


def build_native_handoff(file_bytes: bytes, filename: str) -> dict[str, Any]:
    """Return a metadata-only handoff; never parses or uploads the file."""
    if not isinstance(file_bytes, bytes) or not file_bytes:
        raise FinanceFileError("financial file is empty")
    if len(file_bytes) > MAX_FILE_BYTES:
        raise FinanceFileError("financial file exceeds the 10 MiB limit")
    if not isinstance(filename, str) or not filename.strip():
        raise FinanceFileError("financial filename is required")
    extension = _extension(filename)
    if not _looks_like(file_bytes, extension):
        raise FinanceFileError(f"file content does not match the {extension.upper()} format")
    digest = hashlib.sha256(file_bytes).hexdigest()
    return {
        "status": "PREVIEW",
        "source": "local-financial-file",
        "format": extension.upper(),
        "filename": PurePath(filename).name,
        "file_sha256": digest,
        "size_bytes": len(file_bytes),
        "canonical_target": "Actual Budget native file import",
        "native_import_required": True,
        "requires_confirmation": True,
        "writes_performed": False,
        "reconcile_before_retry": True,
    }
