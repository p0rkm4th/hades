#!/usr/bin/env python3
"""Bounded synthetic throughput probe for accepted HADES inference lanes.

This is qualification evidence, not a model bakeoff. It sends a short public
probe, records queue/first-byte/completion timing, and never includes HADES
conversation or tool data.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import statistics
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROBE = "Reply with exactly EPSILON-PROBE."


def one(endpoint: str, model: str, timeout: float, sequence: int) -> dict[str, Any]:
    url = endpoint.rstrip("/") + "/chat/completions"
    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": PROBE}],
            "stream": True,
            "max_tokens": 16,
            "temperature": 0,
        }
    ).encode()
    started = time.perf_counter()
    first = None
    bytes_seen = 0
    status = None
    try:
        request = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=timeout) as response:
            status = response.status
            for line in response:
                bytes_seen += len(line)
                if first is None and line.strip():
                    first = time.perf_counter()
        ended = time.perf_counter()
        return {
            "sequence": sequence,
            "status": "SUCCEEDED" if status == 200 else "FAILED",
            "http_status": status,
            "queue_or_first_byte_ms": (first - started) * 1000 if first else None,
            "total_ms": (ended - started) * 1000,
            "bytes": bytes_seen,
        }
    except (TimeoutError, HTTPError, URLError, OSError) as exc:
        ended = time.perf_counter()
        return {
            "sequence": sequence,
            "status": "TIMEOUT" if isinstance(exc, TimeoutError) else "FAILED",
            "http_status": status,
            "queue_or_first_byte_ms": (first - started) * 1000 if first else None,
            "total_ms": (ended - started) * 1000,
            "bytes": bytes_seen,
            "error": type(exc).__name__,
        }


def run_lane(name: str, endpoint: str, model: str, concurrency: int, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(one, endpoint, model, timeout, index) for index in range(concurrency)]
        results = [future.result() for future in futures]
    successful = [row for row in results if row["status"] == "SUCCEEDED"]
    firsts = [row["queue_or_first_byte_ms"] for row in successful if row["queue_or_first_byte_ms"] is not None]
    totals = [row["total_ms"] for row in successful]
    return {
        "lane": name,
        "endpoint": endpoint,
        "model": model,
        "concurrency": concurrency,
        "timeout_seconds": timeout,
        "wall_ms": (time.perf_counter() - started) * 1000,
        "successes": len(successful),
        "failures": len(results) - len(successful),
        "first_byte_ms": {
            "p50": statistics.median(firsts) if firsts else None,
            "max": max(firsts) if firsts else None,
        },
        "total_ms": {
            "p50": statistics.median(totals) if totals else None,
            "max": max(totals) if totals else None,
        },
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 2])
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--lane", action="append", choices=("Fast", "Deep", "Code-specialized"))
    parser.add_argument("--fast-url", default=os.environ.get("HADES_BENCHMARK_FAST_URL", ""))
    parser.add_argument("--deep-url", default=os.environ.get("HADES_BENCHMARK_DEEP_URL", ""))
    parser.add_argument("--code-url", default=os.environ.get("HADES_BENCHMARK_CODE_URL", ""))
    args = parser.parse_args()
    lanes = [
        ("Fast", args.fast_url, "qwen3:8b"),
        ("Deep", args.deep_url, "qwen3.6:35b"),
        ("Code-specialized", args.code_url, "gemma4:e4b"),
    ]
    if args.lane:
        lanes = [lane for lane in lanes if lane[0] in args.lane]
    missing = [name for name, endpoint, _model in lanes if not endpoint.strip()]
    if missing:
        parser.error("set the endpoint for each selected lane with --fast-url/--deep-url/--code-url or HADES_BENCHMARK_*_URL")
    report = {
        "schema": "hades-epsilon-provider-throughput/v1",
        "probe": "synthetic_public_exact_response",
        "lanes": [run_lane(name, endpoint, model, level, args.timeout) for name, endpoint, model in lanes for level in args.concurrency],
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
