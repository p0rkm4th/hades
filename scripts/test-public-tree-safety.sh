#!/usr/bin/env bash
set -euo pipefail

# Fast current-tree guard. The history audit remains the authoritative check
# for every reachable commit; this catches new leaks before that slower scan.
tree_ref="${1:-HEAD}"
private_ipv4_pattern='(^|[^0-9])(192\.168\.[0-9]{1,3}\.[0-9]{1,3}|10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|172\.(1[6-9]|2[0-9]|3[01])\.[0-9]{1,3}\.[0-9]{1,3})([^0-9]|$)'
if ! git rev-parse --verify "$tree_ref^{commit}" >/dev/null 2>&1; then
  printf 'FAIL selected tree reference is not a commit (details redacted)\n' >&2
  exit 2
fi

address_fixture=$(printf '%s\n' \
  '10.24.5 is a three-part package version' \
  '10.24.5.6 is private IPv4' \
  '172.16.4.2 is private IPv4' \
  '192.168.3.8 is private IPv4' \
  '8.8.8.8 is public IPv4' | grep -E "$private_ipv4_pattern" || true)
[[ "$(printf '%s\n' "$address_fixture" | awk 'NF {count++} END {print count+0}')" == 3 ]] || {
  printf 'FAIL private IPv4 pattern does not distinguish four-octet addresses\n' >&2
  exit 2
}
printf 'PASS private IPv4 guard requires four octets\n'

# These are container-internal application data paths from upstream images,
# not host checkout or operator home directories. Keep the exception narrow to
# the known Hindsight and n8n data locations.
matches="$(git grep -I -n -E "/home/[[:alnum:]_.-]+/|/Users/[[:alnum:]_.-]+/|/mnt/shared/[[:alnum:]_.-]+|/var/tmp/hades-[[:alnum:]_.-]+|$private_ipv4_pattern|tail[a-z0-9-]+\.ts\.net|(^|[^[:alnum:]_.-])([[:alnum:]-]+\.)+local([^[:alnum:]_.-]|$)|(^|[^[:alnum:]])([[:xdigit:]]{2}:){5}[[:xdigit:]]{2}([^[:alnum:]]|$)" "$tree_ref" -- . ':(exclude)scripts/public-history-audit.sh' ':(exclude)scripts/test-public-tree-safety.sh' | grep -vE '/home/[[:alnum:]_.-]+/\.(pg0|n8n|cache)(/|[^[:alnum:]_-]|$)' | grep -vF '172.17.0.1' | grep -vF '172.18.0.1' | grep -vF 'threading.local' | grep -vF 'self.local' || true)"
fail=0
if [ -n "$matches" ]; then
  match_count="$(printf '%s\n' "$matches" | awk 'END { print NR }')"
  printf 'FAIL private path, address, or tailnet hostname in selected tree (findings=%s; values and paths redacted)\n' "$match_count" >&2
  fail=1
else
  printf 'PASS private paths, addresses, and tailnet hostnames absent\n'
fi
credential_paths="$(git ls-tree -r --name-only "$tree_ref" | grep -Ei '(^|/)(\.env|.*\.(sqlite|db|pem|p12|key)|credentials|secrets)(\.|$|/)' || true)"
if [ -n "$credential_paths" ]; then
  credential_path_count="$(printf '%s\n' "$credential_paths" | awk 'END { print NR }')"
  printf 'FAIL credential-like tracked artifact path in selected tree (findings=%s; paths redacted)\n' "$credential_path_count" >&2
  fail=1
else
  printf 'PASS credential-like tracked artifact paths absent\n'
fi
literal_guest_ids="$(git grep -I -n -E '(^|[^[:alnum:]_])(VMID|VM|CT)[[:space:]#:-]*[0-9]{3,}([^[:alnum:]_]|$)' "$tree_ref" -- README.md CAMPAIGN_STATE.md docs acceptance 2>/dev/null || true)"
if [ -n "$literal_guest_ids" ]; then
  guest_id_count="$(printf '%s\n' "$literal_guest_ids" | awk 'END { print NR }')"
  printf 'FAIL literal infrastructure guest identifiers in public prose (findings=%s; values and paths redacted)\n' "$guest_id_count" >&2
  fail=1
else
  printf 'PASS literal infrastructure guest identifiers absent from public prose\n'
fi
if (( fail == 0 )); then
  printf 'PASS current public tree safety\n'
  exit 0
fi
exit 1
