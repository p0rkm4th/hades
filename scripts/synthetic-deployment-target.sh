#!/usr/bin/env bash
# Shared opt-in boundary for full-stack reconstruction using synthetic inputs.
set -Eeuo pipefail

mode=${1:-verify}
marker=/etc/hades/synthetic-deployment-test-target
machine_id_file=/etc/machine-id

fail() { echo "FAIL synthetic deployment target: $*" >&2; exit 1; }

case "$mode" in
  authorize)
    [[ $EUID -eq 0 ]] || fail 'run authorization as root on the disposable guest'
    [[ ! -L /etc/hades ]] || fail '/etc/hades must not be a symlink'
    [[ -r "$machine_id_file" ]] || fail 'machine ID is unavailable'
    machine_id=$(<"$machine_id_file")
    [[ "$machine_id" =~ ^[0-9a-fA-F-]{16,64}$ ]] || fail 'machine ID has an unexpected format'
    printf 'This marks this machine for full-stack synthetic HADES tests.\nMachine ID: %s\nType the machine ID to confirm: ' "$machine_id" >&2
    IFS= read -r confirmation || fail 'confirmation was not received'
    [[ "$confirmation" == "$machine_id" ]] || fail 'machine ID confirmation did not match'
    install -d -o root -g root -m 0700 /etc/hades
    [[ ! -L "$marker" ]] || fail 'target marker must not be a symlink'
    tmp=$(mktemp /etc/hades/.synthetic-target.XXXXXX)
    trap 'rm -f "$tmp"' EXIT
    printf 'machine_id=%s\nmode=disposable-synthetic-deployment-only\n' "$machine_id" > "$tmp"
    chown root:root "$tmp"
    chmod 0600 "$tmp"
    mv -f "$tmp" "$marker"
    trap - EXIT
    echo 'PASS this machine is explicitly authorized for synthetic deployment tests'
    ;;
  verify)
    [[ $EUID -eq 0 ]] || fail 'full-stack synthetic mode requires root'
    [[ -d /etc/hades && ! -L /etc/hades ]] || fail '/etc/hades is missing or is a symlink'
    [[ -r "$machine_id_file" ]] || fail 'machine ID is unavailable'
    [[ -f "$marker" && ! -L "$marker" ]] || fail 'target is not explicitly authorized; run scripts/authorize-synthetic-deployment-test.sh on the disposable guest'
    [[ "$(stat -c '%u:%g:%a' "$marker")" == '0:0:600' ]] || fail 'target marker must be root-owned mode 0600'
    machine_id=$(<"$machine_id_file")
    grep -Fxq "machine_id=$machine_id" "$marker" || fail 'target marker belongs to a different machine'
    grep -Fxq 'mode=disposable-synthetic-deployment-only' "$marker" || fail 'target marker has an invalid mode'
    ;;
  *) fail 'internal mode must be authorize or verify' ;;
esac
