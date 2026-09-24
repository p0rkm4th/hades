#!/usr/bin/env bash
set -Eeuo pipefail

# Plan-first guest provisioning helper. HADES installation still happens
# inside the resulting Fedora/Rocky guest through scripts/install-hades.sh.
api_url=${HADES_PROXMOX_URL:-}
node=${HADES_PROXMOX_NODE:-}
template_vmid=${HADES_PROXMOX_TEMPLATE_VMID:-}
vmid=${HADES_PROXMOX_VMID:-}
name=${HADES_PROXMOX_VM_NAME:-hades}
cores=${HADES_PROXMOX_CORES:-4}
memory_mib=${HADES_PROXMOX_MEMORY_MIB:-16384}
disk_gib=${HADES_PROXMOX_DISK_GIB:-100}
boot_disk=${HADES_PROXMOX_BOOT_DISK:-scsi0}
guest_user=${HADES_GUEST_USER:-hades}
ssh_key_file=${HADES_GUEST_SSH_PUBLIC_KEY_FILE:-}
apply=0

usage() {
  cat <<'EOF'
usage: proxmox-bootstrap.sh [options]

Plan a supported HADES guest (default) or provision it with --apply.
Options may also be supplied through the HADES_PROXMOX_* environment variables.
  --api-url URL             Proxmox API root ending in /api2/json
  --node NAME               target Proxmox node
  --template-vmid ID        cloud-init-capable VM template to clone
  --vmid ID                 new VM ID
  --name NAME               new VM name (default: hades)
  --cores N                 vCPUs (default: 4)
  --memory-mib N            memory (default: 16384)
  --disk-gib N              requested guest disk size (default: 100)
  --boot-disk NAME          cloned boot disk to resize (default: scsi0)
  --ssh-key-file FILE       public SSH key supplied to cloud-init
  --apply                   perform the explicit clone/configure API calls
EOF
}

while (($#)); do
  case "$1" in
    --api-url) api_url=${2:?--api-url needs a URL}; shift 2 ;;
    --node) node=${2:?--node needs a node}; shift 2 ;;
    --template-vmid) template_vmid=${2:?--template-vmid needs an ID}; shift 2 ;;
    --vmid) vmid=${2:?--vmid needs an ID}; shift 2 ;;
    --name) name=${2:?--name needs a value}; shift 2 ;;
    --cores) cores=${2:?--cores needs a number}; shift 2 ;;
    --memory-mib) memory_mib=${2:?--memory-mib needs a number}; shift 2 ;;
    --disk-gib) disk_gib=${2:?--disk-gib needs a number}; shift 2 ;;
    --boot-disk) boot_disk=${2:?--boot-disk needs a disk name}; shift 2 ;;
    --ssh-key-file) ssh_key_file=${2:?--ssh-key-file needs a file}; shift 2 ;;
    --apply) apply=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "FAIL unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

