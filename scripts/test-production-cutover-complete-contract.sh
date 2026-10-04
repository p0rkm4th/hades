#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
script="$repo_dir/scripts/verify-production-cutover-complete.sh"

[[ -x "$script" ]] || { echo 'FAIL post-cutover verifier is not executable'; exit 1; }
for marker in \
  'real destination acceptance record' \
  'HADES_DESTINATION_SSH:?' \
  'HADES_DESTINATION_HOSTNAME:-hades-core' \
  'destination SSH identity is the expected homelab guest' \
  'authoritative hades.example.invalid reaches destination health' \
  'independent rollback package remains protected and verifiable' \
  'rollback_package_root' \
  'sh -s --' \
  'path "$package_root/rehearsals" -prune' \
  '-type d -perm /077' \
  '-type l -print' \
  'encryption_pending_allowed' \
  'protected Hindsight production export remains verified' \
  'rollback manifest has complete required component coverage' \
  'is-enabled hades-hermes.service' \
  'laptop production containers are absent' \
  'laptop cleanup evidence is complete and secret-free' \
  'development and infrastructure checkouts remain preserved' \
  'made no changes'; do
  grep -Fq -- "$marker" "$script" || { echo "FAIL post-cutover verifier missing: $marker"; exit 1; }
done
if grep -En 'docker (rm|stop|down)|systemctl (disable|stop)|rm -rf|curl .* -X (POST|PUT|DELETE)|resolv|dnsmasq|iptables' "$script"; then
  echo 'FAIL post-cutover verifier contains a mutating or routing operation'
  exit 1
fi
echo 'PASS post-cutover verifier is read-only and checks the final migration invariant'
