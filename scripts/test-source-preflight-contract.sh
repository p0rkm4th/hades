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
grep -q 'Hermes working-directory homelab package module set differs from the tracked source' "$installer" || { echo 'FAIL Hermes working-directory package closure check is missing'; exit 1; }

# Execute the installer's actual working-directory validator against synthetic
# trees to prove incomplete or mixed homelab packages fail before installation.
tmp_root=$(mktemp -d)
trap 'find "$tmp_root" -depth -mindepth 1 -delete 2>/dev/null || true; rmdir "$tmp_root" 2>/dev/null || true' EXIT
chmod 0755 "$tmp_root"
working_tree="$tmp_root/working"
mkdir -p "$working_tree/hermes" "$working_tree/integrations"
cp "$repo_dir/hermes/config.yaml.example" "$working_tree/hermes/config.yaml.example"
cp "$repo_dir/integrations/homelab_views.py" "$working_tree/integrations/homelab_views.py"
cp -a "$repo_dir/integrations/homelab-readonly" "$working_tree/integrations/homelab-readonly"
function_source=$(sed -n '/^validate_hermes_working_directory() {/,/^}/p' "$installer")
validate_fixture_working_directory() (
  fail() { echo "FAIL $*" >&2; exit 1; }
  repo_dir="$repo_dir"
  HADES_HERMES_WORKING_DIRECTORY="$working_tree"
  HADES_HERMES_RUNTIME_USER=nyx-preflight-nonexistent-account
  eval "$function_source"
  validate_hermes_working_directory
)
validate_fixture_working_directory
mv "$working_tree/integrations/homelab-readonly/server.py" \
  "$working_tree/integrations/homelab-readonly/server.py.partial"
if output=$(validate_fixture_working_directory 2>&1); then
  echo 'FAIL incomplete homelab package passed working-directory preflight'
  exit 1
fi
grep -q 'module set differs from the tracked source' <<<"$output" || {
  echo 'FAIL incomplete homelab package produced no actionable closure error'
  exit 1
}
mv "$working_tree/integrations/homelab-readonly/server.py.partial" \
  "$working_tree/integrations/homelab-readonly/server.py"
printf '# mismatched synthetic runtime module\n' > "$working_tree/integrations/homelab-readonly/server.py"
if output=$(validate_fixture_working_directory 2>&1); then
  echo 'FAIL mismatched homelab package passed working-directory preflight'
  exit 1
fi
grep -q 'package differs from tracked source: server.py' <<<"$output" || {
  echo 'FAIL mismatched homelab package produced no actionable source-identity error'
  exit 1
}
cp "$repo_dir/integrations/homelab-readonly/server.py" \
  "$working_tree/integrations/homelab-readonly/server.py"
package_mode=$(stat -c '%a' "$working_tree/integrations/homelab-readonly")
chmod 0700 "$working_tree/integrations/homelab-readonly"
if output=$(validate_fixture_working_directory 2>&1); then
  echo 'FAIL untraversable homelab package passed working-directory preflight'
  exit 1
fi
grep -q 'package directory is not traversable' <<<"$output" || {
  echo 'FAIL untraversable homelab package produced no actionable permission error'
  exit 1
}
chmod "$package_mode" "$working_tree/integrations/homelab-readonly"
echo 'PASS tracked source files are checked before mutation'
