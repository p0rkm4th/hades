#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source config/versions.env
command -v docker >/dev/null 2>&1 || { echo 'FAIL Docker is required for the pinned LLDAP runtime contract' >&2; exit 2; }
docker_cmd=(docker)
if ! docker info >/dev/null 2>&1; then
  docker_cmd=(sudo -n docker)
  "${docker_cmd[@]}" info >/dev/null 2>&1 || {
    echo 'FAIL Docker access is required; run as root, join the docker group, or provide noninteractive sudo access' >&2
    exit 2
  }
fi
"${docker_cmd[@]}" image inspect "$HADES_LLDAP_IMAGE" >/dev/null 2>&1 || { echo 'FAIL pinned LLDAP image is not cached; pull it before running this optional runtime contract' >&2; exit 2; }
[[ "$(id -u)" == 1000 || "$(id -u)" == 0 ]] || { echo 'FAIL run as root or UID 1000 so the pinned LLDAP UID can read the synthetic secrets' >&2; exit 2; }

runtime_tmp=${XDG_CACHE_HOME:-${HOME}/.cache}
mkdir -p "$runtime_tmp"
work=$(mktemp -d "$runtime_tmp/hades-phase3-lldap-runtime.XXXXXX")
name="hades-phase3-lldap-runtime-$$"
port=$((20000 + ($$ % 20000)))
cleanup() {
  "${docker_cmd[@]}" stop "$name" >/dev/null 2>&1 || true
  find "$work" -depth -delete 2>/dev/null || true
}
trap cleanup EXIT
umask 077
mkdir -p "$work/identity" "$work/users" "$work/groups"
printf 'synthetic-jwt-secret-for-phase3-runtime-00000000000000000000000000000000\n' > "$work/identity/jwt_secret"
printf 'synthetic-key-seed-for-phase3-runtime-0000000000000000000000000000000000000000000000000000000000000000\n' > "$work/identity/key_seed"
printf 'synthetic-admin-password\n' > "$work/identity/admin_password"
cat > "$work/groups/owner.json" <<'EOF'
{"name":"hades-owner"}
EOF
cat > "$work/users/reader.json" <<'EOF'
{"id":"hades-phase3-reader","email":"reader@hades.example.test","password":"synthetic-reader-password","displayName":"Synthetic Phase3 Reader","groups":["lldap_strict_readonly"]}
EOF
cat > "$work/users/owner.json" <<'EOF'
{"id":"synthetic-owner","email":"owner@hades.example.test","password":"synthetic-owner-password","displayName":"Synthetic Owner","groups":["hades-owner"]}
EOF
if [[ "$(id -u)" == 0 ]]; then
  chown -R 1000:1000 "$work/identity" "$work/users" "$work/groups"
fi

"${docker_cmd[@]}" run -d --rm --name "$name" -p "127.0.0.1:$port:17170" \
  -e UID=1000 -e GID=1000 -e TZ=UTC \
  -e LLDAP_LDAP_BASE_DN=dc=hades,dc=local -e LLDAP_LDAP_USER_DN=admin \
  -e LLDAP_LDAP_USER_EMAIL=admin@hades.example.test \
  -e LLDAP_JWT_SECRET_FILE=/run/secrets/jwt -e LLDAP_KEY_SEED_FILE=/run/secrets/seed \
  -e LLDAP_LDAP_USER_PASS_FILE=/run/secrets/pass \
  -v "$work/identity/jwt_secret:/run/secrets/jwt:ro,Z" \
  -v "$work/identity/key_seed:/run/secrets/seed:ro,Z" \
  -v "$work/identity/admin_password:/run/secrets/pass:ro,Z" \
  -v "$work/users:/probe/users:ro,Z" -v "$work/groups:/probe/groups:ro,Z" \
  "$HADES_LLDAP_IMAGE" >/dev/null

for attempt in $(seq 1 60); do
  if curl -fsS --connect-timeout 1 "http://127.0.0.1:$port/health" >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -fsS --connect-timeout 2 "http://127.0.0.1:$port/health" >/dev/null
