#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
printf 'manifest fixture\n' > "$tmp/manifest"
printf 'task store fixture\n' > "$tmp/task-store.py"
printf 'epsilon package fixture\n' > "$tmp/phase3-runtime-manifest.json"
source_repo="$tmp/source"
infra_repo="$tmp/infra"
generated_integrations="$tmp/generated/integrations"
runtime_homelab_package="$generated_integrations/homelab-readonly-646577b"
mkdir -p "$tmp/bin" "$tmp/active" "$source_repo/hermes" "$source_repo/scripts" "$source_repo/integrations/task" "$source_repo/integrations/grocy-mcp" "$source_repo/integrations/homelab-readonly" "$source_repo/config" "$infra_repo" "$runtime_homelab_package"
cat > "$source_repo/hermes/sitecustomize.py" <<'PY'
def _hades_load_homelab_views():
    return object()

def _hades_homelab_guest_visibility_response(summary):
    return _hades_load_homelab_views().guest(summary)

def _hades_household_homelab_boundary_response(user_text):
    return _hades_load_homelab_views().household(user_text)
PY
cp "$repo_dir/scripts/hermes-overlay-composition.py" "$source_repo/scripts/"
cp "$repo_dir/scripts/prepare-homelab-overlay-candidate.py" "$source_repo/scripts/"
printf 'task store fixture\n' > "$source_repo/integrations/task/store.py"
printf '# synthetic Grocy launcher source\n' > "$source_repo/integrations/grocy-mcp/launch.py"
printf 'from reconcile import VALUE\n' > "$source_repo/integrations/homelab-readonly/server.py"
printf 'VALUE = "fixture"\n' > "$source_repo/integrations/homelab-readonly/reconcile.py"
printf 'VALUE = "provider-fixture"\n' > "$source_repo/integrations/homelab-readonly/inference_provider.py"
printf 'VALUE = "visibility-fixture"\n' > "$source_repo/integrations/homelab-readonly/proxmox_visibility.py"
printf 'manifest fixture\n' > "$source_repo/config/reconstruction-manifest.json"
git -C "$source_repo" init -q
git -C "$source_repo" config user.email fixture@example.invalid
git -C "$source_repo" config user.name fixture
git -C "$source_repo" add hermes/sitecustomize.py scripts/hermes-overlay-composition.py scripts/prepare-homelab-overlay-candidate.py integrations/task/store.py integrations/grocy-mcp/launch.py integrations/homelab-readonly/server.py integrations/homelab-readonly/reconcile.py integrations/homelab-readonly/inference_provider.py integrations/homelab-readonly/proxmox_visibility.py config/reconstruction-manifest.json
git -C "$source_repo" commit -qm fixture
hades_sha=$(git -C "$source_repo" rev-parse HEAD)
cp "$source_repo/integrations/homelab-readonly/"*.py "$runtime_homelab_package/"
printf 'infra fixture\n' > "$infra_repo/infra.txt"
git -C "$infra_repo" init -q
git -C "$infra_repo" config user.email fixture@example.invalid
git -C "$infra_repo" config user.name fixture
git -C "$infra_repo" add infra.txt
git -C "$infra_repo" commit -qm fixture
infra_sha=$(git -C "$infra_repo" rev-parse HEAD)
cp "$source_repo/hermes/sitecustomize.py" "$tmp/overlay"
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
python3 - "$tmp/hermes-home/profiles/hades/config.yaml" "$source_repo" <<'PY'
from pathlib import Path
import sys
profile = Path(sys.argv[1])
profile.write_text(profile.read_text() + (
    '  homelab-readonly:\n'
    '    enabled: true\n'
    '    command: python3\n'
    '    args: ["${HADES_INTEGRATIONS_ROOT}/homelab-readonly-646577b/server.py"]\n'
))
PY
python3 - "$PWD/scripts/write-deployed-provenance.py" <<'PY'
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
PY
if output=$(python scripts/write-deployed-provenance.py \
  --install-marker /tmp/first-install-contract \
  --install-marker /tmp/second-install-contract 2>&1); then
  echo 'FAIL provenance writer accepted duplicate install-marker options' >&2
  exit 1
fi
grep -Fq 'may be supplied only once' <<<"$output" || {
  echo 'FAIL duplicate install-marker failure had the wrong cause' >&2
  exit 1
}
if output=$(python scripts/write-deployed-provenance.py \
  --overlay-composition-manifest /tmp/first-composition.json \
  --overlay-composition-manifest /tmp/second-composition.json 2>&1); then
  echo 'FAIL provenance writer accepted duplicate composition-manifest options' >&2
  exit 1
