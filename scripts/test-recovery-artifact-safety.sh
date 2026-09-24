#!/usr/bin/env bash
set -euo pipefail

# Exercise the recovery validator's path and archive-link safety checks with
# synthetic data only. No production recovery directory is touched.

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
VALIDATOR="$SCRIPT_DIR/check-recovery-artifacts.sh"
fixture=$(mktemp -d)
archive_source=$(mktemp -d)
root_link="$fixture-root-link"
trap 'rm -rf -- "$fixture" "$archive_source" "$root_link"' EXIT

python3 - "$fixture" <<'PY'
import sqlite3
import sys
from pathlib import Path

root = Path(sys.argv[1])
for name in ("open-webui.db", "lldap-users.db", "grocy.db", "hermes-state.db"):
    path = root / name
    connection = sqlite3.connect(path)
    connection.execute("create table marker (ok integer)")
    connection.execute("insert into marker values (1)")
    connection.commit()
    connection.close()
    path.chmod(0o600)
PY

cat > "$fixture/MANIFEST" <<'EOF'
backup_format=1
hades_manifest_version=1
hermes_version=0.14.0
open_webui_version=0.11.1
lldap_image=lldap:test@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
hindsight_image_digest=sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
grocy_image=grocy:test@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
agent_zero_image=agent:test@sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd
actual_version=26.9.0
EOF
chmod 600 "$fixture/MANIFEST"
(cd "$fixture" && sha256sum ./*.db MANIFEST > SHA256SUMS)
chmod 600 "$fixture/SHA256SUMS"
"$VALIDATOR" "$fixture" >/dev/null
printf 'PASS valid recovery metadata accepted\n'

expect_rejected() {
  local label=$1 path=$2
  if "$VALIDATOR" "$path" >/dev/null 2>&1; then
    printf 'FAIL %s was accepted\n' "$label"
    exit 1
  fi
  printf 'PASS %s rejected\n' "$label"
}

sed -i '/  MANIFEST$/d' "$fixture/SHA256SUMS"
expect_rejected 'metadata without sibling checksum coverage' "$fixture"
(cd "$fixture" && sha256sum MANIFEST >> SHA256SUMS)

ln -s "$fixture" "$root_link"
expect_rejected 'symlinked recovery root' "$root_link"

ln -s /tmp "$fixture/tree-link"
expect_rejected 'symlink in recovery tree' "$fixture"
rm -- "$fixture/tree-link"

ln -s /tmp "$archive_source/outside-link"
tar -czf "$fixture/link.tar.gz" -C "$archive_source" outside-link
chmod 600 "$fixture/link.tar.gz"
expect_rejected 'link in recovery archive' "$fixture"

printf 'Recovery artifact safety regressions passed\n'