"${docker_cmd[@]}" exec -e LLDAP_URL=http://localhost:17170 -e LLDAP_ADMIN_USERNAME=admin \
  -e LLDAP_ADMIN_PASSWORD=synthetic-admin-password -e USER_CONFIGS_DIR=/probe/users \
  -e GROUP_CONFIGS_DIR=/probe/groups -e DO_CLEANUP=false "$name" /app/bootstrap.sh >/dev/null

python3 - "$port" "$work" <<'PY'
import json
import os
import subprocess
import sys
import threading
import urllib.request
import urllib.error
from pathlib import Path

from integrations.automation.phase3_lldap_authority import Phase3LldapAuthority
from integrations.automation.phase3_self_service import (
    Phase3AuthorizationError,
    Phase3Authority,
    Phase3Catalog,
    Phase3Service,
    Phase3Store,
)

port, directory = sys.argv[1], Path(sys.argv[2])
config = directory / "authority.json"
config.write_text(json.dumps({
    "schema": 1,
    "reader_user_id": "hades-phase3-reader",
    "subjects": {"stable-synthetic-subject": "synthetic-owner"},
    "groups": {"hades-owner": {"role": "owner", "resources": ["hades-core.health", "grocy.household"]}},
}), encoding="utf-8")
config.chmod(0o600)
password = directory / "reader-password"
password.write_text("synthetic-reader-password\n", encoding="utf-8")
password.chmod(0o600)
resolver = Phase3LldapAuthority(config, password, f"http://127.0.0.1:{port}")
authority = resolver("stable-synthetic-subject")
assert authority.active and authority.role == "owner"
assert authority.resources == frozenset({"hades-core.health", "grocy.household"})

