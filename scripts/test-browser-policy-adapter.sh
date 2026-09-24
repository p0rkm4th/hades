#!/usr/bin/env bash
set -euo pipefail

PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../integrations/browser-access" && pwd)" python3 - <<'PY'
import os
from policy import select_profile
import proxy
from proxy import ALLOWED_TOOLS, authorize_call, build_command, filtered_tools, validate_navigation
from pathlib import Path

config = Path("hermes/config.yaml.example").read_text()
assert "browser-research:" in config
assert "integrations/browser-access/proxy.py" in config
assert "HADES_BROWSER_ALLOWED_HOSTS" in config

os.environ["HADES_BROWSER_ALLOWED_HOSTS"] = "recipes.example,*.public.example"
assert validate_navigation("https://recipes.example/recipe")
assert validate_navigation("https://blog.public.example/post")
original_getaddrinfo = proxy.socket.getaddrinfo
proxy.socket.getaddrinfo = lambda *args, **kwargs: [(2, 1, 6, '', ('198.51.100.9', 0))]
assert proxy._target_allowed("https://recipes.example/", ("recipes.example",)) is False
proxy.socket.getaddrinfo = original_getaddrinfo
for url in (
    "file:///etc/passwd", "https://user:pass@recipes.example/secret",
    "https://not-allowed.example/", "http://127.0.0.1:8000/",
):
    try:
        validate_navigation(url)
    except ValueError:
        pass
    else:
        raise AssertionError(f"unsafe browser URL accepted: {url}")

assert authorize_call("browser_navigate", {"url": "https://recipes.example/"})["url"].startswith("https://")
for name, args in (
    ("browser_click", {}), ("browser_evaluate", {"function": "() => 1"}),
    ("browser_snapshot", {"filename": "leak.txt"}),
):
    try:
        authorize_call(name, args)
    except (PermissionError, ValueError):
        pass
    else:
        raise AssertionError(f"unsafe browser operation accepted: {name}")

upstream = [
    {"name": "browser_navigate"}, {"name": "browser_snapshot"},
    {"name": "browser_click"}, {"name": "browser_run_code_unsafe"},
]
assert [tool["name"] for tool in filtered_tools(upstream)] == ["browser_navigate", "browser_snapshot"]
command = build_command(("recipes.example", "*.public.example"))
assert "--isolated" in command and "--headless" in command and "--allowed-hosts" in command
assert "--storage-state" not in command and "--user-data-dir" not in command
assert "--proxy-server" not in command
assert select_profile("household", "anonymous") == {"allowed": True, "profile": "anonymous"}
print("PASS anonymous browser adapter filters submit, code, storage, and file tools")
print("PASS browser adapter enforces HTTPS, explicit hosts, and public-target policy")
print("PASS browser adapter launches pinned isolated headless Playwright MCP")
PY
