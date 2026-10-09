#!/usr/bin/env python3
"""Disposable HTTP, Redis-outage, persistence, and live-session revocation test.

Usage:
  python3 scripts/test-open-webui-auth-revocation-candidate.py IMAGE VALKEY_IMAGE

Both images must be supplied by immutable ID/digest. Only synthetic accounts,
a private Docker network, and a temporary Valkey data volume are used.
"""

from __future__ import annotations

import base64
import json
import os
import pathlib
import re
import select
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid


REPO = pathlib.Path(__file__).resolve().parents[1]
IMAGE = sys.argv[1] if len(sys.argv) > 1 else ""
VALKEY_IMAGE = sys.argv[2] if len(sys.argv) > 2 else ""
IMMUTABLE_IMAGE = re.compile(r"(?:[^\s@]+@sha256:|sha256:)[0-9a-f]{64}")
if not IMMUTABLE_IMAGE.fullmatch(IMAGE) or not IMMUTABLE_IMAGE.fullmatch(VALKEY_IMAGE):
    raise SystemExit("FAIL pass both images by immutable sha256 digest")


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=True, text=True, capture_output=True)


def api(base: str, method: str, path: str, payload: dict | None = None,
        token: str | None = None) -> tuple[int, dict | str | None]:
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            return error.code, json.loads(raw)
        except json.JSONDecodeError:
            return error.code, raw


def wait_valkey(container: str) -> None:
    for _ in range(40):
        result = subprocess.run(
            ["docker", "exec", container, "valkey-cli", "ping"],
            capture_output=True, text=True,
        )
        if result.returncode == 0 and result.stdout.strip() == "PONG":
            return
        time.sleep(0.25)
    raise RuntimeError("Valkey did not become ready")


def decode_jwt_payload(token: str) -> dict:
    part = token.split(".")[1]
    part += "=" * (-len(part) % 4)
    return json.loads(base64.urlsafe_b64decode(part))


def snapshot_restore_revocation(valkey: str, suffix: str, created: list[str]) -> None:
    scan = run([
        "docker", "exec", valkey, "valkey-cli", "--raw", "--scan",
        "--pattern", "*auth:token:*:revoked",
    ]).stdout.splitlines()
    if not scan:
        raise RuntimeError("No synthetic token-revocation marker exists for the RDB restore test")
    key = scan[0]
    expected = run(["docker", "exec", valkey, "valkey-cli", "--raw", "GET", key]).stdout.strip()
    if not expected:
        raise RuntimeError("Could not read the synthetic revocation marker before backup")

    before = int(run(["docker", "exec", valkey, "valkey-cli", "--raw", "LASTSAVE"]).stdout.strip())
    run(["docker", "exec", valkey, "valkey-cli", "BGSAVE"])
    for _ in range(90):
        info = run(["docker", "exec", valkey, "valkey-cli", "--raw", "INFO", "persistence"]).stdout
        last_save = int(run(["docker", "exec", valkey, "valkey-cli", "--raw", "LASTSAVE"]).stdout.strip())
        fields = dict(line.split(":", 1) for line in info.splitlines() if ":" in line)
        if fields.get("rdb_bgsave_in_progress") == "0" and fields.get("rdb_last_bgsave_status") == "ok" and last_save > before:
            break
        time.sleep(1)
    else:
        raise RuntimeError("Synthetic Valkey RDB snapshot did not complete")

    restore_name = f"hades-auth-revoke-{suffix}-rdb-restore"
    with tempfile.TemporaryDirectory(prefix="hades-auth-state-rdb-") as raw:
        rdb = pathlib.Path(raw) / "dump.rdb"
        run(["docker", "cp", f"{valkey}:/data/dump.rdb", str(rdb)])
        if rdb.stat().st_size == 0:
            raise RuntimeError("Synthetic Valkey RDB is empty")
        run([
            "docker", "run", "--rm", "--network", "none", "--entrypoint", "valkey-check-rdb",
            "-v", f"{rdb}:/backup/dump.rdb:ro", VALKEY_IMAGE, "/backup/dump.rdb",
        ])
        run([
            "docker", "create", "--name", restore_name, "--network", "none",
            VALKEY_IMAGE, "valkey-server", "--dir", "/data", "--dbfilename", "dump.rdb",
            "--save", "", "--appendonly", "no",
        ])
        created.append(restore_name)
        run(["docker", "cp", str(rdb), f"{restore_name}:/data/dump.rdb"])
        run(["docker", "start", restore_name])
        try:
            wait_valkey(restore_name)
        except Exception as error:
            logs = subprocess.run(["docker", "logs", restore_name], capture_output=True, text=True)
            raise RuntimeError(f"Disposable Valkey RDB restore failed to start: {logs.stdout[-1200:]} {logs.stderr[-1200:]}") from error
        restored = run(["docker", "exec", restore_name, "valkey-cli", "--raw", "GET", key]).stdout.strip()
        if restored != expected:
            raise RuntimeError("Disposable RDB restore did not preserve the token-revocation marker")
    print("PASS pinned Valkey RDB validates, restores, and preserves a synthetic revocation marker")


