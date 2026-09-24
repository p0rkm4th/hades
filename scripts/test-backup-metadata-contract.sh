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
grep -Fq 'sha256sum ./*.db MANIFEST > SHA256SUMS' "$helper" || { echo 'FAIL backup metadata is not checksummed'; exit 1; }
for field in lldap_image hindsight_image_digest grocy_image agent_zero_image actual_version; do
  grep -q "^$field=" "$helper" || { echo "FAIL backup metadata omits $field"; exit 1; }
done
grep -q 'metadata_count=0' "$repo_dir/scripts/check-recovery-artifacts.sh" || { echo 'FAIL recovery validator omits metadata validation'; exit 1; }
grep -q 'metadata_checksum=' "$repo_dir/scripts/check-recovery-artifacts.sh" || { echo 'FAIL recovery validator does not bind metadata to sibling checksums'; exit 1; }
grep -q 'backup destination must not be a symlink' "$helper" || { echo 'FAIL backup helper follows symlinked destination'; exit 1; }
echo 'PASS SQLite backups carry authoritative version metadata'
