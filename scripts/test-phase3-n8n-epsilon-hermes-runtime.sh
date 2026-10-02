#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

image=${HADES_N8N_IMAGE:-docker.n8n.io/n8nio/n8n@sha256:9f693fd5565539efd5e75ad168526c8041a6af516d9e50bc4d9cb1c9c5031523}
[[ "$image" =~ ^[^[:space:]=]+@sha256:[0-9a-f]{64}$ ]] || {
  echo 'FAIL HADES_N8N_IMAGE must be an immutable image digest' >&2
  exit 2
}
source config/versions.env
lldap_image=${HADES_LLDAP_IMAGE:?HADES_LLDAP_IMAGE must be pinned in config/versions.env}
webui_image=${HADES_PHASE3_WEBUI_IMAGE:-hades-open-webui:0.11.1-hades-reconstructed}
container_name="hades-phase3-joined-lldap-$$"
webui_container="hades-phase3-joined-webui-$$"
webui_volume="hades-phase3-joined-webui-$$"
epsilon_unit="hades-phase3-joined-epsilon-$$"
baseline_docker_volumes=$(docker volume ls -q 2>/dev/null || true)
cleanup() {
  systemctl --user stop "$epsilon_unit" >/dev/null 2>&1 || true
  systemctl --user reset-failed "$epsilon_unit" >/dev/null 2>&1 || true
  docker rm -fv "$webui_container" >/dev/null 2>&1 || true
  docker volume rm "$webui_volume" >/dev/null 2>&1 || true
  docker rm -f "$container_name" >/dev/null 2>&1 || true
  while IFS= read -r volume; do
    [[ -n "$volume" ]] || continue
    if ! grep -Fxq "$volume" <<<"$baseline_docker_volumes"; then
      labels=$(docker volume inspect --format '{{json .Labels}}' "$volume" 2>/dev/null || true)
      if [[ "$labels" == *'com.docker.volume.anonymous'* ]]; then
        docker volume rm "$volume" >/dev/null 2>&1 || true
      fi
    fi
  done < <(docker volume ls -q 2>/dev/null || true)
}
trap cleanup EXIT
systemctl --user show-environment >/dev/null 2>&1 || {
  echo 'FAIL a user systemd manager is required for packaged Epsilon runtime acceptance' >&2
  exit 2
}
playwright_module=${HADES_PHASE3_PLAYWRIGHT_MODULE:-}
playwright_version=${HADES_PHASE3_PLAYWRIGHT_VERSION:-1.63.0}
[[ -n "$playwright_module" ]] || {
  echo 'FAIL set HADES_PHASE3_PLAYWRIGHT_MODULE to the installed Playwright Node module for authenticated UI acceptance' >&2
  exit 2
}
node - "$playwright_module" "$playwright_version" <<'NODE'
try {
  if (!require(process.argv[2]).chromium) throw new Error('missing chromium export');
  const manifest = require(`${process.argv[2]}/package.json`);
  if (manifest.version !== process.argv[3]) throw new Error(`expected Playwright ${process.argv[3]}, got ${manifest.version}`);
} catch (error) {
  console.error(`FAIL HADES_PHASE3_PLAYWRIGHT_MODULE is not usable: ${error.message}`);
  process.exit(2);
}
NODE

python3 - "$PWD" "$image" "$lldap_image" "$container_name" "$epsilon_unit" "$webui_image" "$webui_container" "$webui_volume" <<'PY'
import hashlib
import hmac
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from integrations.automation.phase3_self_service import (
    Phase3Authority,
    Phase3Service,
    Phase3Store,
)
from integrations.automation.phase3_request import sign_request

repo = Path(sys.argv[1]).resolve()
image = sys.argv[2]
lldap_image = sys.argv[3]
container_name = sys.argv[4]
epsilon_unit = sys.argv[5]
webui_image = sys.argv[6]
webui_container = sys.argv[7]
webui_volume = sys.argv[8]
runner_key = b"synthetic-phase3-runner-key-for-joined-runtime-test"
result_key = b"synthetic-phase3-result-key-for-joined-runtime-test"
reader_password = "synthetic-phase3-reader-password"
gateway = subprocess.run(
    ["docker", "network", "inspect", "bridge", "--format", "{{(index .IPAM.Config 0).Gateway}}"],
    text=True, capture_output=True, check=True,
).stdout.strip()
socket.inet_aton(gateway)
for pinned_image in (image, lldap_image):
    pulled = subprocess.run(
        ["docker", "pull", pinned_image], capture_output=True, text=True, timeout=600,
    )
    if pulled.returncode:
        raise RuntimeError(
            f"pinned test image acquisition failed for {pinned_image}\n{pulled.stderr[-2500:]}"
        )

