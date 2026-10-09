#!/usr/bin/env python3
"""Disposable HTTP, Redis-outage, persistence, and live-session revocation test.

Usage:
  python3 scripts/test-open-webui-auth-revocation-candidate.py IMAGE VALKEY_IMAGE

Both images must be supplied by immutable ID/digest. Only synthetic accounts,
a private Docker network, and a temporary Valkey data volume are used.
"""

from __future__ import annotations

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
    volume = f"hades-auth-revoke-{suffix}-data"
    created_containers: list[str] = []
    created_volume = False
    created_network = False
    sockets: list[subprocess.Popen[str]] = []
    try:
        run(["docker", "image", "inspect", IMAGE])
        run(["docker", "image", "inspect", VALKEY_IMAGE])
        run(["docker", "network", "create", network])
        created_network = True
        run(["docker", "volume", "create", volume])
        created_volume = True
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
            "-e", "REDIS_SOCKET_CONNECT_TIMEOUT=1", IMAGE,
        ])
        created_containers.append(webui)
        port = run(["docker", "port", webui, "8080/tcp"]).stdout.strip().split(":")[-1]
        base = f"http://127.0.0.1:{port}"
        wait_http(base)

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
        require_disconnect(admin_socket, "store-outage sign-out")
        print("PASS store outage rejects authenticated HTTP requests and reports sign-out failure")

        run(["docker", "start", valkey])
        wait_valkey(valkey)
        time.sleep(0.5)
        status, _ = api(base, "GET", "/api/v1/users/user/info", token=user["token"])
        if status != 401:
            raise RuntimeError(f"Persistent revocation was lost after Valkey restart (HTTP {status})")
        status, _ = api(base, "GET", "/api/v1/users/user/info", token=admin_token)
        if status != 200:
            raise RuntimeError(f"Uncompleted sign-out was not retryable after recovery (HTTP {status})")
        status, _ = api(base, "POST", "/api/v1/auths/signout", {}, admin_token)
        if status != 200:
            raise RuntimeError(f"Retry sign-out after store recovery failed (HTTP {status})")
        status, _ = api(base, "GET", "/api/v1/users/user/info", token=admin_token)
        if status != 401:
            raise RuntimeError(f"Retry sign-out did not revoke the token (HTTP {status})")
        print("PASS Valkey AOF preserves revocations across restart; failed sign-out can be retried")
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
        if created_volume:
            subprocess.run(["docker", "volume", "rm", volume], capture_output=True, text=True)
        if created_network:
            subprocess.run(["docker", "network", "rm", network], capture_output=True, text=True)


if __name__ == "__main__":
    main()
