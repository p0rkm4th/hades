#!/usr/bin/env bash
set -euo pipefail
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
printf '# synthetic overlay fixture\npass\n' > "$tmp/overlay"
printf 'manifest fixture\n' > "$tmp/manifest"
printf 'task store fixture\n' > "$tmp/task-store.py"
printf 'epsilon package fixture\n' > "$tmp/phase3-runtime-manifest.json"
source_repo="$tmp/source"
infra_repo="$tmp/infra"
mkdir -p "$tmp/bin" "$tmp/active" "$source_repo/integrations/task" "$source_repo/integrations/grocy-mcp" "$source_repo/integrations/homelab-readonly" "$source_repo/config" "$infra_repo"
printf 'task store fixture\n' > "$source_repo/integrations/task/store.py"
printf '# synthetic Grocy launcher source\n' > "$source_repo/integrations/grocy-mcp/launch.py"
printf '# synthetic homelab server source\n' > "$source_repo/integrations/homelab-readonly/server.py"
printf '# synthetic homelab view source\n' > "$source_repo/integrations/homelab-readonly/view.py"
printf 'manifest fixture\n' > "$source_repo/config/reconstruction-manifest.json"
git -C "$source_repo" init -q
git -C "$source_repo" config user.email fixture@example.invalid
git -C "$source_repo" config user.name fixture
git -C "$source_repo" add integrations/task/store.py integrations/grocy-mcp/launch.py integrations/homelab-readonly/server.py integrations/homelab-readonly/view.py config/reconstruction-manifest.json
git -C "$source_repo" commit -qm fixture
hades_sha=$(git -C "$source_repo" rev-parse HEAD)
printf 'infra fixture\n' > "$infra_repo/infra.txt"
git -C "$infra_repo" init -q
git -C "$infra_repo" config user.email fixture@example.invalid
git -C "$infra_repo" config user.name fixture
git -C "$infra_repo" add infra.txt
git -C "$infra_repo" commit -qm fixture
infra_sha=$(git -C "$infra_repo" rev-parse HEAD)
cp "$tmp/overlay" "$tmp/active/sitecustomize.py"
cat > "$tmp/active/hermes" <<'SH'
#!/usr/bin/env bash
if [[ "${1:-}" == '--version' ]]; then
  printf 'Hermes Agent 0.21.2\n'
else
  exec -a "$0" python3 -c 'import time; time.sleep(60)' "$@"
