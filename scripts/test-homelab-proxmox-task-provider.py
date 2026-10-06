#!/usr/bin/env python3
"""Synthetic contract for scoped, bounded Proxmox archived task reads."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "integrations" / "homelab-readonly"))

from proxmox_tasks import read_archived_task_pages


base = "https://pve.example.test/api2/json"
scope_all = {
    "scope": "ALL_GUESTS", "all_guests": True,
    "guest_ids": [], "excluded_guest_ids": [],
}
scope_selected = {
    "scope": "SELECTED_GUESTS", "all_guests": False,
    "guest_ids": ["101", "102"], "excluded_guest_ids": [],
}


calls: list[str] = []
unknown = read_archived_task_pages(
    base, ["node-a"], {"scope": "UNKNOWN", "all_guests": False, "guest_ids": []},
    mode="since", since=100, fetch=lambda *args, **kwargs: calls.append("unexpected"),
)
assert unknown["status"] == "UNKNOWN" and calls == []


def selected_fetch(url: str, *_args: object, **_kwargs: object) -> dict:
    calls.append(url)
    return {"data": [
        {"id": "101", "type": "qmstart", "starttime": 150},
        {"id": 102, "type": "qmstop", "starttime": 151},
        {"id": "999", "type": "qmstart", "starttime": 152},
        {"id": True, "type": "qmstart", "starttime": 153},
        {"id": None, "type": "qmstart", "starttime": 154, "upid": "private-upid"},
    ]}


selected = read_archived_task_pages(
    base, ["node-a"], scope_selected, mode="since", since=100,
    fetch=selected_fetch, token_file="token", ca_file="ca", token_id="id",
)
assert selected["status"] == "PARTIAL", selected
assert [row["id"] for row in selected["nodes"][0]["rows"]] == ["101", 102]
assert selected["nodes"][0]["excluded_rows"] == 1
assert selected["nodes"][0]["malformed_rows"] == 2
assert len(calls) == 1 and parse_qs(urlsplit(calls[0]).query) == {
    "source": ["archive"], "limit": ["100"], "since": ["100"],
}

large_guest_scope = {
    "scope": "SELECTED_GUESTS", "all_guests": False,
    "guest_ids": ["1000000000"], "excluded_guest_ids": [],
}
large_guest_row = lambda *_args, **_kwargs: {"data": [{
    "id": "1000000000", "type": "qmstart", "status": "OK", "starttime": 150,
}]}
recent_large_id = read_archived_task_pages(
    base, ["node-a"], large_guest_scope, mode="since", since=100, fetch=large_guest_row,
)
backup_large_id = read_archived_task_pages(
    base, ["node-a"], large_guest_scope, mode="vzdump", fetch=large_guest_row,
)
assert [row["id"] for row in recent_large_id["nodes"][0]["rows"]] == ["1000000000"]
assert backup_large_id["nodes"][0]["rows"] == []
assert backup_large_id["nodes"][0]["malformed_rows"] == 1


def mixed_fetch(url: str, *_args: object, **_kwargs: object) -> dict:
    if "/node-b/" in url:
        raise OSError("private token and URL must not leak")
    return {"data": [
        {"id": "101", "status": "OK", "endtime": 1700000000, "upid": "private-upid"},
        {"id": "999", "status": "OK", "endtime": 1700000001},
        {"id": None, "status": "OK", "endtime": 1700000002, "upid": "private-upid"},
    ]}


mixed = read_archived_task_pages(
    base, ["node-a", "node-b"], {
        "scope": "PARTIAL", "all_guests": True,
        "guest_ids": [], "excluded_guest_ids": ["999"],
    }, mode="vzdump", fetch=mixed_fetch,
)
assert mixed["status"] == "PARTIAL", mixed
assert [row["status"] for row in mixed["nodes"]] == ["HEALTHY", "UNAVAILABLE"]
assert [row["id"] for row in mixed["nodes"][0]["rows"]] == ["101"]
assert len(mixed["nodes"][0]["unattributed_rows"]) == 1
assert mixed["nodes"][0]["excluded_rows"] == 1
assert mixed["nodes"][1]["error_codes"] == ["SOURCE_IO_ERROR"]
assert "private token" not in repr(mixed)
assert "private-upid" not in repr(mixed)


def capped(mode: str, count: int) -> dict:
    def fetch(_url: str, *_args: object, **_kwargs: object) -> dict:
        return {"data": [
            {"id": "101", "type": "qmstart", "status": "OK", "starttime": 100}
            for _ in range(count)
        ]}
    return read_archived_task_pages(
        base, ["node-a"], scope_all, mode=mode, since=100 if mode == "since" else None,
        fetch=fetch,
    )


for mode, limit in (("vzdump", 20), ("since", 100)):
    below = capped(mode, limit - 1)
    exact = capped(mode, limit)
    over = capped(mode, limit + 1)
    assert below["status"] == "READABLE", (mode, below)
    assert exact["status"] == "PARTIAL" and exact["nodes"][0]["truncated"] is True, (mode, exact)
    assert over["status"] == "PARTIAL" and len(over["nodes"][0]["rows"]) == limit, (mode, over)


for mode in ("vzdump", "since"):
    def empty_page(_url: str, *_args: object, **_kwargs: object) -> dict:
        return {"data": []}
    exact_nodes = read_archived_task_pages(
        base, [f"node-{index:02}" for index in range(16)], scope_all,
        mode=mode, since=100 if mode == "since" else None, fetch=empty_page,
    )
    excess_nodes = read_archived_task_pages(
        base, [f"node-{index:02}" for index in range(18)], scope_all,
        mode=mode, since=100 if mode == "since" else None, fetch=empty_page,
    )
    assert exact_nodes["status"] == "READABLE" and len(exact_nodes["nodes"]) == 16
    assert excess_nodes["status"] == "PARTIAL" and excess_nodes["nodes_truncated"] is True
    assert len(excess_nodes["nodes"]) == 16

print("PASS Proxmox task provider scope, node isolation, read bounds, and partial failures")
