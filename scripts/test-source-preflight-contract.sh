#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
installer="$repo_dir/scripts/install-hades.sh"
grep -q 'tracked_sources=(' "$installer" || { echo 'FAIL preflight source list is missing'; exit 1; }
for source_file in config/versions.env deploy/lldap.compose.yaml deploy/grocy.compose.yaml deploy/agent-zero.compose.yaml hermes/sitecustomize.py integrations/grocy-recipe-authoring/server.py integrations/agent-zero-mcp/server.py webui/hades-theme.css webui/hades-theme.js; do
  grep -q "^    $source_file$" "$installer" || { echo "FAIL preflight source list omits $source_file"; exit 1; }
done
grep -q 'required tracked source is absent' "$installer" || { echo 'FAIL missing-source failure is not explicit'; exit 1; }
echo 'PASS tracked source files are checked before mutation'