fi
SH
chmod 700 "$tmp/active/hermes"
mkdir -p "$tmp/hermes-home/profiles/hades"
printf 'mcp_servers:\n  grocy:\n    enabled: true\n    command: python3\n    args:\n      - "${HADES_HERMES_WORKING_DIRECTORY}/integrations/grocy-mcp/launch.py"\n    test_private_value: synthetic-not-for-provenance\n  receipt-ocr-gateway:\n    enabled: true\n    url: "${HADES_TEST_PRIVATE_ENDPOINT}"\n' > "$tmp/hermes-home/profiles/hades/config.yaml"
python3 - "$PWD/scripts/write-deployed-provenance.py" "$tmp" <<'PY'
import importlib.util
import sys
spec = importlib.util.spec_from_file_location("deployed_provenance", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.profile_args('    args: ["one.py", "two"]\n', "inline") == ["one.py", "two"]
assert module.profile_args('    args:\n      - "one.py"\n      - "two"\n    env:\n      TEST: ignored\n', "block") == ["one.py", "two"]
try:
    module.profile_args('    args:\n      key: value\n', "unsupported")
except SystemExit:
    pass
else:
    raise AssertionError("unsupported args mapping should fail closed")

from pathlib import Path
target = Path(sys.argv[2]) / "racing-file"
assert target.parent == Path(sys.argv[2])
target.write_bytes(b"a" * (1024 * 1024 + 16))
original_read = module.os.read
changed = False
def replace_during_read(fd, size):
    global changed
    data = original_read(fd, size)
    if not changed:
        changed = True
        target.write_bytes(b"b" * (1024 * 1024 + 16))
    return data
module.os.read = replace_during_read
try:
    module.read_regular_file(target, "stable read required")
except SystemExit:
    pass
else:
    raise AssertionError("file mutation during snapshot read was accepted")
finally:
    module.os.read = original_read
PY
python3 - "$PWD/scripts/write-deployed-provenance.py" "$source_repo" "$tmp" <<'PY'
import importlib.util
import json
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

script, source, temp = map(Path, sys.argv[1:])
spec = importlib.util.spec_from_file_location("deployed_provenance", script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
source_package = source / "integrations/homelab-readonly"
package = temp / "external-homelab-package"
shutil.copytree(source_package, package)
profile = temp / "homelab-profile.yaml"
def write_profile(server_path):
    profile.write_text(
        "mcp_servers:\n"
        "  homelab-readonly:\n"
        "    enabled: true\n"
        "    command: python3\n"
        "    args:\n"
        f"      - {server_path}\n",
        encoding="utf-8",
    )

write_profile(package / "server.py")
rows, first_digest = module.mcp_runtime_identity(profile, {}, source, package)
assert len(rows) == 1
row = rows[0]
expected_files = [
    {"path": name, "sha256": hashlib.sha256((package / name).read_bytes()).hexdigest()}
    for name in ("server.py", "view.py")
]
expected_package_digest = hashlib.sha256(
    json.dumps(expected_files, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
assert row == {
    "enabled": True,
    "name": "homelab-readonly",
    "transport": "stdio-package-source",
    "source": "integrations/homelab-readonly",
    "source_tree": subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD:integrations/homelab-readonly"], text=True
    ).strip(),
    "package_tree_sha256": expected_package_digest,
    "file_count": 2,
}
assert len(first_digest) == 64
assert "/tmp/" not in json.dumps(rows)
assert module.mcp_runtime_identity(profile, {}, source, package)[1] == first_digest

def must_reject(label):
    try:
        module.mcp_runtime_identity(profile, {}, source, package)
    except SystemExit:
        return
    raise AssertionError(f"external homelab package accepted {label}")

(package / "view.py").write_text("tampered\n", encoding="utf-8")
must_reject("modified module")
shutil.copy(source_package / "view.py", package / "view.py")
(package / "view.py").unlink()
must_reject("missing module")
shutil.copy(source_package / "view.py", package / "view.py")
(package / "extra.py").write_text("unexpected\n", encoding="utf-8")
must_reject("extra module")
(package / "extra.py").unlink()
(package / "view.py").chmod(0o666)
must_reject("group/world-writable source file")
shutil.copy(source_package / "view.py", package / "view.py")
(package / "linked.py").symlink_to(package / "view.py")
must_reject("symlink")
(package / "linked.py").unlink()
original_root_mode = package.stat().st_mode & 0o777
package.chmod(0o770)
must_reject("group-writable package root")
package.chmod(original_root_mode)
write_profile(temp / "wrong" / "server.py")
must_reject("profile entrypoint outside package root")
linked_root = temp / "linked-package-root"
linked_root.symlink_to(package, target_is_directory=True)
write_profile(linked_root / "server.py")
must_reject("symlinked package root")
write_profile(package / "server.py")
unused_profile = temp / "unused-profile.yaml"
unused_profile.write_text("mcp_servers:\n  grocy:\n    enabled: false\n", encoding="utf-8")
try:
    module.mcp_runtime_identity(unused_profile, {}, source, package)
except SystemExit:
    pass
else:
    raise AssertionError("unused homelab package root should fail closed")
write_profile(package / "server.py")
profile.write_text(
    "mcp_servers:\n"
    "  grocy:\n"
    "    enabled: true\n"
    "    command: python3\n"
    f"    args: [\"{package / 'server.py'}\"]\n",
    encoding="utf-8",
)
try:
    module.mcp_runtime_identity(profile, {}, source, package)
except SystemExit:
    pass
else:
    raise AssertionError("external non-homelab MCP was accepted in package mode")
profile.write_text(
    "mcp_servers:\n"
    "  homelab-readonly:\n"
    "    enabled: true\n"
    "    url: https://homelab.example.invalid/mcp\n",
    encoding="utf-8",
)
try:
    module.mcp_runtime_identity(profile, {}, source)
except SystemExit:
    pass
else:
    raise AssertionError("HTTP homelab registration bypassed package identity")
print("PASS external homelab package identity is exact, opt-in, and path-free")
PY
module_root="$tmp/module-root"
mkdir -p "$module_root/hermes_cli" "$module_root/hermes_agent-0.21.2.dist-info"
cat > "$module_root/hermes_cli/main.py" <<'PY'
import time
time.sleep(60)
PY
cat > "$module_root/hermes_agent-0.21.2.dist-info/METADATA" <<'EOF'
Metadata-Version: 2.1
Name: hermes-agent
Version: 0.21.2
EOF
ln -s "$(command -v python3)" "$tmp/active/python"
export HADES_HERMES_WORKING_DIRECTORY="$source_repo"
export HADES_TEST_PRIVATE_ENDPOINT='http://private.example.invalid:8765/mcp'
env PYTHONPATH="$tmp/active:$module_root" \
  HERMES_HOME="$tmp/hermes-home" \
  HADES_HERMES_EXECUTABLE="$tmp/active/hermes" \
  "$tmp/active/hermes" -p hades service-runner &
service_pid=$!
sleep 0.05
export HADES_TEST_MAIN_PID="$service_pid"
trap 'for pid in "${service_pid:-}" "${other_pid:-}" "${module_pid:-}"; do [[ -z "$pid" ]] || kill "$pid" 2>/dev/null || true; done; find "$tmp" -depth -mindepth 1 -delete; rmdir "$tmp"' EXIT
cat > "$tmp/bin/systemctl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
case "$1" in
  is-active) exit 0 ;;
  show)
    case "$2" in
      --property=MainPID)
        count=0
        [[ ! -f "$HADES_TEST_PID_CALLS" ]] || count=$(cat "$HADES_TEST_PID_CALLS")
        count=$((count + 1))
        printf '%s\n' "$count" > "$HADES_TEST_PID_CALLS"
        if [[ -n "${HADES_TEST_PID_SWITCH_AT:-}" && "$count" -ge "$HADES_TEST_PID_SWITCH_AT" ]]; then
          printf '%s\n' "$HADES_TEST_ALTERNATE_PID"
        else
          printf '%s\n' "$HADES_TEST_MAIN_PID"
        fi
        ;;
      *) exit 2 ;;
    esac
    ;;
  *) exit 2 ;;
