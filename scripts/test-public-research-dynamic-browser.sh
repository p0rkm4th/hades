#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HADES_REPO_DIR="$repo_dir" python3 - <<'PY'
import importlib.util
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

root = Path(os.environ["HADES_REPO_DIR"])
sys.path.insert(0, str(root / "integrations/public-research"))
spec = importlib.util.spec_from_file_location(
    "hades_public_research_dynamic", root / "integrations/public-research/research.py"
)
research = importlib.util.module_from_spec(spec)
spec.loader.exec_module(research)
spec = importlib.util.spec_from_file_location(
    "hades_public_research_dynamic_reader", root / "integrations/browser-access/research_reader.py"
)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/app":
            body = (b"<!doctype html><title>HADES dynamic fixture</title>"
                    b"<main id='app'></main><script>document.getElementById('app').textContent="
                    b"'Rendered public status: GREEN';</script>")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def log_message(self, *_args):
        pass


server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
threading.Thread(target=server.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{server.server_port}/app"
os.environ["HADES_PUBLIC_RESEARCH_DYNAMIC_ENABLED"] = "true"
os.environ["HADES_BROWSER_ALLOWED_HOSTS"] = "127.0.0.1"
os.environ["HADES_BROWSER_ALLOW_PRIVATE_TARGETS"] = "1"  # isolated local fixture only

try:
    result = research.research_public_sources(
        "Public service status", subject_class="public_service",
        search=lambda _query: {"results": [{
            "title": "Status application", "url": url, "content": "Search found status application.",
        }]},
        read_page=lambda _url: {"status": "SUCCEEDED", "url": _url,
                                "final_url": _url, "title": "JS shell", "text": ""},
        dynamic_read_page=reader.read_dynamic_page,
    )
    assert result["status"] == "SUCCEEDED", result
    page = result["page_reads"][0]
    assert page["evidence_type"] == "DYNAMIC_PAGE", page
    assert page["url"] == url and page["final_url"] == url, page
    assert page["title"] == "HADES dynamic fixture", page
    assert "Rendered public status: GREEN" in page["excerpt"], page
    assert page["retrieved_at_utc"].endswith("Z"), page
    assert "Anonymous rendered" in " ".join(page["warnings"]), page
    assert "untrusted evidence" in result["evidence_handling"].lower(), result

    # Missing host authorization fails closed before launching a browser.
    os.environ["HADES_BROWSER_ALLOWED_HOSTS"] = "other.example"
    denied = reader.read_dynamic_page(url)
    assert denied["status"] == "FAILED", denied
    print("PASS composed public_research returns rendered page as bounded DYNAMIC_PAGE evidence")
    print("PASS dynamic fallback retains provenance, caveats, and host allowlist enforcement")
finally:
    server.shutdown()
    server.server_close()
PY