fi
grep -Fq 'may be supplied only once' <<<"$output" || {
  echo 'FAIL duplicate composition-manifest failure had the wrong cause' >&2
  exit 1
}
python3 - "$PWD/scripts/write-deployed-provenance.py" "$tmp/hermes-home/profiles/hades/config.yaml" "$source_repo" "$generated_integrations" <<'PY'
import importlib.util
import hashlib
from pathlib import Path
import sys
spec = importlib.util.spec_from_file_location("deployed_provenance", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
profile = Path(sys.argv[2])
root = Path(sys.argv[3])
generated_root = Path(sys.argv[4])
environment = {
    "HADES_HERMES_WORKING_DIRECTORY": str(root),
    "HADES_INTEGRATIONS_ROOT": str(generated_root),
    "HADES_TEST_PRIVATE_ENDPOINT": "http://private.example.invalid:8765/mcp",
}
rows, _ = module.mcp_runtime_identity(profile, environment, root)
homelab = next(row for row in rows if row["name"] == "homelab-readonly")
assert [item["source"] for item in homelab["package"]["files"]] == [
    "integrations/homelab-readonly/inference_provider.py",
    "integrations/homelab-readonly/proxmox_visibility.py",
    "integrations/homelab-readonly/reconcile.py",
    "integrations/homelab-readonly/server.py",
], homelab["package"]["files"]
direct_profile = Path(profile.parent.parent.parent) / "direct-config.yaml"
direct_profile.write_text(
    'mcp_servers:\n'
    '  homelab-readonly:\n'
    '    enabled: true\n'
    '    command: python3\n'
    '    args: ["${HADES_HERMES_WORKING_DIRECTORY}/integrations/homelab-readonly/server.py"]\n',
    encoding="utf-8",
)
direct_rows, _ = module.mcp_runtime_identity(
    direct_profile, {"HADES_HERMES_WORKING_DIRECTORY": str(root)}, root
)
direct_homelab = next(row for row in direct_rows if row["name"] == "homelab-readonly")
assert direct_homelab["package"]["sha256"] == homelab["package"]["sha256"]
alias_profile = Path(profile.parent.parent.parent) / "alias-config.yaml"
alias_profile.write_text(
    profile.read_text(encoding="utf-8").replace(
        "  homelab-readonly:\n", "  homelab-alias:\n"
    ),
    encoding="utf-8",
)
alias_rows, _ = module.mcp_runtime_identity(alias_profile, environment, root)
alias_homelab = next(row for row in alias_rows if row["name"] == "homelab-alias")
assert alias_homelab["package"]["sha256"] == homelab["package"]["sha256"]

# An enabled homelab MCP must bind to its complete path-backed source package.
# Module and inline-code launches can otherwise be recorded only as an
# external executable, leaving their actual implementation unbound.
fake_external = profile.parent.parent.parent.parent / "active" / "hermes"
fake_python = profile.parent.parent.parent.parent / "active" / "python3"
runtime_server = generated_root / "homelab-readonly-646577b" / "server.py"
fake_python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
fake_python.chmod(0o700)
for launch_args in ('["-m", "synthetic_untracked_homelab"]', '["-c", "pass"]'):
    unbound_profile = Path(profile.parent.parent.parent.parent) / "unbound-homelab.yaml"
    unbound_profile.write_text(
        "mcp_servers:\n"
        "  homelab-readonly:\n"
        "    enabled: true\n"
        f"    command: {fake_python}\n"
        f"    args: {launch_args}\n",
        encoding="utf-8",
    )
    try:
        module.mcp_runtime_identity(unbound_profile, environment, root)
    except SystemExit as error:
        assert "path-backed server.py package" in str(error), error
    else:
        raise AssertionError(f"accepted unbound homelab launch arguments: {launch_args}")

http_homelab_profile = Path(profile.parent.parent.parent.parent) / "http-homelab.yaml"
http_homelab_profile.write_text(
    "mcp_servers:\n"
    "  homelab-readonly:\n"
    "    enabled: true\n"
    '    url: "http://127.0.0.1:8765/mcp"\n',
    encoding="utf-8",
)
try:
    module.mcp_runtime_identity(http_homelab_profile, environment, root)
except SystemExit as error:
    assert "path-backed server.py package" in str(error), error
else:
    raise AssertionError("accepted homelab HTTP registration without source package identity")

# A path-looking server.py argument is not enough when the configured command
# is not a Python interpreter that will load the package.
wrong_executor_profile = Path(profile.parent.parent.parent.parent) / "wrong-homelab-executor.yaml"
wrong_executor_profile.write_text(
    "mcp_servers:\n"
    "  homelab-readonly:\n"
    "    enabled: true\n"
    f"    command: {fake_external}\n"
    f"    args: [\"{runtime_server}\"]\n",
    encoding="utf-8",
)
try:
    module.mcp_runtime_identity(wrong_executor_profile, environment, root)
except SystemExit as error:
    assert "path-backed server.py package" in str(error), error
else:
    raise AssertionError("accepted homelab server.py path with a non-Python command")

# Unrelated external executable MCPs retain their existing provenance path.
external_only_profile = Path(profile.parent.parent.parent.parent) / "external-only.yaml"
external_only_profile.write_text(
    "mcp_servers:\n"
    "  unrelated-helper:\n"
    "    enabled: true\n"
    f"    command: {fake_external}\n",
    encoding="utf-8",
)
external_rows, _ = module.mcp_runtime_identity(external_only_profile, environment, root)
assert external_rows == [{
    "enabled": True,
    "name": "unrelated-helper",
    "transport": "external-executable",
    "sha256": hashlib.sha256(fake_external.read_bytes()).hexdigest(),
}]

runtime_package = generated_root / "homelab-readonly-646577b"
reconcile = runtime_package / "reconcile.py"
original = reconcile.read_bytes()
try:
    reconcile.write_text('VALUE = "mixed-package"\n')
    try:
        module.mcp_runtime_identity(profile, environment, root)
    except SystemExit as error:
        assert "package bytes differ" in str(error)
    else:
        raise AssertionError("homelab provenance accepted a mixed sibling module")
finally:
    reconcile.write_bytes(original)
provider = runtime_package / "proxmox_visibility.py"
original = provider.read_bytes()
try:
    provider.write_text('VALUE = "mixed-visibility-package"\n')
    try:
        module.mcp_runtime_identity(profile, environment, root)
    except SystemExit as error:
        assert "package bytes differ" in str(error)
    else:
        raise AssertionError("homelab provenance accepted a changed Proxmox visibility sibling")
finally:
    provider.write_bytes(original)
extra_module = runtime_package / "unexpected.py"
extra_module.write_text('VALUE = "unexpected"\n')
try:
    try:
        module.mcp_runtime_identity(profile, environment, root)
    except SystemExit as error:
        assert "module set differs" in str(error)
    else:
        raise AssertionError("homelab provenance accepted an unexpected runtime module")
finally:
    extra_module.unlink()
package_dir = runtime_package
real_package_dir = generated_root / "homelab-readonly-backup"
package_dir.rename(real_package_dir)
package_dir.symlink_to(real_package_dir, target_is_directory=True)
try:
    try:
        module.mcp_runtime_identity(profile, environment, root)
    except SystemExit as error:
        assert "symlink or missing directory" in str(error)
    else:
        raise AssertionError("homelab provenance accepted a symlinked package directory")
finally:
    package_dir.unlink()
    real_package_dir.rename(package_dir)
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
export HADES_INTEGRATIONS_ROOT="$generated_integrations"
export HADES_TEST_PRIVATE_ENDPOINT='http://private.example.invalid:8765/mcp'
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
      --property=MainPID) printf '%s\n' "$HADES_TEST_MAIN_PID" ;;
      --property=Environment) printf 'PYTHONPATH=%s HADES_HERMES_EXECUTABLE=%s HERMES_HOME=%s\n' "$HADES_TEST_PYTHONPATH" "$HADES_TEST_HERMES_EXECUTABLE" "$HADES_TEST_HERMES_HOME" ;;
      *) exit 2 ;;
    esac
    ;;
  *) exit 2 ;;
