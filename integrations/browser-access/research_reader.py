"""One-shot anonymous dynamic-page reader for public research fallback."""

from __future__ import annotations

import json
import os
import re
import select
import signal
import subprocess
import sys
import time
import importlib.util
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


_PROXY = Path(__file__).with_name("proxy.py")
_SAFE_TOOLS = frozenset({"browser_navigate", "browser_snapshot"})
_MAX_OUTPUT = 32_000


def _rpc(process: subprocess.Popen[bytes], request_id: int, method: str,
         params: dict[str, Any], deadline: float, pending: bytearray) -> dict[str, Any]:
    assert process.stdin is not None and process.stdout is not None
    body = json.dumps({"jsonrpc": "2.0", "id": request_id,
                       "method": method, "params": params}).encode() + b"\n"
    process.stdin.write(body)
    process.stdin.flush()
    while time.monotonic() < deadline:
        if b"\n" in pending:
            line, _, remainder = pending.partition(b"\n")
            pending[:] = remainder
            try:
                message = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(message, dict) and message.get("id") == request_id:
                return message
            continue
        remaining = deadline - time.monotonic()
        ready, _, _ = select.select([process.stdout.fileno()], [], [], remaining)
        if not ready:
            break
        chunk = os.read(process.stdout.fileno(), 65_536)
        if not chunk:
            break
        pending.extend(chunk)
    raise TimeoutError("anonymous browser research timed out")


def _response_text(response: dict[str, Any]) -> str:
    if response.get("error"):
        raise RuntimeError("anonymous browser request failed")
    result = response.get("result")
    if not isinstance(result, dict) or result.get("isError") is True:
        raise RuntimeError("anonymous browser request failed")
    content = result.get("content")
    if not isinstance(content, list):
        raise RuntimeError("anonymous browser response was malformed")
    return "\n".join(
        item["text"] for item in content
        if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str)
    )


def read_dynamic_page(url: str) -> dict[str, Any]:
    """Read one explicitly allowlisted public page without login or interaction."""
    if os.environ.get("HADES_PUBLIC_RESEARCH_DYNAMIC_ENABLED") != "true":
        return {"status": "FAILED", "error": "Dynamic public-page reading is disabled."}
    if not os.environ.get("HADES_BROWSER_ALLOWED_HOSTS", "").strip():
        return {"status": "FAILED", "error": "Dynamic public-page reading has no host allowlist."}

    try:
        spec = importlib.util.spec_from_file_location("hades_research_browser_policy", _PROXY)
        if spec is None or spec.loader is None:
            raise ValueError("browser policy is unavailable")
        policy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(policy)
        policy.validate_navigation(url)
    except Exception:
        return {"status": "FAILED", "error": "The page is outside the anonymous browser policy."}

    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            [sys.executable, str(_PROXY)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env=dict(os.environ), bufsize=0,
            start_new_session=True,
        )
        deadline = time.monotonic() + 18
        pending = bytearray()
        initialized = _rpc(process, 1, "initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "hades-public-research", "version": "1"},
        }, deadline, pending)
        if initialized.get("error"):
            raise RuntimeError("anonymous browser initialization failed")
        assert process.stdin is not None
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}).encode() + b"\n")
        process.stdin.flush()
        listed = _rpc(process, 2, "tools/list", {}, deadline, pending)
        tools = listed.get("result", {}).get("tools", [])
        names = {item.get("name") for item in tools if isinstance(item, dict)}
        if not _SAFE_TOOLS.issubset(names):
            raise RuntimeError("anonymous browser read tools are unavailable")

        navigation = _rpc(process, 3, "tools/call", {
            "name": "browser_navigate", "arguments": {"url": url},
        }, deadline, pending)
        navigation_text = _response_text(navigation)
        page_url = re.search(r"(?m)^- Page URL: (https?://\S+)\s*$", navigation_text)
        page_title = re.search(r"(?m)^- Page Title: (.*?)\s*$", navigation_text)
        if not page_url:
            raise RuntimeError("anonymous browser returned no page URL")
        rendered_text = ""
        for request_id in range(4, 10):
            snapshot = _rpc(process, request_id, "tools/call", {
                "name": "browser_snapshot", "arguments": {},
            }, deadline, pending)
            snapshot_text = _response_text(snapshot)
            rendered = re.search(r"(?s)### Snapshot\s*```yaml\s*(.*?)\s*```", snapshot_text)
            if rendered and rendered.group(1).strip() and "[active]" not in rendered.group(1):
                rendered_text = rendered.group(1).strip()
                break
            time.sleep(0.2)
        if not rendered_text:
            raise RuntimeError("anonymous browser returned no readable page content")
        final_url = page_url.group(1)
        parsed = urlparse(final_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise RuntimeError("anonymous browser returned an invalid final URL")
        text = rendered_text
        return {
            "status": "SUCCEEDED", "url": url, "final_url": final_url,
            "title": page_title.group(1)[:300] if page_title else "Rendered public page",
            "text": text[:_MAX_OUTPUT], "truncated": len(text) > _MAX_OUTPUT,
        }
    except Exception:
        return {"status": "FAILED", "error": "The anonymous browser could not read this page."}
    finally:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=2)
