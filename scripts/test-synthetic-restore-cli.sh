#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
root=$(mktemp -d)
trap 'rm -rf "$root"' EXIT
checkpoint="$root/checkpoint"
target="$root/target"
mkdir -p "$checkpoint" "$target/open-webui-data" "$target/lldap-data" \
  "$target/grocy-config" "$target/hermes-profile"
chmod 700 "$checkpoint" "$target"

python3 - "$checkpoint" "$target" <<'PY'
import sqlite3, sys
from pathlib import Path
checkpoint, target = map(Path, sys.argv[1:])
files = {
    "open-webui.db": ("open-webui-data/webui.db", "conversation"),
    "lldap-users.db": ("lldap-data/users.db", "identity"),
    "grocy.db": ("grocy-config/grocy.db", "stock"),
    "hermes-state.db": ("hermes-profile/state.db", "session"),
}
for source, (relative, table) in files.items():
    for path in (checkpoint / source, target / relative):
        connection = sqlite3.connect(path)
        connection.execute(f"create table {table} (marker text)")
        connection.execute(f"insert into {table} values (?)", (f"before-{source}",))
        connection.commit()
        connection.close()
        path.chmod(0o600)
(checkpoint / "MANIFEST").write_text("""backup_format=1
hades_manifest_version=1
hermes_version=0.21.2
open_webui_version=0.11.1
lldap_image=lldap:test@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
hindsight_image_digest=sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
grocy_image=grocy:test@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
agent_zero_image=agent:test@sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd
actual_version=26.9.0
""")
(checkpoint / "MANIFEST").chmod(0o600)
PY
(cd "$checkpoint" && sha256sum ./*.db MANIFEST > SHA256SUMS)
chmod 600 "$checkpoint/SHA256SUMS"

"$repo_dir/scripts/hades" restore --path "$checkpoint" --target "$target" --apply --confirm
for db in "$target/open-webui-data/webui.db" "$target/lldap-data/users.db" \
  "$target/grocy-config/grocy.db" "$target/hermes-profile/state.db"; do
  sqlite3 "$db" 'PRAGMA integrity_check;' | grep -qx ok
done
find "$target" -maxdepth 1 -type d -name '.hades-pre-restore-*' -print -quit | grep -q .
echo 'PASS synthetic applied restore preserves rollback checkpoint and SQLite integrity'