systemd_ready = subprocess.run(
    ["systemctl", "--user", "show-environment"], capture_output=True, check=False,
).returncode == 0
if systemd_ready:
    state_dir = directory / "state"
    state_dir.mkdir(mode=0o700)
    probe = directory / "systemd-probe.py"
    probe.write_text('''import os\nfrom pathlib import Path\nfrom integrations.automation.phase3_lldap_authority import Phase3LldapAuthority\nfrom integrations.automation.phase3_self_service import Phase3Store\nauthority = Phase3LldapAuthority(os.environ["HADES_PHASE3_AUTHORITY_CONFIG"], os.environ["HADES_PHASE3_READER_PASSWORD"], os.environ["HADES_PHASE3_LLDAP_URL"])\nassert authority("stable-synthetic-subject").role == "owner"\nstate = Path(os.environ["HADES_PHASE3_STATE_FILE"])\nstore = Phase3Store(str(state))\nassert store.path.is_file() and (store.path.stat().st_mode & 0o777) == 0o600\nassert store.path.parent.stat().st_mode & 0o777 == 0o700\nprint("SYSTEMD_AUTHORITY_OK")\n''', encoding="utf-8")
    probe.chmod(0o600)
    unit = f"hades-phase3-lldap-runtime-{os.getpid()}-sandbox"
    command = [
        "systemd-run", "--user", "--wait", "--pipe", "--collect", f"--unit={unit}",
        "--property=ProtectSystem=strict", "--property=ProtectHome=read-only",
        "--property=NoNewPrivileges=true", "--property=PrivateTmp=true",
        "--property=MemoryMax=128M", f"--property=ReadWritePaths={state_dir}",
        f"--setenv=PYTHONPATH={Path.cwd()}",
        f"--setenv=HADES_PHASE3_AUTHORITY_CONFIG={config}",
        f"--setenv=HADES_PHASE3_READER_PASSWORD={password}",
        f"--setenv=HADES_PHASE3_LLDAP_URL=http://127.0.0.1:{port}",
        f"--setenv=HADES_PHASE3_STATE_FILE={state_dir}/phase3/automations.sqlite",
        "/usr/bin/python3", str(probe),
    ]
    sandbox = subprocess.run(command, capture_output=True, text=True, check=False)
    if sandbox.returncode != 0 or "SYSTEMD_AUTHORITY_OK" not in sandbox.stdout:
        raise AssertionError("strict-filesystem systemd authority probe failed: " + sandbox.stderr[-1200:])
    print("PASS transient systemd strict-filesystem authority/state contract")

    # Exercise the actual packaged HTTP service under the same filesystem
    # sandbox. The only source is a local synthetic health fixture.
    import http.server
    import socket
    import time
    from integrations.automation.phase3_request import sign_due_request, sign_request

    class HealthHandler(http.server.BaseHTTPRequestHandler):
        calls = 0
        def do_GET(self):
            type(self).calls += 1
            payload = b'{"status":true}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        def log_message(self, *_args):
            return

    health = http.server.ThreadingHTTPServer(("127.0.0.1", 0), HealthHandler)
    health_thread = threading.Thread(target=health.serve_forever, daemon=True)
    health_thread.start()
    generated = directory / "generated"
    generated.mkdir()
    packaged = subprocess.run(
        [sys.executable, "scripts/package-epsilon-source.py", str(Path.cwd()), str(generated)],
        cwd=Path.cwd(), capture_output=True, text=True, check=False,
    )
    assert packaged.returncode == 0, packaged.stderr
    service_state = directory / "service-state"
    service_state.mkdir(mode=0o700)
    key_file = directory / "service-key"
    key_file.write_bytes(b"synthetic-systemd-epsilon-key-at-least-32-bytes")
    key_file.chmod(0o600)
    with socket.socket() as probe_port:
        probe_port.bind(("127.0.0.1", 0))
        service_port = probe_port.getsockname()[1]
    service_url = f"http://127.0.0.1:{service_port}"
    service_db = service_state / "phase3.sqlite"
    service = Phase3Service(Phase3Store(str(service_db)), Phase3Catalog())
    synthetic_owner = Phase3Authority("stable-synthetic-subject", "owner", frozenset({"hades-core.health"}))
    preview = service.preview(synthetic_owner, "server-health-watch", {
        "resource_id": "hades-core", "display_name": "HADES Core", "interval_minutes": 10,
    })
    automation = service.confirm(synthetic_owner, preview["preview_id"], preview["preview_hash"], "systemd-fixture")
    unit = f"hades-epsilon-phase3-service-{os.getpid()}"
    command = [
        "systemd-run", "--user", "--collect", "--unit=" + unit,
        "--property=ProtectSystem=strict", f"--property=ReadWritePaths={service_state}",
        f"--setenv=PYTHONPATH={generated}",
        f"--setenv=HADES_EPSILON_SOURCE_BIND=127.0.0.1",
        f"--setenv=HADES_EPSILON_SOURCE_PORT={service_port}",
        f"--setenv=HADES_EPSILON_HEALTH_URL=http://127.0.0.1:{health.server_port}/health",
        f"--setenv=HADES_EPSILON_PHASE3_STATE_FILE={service_db}",
        f"--setenv=HADES_EPSILON_PHASE3_DIRECTORY_AUTHORITY_FILE={config}",
        f"--setenv=HADES_EPSILON_PHASE3_LLDAP_URL=http://127.0.0.1:{port}",
        f"--setenv=HADES_EPSILON_PHASE3_LLDAP_READER_PASSWORD_FILE={password}",
        f"--setenv=HADES_EPSILON_PHASE3_HMAC_KEY_FILE={key_file}",
        sys.executable, str(generated / "config/epsilon-source/server.py"),
    ]
    started = subprocess.run(command, capture_output=True, text=True, check=False)
    assert started.returncode == 0, started.stderr[-1200:]

    def signed_post(execution_key):
        raw = json.dumps(
            {"automation_id": automation["automation_id"], "execution_key": execution_key},
            separators=(",", ":"),
        ).encode()
        timestamp = str(int(time.time()))
        request = urllib.request.Request(
            service_url + "/v1/epsilon/phase3/run", data=raw, method="POST",
            headers={
                "Content-Type": "application/json",
                "X-HADES-Timestamp": timestamp,
                "X-HADES-Signature": sign_request(key_file.read_bytes(), timestamp, raw),
            },
        )
        return json.load(urllib.request.urlopen(request, timeout=5))

    def signed_due():
        raw = b"{}"
        timestamp = str(int(time.time()))
        request = urllib.request.Request(
            service_url + "/v1/epsilon/phase3/due", data=raw, method="POST",
            headers={
                "Content-Type": "application/json",
                "X-HADES-Timestamp": timestamp,
                "X-HADES-Signature": sign_due_request(key_file.read_bytes(), timestamp, raw),
            },
        )
        return json.load(urllib.request.urlopen(request, timeout=5))["due"]

    try:
        for _ in range(40):
            try:
                first = signed_post("systemd-execution-1")
                break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.25)
        else:
            raise AssertionError("packaged systemd endpoint did not become ready")
        assert first["status"] == "COMPLETE" and first["result"]["hades_state"] == "UP"
        assert HealthHandler.calls == 1
        import sqlite3
        with sqlite3.connect(service_db) as db:
            db.execute(
                "UPDATE phase3_automations SET updated_at=? WHERE automation_id=?",
                (int(time.time()) - 600, automation["automation_id"]),
            )
        due = signed_due()
        assert len(due) == 1 and due[0]["automation_id"] == automation["automation_id"]
        scheduled = signed_post(due[0]["execution_key"])
        assert scheduled["status"] == "COMPLETE" and HealthHandler.calls == 2
        subprocess.run(["systemctl", "--user", "restart", unit], check=True, capture_output=True)
        for _ in range(40):
            try:
                duplicate = signed_post("systemd-execution-1")
                break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.25)
        assert duplicate["replayed"] is True and HealthHandler.calls == 2

        def directory_post(path, payload, bearer=None):
            headers = {"Content-Type": "application/json"}
            if bearer:
                headers["Authorization"] = "Bearer " + bearer
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}{path}", data=json.dumps(payload).encode(), headers=headers,
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                return json.load(response)

        admin_token = directory_post("/auth/simple/login", {"username": "admin", "password": "synthetic-admin-password"})["token"]
        groups = directory_post("/api/graphql", {"query": "{ groups { id displayName } }"}, admin_token)["data"]["groups"]
        owner_group = next(group["id"] for group in groups if group["displayName"] == "hades-owner")
        directory_post("/api/graphql", {"query": f'mutation {{ removeUserFromGroup(userId: "synthetic-owner", groupId: {owner_group}) {{ ok }} }}'}, admin_token)
        try:
            signed_post("systemd-execution-revoked")
        except urllib.error.HTTPError as exc:
            assert exc.code == 403
        else:
            raise AssertionError("packaged systemd runner did not enforce live LLDAP revocation")
        assert HealthHandler.calls == 2, "revoked request reached the canonical source"
        print("PASS packaged Epsilon service under systemd: signed due/run, private inputs, isolated state, restart replay, live revocation before source read")
    finally:
        subprocess.run(["systemctl", "--user", "stop", unit], capture_output=True, check=False)
        health.shutdown()
        health.server_close()
        health_thread.join(timeout=3)
else:
    print("SKIP transient systemd contract: no user systemd manager is available")

def admin_post(path, payload, token=None):
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=8) as response:
        return json.load(response)

login = admin_post("/auth/simple/login", {"username": "admin", "password": "synthetic-admin-password"})
token = login.get("token")
assert token
groups = admin_post("/api/graphql", {"query": "{ groups { id displayName } }"}, token)["data"]["groups"]
owner_group = next(group["id"] for group in groups if group["displayName"] == "hades-owner")
mutation = "mutation { removeUserFromGroup(userId: \"synthetic-owner\", groupId: %d) { ok } }" % owner_group
admin_post("/api/graphql", {"query": mutation}, token)
revoked = resolver("stable-synthetic-subject")
assert revoked.active and revoked.role == "household" and not revoked.resources

admin_post("/api/graphql", {"query": "mutation { deleteUser(userId: \"synthetic-owner\") { ok } }"}, token)
try:
    resolver("stable-synthetic-subject")
except Phase3AuthorizationError:
    pass
else:
    raise AssertionError("deleted LLDAP account retained authority")
print("PASS pinned LLDAP runtime: strict-readonly mapping, exact grants, immediate group revocation, deleted-user fail-closed")
PY
