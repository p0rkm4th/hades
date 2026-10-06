"""Bounded read-only collection of Proxmox archived task pages."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import re
from typing import Callable
from urllib.parse import quote, urljoin, urlsplit

from source_utils import source_error_code


PAGE_LIMITS = {"vzdump": 20, "since": 100}
MAX_NODES = 16
_NODE = re.compile(r"[A-Za-z0-9._-]{1,128}")
_GUEST = re.compile(r"[1-9][0-9]{0,19}")
_BACKUP_GUEST = re.compile(r"[1-9][0-9]{0,8}")
_TASK_TYPE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,31}")


def _safe_status(value: object) -> str:
    raw = str(value or "").strip().upper()
    if raw == "OK":
        return "OK"
    if raw == "RUNNING":
        return "RUNNING"
    if raw.startswith("ERROR"):
        return "ERROR"
    return "UNKNOWN"


def _project_row(row: dict, mode: str) -> dict:
    projected = {"status": _safe_status(row.get("status"))}
    keys = ("id", "starttime", "endtime")
    for key in keys:
        value = row.get(key)
        if key == "id" or (
            isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0
        ):
            if value is not None:
                projected[key] = value
    if mode == "since":
        task_type = row.get("type")
        if isinstance(task_type, str) and _TASK_TYPE.fullmatch(task_type):
            projected["type"] = task_type
    return projected


def _effective_scope(task_scope: object) -> tuple[bool, set[str], set[str]] | None:
    if not isinstance(task_scope, dict):
        return None
    all_guests = task_scope.get("all_guests") is True
    scope_name = task_scope.get("scope")
    if not isinstance(scope_name, str):
        return None
    raw_guest_ids = task_scope.get("guest_ids")
    raw_excluded = task_scope.get("excluded_guest_ids", [])
    if not isinstance(raw_guest_ids, list) or not isinstance(raw_excluded, list):
        return None
    if any(not isinstance(value, str) or not _GUEST.fullmatch(value) for value in raw_guest_ids):
        return None
    if any(not isinstance(value, str) or not _GUEST.fullmatch(value) for value in raw_excluded):
        return None
    guest_ids = set(raw_guest_ids)
    excluded = set(raw_excluded)
    if not all_guests and not guest_ids:
        return None
    if all_guests and scope_name not in {"ALL_GUESTS", "PARTIAL"}:
        return None
    if not all_guests and scope_name not in {"SELECTED_GUESTS", "PARTIAL"}:
        return None
    return all_guests, guest_ids, excluded


def read_archived_task_pages(
    api_base: str,
    nodes: object,
    task_scope: object,
    *,
    mode: str,
    fetch: Callable[..., dict],
    token_file: str = "",
    ca_file: str = "",
    token_id: str = "",
    since: int | None = None,
) -> dict:
    """Read bounded archive pages, enforcing VM.Audit task visibility.

    The caller resolves credentials, computes effective permission scope, and
    injects its bounded transport. Unknown/empty scope returns without making
    requests. Results retain per-node partial failures and only task rows in
    the supplied effective scope; callers perform domain-specific shaping.
    """
    scope = _effective_scope(task_scope)
    if scope is None:
        return {
            "status": "UNKNOWN", "nodes": [], "nodes_truncated": False,
            "malformed_node_count": 0, "read_only": True,
        }
    limit = PAGE_LIMITS.get(mode) if isinstance(mode, str) else None
    if limit is None or (mode == "since" and (type(since) is not int or since < 0)):
        return {
            "status": "INVALID_REQUEST", "nodes": [], "nodes_truncated": False,
            "malformed_node_count": 0, "read_only": True,
        }
    try:
        if not isinstance(api_base, str):
            raise ValueError("invalid Proxmox API base")
        parsed = urlsplit(api_base)
        if (
            parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
        ):
            raise ValueError("invalid Proxmox API base")
        safe_base = api_base.rstrip("/") + "/"
    except (ValueError, UnicodeError):
        return {
            "status": "SOURCE_UNAVAILABLE", "nodes": [], "nodes_truncated": False,
            "malformed_node_count": 0,
            "error_codes": ["INVALID_RESPONSE_OR_CONFIGURATION"], "read_only": True,
        }
    if not isinstance(nodes, (list, tuple)):
        return {
            "status": "SOURCE_UNAVAILABLE", "nodes": [], "nodes_truncated": False,
            "malformed_node_count": 1,
            "error_codes": ["INVALID_RESPONSE_OR_CONFIGURATION"], "read_only": True,
        }
    valid_nodes = sorted({node for node in nodes if isinstance(node, str) and _NODE.fullmatch(node)})
    malformed_node_count = len(nodes) - sum(
        1 for node in nodes if isinstance(node, str) and _NODE.fullmatch(node)
    )
    nodes_truncated = len(valid_nodes) > MAX_NODES
    selected_nodes = valid_nodes[:MAX_NODES]
    if not selected_nodes:
        return {
            "status": "SOURCE_UNAVAILABLE", "nodes": [], "nodes_truncated": nodes_truncated,
            "malformed_node_count": malformed_node_count,
            "error_codes": [], "read_only": True,
        }

    all_guests, guest_ids, excluded_ids = scope

    def read_node(node: str) -> dict:
        endpoint = urljoin(safe_base, f"nodes/{quote(node, safe='')}/tasks")
        if mode == "vzdump":
            endpoint += "?source=archive&limit=20&typefilter=vzdump"
        else:
            endpoint += f"?source=archive&limit=100&since={since}"
        try:
            payload = fetch(endpoint, token_file, ca_file, token_id)
            if not isinstance(payload, dict):
                raise ValueError("Proxmox task response has an unsupported shape")
            raw_rows = payload.get("data")
            if not isinstance(raw_rows, list):
                raise ValueError("Proxmox task response has an unsupported shape")
            rows = []
            unattributed_rows = []
            excluded_rows = 0
            malformed_rows = 0
            truncated = len(raw_rows) >= limit
            for row in raw_rows[:limit]:
                if not isinstance(row, dict):
                    malformed_rows += 1
                    continue
                raw_id = row.get("id")
                if mode == "vzdump" and raw_id in (None, ""):
                    unattributed_rows.append(_project_row(row, mode))
                    continue
                if mode == "vzdump" and not isinstance(raw_id, str):
                    malformed_rows += 1
                    continue
                if mode == "since" and not isinstance(raw_id, (str, int)):
                    malformed_rows += 1
                    continue
                if isinstance(raw_id, bool):
                    malformed_rows += 1
                    continue
                guest_id = str(raw_id) if isinstance(raw_id, (str, int)) else ""
                valid_guest_id = (
                    _BACKUP_GUEST if mode == "vzdump" else _GUEST
                ).fullmatch(guest_id)
                if not valid_guest_id:
                    malformed_rows += 1
                    continue
                if all_guests:
                    if guest_id in excluded_ids:
                        excluded_rows += 1
                        continue
                elif guest_id not in guest_ids:
                    excluded_rows += 1
                    continue
                rows.append(_project_row(row, mode))
            state = "PARTIAL" if malformed_rows or truncated else "HEALTHY"
            return {
                "node": node, "status": state, "rows": rows,
                "unattributed_rows": unattributed_rows,
                "excluded_rows": excluded_rows, "malformed_rows": malformed_rows,
                "truncated": truncated, "error_codes": [],
            }
        except (OSError, ValueError, UnicodeError, OverflowError) as exc:
            return {
                "node": node, "status": "UNAVAILABLE", "rows": [],
                "unattributed_rows": [], "excluded_rows": 0,
                "malformed_rows": 0, "truncated": False,
                "error_codes": [source_error_code(exc)],
            }

    with ThreadPoolExecutor(max_workers=min(8, len(selected_nodes))) as pool:
        results = list(pool.map(read_node, selected_nodes))
    states = [row["status"] for row in results]
    errors = sorted({code for row in results for code in row["error_codes"]})
    status = "SOURCE_UNAVAILABLE" if all(state == "UNAVAILABLE" for state in states) else (
        "PARTIAL" if (
            nodes_truncated or malformed_node_count or any(state != "HEALTHY" for state in states)
        ) else "READABLE"
    )
    return {
        "status": status, "nodes": results, "nodes_truncated": nodes_truncated,
        "malformed_node_count": malformed_node_count, "error_codes": errors,
        "read_only": True,
    }