def wait_http(base: str) -> None:
    for _ in range(120):
        try:
            status, _ = api(base, "GET", "/health")
            if status == 200:
                return
        except (OSError, TimeoutError):
            pass
        time.sleep(1)
    raise RuntimeError("Open WebUI candidate did not become healthy")


def connect_socket(container: str, token: str) -> subprocess.Popen[str]:
    client = r'''import asyncio, os, socketio
sio = socketio.AsyncClient(reconnection=False)
@sio.event
async def disconnect():
    print("DISCONNECTED", flush=True)
async def main():
    await sio.connect("http://127.0.0.1:8080", auth={"token":os.environ["HADES_SOCKET_TOKEN"]}, socketio_path="ws/socket.io", transports=["websocket"], wait_timeout=12)
    print("CONNECTED", flush=True)
    await asyncio.wait_for(sio.wait(), timeout=40)
asyncio.run(main())
'''
    process = subprocess.Popen(
        ["docker", "exec", "-e", "HADES_SOCKET_TOKEN=" + token,
         container, "python", "-u", "-c", client],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if process.stdout is None:
        raise RuntimeError("Socket.IO probe has no output stream")
    ready, _, _ = select.select([process.stdout], [], [], 20)
    if not ready:
        process.kill()
        raise RuntimeError("Socket.IO session did not connect in time")
    marker = process.stdout.readline().strip()
    if marker != "CONNECTED":
        stderr = process.stderr.read() if process.stderr else ""
        raise RuntimeError(f"Socket.IO session failed to connect: {marker} {stderr[:500]}")
    return process


def require_disconnect(process: subprocess.Popen[str], name: str) -> None:
    if process.stdout is None:
        raise RuntimeError(f"{name}: no Socket.IO output stream")
    ready, _, _ = select.select([process.stdout], [], [], 10)
    marker = process.stdout.readline().strip() if ready else ""
    if marker != "DISCONNECTED":
        raise RuntimeError(f"{name}: existing Socket.IO session was not disconnected ({marker!r})")
    process.wait(timeout=10)
    print(f"PASS {name}: existing Socket.IO session closed")


def main() -> None:
    suffix = uuid.uuid4().hex[:8]
    network = f"hades-auth-revoke-{suffix}-net"
    valkey = f"hades-auth-revoke-{suffix}-valkey"
    webui = f"hades-auth-revoke-{suffix}-webui"
    peer = f"hades-auth-revoke-{suffix}-webui-peer"
    volume = f"hades-auth-revoke-{suffix}-valkey-data"
    webui_data_volume = f"hades-auth-revoke-{suffix}-webui-data"
    created_containers: list[str] = []
    created_volumes: list[str] = []
    created_network = False
    sockets: list[subprocess.Popen[str]] = []
    try:
        run(["docker", "image", "inspect", IMAGE])
        run(["docker", "image", "inspect", VALKEY_IMAGE])
        run(["docker", "network", "create", network])
        created_network = True
        for named_volume in (volume, webui_data_volume):
            run(["docker", "volume", "create", named_volume])
            created_volumes.append(named_volume)
        run([
            "docker", "run", "-d", "--name", valkey, "--network", network,
            "--network-alias", "redis", "-v", f"{volume}:/data",
            VALKEY_IMAGE, "valkey-server", "--save", "", "--appendonly", "yes",
            "--appendfsync", "always",
        ])
        created_containers.append(valkey)
        wait_valkey(valkey)
        run([
            "docker", "run", "-d", "--name", webui, "--network", network,
            "-p", "127.0.0.1::8080", "-e", "ENABLE_SIGNUP=true",
            "-e", "ENABLE_LOGIN_FORM=true", "-e", "ENABLE_OLLAMA_API=false",
            "-e", "RAG_EMBEDDING_ENGINE=ollama", "-e", "REDIS_URL=redis://redis:6379/0",
            "-e", "WEBSOCKET_MANAGER=redis", "-e", "WEBSOCKET_REDIS_URL=redis://redis:6379/1",
            "-e", "REDIS_SOCKET_CONNECT_TIMEOUT=1",
            "-v", f"{webui_data_volume}:/app/backend/data", IMAGE,
        ])
        created_containers.append(webui)
        port = run(["docker", "port", webui, "8080/tcp"]).stdout.strip().split(":")[-1]
        base = f"http://127.0.0.1:{port}"
        wait_http(base)
        run([
            "docker", "run", "-d", "--name", peer, "--network", network,
            "-p", "127.0.0.1::8080", "-e", "ENABLE_SIGNUP=true",
            "-e", "ENABLE_LOGIN_FORM=true", "-e", "ENABLE_OLLAMA_API=false",
            "-e", "RAG_EMBEDDING_ENGINE=ollama", "-e", "REDIS_URL=redis://redis:6379/0",
            "-e", "WEBSOCKET_MANAGER=redis", "-e", "WEBSOCKET_REDIS_URL=redis://redis:6379/1",
            "-e", "REDIS_SOCKET_CONNECT_TIMEOUT=1",
            "-v", f"{webui_data_volume}:/app/backend/data", IMAGE,
        ])
        created_containers.append(peer)
        peer_port = run(["docker", "port", peer, "8080/tcp"]).stdout.strip().split(":")[-1]
        wait_http(f"http://127.0.0.1:{peer_port}")

        status, admin = api(base, "POST", "/api/v1/auths/signup", {
            "name": "Synthetic Admin", "email": f"admin-{suffix}@example.invalid",
            "password": "Synthetic-Only-123!",
        })
        if status != 200 or not isinstance(admin, dict) or not admin.get("token"):
            raise RuntimeError(f"Synthetic admin signup failed (HTTP {status})")
        admin_token = admin["token"]
        status, user = api(base, "POST", "/api/v1/auths/add", {
            "name": "Synthetic User", "email": f"user-{suffix}@example.invalid",
            "password": "Synthetic-Only-123!", "role": "user",
        }, admin_token)
        if status != 200 or not isinstance(user, dict) or not user.get("token"):
            raise RuntimeError(f"Synthetic user creation failed (HTTP {status})")

        status, _ = api(base, "GET", "/api/v1/users/user/info", token=user["token"])
        if status != 200:
            raise RuntimeError(f"Healthy Redis did not authenticate user (HTTP {status})")
        user_socket = connect_socket(webui, user["token"])
        sockets.append(user_socket)
        status, _ = api(base, "POST", "/api/v1/auths/signout", {}, user["token"])
        if status != 200:
            raise RuntimeError(f"Sign-out with healthy Redis failed (HTTP {status})")
        status, _ = api(base, "GET", "/api/v1/users/user/info", token=user["token"])
        if status != 401:
            raise RuntimeError(f"Signed-out token was not rejected (HTTP {status})")
        require_disconnect(user_socket, "healthy-store sign-out")
        print("PASS sign-out stores revocation and rejects the token through HTTP")
        snapshot_restore_revocation(valkey, suffix, created_containers)

        admin_socket = connect_socket(webui, admin_token)
        sockets.append(admin_socket)
        run(["docker", "stop", valkey])
        time.sleep(0.5)
        status, _ = api(base, "GET", "/api/v1/users/user/info", token=admin_token)
        if status != 503:
            raise RuntimeError(f"Store outage did not fail closed with HTTP 503 (got {status})")
        status, _ = api(base, "POST", "/api/v1/auths/signout", {}, admin_token)
        if status != 503:
            raise RuntimeError(f"Sign-out outage was not reported with HTTP 503 (got {status})")
        status, _ = api(base, "POST", f"/api/v1/users/{user['id']}/update", {"role": "pending"}, admin_token)
        if status != 503:
            raise RuntimeError(f"Authority mutation during store outage did not fail closed (HTTP {status})")
        if admin_socket.poll() is not None:
            raise RuntimeError("Existing Socket.IO session unexpectedly exited during the store outage")
        print("PASS store outage rejects HTTP authority, blocks role mutation, and leaves the unchanged socket session observable")

        run(["docker", "start", valkey])
        wait_valkey(valkey)
        time.sleep(0.5)
        status, _ = api(base, "GET", "/api/v1/users/user/info", token=user["token"])
        if status != 401:
            raise RuntimeError(f"Persistent revocation was lost after Valkey restart (HTTP {status})")
        status, _ = api(base, "GET", "/api/v1/users/user/info", token=admin_token)
        if status != 200:
            raise RuntimeError(f"Uncompleted sign-out was not retryable after recovery (HTTP {status})")
        status, recovered_user = api(base, "GET", "/api/v1/users/user/info", token=user["token"])
        if status != 200 or not isinstance(recovered_user, dict) or recovered_user.get("role") != "user":
            raise RuntimeError("Failed closed role mutation changed authority despite store outage")
        status, _ = api(base, "POST", "/api/v1/auths/signout", {}, admin_token)
        if status != 200:
            raise RuntimeError(f"Retry sign-out after store recovery failed (HTTP {status})")
        status, _ = api(base, "GET", "/api/v1/users/user/info", token=admin_token)
        if status != 401:
            raise RuntimeError(f"Retry sign-out did not revoke the token (HTTP {status})")
        status, admin = api(base, "POST", "/api/v1/auths/signin", {
            "email": f"admin-{suffix}@example.invalid", "password": "Synthetic-Only-123!",
        })
        if status != 200 or not isinstance(admin, dict) or not admin.get("token"):
            raise RuntimeError(f"Admin reauthentication after sign-out failed (HTTP {status})")
        admin_token = admin["token"]
        print("PASS Valkey AOF preserves revocations across restart; failed sign-out can be retried")

        def add_user(name: str) -> dict:
            status, created = api(base, "POST", "/api/v1/auths/add", {
                "name": name, "email": f"{name.lower().replace(' ', '-')}-{suffix}@example.invalid",
                "password": "Synthetic-Only-123!", "role": "user",
            }, admin_token)
            if status != 200 or not isinstance(created, dict) or not created.get("token"):
                raise RuntimeError(f"Could not create synthetic {name} (HTTP {status})")
            return created

        role_user = add_user("Role User")
        role_socket = connect_socket(peer, role_user["token"])
        sockets.append(role_socket)
        status, _ = api(base, "POST", f"/api/v1/users/{role_user['id']}/update", {"role": "pending"}, admin_token)
        if status != 200:
            raise RuntimeError(f"Role demotion failed (HTTP {status})")
        status, _ = api(base, "GET", "/api/v1/users/user/info", token=role_user["token"])
        if status != 401:
            raise RuntimeError(f"Old token remained valid after role demotion (HTTP {status})")
        require_disconnect(role_socket, "role demotion")
        print("PASS role demotion revokes the old HTTP token and live socket")

        password_user = add_user("Password User")
        status, _ = api(base, "POST", f"/api/v1/users/{password_user['id']}/update", {
            "password": "Synthetic-Changed-123!",
        }, admin_token)
        if status != 200:
            raise RuntimeError(f"Password change failed (HTTP {status})")
        status, _ = api(base, "GET", "/api/v1/users/user/info", token=password_user["token"])
        if status != 401:
            raise RuntimeError(f"Old token remained valid after password change (HTTP {status})")
        print("PASS admin password change revokes previously issued tokens")

        self_password_user = add_user("Self Password User")
        self_started = time.monotonic()
        status, changed = api(base, "POST", "/api/v1/auths/update/password", {
            "password": "Synthetic-Only-123!", "new_password": "Synthetic-Self-Changed-123!",
        }, self_password_user["token"])
        if status != 200 or changed is not True:
            raise RuntimeError(f"Self-service password change failed (HTTP {status})")
        status, _ = api(base, "GET", "/api/v1/users/user/info", token=self_password_user["token"])
        if status != 401:
            raise RuntimeError(f"Self-service password change left the old token valid (HTTP {status})")
        status, changed_login = api(base, "POST", "/api/v1/auths/signin", {
            "email": f"self-password-user-{suffix}@example.invalid",
            "password": "Synthetic-Self-Changed-123!",
        })
        self_elapsed = time.monotonic() - self_started
        if status != 200 or not isinstance(changed_login, dict) or not changed_login.get("token"):
            raise RuntimeError(f"Immediate re-login after self-service password change failed (HTTP {status})")
        if self_elapsed > 2.0:
            raise RuntimeError(f"Immediate token refresh exceeded the 2 second bound ({self_elapsed:.3f}s)")
        marker_keys = run([
            "docker", "exec", valkey, "valkey-cli", "--raw", "--scan", "--pattern",
            f"*auth:user:{self_password_user['id']}:revoked_at",
        ]).stdout.splitlines()
        if len(marker_keys) != 1:
            raise RuntimeError("Self-service password change did not create exactly one user revocation marker")
        marker = float(run(["docker", "exec", valkey, "valkey-cli", "--raw", "GET", marker_keys[0]]).stdout.strip())
        replacement_iat = float(decode_jwt_payload(changed_login["token"]).get("iat", -1))
        if replacement_iat <= marker:
            raise RuntimeError("Immediate replacement JWT iat is not newer than the revocation marker")
        status, _ = api(base, "GET", "/api/v1/users/user/info", token=changed_login["token"])
        if status != 200:
            raise RuntimeError(f"Replacement token was invalid immediately after password change (HTTP {status})")
        status, _ = api(base, "POST", "/api/v1/auths/signin", {
            "email": f"self-password-user-{suffix}@example.invalid",
            "password": "Synthetic-Only-123!",
        })
        if status not in (400, 401):
            raise RuntimeError(f"Old self-service password remained accepted (HTTP {status})")
        print(f"PASS self-service password revocation and immediate replacement token ({self_elapsed:.3f}s)")

        deleted_user = add_user("Deleted User")
        deleted_socket = connect_socket(peer, deleted_user["token"])
        sockets.append(deleted_socket)
        status, _ = api(base, "DELETE", f"/api/v1/users/{deleted_user['id']}", token=admin_token)
        if status != 200:
            raise RuntimeError(f"Synthetic account deletion failed (HTTP {status})")
        status, _ = api(base, "GET", "/api/v1/users/user/info", token=deleted_user["token"])
        if status != 401:
            raise RuntimeError(f"Deleted-account token remained valid (HTTP {status})")
        require_disconnect(deleted_socket, "account deletion")
        print("PASS account deletion revokes old HTTP and live socket sessions")
    finally:
        for process in sockets:
            if process.poll() is None:
                process.kill()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
        for container in reversed(created_containers):
            subprocess.run(["docker", "rm", "-f", container], capture_output=True, text=True)
        for named_volume in created_volumes:
            subprocess.run(["docker", "volume", "rm", named_volume], capture_output=True, text=True)
        if created_network:
            subprocess.run(["docker", "network", "rm", network], capture_output=True, text=True)


if __name__ == "__main__":
    main()