fail() { echo "FAIL $*" >&2; exit 1; }
[[ "$api_url" =~ ^https://[^[:space:]]+/api2/json$ ]] || fail 'API URL must be HTTPS and end in /api2/json'
[[ "$node" =~ ^[A-Za-z0-9._-]+$ ]] || fail 'node must contain only letters, digits, dot, underscore, or dash'
[[ "$template_vmid" =~ ^[0-9]+$ ]] || fail 'template VMID must be numeric'
[[ "$vmid" =~ ^[0-9]+$ ]] || fail 'new VMID must be numeric'
[[ "$template_vmid" != "$vmid" ]] || fail 'new VMID must differ from template VMID'
[[ "$name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || fail 'VM name contains unsupported characters'
[[ "$guest_user" =~ ^[a-z_][a-z0-9_-]*$ ]] || fail 'guest user contains unsupported characters'
[[ "$cores" =~ ^[1-9][0-9]*$ && "$cores" -le 64 ]] || fail 'cores must be between 1 and 64'
[[ "$memory_mib" =~ ^[1-9][0-9]*$ && "$memory_mib" -ge 2048 ]] || fail 'memory must be at least 2048 MiB'
[[ "$disk_gib" =~ ^[1-9][0-9]*$ && "$disk_gib" -ge 40 ]] || fail 'disk must be at least 40 GiB'
[[ "$boot_disk" =~ ^[A-Za-z][A-Za-z0-9-]*[0-9]+$ ]] || fail 'boot disk must be a Proxmox disk name'
[[ -n "$ssh_key_file" && -f "$ssh_key_file" && ! -L "$ssh_key_file" ]] || fail 'SSH public-key file is missing or linked'
key_mode=$(stat -c '%a' "$ssh_key_file")
[[ "$key_mode" == 600 || "$key_mode" == 640 || "$key_mode" == 644 ]] || fail 'SSH public-key file must be mode 0600, 0640, or 0644'
grep -Eq '^ssh-(ed25519|rsa|ecdsa) [A-Za-z0-9+/=]+' "$ssh_key_file" || fail 'SSH public-key file is not a supported single-line public key'

echo "PLAN Proxmox node=$node template_vmid=$template_vmid vmid=$vmid name=$name cores=$cores memory_mib=$memory_mib disk_gib=$disk_gib boot_disk=$boot_disk guest_user=$guest_user"
echo 'PLAN guest OS must be Fedora Server 44 or Rocky Linux 9/10 with systemd and cloud-init'
echo 'PLAN after provisioning: clone repository, provide operator inputs, run install-hades.sh --preflight, then install/doctor/validate'
((apply)) || exit 0

token_id=${HADES_PROXMOX_TOKEN_ID:-}
token_secret=${HADES_PROXMOX_TOKEN_SECRET:-}
[[ -n "$token_id" && -n "$token_secret" ]] || fail '--apply requires HADES_PROXMOX_TOKEN_ID and HADES_PROXMOX_TOKEN_SECRET'
[[ "$token_id" != *$'\n'* && "$token_secret" != *$'\n'* ]] || fail 'Proxmox token values must not contain newlines'
command -v curl >/dev/null 2>&1 || fail 'curl is required for --apply'

curl_config=$(mktemp)
trap 'rm -f -- "$curl_config"' EXIT
chmod 600 "$curl_config"
printf 'header = "Authorization: PVEAPIToken=%s=%s"\n' "$token_id" "$token_secret" > "$curl_config"
base="$api_url"
status_url="$base/nodes/$node/qemu/$vmid/status/current"
if curl --config "$curl_config" --fail --silent --show-error --output /dev/null "$status_url" 2>/dev/null; then
  fail "VMID already exists: $vmid"
fi
clone_url="$base/nodes/$node/qemu/$template_vmid/clone"
curl --config "$curl_config" --fail --silent --show-error --output /dev/null \
  --data "newid=$vmid" --data-urlencode "name=$name" --data 'full=1' \
  --data-urlencode "target=$node" "$clone_url" || fail 'Proxmox clone request failed; inspect the target before retrying'
config_url="$base/nodes/$node/qemu/$vmid/config"
curl --config "$curl_config" --fail --silent --show-error --output /dev/null \
  --data "cores=$cores" --data "memory=$memory_mib" --data 'ipconfig0=ip=dhcp' \
  --data-urlencode "ciuser=$guest_user" --data-urlencode "sshkeys@$ssh_key_file" \
  "$config_url" || fail 'Proxmox VM configuration failed after clone; inspect the VM before retrying'
resize_url="$base/nodes/$node/qemu/$vmid/resize"
curl --config "$curl_config" --fail --silent --show-error --output /dev/null \
  --data-urlencode "disk=$boot_disk" --data-urlencode "size=${disk_gib}G" \
  "$resize_url" || fail 'Proxmox disk resize failed after clone; inspect the VM before retrying'
echo 'PASS Proxmox guest provisioned; continue inside the guest with the canonical HADES installer'