esac
SH
chmod 700 "$tmp/bin/systemctl"
export PATH="$tmp/bin:$PATH"
export HADES_TEST_PID_CALLS="$tmp/systemctl-mainpid-calls"
# The process imported the original overlay before this file replacement. The
# writer may attest the stable current disk bytes, but must not classify them
# as proof of the already-loaded Python code object.
printf '# replaced after process start\npass\n' > "$tmp/active/sitecustomize.py"
python scripts/write-deployed-provenance.py \
  --output "$tmp/provenance.json" \
  --hades-sha "$hades_sha" \
  --source-repo "$source_repo" \
  --infra-sha "$infra_sha" \
  --infra-repo "$infra_repo" \
  --hermes-version 0.21.2 \
  --hermes-executable "$tmp/active/hermes" \
  --overlay "$tmp/active/sitecustomize.py" \
  --hermes-profile "$tmp/hermes-home/profiles/hades/config.yaml" \
  --task-store "$source_repo/integrations/task/store.py" \
  --manifest "$source_repo/config/reconstruction-manifest.json" \
  --epsilon-manifest "$tmp/phase3-runtime-manifest.json" \
  --deployment-path /srv/hades \
  --service hades-hermes.service >"$tmp/provenance.stdout"
test "$(cat "$tmp/provenance.stdout")" = 'PASS deployed provenance artifact written (mode=0600)' || {
  echo 'FAIL provenance writer did not emit its safe success summary' >&2
  exit 1
}
if grep -Eq '"(deployment_path|hermes_executable|mcp_runtime|infra_sha)"|/srv/hades|"mcp_runtime_sha256"' "$tmp/provenance.stdout"; then
  echo 'FAIL provenance writer emitted protected artifact details to stdout' >&2
  exit 1