esac
SH
chmod 700 "$tmp/bin/systemctl"
export PATH="$tmp/bin:$PATH"
export HADES_TEST_PYTHONPATH="$tmp/active:$module_root"
export HADES_TEST_HERMES_EXECUTABLE="$tmp/active/hermes"
export HADES_TEST_HERMES_HOME="$tmp/hermes-home"
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
  --service hades-hermes.service >/dev/null
chmod 0666 "$tmp/active/sitecustomize.py"
if python scripts/write-deployed-provenance.py \
  --output "$tmp/unsafe-tracked-overlay-provenance.json" \
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
  echo 'FAIL provenance writer accepted unsafe permissions on a tracked Hermes overlay' >&2
  exit 1
fi
test ! -e "$tmp/unsafe-tracked-overlay-provenance.json"
chmod 0644 "$tmp/active/sitecustomize.py"
cp "$tmp/active/sitecustomize.py" "$tmp/source-overlay.py"
printf '\n# unbound local customization\n' >> "$tmp/active/sitecustomize.py"
if python scripts/write-deployed-provenance.py \
  --output "$tmp/unbound-overlay-provenance.json" \
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
  echo 'FAIL provenance writer accepted an unbound customized Hermes overlay' >&2
  exit 1
fi
test ! -e "$tmp/unbound-overlay-provenance.json"
cp "$tmp/source-overlay.py" "$tmp/active/sitecustomize.py"
composition_dir="$tmp/composition"
mkdir -m 0700 "$composition_dir"
mkdir -m 0700 "$composition_dir/state"
cp "$tmp/source-overlay.py" "$composition_dir/base.py"
printf '\n# deployment-local, explicitly composed overlay\nLOCAL_OVERLAY = True\n' >> "$composition_dir/base.py"
chmod 600 "$composition_dir/base.py"
python scripts/prepare-homelab-overlay-candidate.py \
  --repo "$source_repo" \
  --active-overlay "$composition_dir/base.py" \
  --output "$composition_dir/candidate.py" \
  --manifest-output "$composition_dir/composition.json" >/dev/null
