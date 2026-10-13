#!/usr/bin/env python3
"""Normalize timestamps on files changed by the isolated 0.12 image build."""

from __future__ import annotations

import os
from pathlib import Path


ZERO = (0, 0)
HADES_ROOT = Path("/opt/hades")
WEBUI_FILES = [
    Path("/app/backend/open_webui/utils/auth.py"),
    Path("/app/backend/open_webui/routers/auths.py"),
    Path("/app/backend/open_webui/routers/users.py"),
    Path("/app/backend/open_webui/routers/groups.py"),
    Path("/app/backend/open_webui/socket/main.py"),
    Path("/app/backend/open_webui/main.py"),
    Path("/app/backend/open_webui/utils/middleware.py"),
    Path("/app/backend/open_webui/utils/hades_stream_disconnect_compat.py"),
    Path("/app/backend/open_webui/static/hades-theme.css"),
    Path("/app/backend/open_webui/static/hades-theme.js"),
    Path("/app/build/static/hades-theme.css"),
    Path("/app/build/static/hades-theme.js"),
    Path("/app/build/static/finance-upload.js"),
    Path("/app/build/static/receipt-upload.js"),
]
CHUNK_MARKER = 'typeof s!=="string"'


def main() -> None:
    if not HADES_ROOT.is_dir():
        raise SystemExit("candidate HADES payload is missing")
    chunks = [
        path for path in Path("/app/build/_app/immutable/chunks").glob("*.js")
        if CHUNK_MARKER in path.read_text(encoding="utf-8")
    ]
    if len(chunks) != 1:
        raise SystemExit(f"expected exactly one patched stream chunk, found {len(chunks)}")
    changed_files = [*WEBUI_FILES, *chunks]
    missing = [str(path) for path in changed_files if not path.is_file()]
    if missing:
        raise SystemExit("expected candidate output files are missing")

    changed_dirs = {HADES_ROOT}
    for path in HADES_ROOT.rglob("*"):
        os.utime(path, ns=ZERO, follow_symlinks=False)
        if path.is_dir():
            changed_dirs.add(path)
    for path in changed_files:
        os.utime(path, ns=ZERO, follow_symlinks=False)
        changed_dirs.add(path.parent)
    for path in changed_dirs:
        if path.exists() and path.is_dir():
            os.utime(path, ns=ZERO, follow_symlinks=False)


if __name__ == "__main__":
    main()
