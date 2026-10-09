#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
helper="$repo_dir/scripts/upgrade-hades.sh"
[[ -x "$helper" ]] || { echo 'FAIL upgrade helper is not executable'; exit 1; }
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
cp "$repo_dir/config/operator-inputs.env.example" "$tmp/operator.env"
chmod 600 "$tmp/operator.env"
mkdir -m 700 "$tmp/backup"
for component in lldap grocy agent-zero hermes open-webui hindsight searxng; do
  output=$(bash "$helper" --component "$component" --inputs "$tmp/operator.env" --backup-dir "$tmp/backup")
  grep -q "^PLAN one-component upgrade: $component$" <<<"$output" || { echo "FAIL $component plan missing"; exit 1; }
done
hermes_plan=$(bash "$helper" --component hermes --inputs "$tmp/operator.env" --backup-dir "$tmp/backup")
grep -q '^PLAN candidate version: 0.21.6$' <<<"$hermes_plan" || { echo 'FAIL Hermes candidate metadata missing'; exit 1; }
grep -q '^PLAN candidate source URL: https://github.com/NousResearch/hermes-agent/archive/refs/tags/v0.21.6.tar.gz$' <<<"$hermes_plan" || { echo 'FAIL Hermes candidate source URL missing'; exit 1; }
grep -q '^PLAN candidate source SHA-256: 1ba3500cdbe876bb9d347b3c12f41c591a421293eac58faba23571287dfe1cf8$' <<<"$hermes_plan" || { echo 'FAIL Hermes candidate source checksum missing'; exit 1; }
grep -q '^PLAN candidate source commit: 818c13be1dc4fd28987e1e881a9408224afd4535$' <<<"$hermes_plan" || { echo 'FAIL Hermes candidate source commit missing'; exit 1; }
open_webui_plan=$(bash "$helper" --component open-webui --inputs "$tmp/operator.env" --backup-dir "$tmp/backup")
grep -q '^PLAN candidate version: 0.11.4$' <<<"$open_webui_plan" || { echo 'FAIL Open WebUI candidate version missing'; exit 1; }
grep -q '^PLAN candidate image: ghcr.io/open-webui/open-webui@sha256:332438e079ad23bb11b0ab278b43e7c98b50e8cec14b0840281644e8a289f49f$' <<<"$open_webui_plan" || { echo 'FAIL Open WebUI candidate image missing'; exit 1; }
for component in hermes open-webui hindsight searxng; do
  if HADES_UPGRADE_BACKUP_VERIFIED=1 bash "$helper" --component "$component" --inputs "$tmp/operator.env" --backup-dir "$tmp/backup" --apply >/dev/null 2>&1; then
    echo "FAIL $component private-record apply was accepted"; exit 1
  fi
done
if bash "$helper" --component all --inputs "$tmp/operator.env" --backup-dir "$tmp/backup" >/dev/null 2>&1; then
  echo 'FAIL bulk component upgrade accepted'; exit 1
fi
if bash "$helper" --component grocy --inputs "$tmp/operator.env" --backup-dir "$tmp/backup" --apply >/dev/null 2>&1; then
  echo 'FAIL apply accepted without backup approval/root path'; exit 1
fi
echo 'PASS bounded one-component upgrade helper contract'