fi
python - "$tmp/provenance.json" <<'PY'
import json, sys
from pathlib import Path
artifact = Path(sys.argv[1])
assert artifact.stat().st_mode & 0o777 == 0o600
value = json.loads(artifact.read_text())
assert value["deployment_path"] == "/srv/hades"
assert value["mcp_runtime"]
assert value["classification"] == "tested-source-and-current-disk-artifact-identity"
print("PASS protected provenance is persisted while stdout stays redacted")
PY
sleep 60 &
other_pid=$!
printf '0\n' > "$HADES_TEST_PID_CALLS"
export HADES_TEST_ALTERNATE_PID="$other_pid"
export HADES_TEST_PID_SWITCH_AT=2
if python scripts/write-deployed-provenance.py \
  --output "$tmp/restart-race-provenance.json" \
  --hades-sha "$hades_sha" \
  --source-repo "$source_repo" \
  --infra-sha "$infra_sha" \
  --infra-repo "$infra_repo" \
  --hermes-version 0.21.2 \
  --hermes-executable "$tmp/active/hermes" \
  --overlay "$tmp/active/sitecustomize.py" \
  --hermes-profile "$tmp/hermes-home/profiles/hades/config.yaml" \
  --task-store "$source_repo/integrations/task/store.py" \
  --manifest "$source_repo/config/reconstruction-manifest.json" \
  --deployment-path /srv/hades \
  --service hades-hermes.service >/dev/null 2>&1; then
  echo 'FAIL provenance writer accepted a MainPID change during capture' >&2
  exit 1
fi
unset HADES_TEST_PID_SWITCH_AT HADES_TEST_ALTERNATE_PID
kill "$other_pid" 2>/dev/null || true
wait "$other_pid" 2>/dev/null || true
test ! -e "$tmp/restart-race-provenance.json"
printf '0\n' > "$HADES_TEST_PID_CALLS"
if python scripts/write-deployed-provenance.py \
  --output "$tmp/wrong-provenance.json" \
  --hades-sha "$hades_sha" \
  --source-repo "$source_repo" \
  --infra-sha "$infra_sha" \
  --infra-repo "$infra_repo" \
  --hermes-version 0.21.2 \
  --hermes-executable "$tmp/active/hermes" \
  --overlay "$tmp/overlay" \
  --hermes-profile "$tmp/hermes-home/profiles/hades/config.yaml" \
  --task-store "$source_repo/integrations/task/store.py" \
  --manifest "$source_repo/config/reconstruction-manifest.json" \
  --deployment-path /srv/hades \
  --service hades-hermes.service >/dev/null 2>&1; then
  echo 'FAIL provenance writer accepted a non-active overlay path' >&2
  exit 1
fi
test ! -e "$tmp/wrong-provenance.json"
mkdir -p "$tmp/hermes-home/profiles/other"
cp "$tmp/hermes-home/profiles/hades/config.yaml" "$tmp/hermes-home/profiles/other/config.yaml"
if python scripts/write-deployed-provenance.py \
  --output "$tmp/wrong-profile-provenance.json" \
  --hades-sha "$hades_sha" \
  --source-repo "$source_repo" \
  --infra-sha "$infra_sha" \
  --infra-repo "$infra_repo" \
  --hermes-version 0.21.2 \
  --hermes-executable "$tmp/active/hermes" \
  --overlay "$tmp/active/sitecustomize.py" \
  --hermes-profile "$tmp/hermes-home/profiles/other/config.yaml" \
  --task-store "$source_repo/integrations/task/store.py" \
  --manifest "$source_repo/config/reconstruction-manifest.json" \
  --deployment-path /srv/hades \
  --service hades-hermes.service >/dev/null 2>&1; then
  echo 'FAIL provenance writer accepted a profile other than the one selected by the running Hermes process' >&2
  exit 1
