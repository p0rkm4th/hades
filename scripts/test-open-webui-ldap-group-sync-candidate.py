#!/usr/bin/env python3
"""Disposable LDAP auth and group-revocation acceptance for a WebUI image.

Usage: python3 scripts/test-open-webui-ldap-group-sync-candidate.py IMAGE

The test uses pinned LLDAP, synthetic identities, a temporary WebUI volume, and
a private Docker network. No production service or identity is touched.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading


REPO = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = REPO / "config" / "versions.env"
IMAGE = sys.argv[1] if len(sys.argv) == 2 else ""
if not re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", IMAGE):
    raise SystemExit("FAIL pass the candidate as repository@sha256:<64 hex digits>")


def manifest_value(key: str) -> str:
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1]
    raise RuntimeError(f"{key} is missing from config/versions.env")


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=True, text=True, capture_output=True)


def api(base: str, path: str, payload: dict, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"{path} returned HTTP {error.code}: {detail}") from None


class SyntheticModelHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args: object) -> None:
        pass

    def _reply(self, status: int, body: bytes, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/v1/models":
            self._reply(200, json.dumps({"data": [{"id": "synthetic-household-model", "object": "model"}]}).encode())
        elif self.path in ("/api/tags", "/api/version"):
            self._reply(200, json.dumps({"models": []} if self.path == "/api/tags" else {"version": "synthetic"}).encode())
        else:
            self._reply(404, b"{}")

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length) or b"{}")
        if self.path in ("/api/embeddings", "/api/embed"):
            body = {"embedding": [0.125] * 16} if self.path.endswith("embeddings") else {"embeddings": [[0.125] * 16]}
            self._reply(200, json.dumps(body).encode())
            return
        if self.path != "/v1/chat/completions":
            self._reply(404, b"{}")
            return
        user_text = " ".join(str(message.get("content", "")) for message in request.get("messages", []) if message.get("role") == "user")
        reply = "Alpha-ldap-chat-confirmed" if "Alpha" in user_text else "Beta-ldap-chat-confirmed"
        if request.get("stream"):
            chunks = [
                {"id": "synthetic-ldap-chat", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]},
                {"id": "synthetic-ldap-chat", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"content": reply}, "finish_reason": None}]},
                {"id": "synthetic-ldap-chat", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
            ]
            body = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"
            self._reply(200, body.encode(), "text/event-stream")
            return
        body = {"id": "synthetic-ldap-chat", "object": "chat.completion", "model": "synthetic-household-model", "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}]}
        self._reply(200, json.dumps(body).encode())


def dynamic_port(container: str, port: str) -> int:
    inspection = json.loads(run(["docker", "inspect", container]).stdout)[0]
    return int(inspection["NetworkSettings"]["Ports"][port][0]["HostPort"])


def wait_health(url: str, name: str, attempts: int) -> None:
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except Exception:
            time.sleep(1)
    raise RuntimeError(f"{name} did not become healthy")


def main() -> None:
    lldap_image = manifest_value("HADES_LLDAP_IMAGE")
    suffix = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
    network = f"hades-ldap-candidate-{suffix}-net"
    lldap = f"hades-ldap-candidate-{suffix}-ldap"
    webui = f"hades-ldap-candidate-{suffix}-webui"
    volume = f"hades-ldap-candidate-{suffix}-data"
    created: list[tuple[str, str]] = []
    model_server: ThreadingHTTPServer | None = None
    try:
        run(["docker", "image", "inspect", IMAGE])
        run(["docker", "image", "inspect", lldap_image])
        run(["docker", "network", "create", network])
        created.append(("network", network))
        docker_gateway = run([
            "docker", "network", "inspect", "bridge",
            "--format", "{{(index .IPAM.Config 0).Gateway}}",
        ]).stdout.strip()
        if not re.fullmatch(r"(?:[0-9]{1,3}\.){3}[0-9]{1,3}", docker_gateway):
            raise RuntimeError("Docker bridge gateway is not a valid IPv4 address")
        model_server = ThreadingHTTPServer((docker_gateway, 0), SyntheticModelHandler)
        model_thread = threading.Thread(target=model_server.serve_forever, daemon=True)
        model_thread.start()
        model_port = int(model_server.server_address[1])
        with tempfile.TemporaryDirectory(prefix="hades-ldap-candidate-") as raw:
            root = pathlib.Path(raw)
            identity, users, groups = (root / name for name in ("identity", "users", "groups"))
            for directory in (identity, users, groups):
                directory.mkdir(mode=0o700)
            secrets = {
                "jwt_secret": "synthetic-jwt-secret-00000000000000000000000000000000",
                "key_seed": "synthetic-key-seed-0000000000000000000000000000000000000000000000000000000000000000",
                "admin_password": "synthetic-lldap-admin-password",
            }
            for filename, value in secrets.items():
                path = identity / filename
                path.write_text(value + "\n", encoding="utf-8")
                path.chmod(0o600)
            for name in ("hades-household", "hades-users"):
                (groups / f"{name}.json").write_text(json.dumps({"name": name}) + "\n", encoding="utf-8")
            for username in ("candidate-alpha", "candidate-beta"):
                user = {
                    "id": username,
                    "email": f"{username}@hades.example.invalid",
                    "password": "Synthetic-User-123!",
                    "displayName": username,
                    "groups": ["hades-household", "hades-users"],
                }
                (users / f"{username}.json").write_text(json.dumps(user) + "\n", encoding="utf-8")
            if os.geteuid() == 0:
                for directory in (identity, users, groups):
                    os.chown(directory, 1000, 1000)
                    for path in directory.iterdir():
                        os.chown(path, 1000, 1000)

            run([
                "docker", "run", "-d", "--rm", "--name", lldap, "--network", network,
                "--network-alias", "ldap", "-p", "127.0.0.1::17170",
                "-e", "UID=1000", "-e", "GID=1000", "-e", "TZ=UTC",
                "-e", "LLDAP_LDAP_BASE_DN=dc=hades,dc=local",
                "-e", "LLDAP_LDAP_USER_DN=admin",
                "-e", "LLDAP_LDAP_USER_EMAIL=admin@hades.example.invalid",
                "-e", "LLDAP_JWT_SECRET_FILE=/run/secrets/jwt",
                "-e", "LLDAP_KEY_SEED_FILE=/run/secrets/seed",
                "-e", "LLDAP_LDAP_USER_PASS_FILE=/run/secrets/pass",
                "-v", f"{identity / 'jwt_secret'}:/run/secrets/jwt:ro,Z",
                "-v", f"{identity / 'key_seed'}:/run/secrets/seed:ro,Z",
                "-v", f"{identity / 'admin_password'}:/run/secrets/pass:ro,Z",
                "-v", f"{users}:/probe/users:ro,Z", "-v", f"{groups}:/probe/groups:ro,Z",
                lldap_image,
            ])
            created.append(("container", lldap))
            lldap_url = f"http://127.0.0.1:{dynamic_port(lldap, '17170/tcp')}"
            wait_health(lldap_url + "/health", "pinned LLDAP fixture", 60)
            run([
                "docker", "exec", "-e", "LLDAP_URL=http://localhost:17170",
                "-e", "LLDAP_ADMIN_USERNAME=admin",
                "-e", "LLDAP_ADMIN_PASSWORD=synthetic-lldap-admin-password",
                "-e", "USER_CONFIGS_DIR=/probe/users", "-e", "GROUP_CONFIGS_DIR=/probe/groups",
                "-e", "DO_CLEANUP=false", lldap, "/app/bootstrap.sh",
            ])
            directory_token = api(
                lldap_url, "/auth/simple/login",
                {"username": "admin", "password": "synthetic-lldap-admin-password"},
            )["token"]
            directory_groups = api(
                lldap_url, "/api/graphql", {"query": "{ groups { id displayName } }"}, directory_token
            )["data"]["groups"]
            group_ids = {row["displayName"]: row["id"] for row in directory_groups}
            if not {"hades-household", "hades-users"}.issubset(group_ids):
                raise RuntimeError("LLDAP fixture is missing one of the required groups")

            run(["docker", "volume", "create", volume])
            created.append(("volume", volume))
            run([
                "docker", "run", "-d", "--rm", "--name", webui, "--network", network,
                "--add-host", "host.docker.internal:host-gateway",
                "-p", "127.0.0.1::8080", "-e", "WEBUI_AUTH=true", "-e", "ENABLE_SIGNUP=true",
                "-e", "ENABLE_LOGIN_FORM=true", "-e", "ENABLE_LDAP=true",
                "-e", "LDAP_SERVER_HOST=ldap", "-e", "LDAP_SERVER_PORT=3890",
                "-e", "LDAP_USE_TLS=false",
                "-e", "LDAP_APP_DN=uid=admin,ou=people,dc=hades,dc=local",
                "-e", "LDAP_APP_PASSWORD=synthetic-lldap-admin-password",
                "-e", "LDAP_SEARCH_BASE=ou=people,dc=hades,dc=local",
                "-e", "LDAP_ATTRIBUTE_FOR_USERNAME=uid", "-e", "LDAP_ATTRIBUTE_FOR_MAIL=mail",
                "-e", "ENABLE_LDAP_GROUP_MANAGEMENT=true", "-e", "ENABLE_LDAP_GROUP_CREATION=true",
                "-e", "LDAP_ATTRIBUTE_FOR_GROUPS=memberOf", "-e", "DEFAULT_USER_ROLE=user",
                "-e", "RAG_EMBEDDING_ENGINE=ollama", "-e", "RAG_EMBEDDING_MODEL=nomic-embed-text:latest",
                "-e", "ENABLE_TITLE_GENERATION=false", "-e", "ENABLE_FOLLOW_UP_GENERATION=false",
                "-e", "ENABLE_TAGS_GENERATION=false",
                "-e", "WEBUI_SECRET_KEY=synthetic-webui-secret-00000000000000000000000000000000",
                "-v", f"{volume}:/app/backend/data", IMAGE,
            ])
            created.append(("container", webui))
            webui_url = f"http://127.0.0.1:{dynamic_port(webui, '8080/tcp')}"
            wait_health(webui_url + "/health", "Open WebUI candidate", 120)
            admin = api(webui_url, "/api/v1/auths/signup", {
                "name": "Synthetic Admin", "email": "synthetic-admin@hades.example.invalid",
                "password": "Synthetic-Admin-123!",
            })
            admin_token = admin["token"]

            def ldap_login(username: str) -> dict:
                return api(webui_url, "/api/v1/auths/ldap", {
                    "user": username, "password": "Synthetic-User-123!",
                })

            alpha = ldap_login("candidate-alpha")
            alpha_again = ldap_login("candidate-alpha")
            beta = ldap_login("candidate-beta")
            if alpha["id"] != alpha_again["id"]:
                raise RuntimeError("Alpha's Open WebUI subject changed across LDAP logins")
            if alpha["role"] != "user" or beta["role"] != "user":
                raise RuntimeError("LDAP household identity received a non-user role")

            query = (
                "import sqlite3,json,sys; "
                "c=sqlite3.connect('/app/backend/data/webui.db'); "
                "print(json.dumps([r[0] for r in c.execute("
                "'select g.name from \"group\" g join group_member m on m.group_id=g.id where m.user_id=?',"
                "(sys.argv[1],))]))"
            )

            def memberships(user_id: str) -> set[str]:
                result = run(["docker", "exec", webui, "python", "-c", query, user_id])
                return set(json.loads(result.stdout))

            expected = {"hades-household", "hades-users"}
            if memberships(alpha["id"]) != expected or memberships(beta["id"]) != expected:
                raise RuntimeError("LDAP group membership did not match the fixture for both users")
            print("PASS Alpha/Beta LDAP login, stable subject, user role, and initial group sync")

            api(webui_url, "/openai/config/update", {
                "ENABLE_OPENAI_API": True,
                "OPENAI_API_BASE_URLS": [f"http://host.docker.internal:{model_port}/v1"],
                "OPENAI_API_KEYS": ["synthetic-ldap-model-key"],
                "OPENAI_API_CONFIGS": {"0": {}},
            }, admin_token)
            api(webui_url, "/api/v1/models/model/access/update", {
                "id": "synthetic-household-model",
                "name": "synthetic-household-model",
                "access_grants": [
                    {"principal_type": "user", "principal_id": user["id"], "permission": "read"}
                    for user in (alpha, beta)
                ],
            }, admin_token)
            model_request = urllib.request.Request(
                webui_url + "/api/models",
                headers={"Authorization": "Bearer " + beta["token"]},
            )
            with urllib.request.urlopen(model_request, timeout=20) as response:
                beta_models = json.load(response)
            visible_models = beta_models if isinstance(beta_models, list) else beta_models.get("data", beta_models.get("models", []))
            if not any(row.get("id") == "synthetic-household-model" for row in visible_models):
                raise RuntimeError("verified LDAP household user has no explicitly granted model")
            print("PASS verified LDAP household user sees the explicitly granted model")

            playwright_module = os.environ.get("HADES_PLAYWRIGHT_MODULE", "")
            if playwright_module:
                base_env = {
                    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "HOME": os.environ.get("HOME", "/tmp"),
                    "LANG": os.environ.get("LANG", "C.UTF-8"),
                    "HADES_CANDIDATE_BROWSER_URL": webui_url,
                    "HADES_CANDIDATE_BROWSER_PASSWORD": "Synthetic-User-123!",
                    "HADES_CANDIDATE_BROWSER_PROMPT": "Please confirm the Alpha LDAP browser conversation.",
                    "HADES_CANDIDATE_BROWSER_EXPECTED_REPLY": "Alpha-ldap-chat-confirmed",
                    "HADES_PLAYWRIGHT_MODULE": playwright_module,
                }
                if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
                    base_env["PLAYWRIGHT_BROWSERS_PATH"] = os.environ["PLAYWRIGHT_BROWSERS_PATH"]
                base_env["HADES_CANDIDATE_BROWSER_EMAIL"] = "candidate-alpha@hades.example.invalid"
                base_env["HADES_CANDIDATE_BROWSER_USERNAME"] = "candidate-alpha"
                subprocess.run(["node", str(REPO / "scripts/dom-open-webui-candidate-smoke.js")], check=True, env=base_env)
                beta_env = {
                    **base_env,
                    "HADES_CANDIDATE_BROWSER_EMAIL": "candidate-beta@hades.example.invalid",
                    "HADES_CANDIDATE_BROWSER_USERNAME": "candidate-beta",
                    "HADES_CANDIDATE_BROWSER_PROMPT": "Please confirm the Beta LDAP browser conversation.",
                    "HADES_CANDIDATE_BROWSER_EXPECTED_REPLY": "Beta-ldap-chat-confirmed",
                    "HADES_CANDIDATE_BROWSER_FORBIDDEN_TEXT": "Alpha-ldap-chat-confirmed",
                }
                subprocess.run(["node", str(REPO / "scripts/dom-open-webui-candidate-smoke.js")], check=True, env=beta_env)
                print("PASS LDAP Alpha/Beta browser login, independent chats, and private response isolation")

            def remove_group(name: str) -> None:
                result = api(lldap_url, "/api/graphql", {
                    "query": (
                        'mutation { removeUserFromGroup(userId: "candidate-beta", '
                        f'groupId: {group_ids[name]}) {{ ok }} }}'
                    )
                }, directory_token)
                if result.get("data", {}).get("removeUserFromGroup", {}).get("ok") is not True:
                    raise RuntimeError(f"LLDAP could not remove Beta from {name}")

            remove_group("hades-household")
            beta_again = ldap_login("candidate-beta")
            if beta_again["id"] != beta["id"] or memberships(beta["id"]) != {"hades-users"}:
                raise RuntimeError("candidate did not reconcile one revoked group on fresh LDAP login")
            if memberships(alpha["id"]) != expected:
                raise RuntimeError("Beta's group change altered Alpha's memberships")
            print("PASS single-group revocation removes only Beta's revoked membership")

            remove_group("hades-users")
            beta_last = ldap_login("candidate-beta")
            if beta_last["id"] != beta["id"]:
                raise RuntimeError("Beta's Open WebUI subject changed after all groups were revoked")
            if memberships(beta["id"]):
                raise RuntimeError("candidate retained stale groups after all LDAP groups were revoked")
            print("PASS total group revocation removes Beta's final Open WebUI membership")

            revoke_env = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": os.environ.get("HOME", "/tmp"),
                "LANG": os.environ.get("LANG", "C.UTF-8"),
                "HADES_LLDAP_URL": lldap_url,
                "HADES_OPEN_WEBUI_URL": webui_url,
                "LLDAP_ADMIN_TOKEN": directory_token,
                "OPEN_WEBUI_ADMIN_TOKEN": admin_token,
            }
            subprocess.run([str(REPO / "scripts/revoke-directory-user.sh"), "candidate-beta"], check=True, env=revoke_env)
            old_token_request = urllib.request.Request(
                webui_url + "/api/v1/users/user/info",
                headers={"Authorization": "Bearer " + beta["token"]},
            )
            try:
                urllib.request.urlopen(old_token_request, timeout=20)
            except urllib.error.HTTPError as error:
                if error.code not in (401, 403):
                    raise RuntimeError(f"revoked Beta token returned unexpected HTTP {error.code}") from None
            else:
                raise RuntimeError("revoked Beta's existing session token remained usable")
            print("PASS documented offboarding removes Open WebUI access and invalidates Beta's existing token")
    finally:
        for kind, name in reversed(created):
            command = (
                ["docker", "rm", "-f", name] if kind == "container"
                else ["docker", "volume", "rm", name] if kind == "volume"
                else ["docker", "network", "rm", name]
            )
            subprocess.run(command, capture_output=True, text=True)
        if model_server is not None:
            model_server.shutdown()
            model_server.server_close()


if __name__ == "__main__":
    main()