cache_dir = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
cache_dir.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="hades-phase3-joined-runtime-", dir=cache_dir) as raw_tmp:
    tmp = Path(raw_tmp)
    state_dir = tmp / "epsilon-state"
    state_dir.mkdir(mode=0o700)
    state = state_dir / "phase3.sqlite"
    authority_file = tmp / "authority.json"
    password_file = tmp / "reader-password"
    runner_key_file = tmp / "runner.key"
    result_key_file = tmp / "result.key"
    identity_dir, users_dir, groups_dir = tmp / "identity", tmp / "users", tmp / "groups"
    for directory_path in (identity_dir, users_dir, groups_dir):
        directory_path.mkdir(mode=0o700)
    for filename, value in (
        ("jwt_secret", "synthetic-jwt-secret-for-phase3-joined-runtime-00000000000000000000000000000000"),
        ("key_seed", "synthetic-key-seed-for-phase3-joined-runtime-0000000000000000000000000000000000000000000000000000000000000000"),
        ("admin_password", "synthetic-lldap-admin-password"),
    ):
        (identity_dir / filename).write_text(value + "\n", encoding="utf-8")
        (identity_dir / filename).chmod(0o600)
    for filename, group in (("owner.json", "hades-owner"), ("household.json", "hades-household"), ("reader.json", "lldap_strict_readonly")):
        (groups_dir / filename).write_text(json.dumps({"name": group}) + "\n", encoding="utf-8")
    for filename, user in (
        ("reader.json", {"id": "phase3-reader", "email": "reader@hades.example.test", "password": reader_password, "displayName": "Phase3 Read Only Reader", "groups": ["lldap_strict_readonly"]}),
        ("owner.json", {"id": "synthetic-owner-directory-id", "email": "owner@hades.example.test", "password": "synthetic-owner-password", "displayName": "Synthetic Owner", "groups": ["hades-owner"]}),
        ("beta.json", {"id": "synthetic-beta-directory-id", "email": "beta@hades.example.test", "password": "synthetic-beta-password", "displayName": "Synthetic Beta", "groups": ["hades-household"]}),
        ("gamma.json", {"id": "synthetic-gamma-directory-id", "email": "gamma@hades.example.test", "password": "synthetic-gamma-password", "displayName": "Synthetic Gamma", "groups": ["hades-household"]}),
    ):
        (users_dir / filename).write_text(json.dumps(user) + "\n", encoding="utf-8")
    if os.geteuid() == 0:
        for directory_path in (identity_dir, users_dir, groups_dir):
            os.chown(directory_path, 1000, 1000)
            for entry in directory_path.iterdir():
                os.chown(entry, 1000, 1000)
    subprocess.run([
        "docker", "run", "-d", "--rm", "--name", container_name,
        "-p", "127.0.0.1::17170", "-e", "UID=1000", "-e", "GID=1000", "-e", "TZ=UTC",
        "-e", "LLDAP_LDAP_BASE_DN=dc=hades,dc=local", "-e", "LLDAP_LDAP_USER_DN=admin",
        "-e", "LLDAP_LDAP_USER_EMAIL=admin@hades.example.test",
        "-e", "LLDAP_JWT_SECRET_FILE=/run/secrets/jwt", "-e", "LLDAP_KEY_SEED_FILE=/run/secrets/seed",
        "-e", "LLDAP_LDAP_USER_PASS_FILE=/run/secrets/pass",
        "-v", f"{identity_dir / 'jwt_secret'}:/run/secrets/jwt:ro,Z",
        "-v", f"{identity_dir / 'key_seed'}:/run/secrets/seed:ro,Z",
        "-v", f"{identity_dir / 'admin_password'}:/run/secrets/pass:ro,Z",
        "-v", f"{users_dir}:/probe/users:ro,Z", "-v", f"{groups_dir}:/probe/groups:ro,Z",
        lldap_image,
    ], check=True, capture_output=True, text=True)
    inspection = json.loads(subprocess.run(
        ["docker", "inspect", container_name], check=True, capture_output=True, text=True,
    ).stdout)[0]
    directory_port = int(inspection["NetworkSettings"]["Ports"]["17170/tcp"][0]["HostPort"])
    directory_url = f"http://127.0.0.1:{directory_port}"
    import urllib.request
    for attempt in range(60):
        try:
            urllib.request.urlopen(directory_url + "/health", timeout=2).read()
            break
        except Exception:
            if attempt == 59:
                raise RuntimeError("pinned LLDAP fixture did not become healthy")
            time.sleep(1)
    bootstrap = subprocess.run([
        "docker", "exec", "-e", "LLDAP_URL=http://localhost:17170", "-e", "LLDAP_ADMIN_USERNAME=admin",
        "-e", "LLDAP_ADMIN_PASSWORD=synthetic-lldap-admin-password", "-e", "USER_CONFIGS_DIR=/probe/users",
        "-e", "GROUP_CONFIGS_DIR=/probe/groups", "-e", "DO_CLEANUP=false", container_name, "/app/bootstrap.sh",
    ], capture_output=True, text=True)
    if bootstrap.returncode:
        raise RuntimeError("pinned LLDAP synthetic fixture bootstrap failed")

    def directory_post(path, payload, token=None):
        from urllib.request import Request, urlopen
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        request = Request(directory_url + path, data=json.dumps(payload).encode(), headers=headers, method="POST")
        with urlopen(request, timeout=5) as response:
            return json.load(response)

    admin_token = directory_post("/auth/simple/login", {
        "username": "admin", "password": "synthetic-lldap-admin-password",
    })["token"]
    api_key = "synthetic-phase3-hermes-gateway-key"
    with socket.socket() as gateway_probe:
        gateway_probe.bind(("0.0.0.0", 0))
        gateway_port = gateway_probe.getsockname()[1]
    subprocess.run(["docker", "image", "inspect", webui_image], check=True, capture_output=True)
    subprocess.run(["docker", "volume", "create", webui_volume], check=True, capture_output=True)
    subprocess.run([
        "docker", "run", "-d", "--rm", "--name", webui_container,
        "--add-host", "host.docker.internal:host-gateway", "-p", "127.0.0.1::8080",
        "-e", "ENABLE_SIGNUP=true", "-e", "ENABLE_LOGIN_FORM=true",
        "-e", "ENABLE_OLLAMA_API=false", "-e", "RAG_EMBEDDING_ENGINE=ollama",
        "-e", f"HADES_TASK_NOTIFICATIONS_HERMES_API_BASE_URL=http://host.docker.internal:{gateway_port}/v1",
        "-e", f"HADES_TASK_NOTIFICATIONS_HERMES_API_KEY={api_key}",
        "-v", f"{webui_volume}:/app/backend/data", webui_image,
    ], check=True, capture_output=True, text=True)
    webui_inspection = json.loads(subprocess.run(
        ["docker", "inspect", webui_container], check=True, capture_output=True, text=True,
    ).stdout)[0]
    webui_port = int(webui_inspection["NetworkSettings"]["Ports"]["8080/tcp"][0]["HostPort"])
    webui_url = f"http://127.0.0.1:{webui_port}"
    for attempt in range(120):
        try:
            urllib.request.urlopen(webui_url + "/health", timeout=2).read()
            break
        except Exception:
            if attempt == 119:
                raise RuntimeError("disposable Open WebUI did not become healthy")
            time.sleep(1)

    def webui_post(path, payload, token=None):
        from urllib.request import Request, urlopen
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        request = Request(webui_url + path, data=json.dumps(payload).encode(), headers=headers, method="POST")
        with urlopen(request, timeout=10) as response:
            return json.load(response)

    alpha_account = webui_post("/api/v1/auths/signup", {
        "name": "Alpha", "email": "alpha-phase3@example.invalid", "password": "Synthetic-Only-123!",
    })
    alpha_token = alpha_account["token"]
    for name, email in (("Beta", "beta-phase3@example.invalid"), ("Gamma", "gamma-phase3@example.invalid")):
        webui_post("/api/v1/auths/add", {
            "name": name, "email": email, "password": "Synthetic-Only-123!", "role": "user",
        }, alpha_token)
    users_payload = urllib.request.Request(
        webui_url + "/api/v1/users/", headers={"Authorization": "Bearer " + alpha_token},
    )
    with urllib.request.urlopen(users_payload, timeout=10) as response:
        user_rows = json.load(response)
    if not isinstance(user_rows, list):
        user_rows = user_rows.get("users", user_rows.get("items", []))
    user_ids = {
        row["email"]: row["id"] for row in user_rows
        if isinstance(row, dict) and row.get("email") and row.get("id")
    }
    alpha_id = user_ids.get("alpha-phase3@example.invalid")
    beta_id = user_ids.get("beta-phase3@example.invalid")
    gamma_id = user_ids.get("gamma-phase3@example.invalid")
    if not all((alpha_id, beta_id, gamma_id)):
        raise RuntimeError("disposable Open WebUI did not create all synthetic subjects")

    for path, value in (
        (authority_file, json.dumps({
            "schema": 1,
            "reader_user_id": "phase3-reader",
            "subjects": {
                alpha_id: "synthetic-owner-directory-id",
                beta_id: "synthetic-beta-directory-id",
                gamma_id: "synthetic-gamma-directory-id",
            },
            "groups": {
                "hades-owner": {"role": "owner", "resources": ["grocy.household"]},
                "hades-household": {"role": "household", "resources": ["grocy.household"]},
            },
        }) + "\n"),
        (password_file, reader_password + "\n"),
        (runner_key_file, runner_key + b"\n"),
        (result_key_file, result_key + b"\n"),
    ):
        path.write_bytes(value.encode() if isinstance(value, str) else value)
        path.chmod(0o600)

    epsilon_env = {
        "HADES_EPSILON_PHASE3_STATE_FILE": str(state),
        "HADES_EPSILON_PHASE3_DIRECTORY_AUTHORITY_FILE": str(authority_file),
        "HADES_EPSILON_PHASE3_LLDAP_URL": directory_url,
        "HADES_EPSILON_PHASE3_LLDAP_READER_PASSWORD_FILE": str(password_file),
        "HADES_EPSILON_PHASE3_HMAC_KEY_FILE": str(runner_key_file),
        "HADES_EPSILON_PHASE3_RESULT_HMAC_KEY_FILE": str(result_key_file),
    }
    source_reads = []

    class InventoryHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            type(self).reads.append(True)
            body = json.dumps({
                "hades_state": "READY", "low": ["Synthetic Rice"],
                "out": [], "no_minimum": [],
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            return

    InventoryHandler.reads = source_reads
    inventory = ThreadingHTTPServer(("127.0.0.1", 0), InventoryHandler)
    inventory_thread = threading.Thread(target=inventory.serve_forever, daemon=True)
    inventory_thread.start()

    generated = tmp / "generated-epsilon"
    generated.mkdir(mode=0o700)
    packaged = subprocess.run(
        [sys.executable, str(repo / "scripts/package-epsilon-source.py"), str(repo), str(generated)],
        cwd=repo, capture_output=True, text=True, timeout=60,
    )
    if packaged.returncode:
        raise RuntimeError("Epsilon source packaging failed")
    wrapper = tmp / "packaged-server-wrapper.py"
    wrapper.write_text('''import importlib.util, json, os, urllib.request
from http.server import ThreadingHTTPServer
path = os.environ["HADES_TEST_EPSILON_SERVER"]
spec = importlib.util.spec_from_file_location("hades_packaged_epsilon_server", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
def inventory_fixture():
    with urllib.request.urlopen(os.environ["HADES_TEST_INVENTORY_URL"], timeout=5) as response:
        return json.load(response)
module.inventory = inventory_fixture
ThreadingHTTPServer((module.BIND, module.PORT), module.Handler).serve_forever()
''', encoding="utf-8")
    wrapper.chmod(0o600)
    service_server = generated / "config/epsilon-source/server.py"
    with socket.socket() as port_probe:
        port_probe.bind((gateway, 0))
        epsilon_port = port_probe.getsockname()[1]
    state_dir.chmod(0o700)
    systemd_args = [
        "systemd-run", "--user", "--collect", "--unit=" + epsilon_unit,
        "--property=ProtectSystem=strict", "--property=ProtectHome=read-only",
        "--property=NoNewPrivileges=true", "--property=PrivateTmp=true",
        "--property=MemoryMax=256M", f"--property=ReadWritePaths={state_dir}",
        f"--setenv=PYTHONPATH={generated}",
        f"--setenv=HADES_EPSILON_SOURCE_BIND={gateway}",
        f"--setenv=HADES_EPSILON_SOURCE_PORT={epsilon_port}",
        f"--setenv=HADES_EPSILON_PHASE3_STATE_FILE={state}",
        f"--setenv=HADES_EPSILON_PHASE3_DIRECTORY_AUTHORITY_FILE={authority_file}",
        f"--setenv=HADES_EPSILON_PHASE3_LLDAP_URL={directory_url}",
        f"--setenv=HADES_EPSILON_PHASE3_LLDAP_READER_PASSWORD_FILE={password_file}",
        f"--setenv=HADES_EPSILON_PHASE3_HMAC_KEY_FILE={runner_key_file}",
        f"--setenv=HADES_EPSILON_PHASE3_RESULT_HMAC_KEY_FILE={result_key_file}",
        f"--setenv=HADES_TEST_EPSILON_SERVER={service_server}",
        f"--setenv=HADES_TEST_INVENTORY_URL=http://127.0.0.1:{inventory.server_port}",
        sys.executable, str(wrapper),
    ]
    started = subprocess.run(systemd_args, capture_output=True, text=True, timeout=30)
    if started.returncode:
        raise RuntimeError("strict-systemd packaged Epsilon service did not start: " + started.stderr[-1600:])
    try:
        def wait_epsilon():
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline:
                if subprocess.run(["systemctl", "--user", "is-active", epsilon_unit], capture_output=True).returncode != 0:
                    logs = subprocess.run(
                        ["journalctl", "--user", "-u", epsilon_unit, "--no-pager", "-n", "30"],
                        capture_output=True, text=True, check=False,
                    ).stdout[-3000:]
                    raise RuntimeError("strict-systemd Epsilon unit exited before readiness\n" + logs)
                try:
                    with socket.create_connection((gateway, epsilon_port), timeout=1):
                        return
                except OSError:
                    time.sleep(0.2)
            raise RuntimeError("strict-systemd Epsilon listener did not become ready")

        wait_epsilon()
        # Create only disposable staged data. Backdate its interval so one
        # inactive-workflow execution has a deterministic due row.
        owner = Phase3Authority(alpha_id, "owner", frozenset({"grocy.household"}))
        beta = Phase3Authority(beta_id, "household", frozenset({"grocy.household"}))
        store = Phase3Store(str(state))
        service = Phase3Service(store)
        preview = service.preview(owner, "low-inventory-summary", {
            "interval_minutes": 5, "resource_scope": ["grocy.household"],
        })
        automation = service.confirm(
            owner, preview["preview_id"], preview["preview_hash"], "joined-runtime-confirmation",
        )
        service.store.share(owner, automation["automation_id"], beta)
        with __import__("sqlite3").connect(state) as db:
            db.execute(
                "UPDATE phase3_automations SET updated_at=? WHERE automation_id=?",
                (int(time.time()) - 600, automation["automation_id"]),
            )
        due_rows = store.due_schedule_items(now=int(time.time()))
        if len(due_rows) != 1:
            raise RuntimeError("synthetic Epsilon fixture did not produce exactly one due row")

        workflow = json.loads((repo / "config/epsilon-workflows/phase3-runner-dispatch.json").read_text())
        assert workflow["active"] is False
        # Replace the schedule trigger only in this temporary n8n import.
        for node in workflow["nodes"]:
            if node["name"] == "Every five minutes":
                node["type"] = "n8n-nodes-base.manualTrigger"
                node["typeVersion"] = 1
                node["parameters"] = {}
            if node["type"] == "n8n-nodes-base.crypto":
                node["credentials"]["crypto"]["id"] = "synthetic-phase3-crypto"
            if node["type"] == "n8n-nodes-base.httpRequest":
                node["parameters"]["url"] = node["parameters"]["url"].replace(
                    "host.docker.internal:8643", f"host.docker.internal:{epsilon_port}",
                )
        data = tmp / "n8n-data"
        data.mkdir(mode=0o700)
        credentials = tmp / "credentials.json"
        credentials.write_text(json.dumps([{
            "id": "synthetic-phase3-crypto",
            "name": "HADES Phase3 Runner HMAC",
            "type": "crypto",
            "data": {"hmacSecret": runner_key.decode()},
        }]))
        credentials.chmod(0o600)
        workflow_file = tmp / "workflow.json"
        workflow_file.write_text(json.dumps(workflow))
        workflow_file.chmod(0o600)
        base = [
            "docker", "run", "--rm", "--network", "bridge",
            "--add-host", "host.docker.internal:host-gateway",
            "-v", f"{data}:/home/node/.n8n:Z",
            "-e", "N8N_ENCRYPTION_KEY=synthetic-n8n-encryption-key-for-joined-runtime",
            "-e", "N8N_USER_FOLDER=/home/node", image,
        ]
        for source, target, command in (
            (credentials, "/tmp/credentials.json", "import:credentials"),
            (workflow_file, "/tmp/workflow.json", "import:workflow"),
        ):
            result = subprocess.run(
                base[:3] + ["-v", f"{source}:{target}:ro,Z"] + base[3:] + [command, "--input=" + target],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode:
                raise RuntimeError(
                    f"pinned n8n {command} fixture import failed\n"
                    + result.stdout[-2500:] + result.stderr[-2500:]
                )
        executed = subprocess.run(
            base + ["execute", "--id=hades-phase3-runner-dispatch", "--rawOutput"],
            capture_output=True, text=True, timeout=120,
        )
        if executed.returncode:
            raise RuntimeError(
                "pinned n8n dispatch against actual Epsilon failed\n"
                + executed.stdout[-2500:] + executed.stderr[-2500:]
            )
        if len(source_reads) != 1:
            raise RuntimeError(f"expected one synthetic source call from n8n dispatch; saw {len(source_reads)}")
        if (state.stat().st_mode & 0o777) != 0o600 or state.stat().st_uid != os.geteuid():
            raise RuntimeError("packaged systemd Epsilon state did not retain private file ownership and mode")
        if (state_dir.stat().st_mode & 0o777) != 0o700 or state_dir.stat().st_uid != os.geteuid():
            raise RuntimeError("packaged systemd Epsilon state directory did not retain private ownership and mode")

        # Prove the packaged systemd process can restart with the same key and
        # SQLite state, then safely replay n8n's exact completed delivery.
        restarted = subprocess.run(
            ["systemctl", "--user", "restart", epsilon_unit],
            capture_output=True, text=True, timeout=30,
        )
        if restarted.returncode:
            raise RuntimeError("packaged Epsilon service did not restart cleanly")
        wait_epsilon()
        replay_record = due_rows[0]
        replay_body = json.dumps({
            "automation_id": replay_record["automation_id"],
            "execution_key": replay_record["execution_key"],
        }, separators=(",", ":")).encode()
        replay_timestamp = str(int(time.time()))
        from urllib.request import Request, urlopen
        replay_request = Request(
            f"http://{gateway}:{epsilon_port}/v1/epsilon/phase3/run",
            data=replay_body,
            headers={
                "Content-Type": "application/json",
                "X-HADES-Timestamp": replay_timestamp,
                "X-HADES-Signature": sign_request(runner_key, replay_timestamp, replay_body),
            },
            method="POST",
        )
        with urlopen(replay_request, timeout=5) as response:
            replay = json.load(response)
        if replay.get("status") != "COMPLETE" or replay.get("replayed") is not True or len(source_reads) != 1:
            raise RuntimeError("restart replay duplicated or lost the completed fixed-source run")

        # A second visible automation with the same template/resource identity
        # exercises notification snapshot selection across separate histories.
        # Its older healthy run must not override the newer low-stock result.
        older_automation_id = "synthetic-legacy-duplicate-summary"
        older_completed_at = int(time.time()) - 600
        with __import__("sqlite3").connect(state) as db:
            # Model a legacy duplicate that current service.confirm rejects.
            # It stays disabled; only its visible old result is under test.
            db.execute(
                """INSERT INTO phase3_automations VALUES
                   (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    older_automation_id, alpha_id, alpha_id, "low-inventory-summary",
                    json.dumps(["grocy.household"]), json.dumps([beta_id]), 5, 0,
                    "STAGED", json.dumps({"template_type": "low-inventory-summary", "resource_scope": ["grocy.household"], "interval_minutes": 5}),
                    older_completed_at, older_completed_at, 0,
                ),
            )
            db.execute(
                """INSERT INTO phase3_runs
                   (run_id,automation_id,execution_key,status,result,reason,started_at,completed_at)
                   VALUES(?,?,?,'COMPLETE',?,'',?,?)""",
                (
                    "synthetic-older-healthy-summary", older_automation_id,
                    "synthetic-older-healthy-summary",
                    json.dumps({"hades_state": "READY", "low": [], "out": [], "no_minimum": []}),
                    older_completed_at, older_completed_at,
                ),
            )

        # Start a disposable Hermes API gateway, connect authenticated
        # Open WebUI users to its actual Phase 3 result route, and verify
        # scoped delivery and real LLDAP group revocation in browser UI.
        hermes_bin = os.environ.get("HADES_PHASE3_HERMES_BIN") or shutil.which("hermes")
        if not hermes_bin:
            raise RuntimeError("Hermes CLI is required for the joined acceptance")
        hermes_bin = str(Path(hermes_bin).resolve())
        hermes_bin_dir = Path(hermes_bin).parent
        hermes_python_candidates = (
            Path(os.environ["HADES_PHASE3_HERMES_PYTHON"])
            if os.environ.get("HADES_PHASE3_HERMES_PYTHON") else None,
            hermes_bin_dir / "python3.11",
            hermes_bin_dir.parent / "venv/bin/python",
        )
        hermes_python = next(
            (candidate for candidate in hermes_python_candidates if candidate and candidate.is_file()),
            None,
        )
        if not hermes_python:
            raise RuntimeError("Hermes Python runtime could not be derived from the installed CLI")
        hermes_probe_env = os.environ.copy()
        hermes_probe_env.pop("PYTHONPATH", None)
        hermes_source = Path(subprocess.check_output(
            [str(hermes_python), "-c", "import pathlib, run_agent; print(pathlib.Path(run_agent.__file__).resolve().parent)"],
            env=hermes_probe_env, text=True,
        ).strip())
        hermes_home = tmp / "hermes"
        hermes_home.mkdir(mode=0o700)
        home = tmp / "home"
        home.mkdir(mode=0o700)
        hermes_env = {
            key: os.environ[key]
            for key in ("PATH", "LANG", "LC_ALL", "TZ") if key in os.environ
        }
        hermes_env.update({
            "HOME": str(home),
            "HERMES_HOME": str(hermes_home),
            "PYTHONPATH": f"{repo / 'hermes'}:{repo}:{hermes_source}",
            "HADES_OWNER_SUBJECT_IDS": alpha_id,
            "HADES_TASK_STATE_FILE": str(tmp / "tasks.sqlite"),
            "HADES_EPSILON_PHASE3_RESULT_QUERY_URL": f"http://{gateway}:{epsilon_port}/v1/epsilon/phase3/results",
            "HADES_EPSILON_PHASE3_RESULT_HMAC_KEY_FILE": str(result_key_file),
            "API_SERVER_ENABLED": "true",
            "API_SERVER_KEY": api_key,
            "API_SERVER_HOST": "0.0.0.0",
            "API_SERVER_PORT": str(gateway_port),
            "OPENAI_API_KEY": "synthetic-unused-provider-key",
            "OPENAI_BASE_URL": "http://127.0.0.1:9/v1",
            "MODEL": "synthetic-no-call",
            "HERMES_ACCEPT_HOOKS": "1",
        })
        profile = subprocess.run(
            [hermes_bin, "profile", "create", "hades", "--no-alias", "--no-skills"],
            cwd=repo, env=hermes_env, capture_output=True, text=True, timeout=60,
        )
        if profile.returncode:
            raise RuntimeError("temporary Hermes profile creation failed")
        hermes_log = (tmp / "hermes-gateway.log").open("w", encoding="utf-8")
        gateway_process = subprocess.Popen(
            [hermes_bin, "-p", "hades", "gateway", "run", "--quiet"],
            cwd=repo, env=hermes_env, stdout=hermes_log, stderr=subprocess.STDOUT,
        )
        try:
            gateway_url = f"http://127.0.0.1:{gateway_port}"
            for attempt in range(90):
                if gateway_process.poll() is not None:
                    raise RuntimeError("temporary Hermes gateway exited before readiness")
                try:
                    urllib.request.urlopen(gateway_url + "/health", timeout=2).read()
                    break
                except Exception:
                    if attempt == 89:
                        raise RuntimeError("temporary Hermes API gateway did not become healthy")
                    time.sleep(1)
            model_request = urllib.request.Request(
                gateway_url + "/v1/models", headers={"Authorization": "Bearer " + api_key},
            )
            with urllib.request.urlopen(model_request, timeout=5) as response:
                models = json.load(response).get("data", [])
            model_id = models[0]["id"] if models else ""
            if not model_id:
                raise RuntimeError("temporary Hermes gateway exposed no model")

            webui_post("/openai/config/update", {
                "ENABLE_OPENAI_API": True,
                "OPENAI_API_BASE_URLS": [f"http://host.docker.internal:{gateway_port}/v1"],
                "OPENAI_API_KEYS": [api_key],
                "OPENAI_API_CONFIGS": {"0": {"headers": {"X-Hermes-Session-Key": "hades-user-{{USER_ID}}"}}},
            }, alpha_token)
            access = {
                "id": model_id,
                "name": model_id,
                "access_grants": [
                    {"principal_type": "user", "principal_id": user_id, "permission": "read"}
                    for user_id in (alpha_id, beta_id, gamma_id)
                ],
            }
            webui_post("/api/v1/models/model/access/update", access, alpha_token)

            def run_ui(mode, report):
                environment = dict(os.environ)
                environment.update({
                    "HADES_PHASE3_UI_BASE_URL": webui_url,
                    "HADES_PHASE3_UI_MODEL_ID": model_id,
                    "HADES_PHASE3_UI_PASSWORD": "Synthetic-Only-123!",
                    "HADES_PHASE3_UI_ALPHA_EMAIL": "alpha-phase3@example.invalid",
                    "HADES_PHASE3_UI_BETA_EMAIL": "beta-phase3@example.invalid",
                    "HADES_PHASE3_UI_GAMMA_EMAIL": "gamma-phase3@example.invalid",
                    "HADES_PHASE3_UI_MODE": mode,
                    "HADES_PHASE3_UI_REPORT": str(report),
                })
                result = subprocess.run(
                    ["node", str(repo / "scripts/dom-phase3-result-ui.js")],
                    cwd=repo, env=environment, capture_output=True, text=True, timeout=120,
                )
                if result.returncode:
                    raise RuntimeError("authenticated disposable Open WebUI result acceptance failed\n" + result.stdout + result.stderr[-2500:])
                return result.stdout.strip()

            initial_report = tmp / "phase3-ui-initial.json"
            initial_ui = run_ui("initial", initial_report)
            groups = directory_post("/api/graphql", {"query": "{ groups { id displayName } }"}, admin_token)["data"]["groups"]
            household_group = next(row["id"] for row in groups if row["displayName"] == "hades-household")
            revoke = directory_post("/api/graphql", {
                "query": f'mutation {{ removeUserFromGroup(userId: "synthetic-beta-directory-id", groupId: {household_group}) {{ ok }} }}',
            }, admin_token)
            if revoke["data"]["removeUserFromGroup"]["ok"] is not True:
                raise RuntimeError("pinned LLDAP did not revoke Beta's synthetic household grant")
            revoked_report = tmp / "phase3-ui-revoked.json"
            revoked_ui = run_ui("revoked-beta", revoked_report)
        finally:
            gateway_process.terminate()
            try:
                gateway_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                gateway_process.kill()
                gateway_process.wait(timeout=5)
            hermes_log.close()
        if not json.loads(initial_report.read_text()).get("status") == "PASS":
            raise RuntimeError("initial authenticated Open WebUI result report was not PASS")
        if not json.loads(revoked_report.read_text()).get("status") == "PASS":
            raise RuntimeError("revoked authenticated Open WebUI result report was not PASS")
        print("PASS exact generated Epsilon package under strict transient systemd; pinned n8n signed due/run caused one synthetic source call")
        print("PASS packaged service restart and duplicate signed delivery replayed persisted outcome without another source call")
        print(initial_ui)
        print(revoked_ui)
    finally:
        subprocess.run(["systemctl", "--user", "stop", epsilon_unit], capture_output=True, check=False, timeout=30)
        subprocess.run(["systemctl", "--user", "reset-failed", epsilon_unit], capture_output=True, check=False, timeout=30)
        inventory.shutdown()
        inventory.server_close()
        inventory_thread.join(timeout=3)

print("PASS joined disposable Phase 3 acceptance; production and active schedules untouched")
PY
