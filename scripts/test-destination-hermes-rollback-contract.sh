#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
script=$repo_dir/scripts/rollback-destination-hermes-source.sh
[[ -x "$script" ]] || { echo 'FAIL rollback script is not executable'; exit 1; }
bash -n "$script"
for marker in \
  'HADES_ROLLBACK_CONFIRM' \
  'sha256sum -c' \
  'systemctl show -p WorkingDirectory --value hades-hermes.service' \
  'systemctl daemon-reload' \
  'systemctl restart hades-hermes.service' \
  'docker' \
  'hades.local'; do
  case "$marker" in
    docker|hades.local)
      if grep -Fq "$marker" "$script"; then
        echo "FAIL rollback script must not reference $marker" >&2
        exit 1
      fi
      ;;
    *)
      grep -Fq -- "$marker" "$script" || { echo "FAIL rollback marker missing: $marker" >&2; exit 1; }
      ;;
  esac
done
echo 'PASS destination Hermes rollback is confirmation-gated, checksum-verified, and authority-bounded'
