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
