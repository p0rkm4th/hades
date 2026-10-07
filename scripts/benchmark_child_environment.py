"""Build a small inherited environment for isolated benchmark services."""

from __future__ import annotations

import os
from collections.abc import Mapping


_INHERITED_KEYS = (
    "PATH",
    "LANG",
    "LC_ALL",
    "TZ",
    "TMPDIR",
)


def benchmark_child_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    """Keep runtime basics; drop credentials, service URLs, proxies, and HADES state."""
    parent = os.environ if source is None else source
    environment = {key: parent[key] for key in _INHERITED_KEYS if parent.get(key)}
    environment["NO_PROXY"] = "127.0.0.1,localhost,::1"
    environment["no_proxy"] = environment["NO_PROXY"]
    return environment