cp "$composition_dir/candidate.py" "$tmp/active/sitecustomize.py"
chmod 640 "$tmp/active/sitecustomize.py"
printf 'hermes_overlay_composition_manifest_sha256=%s\n' \
  "$(sha256sum "$composition_dir/composition.json" | awk '{print $1}')" \
  > "$composition_dir/state/install-contract"
chmod 640 "$composition_dir/state/install-contract"
HADES_STATE_ROOT="$composition_dir/state" python scripts/write-deployed-provenance.py \
  --output "$tmp/composed-overlay-provenance.json" \
  --hades-sha "$hades_sha" \
  --source-repo "$source_repo" \
  --infra-sha "$infra_sha" \
  --infra-repo "$infra_repo" \
  --hermes-version 0.21.2 \
  --hermes-executable "$tmp/active/hermes" \
  --overlay "$tmp/active/sitecustomize.py" \
  --overlay-composition-manifest "$composition_dir/composition.json" \
  --install-marker "$composition_dir/state/install-contract" \
  --hermes-profile "$tmp/hermes-home/profiles/hades/config.yaml" \
  --task-store "$source_repo/integrations/task/store.py" \
  --manifest "$source_repo/config/reconstruction-manifest.json" \
  --deployment-path /srv/hades \
  --service hades-hermes.service >/dev/null
python3 - "$tmp/composed-overlay-provenance.json" "$composition_dir/composition.json" <<'PY'
import hashlib
import json
from pathlib import Path
import sys
artifact = json.loads(Path(sys.argv[1]).read_text())
composition = json.loads(Path(sys.argv[2]).read_text())
assert artifact["hermes_overlay_composition"]["final_overlay_sha256"] == composition["final_overlay_sha256"]
assert artifact["hermes_overlay_composition"]["manifest_sha256"] == hashlib.sha256(Path(sys.argv[2]).read_bytes()).hexdigest()
assert artifact["hermes_overlay_composition"]["source_revision"] == composition["source_revision"]
assert artifact["hermes_overlay_composition"]["source_tree"] == composition["source_tree"]
PY
cp "$composition_dir/state/install-contract" "$composition_dir/fake-install-contract"
chmod 640 "$composition_dir/fake-install-contract"
if HADES_STATE_ROOT="$composition_dir/state" python scripts/write-deployed-provenance.py \
  --output "$tmp/fake-marker-provenance.json" \
  --hades-sha "$hades_sha" \
  --source-repo "$source_repo" \
  --infra-sha "$infra_sha" \
  --infra-repo "$infra_repo" \
  --hermes-version 0.21.2 \
  --hermes-executable "$tmp/active/hermes" \
  --overlay "$tmp/active/sitecustomize.py" \
  --overlay-composition-manifest "$composition_dir/composition.json" \
  --install-marker "$composition_dir/fake-install-contract" \
  --hermes-profile "$tmp/hermes-home/profiles/hades/config.yaml" \
  --task-store "$source_repo/integrations/task/store.py" \
  --manifest "$source_repo/config/reconstruction-manifest.json" \
  --deployment-path /srv/hades \
  --service hades-hermes.service >/dev/null 2>&1; then
  echo 'FAIL provenance writer accepted a composition marker outside HADES_STATE_ROOT' >&2
  exit 1
