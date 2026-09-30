#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
installer="$repo_dir/scripts/install-hades.sh"
grep -q 'tracked_sources=(' "$installer" || { echo 'FAIL preflight source list is missing'; exit 1; }
for source_file in config/versions.env deploy/lldap.compose.yaml deploy/grocy.compose.yaml deploy/agent-zero.compose.yaml scripts/sync-agent-zero-client-auth.sh hermes/sitecustomize.py integrations/grocy-recipe-authoring/server.py integrations/agent-zero-mcp/server.py integrations/public-research/server.py integrations/public-research/research.py webui/hades-theme.css webui/hades-theme.js webui/finance-upload.js webui/receipt-upload.js webui/task_notification_compat.py; do
  grep -q "^    $source_file$" "$installer" || { echo "FAIL preflight source list omits $source_file"; exit 1; }
done
grep -q 'required tracked source is absent' "$installer" || { echo 'FAIL missing-source failure is not explicit'; exit 1; }
grep -q '"\$HADES_HERMES_PROFILE"' "$installer" || { echo 'FAIL Hermes profile parent is not covered by filesystem preflight'; exit 1; }
grep -q '^validate_hermes_working_directory()' "$installer" || { echo 'FAIL Hermes working-directory accessibility check is missing'; exit 1; }
grep -q '^  validate_hermes_working_directory$' "$installer" || { echo 'FAIL Hermes working-directory check is not invoked by preflight'; exit 1; }
grep -q 'Hermes runtime cannot traverse or read its working directory' "$installer" || { echo 'FAIL Hermes working-directory failure is not actionable'; exit 1; }
echo 'PASS tracked source files are checked before mutation'
