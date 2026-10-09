#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
helper="$repo_dir/scripts/backup-sqlite-state.sh"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir "$tmp/real"
ln -s "$tmp/real" "$tmp/link"
if "$helper" "$tmp/link" >/dev/null 2>&1; then
  echo 'FAIL backup helper accepted a symlinked destination'; exit 1
fi
echo 'PASS symlinked backup destination rejected'
grep -q 'source "$repo_dir/config/versions.env"' "$helper" || { echo 'FAIL backup helper omits authoritative manifest'; exit 1; }
grep -q 'backup_format=1' "$helper" || { echo 'FAIL backup metadata format is missing'; exit 1; }
grep -Fq 'sha256sum "${backup_files[@]##*/}" > SHA256SUMS' "$helper" || { echo 'FAIL backup metadata does not checksum all state artifacts'; exit 1; }
grep -Fq 'open-webui-auth-state.rdb' "$helper" || { echo 'FAIL backup helper omits persistent Open WebUI revocation state'; exit 1; }
grep -Fq 'open_webui_valkey_image=$HADES_OPEN_WEBUI_VALKEY_IMAGE' "$helper" || { echo 'FAIL backup metadata omits the Valkey image pin'; exit 1; }
grep -Fq 'HADES_EPSILON_PHASE3_STATE_FILE' "$helper" || { echo 'FAIL backup helper omits isolated Phase 3 state'; exit 1; }
grep -Fq 'lldap_container=${HADES_LLDAP_CONTAINER:-hades-lldap-production}' "$helper" || { echo 'FAIL backup helper does not support reconstructed LLDAP container names'; exit 1; }
grep -Fq 'source.backup(destination)' "$helper" || { echo 'FAIL backup helper does not use SQLite online backup API'; exit 1; }
grep -Fq 'PRAGMA integrity_check' "$helper" || { echo 'FAIL backup helper does not validate SQLite integrity'; exit 1; }
if grep -Eq '(^|[[:space:]])sqlite3[[:space:]]' "$helper"; then echo 'FAIL backup helper depends on the host sqlite3 CLI'; exit 1; fi
grep -Fq 'mode=ro&immutable=1' "$helper" || { echo 'FAIL backup helper does not validate snapshots without mutation'; exit 1; }
grep -Fq 'mode=ro&immutable=1' "$repo_dir/scripts/check-recovery-artifacts.sh" || { echo 'FAIL recovery validator does not open SQLite snapshots immutably'; exit 1; }
grep -Fq 'phase3_state=$phase3_state' "$helper" || { echo 'FAIL backup manifest omits Phase 3 state presence'; exit 1; }
for field in lldap_image hindsight_image_digest grocy_image agent_zero_image actual_version; do
  grep -q "^$field=" "$helper" || { echo "FAIL backup metadata omits $field"; exit 1; }
done
grep -q 'metadata_count=0' "$repo_dir/scripts/check-recovery-artifacts.sh" || { echo 'FAIL recovery validator omits metadata validation'; exit 1; }
grep -q 'metadata_checksum=' "$repo_dir/scripts/check-recovery-artifacts.sh" || { echo 'FAIL recovery validator does not bind metadata to sibling checksums'; exit 1; }
grep -q 'backup destination must not be a symlink' "$helper" || { echo 'FAIL backup helper follows symlinked destination'; exit 1; }
echo 'PASS SQLite backups carry authoritative version metadata'
