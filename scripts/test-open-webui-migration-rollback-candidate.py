#!/usr/bin/env python3
"""Exercise an isolated Open WebUI 0.11.1 -> candidate data migration.

Usage: python3 scripts/test-open-webui-migration-rollback-candidate.py OLD_IMAGE NEW_IMAGE

The script creates synthetic users/chats on the old image, upgrades a copy of
its stopped data directory, verifies persistence and isolation on the candidate,
then restores the original snapshot under the old image to test rollback.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


if len(sys.argv) != 3:
    raise SystemExit("usage: test-open-webui-migration-rollback-candidate.py OLD_IMAGE NEW_IMAGE")
OLD_IMAGE, NEW_IMAGE = sys.argv[1:]
SECRET = "synthetic-open-webui-migration-secret-00000000000000000000000000000000"
PASSWORD = "Synthetic-Migration-123!"
MODEL = "synthetic-migration-model"
MARKERS = {"alpha": "Migration-Alpha-Marker", "beta": "Migration-Beta-Marker"}


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=True, text=True, capture_output=True)


def api(base: str, method: str, path: str, payload: dict | None = None, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"{method} {path} returned HTTP {error.code}: {detail}") from None


class Backend(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _send(self, payload: dict):
        encoded = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path == "/api/tags":
            self._send({"models": [{"name": "nomic-embed-text:latest", "model": "nomic-embed-text:latest", "digest": "synthetic"}]})
        elif self.path == "/v1/models":
            self._send({"data": [{"id": MODEL, "object": "model", "owned_by": "synthetic"}]})
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
        if self.path in {"/api/embeddings", "/api/embed"}:
            if self.path.endswith("/embed"):
                self._send({"embeddings": [[0.125] * 16 for _ in request.get("input", [])]})
            else:
                self._send({"embedding": [0.125] * 16})
            return
        if self.path != "/v1/chat/completions":
            self.send_response(404); self.end_headers(); return
        prompt = " ".join(str(m.get("content", "")) for m in request.get("messages", []))
        reply = "Migration-Beta-Confirmed" if "Beta" in prompt else "Migration-Alpha-Confirmed"
        self._send({
            "id": str(uuid.uuid4()), "object": "chat.completion", "created": int(time.time()),
            "model": MODEL,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
        })


def reserve_port() -> int:
    with socket.socket() as sock:
        sock.bind(("0.0.0.0", 0))
        return sock.getsockname()[1]


def wait_health(url: str, name: str) -> None:
    for _ in range(120):
        try:
            with urllib.request.urlopen(url + "/health", timeout=2):
                return
        except Exception:
            time.sleep(1)
    raise RuntimeError(f"{name} did not become healthy")


def current_url(name: str) -> str:
    mapping = run(["docker", "port", name, "8080/tcp"]).stdout.strip().rsplit(":", 1)
    return "http://127.0.0.1:" + mapping[-1]


def start(name: str, image: str, data_dir: pathlib.Path, provider_port: int) -> tuple[int, str]:
    run([
        "docker", "run", "-d", "--rm", "--name", name,
        "-p", "127.0.0.1::8080", "--add-host", "host.docker.internal:host-gateway",
        "-e", "ENABLE_SIGNUP=true", "-e", "ENABLE_LOGIN_FORM=true",
        "-e", "ENABLE_OLLAMA_API=false", "-e", "RAG_EMBEDDING_ENGINE=ollama",
        "-e", "OLLAMA_BASE_URL=http://host.docker.internal:" + str(provider_port),
        "-e", "WEBUI_SECRET_KEY=" + SECRET,
        "-e", "ENABLE_TITLE_GENERATION=false", "-e", "ENABLE_FOLLOW_UP_GENERATION=false",
        "-e", "ENABLE_TAGS_GENERATION=false",
        "-v", f"{data_dir}:/app/backend/data:Z", image,
    ])
    inspection = json.loads(run(["docker", "inspect", name]).stdout)[0]
    host_port = int(inspection["NetworkSettings"]["Ports"]["8080/tcp"][0]["HostPort"])
    base = f"http://127.0.0.1:{host_port}"
    wait_health(base, name)
    return host_port, base


def login(base: str, email: str) -> str:
    return api(base, "POST", "/api/v1/auths/signin", {"email": email, "password": PASSWORD})["token"]


def create_chat(base: str, token: str, prompt: str) -> str:
    message_id, assistant_id, session_id = (str(uuid.uuid4()) for _ in range(3))
    payload = {
        "model": MODEL,
        "messages": [{"id": message_id, "role": "user", "content": prompt}],
        "stream": False,
        "parent_id": None,
        "id": assistant_id,
        "session_id": session_id,
        "user_message": {"id": message_id, "role": "user", "content": prompt},
    }
    response = api(base, "POST", "/api/chat/completions", payload, token)
    chat_id = response.get("chat_id")
    if not chat_id:
        raise RuntimeError("synthetic chat completion did not return a chat ID")
    stored = api(base, "GET", f"/api/v1/chats/{chat_id}", token=token)
    if prompt not in json.dumps(stored) or "Migration-" not in json.dumps(stored):
        raise RuntimeError("synthetic chat was not persisted with its completion")
    return chat_id


def assert_chat_isolation(base: str, alpha_token: str, beta_token: str, chat_id: str, marker: str) -> None:
    alpha_chat = api(base, "GET", f"/api/v1/chats/{chat_id}", token=alpha_token)
    if marker not in json.dumps(alpha_chat):
        raise RuntimeError("Alpha's migrated chat marker is missing")
    try:
        api(base, "GET", f"/api/v1/chats/{chat_id}", token=beta_token)
    except RuntimeError as error:
        if "HTTP 401" not in str(error) and "HTTP 403" not in str(error):
            raise
    else:
        raise RuntimeError("Beta could access Alpha's private chat")


def integrity(name: str) -> None:
    output = run([
        "docker", "exec", name, "python", "-c",
        "import sqlite3; c=sqlite3.connect('/app/backend/data/webui.db'); "
        "assert c.execute('pragma integrity_check').fetchone()[0]=='ok'",
    ])
    if output.returncode:
        raise RuntimeError("Open WebUI database integrity check failed")


def normalize_owner(path: pathlib.Path) -> None:
    run([
        "docker", "run", "--rm", "--user", "0", "--entrypoint", "/bin/sh",
        "-v", f"{path}:/cleanup:Z", OLD_IMAGE,
        "-c", f"chown -R {os.getuid()}:{os.getgid()} /cleanup",
    ])


def main() -> None:
    run(["docker", "image", "inspect", OLD_IMAGE])
    run(["docker", "image", "inspect", NEW_IMAGE])
    with socket.socket() as sock:
        sock.bind(("0.0.0.0", 0))
        provider_port = sock.getsockname()[1]
    provider = ThreadingHTTPServer(("0.0.0.0", provider_port), Backend)
    thread = threading.Thread(target=provider.serve_forever, daemon=True)
    thread.start()
    suffix = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
    names = [f"hades-webui-migrate-old-{suffix}", f"hades-webui-migrate-new-{suffix}", f"hades-webui-rollback-{suffix}"]
    root = pathlib.Path(tempfile.mkdtemp(prefix="hades-webui-migration-"))
    try:
        old_data, candidate_data, rollback_data = (root / n for n in ("old", "candidate", "rollback"))
        for path in (old_data, candidate_data, rollback_data):
            path.mkdir(mode=0o700)
            if os.geteuid() == 0:
                os.chown(path, 1000, 1000)

        _, old_url = start(names[0], OLD_IMAGE, old_data, provider_port)
        alpha = api(old_url, "POST", "/api/v1/auths/signup", {
            "name": "Migration Alpha", "email": "migration-alpha@example.invalid", "password": PASSWORD,
        })
        alpha_token = alpha["token"]
        beta = api(old_url, "POST", "/api/v1/auths/add", {
            "name": "Migration Beta", "email": "migration-beta@example.invalid",
            "password": PASSWORD, "role": "user",
        }, alpha_token)
        beta_token = beta["token"]
        api(old_url, "POST", "/openai/config/update", {
            "ENABLE_OPENAI_API": True,
            "OPENAI_API_BASE_URLS": [f"http://host.docker.internal:{provider_port}/v1"],
            "OPENAI_API_KEYS": ["synthetic"], "OPENAI_API_CONFIGS": {},
        }, alpha_token)
        alpha_chat = create_chat(old_url, alpha_token, "Alpha " + MARKERS["alpha"])
        assert_chat_isolation(old_url, alpha_token, beta_token, alpha_chat, MARKERS["alpha"])
        integrity(names[0])
        run(["docker", "rm", "-f", names[0]])
        normalize_owner(old_data)
        shutil.copytree(old_data, candidate_data, dirs_exist_ok=True)
        shutil.copytree(old_data, rollback_data, dirs_exist_ok=True)
        print("PASS 0.11.1 legacy database seeded with two accounts and isolated chats")

        _, candidate_url = start(names[1], NEW_IMAGE, candidate_data, provider_port)
        alpha_new = login(candidate_url, "migration-alpha@example.invalid")
        beta_new = login(candidate_url, "migration-beta@example.invalid")
        assert_chat_isolation(candidate_url, alpha_new, beta_new, alpha_chat, MARKERS["alpha"])
        integrity(names[1])
        run(["docker", "restart", names[1]])
        candidate_url = current_url(names[1])
        wait_health(candidate_url, names[1] + " restart")
        assert_chat_isolation(candidate_url, alpha_new, beta_new, alpha_chat, MARKERS["alpha"])
        integrity(names[1])
        run(["docker", "rm", "-f", names[1]])
        print("PASS patched 0.11.4 migration preserves both accounts, Alpha's private chat, isolation, and SQLite integrity after restart")

        _, rollback_url = start(names[2], OLD_IMAGE, rollback_data, provider_port)
        alpha_rollback = login(rollback_url, "migration-alpha@example.invalid")
        beta_rollback = login(rollback_url, "migration-beta@example.invalid")
        assert_chat_isolation(rollback_url, alpha_rollback, beta_rollback, alpha_chat, MARKERS["alpha"])
        integrity(names[2])
        print("PASS restored pre-upgrade snapshot boots on 0.11.1 with private chats intact")
    finally:
        for name in names:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True)
        normalize_owner(root)
        shutil.rmtree(root)
        provider.shutdown()
        provider.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
