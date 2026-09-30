#!/usr/bin/env bash
set -Eeuo pipefail

# Restore only the preserved Hermes systemd unit on a destination host.
# This does not touch DNS, application data, containers, or the laptop.

destination_ssh=${1:?usage: rollback-destination-hermes-source.sh SSH ROLLBACK_DIR CANDIDATE_DIR CANDIDATE_REVISION PRIOR_WORKDIR}
rollback_dir=${2:?usage: rollback-destination-hermes-source.sh SSH ROLLBACK_DIR CANDIDATE_DIR CANDIDATE_REVISION PRIOR_WORKDIR}
candidate_dir=${3:?usage: rollback-destination-hermes-source.sh SSH ROLLBACK_DIR CANDIDATE_DIR CANDIDATE_REVISION PRIOR_WORKDIR}
candidate_revision=${4:?usage: rollback-destination-hermes-source.sh SSH ROLLBACK_DIR CANDIDATE_DIR CANDIDATE_REVISION PRIOR_WORKDIR}
prior_workdir=${5:?usage: rollback-destination-hermes-source.sh SSH ROLLBACK_DIR CANDIDATE_DIR CANDIDATE_REVISION PRIOR_WORKDIR}

[[ "${HADES_ROLLBACK_CONFIRM:-}" == 1 ]] || {
  echo 'FAIL set HADES_ROLLBACK_CONFIRM=1 to authorize the destination-only rollback' >&2
  exit 2
}
[[ "$candidate_revision" =~ ^[0-9a-f]{40}$ ]] || {
  echo 'FAIL candidate revision must be a full commit id' >&2
  exit 2
}
[[ "$rollback_dir" == /* && "$candidate_dir" == /* && "$prior_workdir" == /* ]] || {
  echo 'FAIL rollback and working-directory inputs must be absolute paths' >&2
  exit 2
}

ssh -o BatchMode=yes -o ConnectTimeout=5 "$destination_ssh" \
  bash -s -- "$rollback_dir" "$candidate_dir" "$candidate_revision" "$prior_workdir" <<'REMOTE_ROLLBACK'
set -Eeuo pipefail
rollback_dir=$1
candidate_dir=$2
candidate_revision=$3
prior_workdir=$4
unit=/etc/systemd/system/hades-hermes.service
backup_unit="$rollback_dir/hades-hermes.service"
checksum="$rollback_dir/hades-hermes.service.sha256"

test -d "$candidate_dir/.git"
test "$(git -C "$candidate_dir" rev-parse HEAD)" = "$candidate_revision"
test -z "$(git -C "$candidate_dir" status --porcelain --untracked-files=all)"
test "$(sudo -n systemctl show -p WorkingDirectory --value hades-hermes.service)" = "$candidate_dir"
test -s "$backup_unit" && test -s "$checksum"
(cd "$rollback_dir" && sha256sum -c "$(basename "$checksum")" >/dev/null)
grep -Fqx "WorkingDirectory=$prior_workdir" "$backup_unit"

current=$(mktemp)
trap 'rm -f "$current"' EXIT
sudo -n cat "$unit" > "$current"
restore_current() {
  sudo -n install -o root -g root -m 0600 "$current" "$unit"
  sudo -n systemctl daemon-reload
  sudo -n systemctl restart hades-hermes.service || true
}
trap restore_current ERR

sudo -n install -o root -g root -m 0600 "$backup_unit" "$unit"
sudo -n systemctl daemon-reload
sudo -n systemctl restart hades-hermes.service
sleep 2
test "$(sudo -n systemctl is-active hades-hermes.service)" = active
test "$(sudo -n systemctl show -p WorkingDirectory --value hades-hermes.service)" = "$prior_workdir"
trap - ERR
printf 'PASS destination Hermes source rollback to %s\n' "$prior_workdir"
REMOTE_ROLLBACK
