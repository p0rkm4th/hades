#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import ast
from pathlib import Path

server = Path("integrations/web-extract/server.py")
source = server.read_text(encoding="utf-8")
ast.parse(source)
assert "public_page_read" in source
assert "MAX_HTML_BYTES = 2 * 1024 * 1024" in source
assert "MAX_TEXT_CHARS = 32_000" in source
assert "HTTPRedirectHandler" in source
assert "Only globally routable unicast page targets are allowed." in source
assert "not address.is_global" in source and "address.is_multicast" in source
assert '"evidence": "PAGE"' in source
assert "logs in" in source.lower() and "forms" in source.lower()

config = Path("hermes/config.yaml.example").read_text(encoding="utf-8")
assert "public-page-extract:" in config
assert "integrations/web-extract/server.py" in config

overlay = Path("hermes/sitecustomize.py").read_text(encoding="utf-8")
assert "_HADES_PAGE_INTENT" in overlay
assert "_hades_page_tool_definitions" in overlay
assert "public_page_read" in overlay
research = Path("integrations/public-research/research.py").read_text(encoding="utf-8")
server = Path("integrations/public-research/server.py").read_text(encoding="utf-8")
assert "retrieved_at_utc" in research
assert "SEARCH_SNIPPET" in research and "STATIC_PAGE" in research
assert "publisher_independence" in research
assert "public_research" in server and "private-person dossiers" in server
assert "_HADES_PUBLIC_RESEARCH_TOOLSETS" in overlay
assert "untrusted data" in overlay.lower()
print("PASS bounded public-page extraction contract")
print("PASS page evidence is distinct from search evidence")
print("PASS static extraction rejects private targets and side-effect surfaces")
print("PASS public research composes bounded evidence with per-source provenance")
PY
python3 -m py_compile integrations/web-extract/server.py
