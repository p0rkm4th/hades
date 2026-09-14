#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
helper="$repo_dir/scripts/proxmox-bootstrap.sh"
[[ -x "$helper" ]] || { echo 'FAIL Proxmox helper is not executable'; exit 1; }
key=$(mktemp)
trap 'rm -f -- "$key"' EXIT
printf 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFakeSyntheticKey dogfood\n' > "$key"
chmod 600 "$key"
output=$(bash "$helper" --api-url https://proxmox.example.test:8006/api2/json \
  --node pve01 --template-vmid 9000 --vmid 9010 --disk-gib 80 \
  --boot-disk scsi0 --ssh-key-file "$key")
grep -q '^PLAN Proxmox node=pve01 template_vmid=9000 vmid=9010 .*disk_gib=80 boot_disk=scsi0' <<<"$output" || {
  echo 'FAIL helper plan is incomplete'; exit 1;
}
grep -q 'install-hades.sh --preflight' <<<"$output" || { echo 'FAIL helper omits guest handoff'; exit 1; }
if grep -q 'PVEAPIToken\|TOKEN_SECRET' <<<"$output"; then
  echo 'FAIL helper plan exposed credential material'; exit 1
fi
if bash "$helper" --api-url http://proxmox.example.test/api2/json --node pve01 \
    --template-vmid 9000 --vmid 9010 --ssh-key-file "$key" >/dev/null 2>&1; then
  echo 'FAIL non-HTTPS Proxmox URL accepted'; exit 1
fi
if bash "$helper" --api-url https://proxmox.example.test/api2/json --node pve01 \
    --template-vmid 9000 --vmid 9010 --ssh-key-file "$key" --apply >/dev/null 2>&1; then
  echo 'FAIL apply accepted without token inputs'; exit 1
fi
echo 'PASS Proxmox bootstrap plan and guest-handoff contract'
