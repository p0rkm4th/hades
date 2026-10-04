#!/usr/bin/env bash
set -Eeuo pipefail

script=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/production-cutover-preflight.sh
[[ -x "$script" ]] || { echo 'FAIL preflight script is not executable'; exit 1; }
[[ -x "$(dirname "$script")/verify-destination-source.sh" ]] || { echo 'FAIL destination source verifier is not executable'; exit 1; }
for marker in \
  'never changes DNS' \
  'owner account' \
  'systemctl is-active hades-hermes.service' \
  'systemctl show -p WorkingDirectory --value hades-hermes.service' \
  'expected_guest|active|$destination_repo' \
  'qm config' \
  '--resolve' \
  'rollback_package_root' \
  'sh -s --' \
  'path "$package_root/rehearsals" -prune' \
  '-type d -perm /077' \
  '-type l -print' \
  'SHA256SUMS' \
  'sha256sum -c' \
  'protected Hindsight production export is present and verified' \
  'rollback manifest has complete required component coverage' \
  'incomplete rollback components:' \
  'CAPTURED_PROTECTED_ENCRYPTION_PENDING' \
  'encrypted custody remains pending:' \
  'HADES_DESTINATION_IP:?' \
  'HADES_DESTINATION_VMID:?' \
  'HADES_DESTINATION_HOSTNAME:?' \
  'HADES_ROLLBACK_HOST:?' \
  'HADES_PROXMOX_HOST:?' \
  'HADES_DESTINATION_REPO:?' \
  'HADES_DESTINATION_SOURCE_REVISION:?' \
  'destination source revision and cleanliness' \
  'laptop source runtime remains preserved'; do
  grep -Fq -- "$marker" "$script" || { echo "FAIL preflight missing: $marker"; exit 1; }
done
if grep -En 'docker (rm|stop|down)|systemctl (disable|stop)|rm -rf|curl .* -X (POST|PUT|DELETE)' "$script"; then
  echo 'FAIL preflight contains a mutating command'; exit 1
fi
echo 'PASS production cutover preflight is read-only and fail-closed'
