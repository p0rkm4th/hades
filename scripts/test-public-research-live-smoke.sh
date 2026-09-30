#!/usr/bin/env bash
set -Eeuo pipefail

# Opt-in online smoke for the real pinned SearXNG -> research collector ->
# pinned public-page reader path. It sends only fixed generic public-topic
# queries to configured search engines; it never includes user data.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
source "$repo_dir/config/versions.env"
command -v docker >/dev/null 2>&1 || { echo 'FAIL Docker is required' >&2; exit 2; }
command -v curl >/dev/null 2>&1 || { echo 'FAIL curl is required' >&2; exit 2; }

docker image inspect "$HADES_SEARXNG_IMAGE_RECORD" >/dev/null 2>&1 || {
  echo 'FAIL pinned SearXNG image is not present locally; pull the exact manifest pin first' >&2
  exit 2
}

suffix=$$
container="hades-public-research-smoke-$suffix"
network="hades-public-research-smoke-net-$suffix"
volume="hades-public-research-smoke-data-$suffix"
work=$(mktemp -d /tmp/hades-public-research-smoke.XXXXXX)
chmod 700 "$work"
cleanup() {
  docker stop "$container" >/dev/null 2>&1 || true
  docker rm "$container" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
  docker volume rm "$volume" >/dev/null 2>&1 || true
  python3 -c 'import shutil,sys; shutil.rmtree(sys.argv[1],ignore_errors=True)' "$work"
}
trap cleanup EXIT

sed 's/__SEARXNG_SECRET__/synthetic-public-research-smoke-secret/' \
  "$repo_dir/searxng/settings.yml" > "$work/settings.yml"
chmod 600 "$work/settings.yml"
docker network create "$network" >/dev/null
docker volume create "$volume" >/dev/null
docker run -d --name "$container" --network "$network" \
  -p 127.0.0.1::8080 \
  -v "$volume:/etc/searxng:Z" \
  -v "$work/settings.yml:/tmp/hades-settings.yml:ro,Z" \
  -e SEARXNG_SETTINGS_PATH=/tmp/hades-settings.yml \
  "$HADES_SEARXNG_IMAGE_RECORD" >/dev/null
port=$(docker port "$container" 8080/tcp | sed 's/.*://')
ready=false
for _ in $(seq 1 60); do
  if curl -fsS --max-time 2 "http://127.0.0.1:$port/" -o /dev/null 2>/dev/null; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "$ready" != true ]]; then
  echo 'FAIL pinned SearXNG did not become ready' >&2
  docker logs --tail 30 "$container" >&2 || true
  exit 1
fi

HADES_REPO_ROOT="$repo_dir" SEARXNG_URL="http://127.0.0.1:$port" python3 - <<'PY'
import importlib.util
import json
import os
import sys
import types
from pathlib import Path
from urllib.parse import urlparse

# Public-research uses the optional MCP package at its entrypoint, but this
# smoke calls its pure collector directly and does not need to install MCP.
anyio = types.ModuleType("anyio")
mcp = types.ModuleType("mcp")
mcp_server = types.ModuleType("mcp.server")
lowlevel = types.ModuleType("mcp.server.lowlevel")
lowlevel.Server = lambda *args, **kwargs: None
stdio = types.ModuleType("mcp.server.stdio")
stdio.stdio_server = lambda: None
mcp_types = types.ModuleType("mcp.types")
for name in ("CallToolResult", "ListToolsResult", "TextContent", "Tool"):
    setattr(mcp_types, name, type(name, (), {
        "__init__": lambda self, **kwargs: self.__dict__.update(kwargs),
    }))
sys.modules.update({
    "anyio": anyio,
    "mcp": mcp,
    "mcp.server": mcp_server,
    "mcp.server.lowlevel": lowlevel,
    "mcp.server.stdio": stdio,
    "mcp.types": mcp_types,
})
root = Path(os.environ["HADES_REPO_ROOT"])
sys.path.insert(0, str(root / "integrations/public-research"))

reader_spec = importlib.util.spec_from_file_location(
    "hades_public_page_reader", root / "integrations/web-extract/server.py",
)
reader = importlib.util.module_from_spec(reader_spec)
reader_spec.loader.exec_module(reader)
server_spec = importlib.util.spec_from_file_location(
    "hades_public_research_server", root / "integrations/public-research/server.py",
)
server = importlib.util.module_from_spec(server_spec)
server_spec.loader.exec_module(server)
research_spec = importlib.util.spec_from_file_location(
    "hades_public_research_collector", root / "integrations/public-research/research.py",
)
research = importlib.util.module_from_spec(research_spec)
research_spec.loader.exec_module(research)

live_rows = []
def live_search(query):
    payload = server._search(query)
    rows = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise RuntimeError("pinned SearXNG returned an invalid result list")
    live_rows.extend(rows)
    return {"results": rows[:1]}

cases = (
    ("Example Domain", True),
    ("Python programming language", False),
    ("NASA Artemis I launch date", False),
)
summaries = []
for query, require_page in cases:
    live_rows.clear()
    result = research.research_public_sources(
        query,
        subject_class="public_topic",
        search=live_search,
        read_page=reader.read_public_page,
    )
    pages = result.get("page_reads", [])
    if result.get("status") not in {"SUCCEEDED", "PARTIAL"} or not live_rows or not result.get("sources"):
        raise SystemExit(f"FAIL live search/collection for {query!r}: {result.get('status')}")
    if require_page and not any(page.get("evidence_type") == "STATIC_PAGE" for page in pages):
        raise SystemExit("FAIL stable Example Domain control did not produce a static page")
    records = result["sources"] + pages
    if not all(record.get("retrieved_at_utc", "").endswith("Z") for record in records):
        raise SystemExit(f"FAIL an evidence record for {query!r} is missing its UTC retrieval time")
    summaries.append({
        "query": query,
        "status": result["status"],
        "search_result_count": len(live_rows),
        "evidence_types": [row.get("evidence_type") for row in records],
        "page_hosts": [urlparse(row.get("final_url", "")).hostname for row in pages if row.get("final_url")],
        "limitations": result.get("limitations"),
    })
print("PASS live pinned SearXNG -> collector -> public page reader across three public-topic queries")
print(json.dumps({
    "cases": summaries,
    "utc_timestamps": True,
}, sort_keys=True))
PY

if [[ "${HADES_PUBLIC_RESEARCH_LIVE_AUTH_UI:-0}" == 1 ]]; then
  live_auth_scenario=${HADES_PUBLIC_RESEARCH_LIVE_AUTH_SCENARIO:-live_smoke}
  [[ "$live_auth_scenario" == live_smoke || "$live_auth_scenario" == live_python || "$live_auth_scenario" == live_fact ]] || {
    echo 'FAIL authenticated live scenario must be live_smoke, live_python, or live_fact' >&2
    exit 2
  }
  HADES_PUBLIC_RESEARCH_UI_SCENARIO="$live_auth_scenario" \
    HADES_PUBLIC_RESEARCH_UI_LIVE_SEARXNG_URL="http://127.0.0.1:$port" \
    bash "$repo_dir/scripts/test-public-research-authenticated-ui.sh"
fi