fi
test ! -e "$tmp/wrong-profile-provenance.json"
cp "$tmp/hermes-home/profiles/hades/config.yaml" "$tmp/profile-good.yaml"
printf 'external MCP source\n' > "$tmp/external-launch.py"
python3 - "$tmp/hermes-home/profiles/hades/config.yaml" "$tmp/external-launch.py" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text().replace(
    '${HADES_HERMES_WORKING_DIRECTORY}/integrations/grocy-mcp/launch.py',
    sys.argv[2],
)
p.write_text(s)
PY
if python scripts/write-deployed-provenance.py \
  --output "$tmp/untracked-mcp-provenance.json" \
  --hades-sha "$hades_sha" \
  --source-repo "$source_repo" \
  --infra-sha "$infra_sha" \
  --infra-repo "$infra_repo" \
  --hermes-version 0.21.2 \
  --hermes-executable "$tmp/active/hermes" \
  --overlay "$tmp/active/sitecustomize.py" \
  --hermes-profile "$tmp/hermes-home/profiles/hades/config.yaml" \
  --task-store "$source_repo/integrations/task/store.py" \
  --manifest "$source_repo/config/reconstruction-manifest.json" \
  --deployment-path /srv/hades \
  --service hades-hermes.service >/dev/null 2>&1; then
  echo 'FAIL provenance writer accepted an MCP source outside the clean HADES checkout' >&2
  exit 1
fi
test ! -e "$tmp/untracked-mcp-provenance.json"
cp "$tmp/profile-good.yaml" "$tmp/hermes-home/profiles/hades/config.yaml"
if python scripts/write-deployed-provenance.py \
  --output "$tmp/mismatched-sha.json" \
  --hades-sha 0123456789abcdef0123456789abcdef01234567 \
  --source-repo "$source_repo" \
  --infra-sha "$infra_sha" \
  --infra-repo "$infra_repo" \
  --hermes-version 0.21.2 \
  --hermes-executable "$tmp/active/hermes" \
  --overlay "$tmp/active/sitecustomize.py" \
  --hermes-profile "$tmp/hermes-home/profiles/hades/config.yaml" \
  --task-store "$source_repo/integrations/task/store.py" \
  --manifest "$source_repo/config/reconstruction-manifest.json" \
  --deployment-path /srv/hades \
  --service hades-hermes.service >/dev/null 2>&1; then
  echo 'FAIL provenance writer accepted a HADES SHA different from source HEAD' >&2
  exit 1
fi
test ! -e "$tmp/mismatched-sha.json"
printf 'untracked drift\n' > "$source_repo/untracked.txt"
if python scripts/write-deployed-provenance.py \
  --output "$tmp/dirty-provenance.json" \
  --hades-sha "$hades_sha" \
  --source-repo "$source_repo" \
  --infra-sha "$infra_sha" \
  --infra-repo "$infra_repo" \
  --hermes-version 0.21.2 \
  --hermes-executable "$tmp/active/hermes" \
  --overlay "$tmp/active/sitecustomize.py" \
  --hermes-profile "$tmp/hermes-home/profiles/hades/config.yaml" \
  --task-store "$source_repo/integrations/task/store.py" \
  --manifest "$source_repo/config/reconstruction-manifest.json" \
  --deployment-path /srv/hades \
  --service hades-hermes.service >/dev/null 2>&1; then
  echo 'FAIL provenance writer accepted a dirty source repository' >&2
  exit 1