fi
test ! -e "$tmp/fake-marker-provenance.json"
chmod 666 "$tmp/active/sitecustomize.py"
if HADES_STATE_ROOT="$composition_dir/state" python scripts/write-deployed-provenance.py \
  --output "$tmp/unsafe-mode-provenance.json" \
  --hades-sha "$hades_sha" \
  --source-repo "$source_repo" \
  --infra-sha "$infra_sha" \
  --infra-repo "$infra_repo" \
  --hermes-version 0.21.2 \
  --hermes-executable "$tmp/active/hermes" \
  --overlay "$tmp/active/sitecustomize.py" \
  --overlay-composition-manifest "$composition_dir/composition.json" \
  --install-marker "$composition_dir/state/install-contract" \
  --hermes-profile "$tmp/hermes-home/profiles/hades/config.yaml" \
  --task-store "$source_repo/integrations/task/store.py" \
  --manifest "$source_repo/config/reconstruction-manifest.json" \
  --deployment-path /srv/hades \
  --service hades-hermes.service >/dev/null 2>&1; then
  echo 'FAIL provenance writer accepted an unsafe composed-overlay mode' >&2
  exit 1
fi
test ! -e "$tmp/unsafe-mode-provenance.json"
chmod 640 "$tmp/active/sitecustomize.py"
python3 - "$composition_dir/composition.json" "$composition_dir/unrecorded-composition.json" <<'PY'
import json
from pathlib import Path
import sys
source, target = map(Path, sys.argv[1:])
manifest = json.loads(source.read_text())
manifest["base_overlay_sha256"] = "0" * 64
target.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
target.chmod(0o600)
PY
if HADES_STATE_ROOT="$composition_dir/state" python scripts/write-deployed-provenance.py \
  --output "$tmp/unrecorded-manifest-provenance.json" \
  --hades-sha "$hades_sha" \
  --source-repo "$source_repo" \
  --infra-sha "$infra_sha" \
  --infra-repo "$infra_repo" \
  --hermes-version 0.21.2 \
  --hermes-executable "$tmp/active/hermes" \
  --overlay "$tmp/active/sitecustomize.py" \
  --overlay-composition-manifest "$composition_dir/unrecorded-composition.json" \
  --install-marker "$composition_dir/state/install-contract" \
  --hermes-profile "$tmp/hermes-home/profiles/hades/config.yaml" \
  --task-store "$source_repo/integrations/task/store.py" \
  --manifest "$source_repo/config/reconstruction-manifest.json" \
  --deployment-path /srv/hades \
  --service hades-hermes.service >/dev/null 2>&1; then
  echo 'FAIL provenance writer accepted a manifest that differs from the installed record' >&2
  exit 1
fi
test ! -e "$tmp/unrecorded-manifest-provenance.json"
cp "$tmp/source-overlay.py" "$tmp/active/sitecustomize.py"
chmod 0644 "$tmp/active/sitecustomize.py"
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
export PYTHONPATH="$module_root"
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
assert [row["name"] for row in value["mcp_runtime"]] == ["grocy", "homelab-readonly", "receipt-ocr-gateway"]
homelab = value["mcp_runtime"][1]
assert homelab["source"] == "integrations/homelab-readonly/server.py"
assert [item["source"] for item in homelab["package"]["files"]] == [
    "integrations/homelab-readonly/inference_provider.py",
    "integrations/homelab-readonly/proxmox_visibility.py",
    "integrations/homelab-readonly/reconcile.py",
    "integrations/homelab-readonly/server.py",
]
assert all(len(item["sha256"]) == 64 for item in homelab["package"]["files"])
package_bytes = json.dumps(homelab["package"]["files"], sort_keys=True, separators=(",", ":")).encode()
assert homelab["package"]["sha256"] == hashlib.sha256(package_bytes).hexdigest()
assert value["mcp_runtime"][0] == {"enabled": True, "name": "grocy", "sha256": hashlib.sha256((Path(sys.argv[1]).parent / "source" / "integrations" / "grocy-mcp" / "launch.py").read_bytes()).hexdigest(), "source": "integrations/grocy-mcp/launch.py", "transport": "stdio-source"}
assert value["mcp_runtime"][2] == {"enabled": True, "name": "receipt-ocr-gateway", "transport": "http", "endpoint_sha256": hashlib.sha256(b"http://private.example.invalid:8765/mcp").hexdigest()}
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
