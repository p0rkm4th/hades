#!/usr/bin/env python3
"""Print aggregate Hindsight backlog counts without exposing bank identities."""
from __future__ import annotations

import argparse
import ipaddress
import json
import sys
from urllib.error import URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen


MAX_BANKS = 128
REQUIRED_COUNTS = (
    "pending_operations",
    "failed_operations",
    "pending_consolidation",
    "failed_consolidation",
)


def _get_json(base_url: str, path: str, timeout: float) -> object:
    request = Request(
        f"{base_url}{path}",
        headers={"Accept": "application/json"},
        method="GET",
    )
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError("unexpected HTTP status")
        return json.load(response)


def aggregate(base_url: str, timeout: float = 5.0) -> tuple[int, dict[str, int]]:
    parts = urlsplit(base_url)
    try:
        host_is_loopback = bool(parts.hostname) and ipaddress.ip_address(parts.hostname).is_loopback
    except ValueError:
        host_is_loopback = False
    if (
        parts.scheme != "http"
        or not host_is_loopback
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
    ):
        raise ValueError("base URL must be an HTTP loopback address without credentials or query")
    base = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
    if not base:
        raise ValueError("base URL is required")

    bank_result = _get_json(base, "/v1/default/banks", timeout)
    banks = bank_result.get("banks") if isinstance(bank_result, dict) else None
    if not isinstance(banks, list) or len(banks) > MAX_BANKS:
        raise ValueError("bank list response is invalid or exceeds the bounded limit")
    bank_ids = [
        bank.get("bank_id") for bank in banks
        if isinstance(bank, dict) and isinstance(bank.get("bank_id"), str) and bank["bank_id"]
    ]
    if len(bank_ids) != len(banks):
        raise ValueError("bank list contains an invalid entry")

    totals = {name: 0 for name in REQUIRED_COUNTS}
    for bank_id in bank_ids:
        stats = _get_json(base, f"/v1/default/banks/{quote(bank_id, safe='')}/stats", timeout)
        if not isinstance(stats, dict):
            raise ValueError("bank stats response is invalid")
        for name in REQUIRED_COUNTS:
            value = stats.get(name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("bank stats contain an invalid aggregate count")
            totals[name] += value
    return len(bank_ids), totals


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8888")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()
    if args.timeout <= 0 or args.timeout > 30:
        parser.error("--timeout must be greater than 0 and at most 30 seconds")
    try:
        bank_count, totals = aggregate(args.base_url, args.timeout)
    except (OSError, URLError, ValueError, TimeoutError):
        print("FAIL Hindsight aggregate stats could not be read safely", file=sys.stderr)
        return 1
    print(
        "PASS Hindsight aggregate stats "
        f"banks={bank_count} "
        + " ".join(f"{key}={totals[key]}" for key in REQUIRED_COUNTS)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