fi
test ! -e "$tmp/dirty-provenance.json"
rm "$source_repo/untracked.txt"
if python scripts/write-deployed-provenance.py \
  --output "$tmp/mismatched-infra.json" \
  --hades-sha "$hades_sha" \
  --source-repo "$source_repo" \
  --infra-sha fedcba9876543210fedcba9876543210fedcba98 \
  --infra-repo "$infra_repo" \
  --hermes-version 0.21.2 \
  --hermes-executable "$tmp/active/hermes" \
  --overlay "$tmp/active/sitecustomize.py" \
  --hermes-profile "$tmp/hermes-home/profiles/hades/config.yaml" \
  --task-store "$source_repo/integrations/task/store.py" \
  --manifest "$source_repo/config/reconstruction-manifest.json" \
  --deployment-path /srv/hades \
  --service hades-hermes.service >/dev/null 2>&1; then
  echo 'FAIL provenance writer accepted an infra SHA different from source HEAD' >&2
  exit 1
fi
test ! -e "$tmp/mismatched-infra.json"
printf 'untracked infra drift\n' > "$infra_repo/untracked.txt"
if python scripts/write-deployed-provenance.py \
  --output "$tmp/dirty-infra-provenance.json" \
  --hades-sha "$hades_sha" \
  --source-repo "$source_repo" \
  --infra-sha "$infra_sha" \
  --infra-repo "$infra_repo" \
  --hermes-version 0.21.2 \
  --hermes-executable "$tmp/active/hermes" \
  --overlay "$tmp/active/sitecustomize.py" \
  --hermes-profile "$tmp/hermes-home/profiles/hades/config.yaml" \
  --task-store "$source_repo/integrations/task/store.py" \
  --manifest "$source_repo/config/reconstruction-manifest.json" \
  --deployment-path /srv/hades \
  --service hades-hermes.service >/dev/null 2>&1; then
  echo 'FAIL provenance writer accepted a dirty infra repository' >&2
  exit 1
fi
test ! -e "$tmp/dirty-infra-provenance.json"
rm "$infra_repo/untracked.txt"
if python scripts/write-deployed-provenance.py \
  --output "$tmp/mismatched-version.json" \
  --hades-sha "$hades_sha" \
  --source-repo "$source_repo" \
  --infra-sha "$infra_sha" \
  --infra-repo "$infra_repo" \
  --hermes-version 0.14.0 \
  --hermes-executable "$tmp/active/hermes" \
  --overlay "$tmp/active/sitecustomize.py" \
  --hermes-profile "$tmp/hermes-home/profiles/hades/config.yaml" \
  --task-store "$source_repo/integrations/task/store.py" \
  --manifest "$source_repo/config/reconstruction-manifest.json" \
  --deployment-path /srv/hades \
  --service hades-hermes.service >/dev/null 2>&1; then
  echo 'FAIL provenance writer accepted a Hermes version different from the executable' >&2
  exit 1
fi
test ! -e "$tmp/mismatched-version.json"
if python scripts/write-deployed-provenance.py \
  --output "$tmp/mismatched-executable.json" \
  --hades-sha "$hades_sha" \
  --source-repo "$source_repo" \
  --infra-sha "$infra_sha" \
  --infra-repo "$infra_repo" \
  --hermes-version 0.21.2 \
  --hermes-executable "$tmp/overlay" \
  --overlay "$tmp/active/sitecustomize.py" \
  --hermes-profile "$tmp/hermes-home/profiles/hades/config.yaml" \
  --task-store "$source_repo/integrations/task/store.py" \
  --manifest "$source_repo/config/reconstruction-manifest.json" \
  --deployment-path /srv/hades \
  --service hades-hermes.service >/dev/null 2>&1; then
  echo 'FAIL provenance writer accepted an executable outside active service configuration' >&2
  exit 1
fi
test ! -e "$tmp/mismatched-executable.json"
sleep 60 &
other_pid=$!
export HADES_TEST_MAIN_PID="$other_pid"
if python scripts/write-deployed-provenance.py \
  --output "$tmp/mismatched-running-process.json" \
  --hades-sha "$hades_sha" \
  --source-repo "$source_repo" \
  --infra-sha "$infra_sha" \
  --infra-repo "$infra_repo" \
  --hermes-version 0.21.2 \
  --hermes-executable "$tmp/active/hermes" \
  --overlay "$tmp/active/sitecustomize.py" \
  --hermes-profile "$tmp/hermes-home/profiles/hades/config.yaml" \
  --task-store "$source_repo/integrations/task/store.py" \
  --manifest "$source_repo/config/reconstruction-manifest.json" \
  --deployment-path /srv/hades \
  --service hades-hermes.service >/dev/null 2>&1; then
  echo 'FAIL provenance writer accepted a running process different from the configured Hermes executable' >&2
  kill "$other_pid" 2>/dev/null || true
  exit 1
