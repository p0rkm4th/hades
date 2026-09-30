#!/usr/bin/env python3
"""Launch the pinned Grocy MCP without storing its API key in Hermes config."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path
from urllib.parse import urlsplit

MCP_EXECUTABLE = "/opt/hades-grocy-mcp/venv/bin/grocy-mcp"

def fail(message: str) -> "NoReturn":
    print(f"HADES Grocy MCP: {message}", file=sys.stderr)
    raise SystemExit(2)


def main() -> None:
    url = os.environ.get("GROCY_URL", "").strip().rstrip("/")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        fail("GROCY_URL must be an absolute HTTP(S) URL without embedded credentials")

    key_path = Path(os.environ.get("GROCY_API_KEY_FILE", ""))
    try:
        if key_path.is_symlink():
            fail("API key file must not be a symlink")
        info = key_path.stat()
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) not in {0o600, 0o640}:
            fail("API key file must be a regular mode 0600 or 0640 file")
        key = key_path.read_text(encoding="utf-8").strip()
    except OSError:
        fail("API key file is unavailable")
    if not key or "\n" in key or "\r" in key:
        fail("API key file is empty or malformed")

    if not os.path.isabs(MCP_EXECUTABLE) or not os.access(MCP_EXECUTABLE, os.X_OK):
        fail("pinned grocy-mcp executable is missing; rerun the HADES installer")

    child_env = os.environ.copy()
    child_env.pop("GROCY_API_KEY_FILE", None)
    child_env["GROCY_URL"] = url
    child_env["GROCY_API_KEY"] = key
    os.execve(MCP_EXECUTABLE, [MCP_EXECUTABLE, "--transport=stdio"], child_env)


if __name__ == "__main__":
    main()
