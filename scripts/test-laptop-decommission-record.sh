#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
validator="$repo_dir/scripts/validate-laptop-decommission-record.sh"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

cat > "$tmp/valid" <<'EOF'
schema=laptop-production-decommission/v1
production_services_disabled=PASS
production_containers_removed=PASS
allowlisted_cleanup=PASS
ambiguous_material_preserved=PASS
disk_usage_before_after_recorded=PASS
operator_notes=Removed only classified production artifacts after destination acceptance.
EOF

bash "$validator" "$tmp/valid" >/dev/null

cp "$tmp/valid" "$tmp/missing"
sed -i '/allowlisted_cleanup/d' "$tmp/missing"
if bash "$validator" "$tmp/missing" >/dev/null 2>&1; then
  echo 'FAIL missing cleanup field accepted'
  exit 1
fi

cp "$tmp/valid" "$tmp/unknown"
printf '%s\n' 'unexpected=PASS' >> "$tmp/unknown"
if bash "$validator" "$tmp/unknown" >/dev/null 2>&1; then
  echo 'FAIL unknown cleanup field accepted'
  exit 1
fi

cp "$tmp/valid" "$tmp/secret"
printf '%s\n' 'operator_notes=token=should-not-be-recorded' > "$tmp/secret"
if bash "$validator" "$tmp/secret" >/dev/null 2>&1; then
  echo 'FAIL secret-like cleanup record accepted'
  exit 1
fi

echo 'PASS laptop decommission record validation rejects incomplete, unknown, and secret-bearing fixtures'