fi
kill "$other_pid" 2>/dev/null || true
wait "$other_pid" 2>/dev/null || true
test ! -e "$tmp/mismatched-running-process.json"
env PYTHONPATH="$tmp/active:$module_root" \
  HERMES_HOME="$tmp/hermes-home" \
  HADES_HERMES_EXECUTABLE='' \
  "$tmp/active/python" -m hermes_cli.main -p hades &
module_pid=$!
sleep 0.05
export HADES_TEST_MAIN_PID="$module_pid"
export HADES_TEST_HERMES_EXECUTABLE=''
python scripts/write-deployed-provenance.py \
  --output "$tmp/module-provenance.json" \
  --hades-sha "$hades_sha" \
  --source-repo "$source_repo" \
  --infra-sha "$infra_sha" \
  --infra-repo "$infra_repo" \
  --hermes-version 0.21.2 \
  --hermes-executable "$tmp/active/python" \
  --overlay "$tmp/active/sitecustomize.py" \
  --hermes-profile "$tmp/hermes-home/profiles/hades/config.yaml" \
  --task-store "$source_repo/integrations/task/store.py" \
  --manifest "$source_repo/config/reconstruction-manifest.json" \
  --deployment-path /srv/hades \
  --service hades-hermes.service >/dev/null
if python scripts/write-deployed-provenance.py \
  --output "$tmp/module-mismatched-version.json" \
  --hades-sha "$hades_sha" \
  --source-repo "$source_repo" \
  --infra-sha "$infra_sha" \
  --infra-repo "$infra_repo" \
  --hermes-version 0.14.0 \
  --hermes-executable "$tmp/active/python" \
  --overlay "$tmp/active/sitecustomize.py" \
  --hermes-profile "$tmp/hermes-home/profiles/hades/config.yaml" \
  --task-store "$source_repo/integrations/task/store.py" \
  --manifest "$source_repo/config/reconstruction-manifest.json" \
  --deployment-path /srv/hades \
  --service hades-hermes.service >/dev/null 2>&1; then
  echo 'FAIL provenance writer accepted an incorrect Hermes package version for the Python-module runtime' >&2
  kill "$module_pid" 2>/dev/null || true
  exit 1
fi
kill "$module_pid" 2>/dev/null || true
wait "$module_pid" 2>/dev/null || true
test ! -e "$tmp/module-mismatched-version.json"
python - "$tmp/provenance.json" <<'PY'
import hashlib
import json, sys
from pathlib import Path
value = json.load(open(sys.argv[1]))
assert value["schema"] == "hades/deployed-provenance/v1"
assert value["hades_sha"] == __import__("subprocess").check_output(["git", "-C", str(Path(sys.argv[1]).parent / "source"), "rev-parse", "HEAD"], text=True).strip()
assert len(value["hades_tree_sha256"]) == 40
assert value["infra_sha"] == __import__("subprocess").check_output(["git", "-C", str(Path(sys.argv[1]).parent / "infra"), "rev-parse", "HEAD"], text=True).strip()
assert len(value["infra_tree_sha256"]) == 40
assert value["hermes_version"] == "0.21.2"
assert value["hermes_executable"] == str((Path(sys.argv[1]).parent / "active" / "hermes").resolve())
assert len(value["hermes_executable_sha256"]) == 64
assert value["hermes_runtime_kind"] == "configured-executable"
assert value["hermes_profile_sha256"] == hashlib.sha256((Path(sys.argv[1]).parent / "hermes-home" / "profiles" / "hades" / "config.yaml").read_bytes()).hexdigest()
assert value["mcp_runtime"] == [
    {"enabled": True, "name": "grocy", "sha256": hashlib.sha256((Path(sys.argv[1]).parent / "source" / "integrations" / "grocy-mcp" / "launch.py").read_bytes()).hexdigest(), "source": "integrations/grocy-mcp/launch.py", "transport": "stdio-source"},
    {"enabled": True, "name": "receipt-ocr-gateway", "transport": "http", "endpoint_sha256": hashlib.sha256(b"http://private.example.invalid:8765/mcp").hexdigest()},
]
assert len(value["mcp_runtime_sha256"]) == 64
assert "synthetic-not-for-provenance" not in json.dumps(value)
assert "private.example.invalid" not in json.dumps(value)
assert len(value["overlay_sha256"]) == 64 and len(value["manifest_sha256"]) == 64
assert len(value["task_store_sha256"]) == 64
epsilon_manifest = Path(sys.argv[1]).parent / "phase3-runtime-manifest.json"
assert value["epsilon_package_manifest_sha256"] == hashlib.sha256(epsilon_manifest.read_bytes()).hexdigest()
assert value["overlay_sha256"] == hashlib.sha256((Path(sys.argv[1]).parent / "active" / "sitecustomize.py").read_bytes()).hexdigest()
assert value["task_store_sha256"] == hashlib.sha256((Path(sys.argv[1]).parent / "task-store.py").read_bytes()).hexdigest()
assert "generated_at" in value
print("PASS deployed provenance artifact is bounded, machine-readable, and hashed")
PY
python - "$tmp/module-provenance.json" <<'PY'
import json, sys
value = json.load(open(sys.argv[1]))
assert value["hermes_runtime_kind"] == "python-module"
assert value["hermes_version"] == "0.21.2"
assert len(value["hermes_executable_sha256"]) == 64
print("PASS legacy Hermes Python-module launch provenance matches the running interpreter and package metadata")
PY
mkdir -p "$tmp/external-homelab-package"
cp -a "$source_repo/integrations/homelab-readonly/." "$tmp/external-homelab-package/"
printf 'mcp_servers:\n  homelab-readonly:\n    enabled: true\n    command: python3\n    args:\n      - %s/server.py\n' "$tmp/external-homelab-package" > "$tmp/hermes-home/profiles/hades/config.yaml"
env PYTHONPATH="$tmp/active:$module_root" \
  HERMES_HOME="$tmp/hermes-home" \
  HADES_HERMES_EXECUTABLE='' \
  "$tmp/active/python" -m hermes_cli.main -p hades &
module_pid=$!
sleep 0.05
export HADES_TEST_MAIN_PID="$module_pid"
python scripts/write-deployed-provenance.py \
  --output "$tmp/homelab-package-provenance.json" \
  --hades-sha "$hades_sha" \
  --source-repo "$source_repo" \
  --infra-sha "$infra_sha" \
  --infra-repo "$infra_repo" \
  --hermes-version 0.21.2 \
  --hermes-executable "$tmp/active/python" \
  --overlay "$tmp/active/sitecustomize.py" \
  --hermes-profile "$tmp/hermes-home/profiles/hades/config.yaml" \
  --task-store "$source_repo/integrations/task/store.py" \
  --manifest "$source_repo/config/reconstruction-manifest.json" \
  --homelab-package-root "$tmp/external-homelab-package" \
  --deployment-path /srv/hades \
  --service hades-hermes.service >/dev/null
python - "$tmp/homelab-package-provenance.json" <<'PY'
import json, sys
value = json.load(open(sys.argv[1]))
assert len(value["mcp_runtime"]) == 1
row = value["mcp_runtime"][0]
assert row["name"] == "homelab-readonly"
assert row["transport"] == "stdio-package-source"
assert row["source"] == "integrations/homelab-readonly"
assert row["file_count"] == 2
assert len(row["package_tree_sha256"]) == 64
assert "/external-homelab-package" not in json.dumps(value)
print("PASS CLI provenance binds the selected external homelab package to the clean HADES tree")
PY
