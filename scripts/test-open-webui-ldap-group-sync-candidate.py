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


def api_status(base: str, method: str, path: str, token: str) -> int:
    request = urllib.request.Request(
        base + path, headers={"Authorization": "Bearer " + token}, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read()
            return response.status
    except urllib.error.HTTPError as error:
        error.read()
        return error.code


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
    valkey_image = manifest_value("HADES_OPEN_WEBUI_VALKEY_IMAGE")
    suffix = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
    network = f"hades-ldap-candidate-{suffix}-net"
    lldap = f"hades-ldap-candidate-{suffix}-ldap"
    valkey = f"hades-ldap-candidate-{suffix}-valkey"
    webui = f"hades-ldap-candidate-{suffix}-webui"
    volume = f"hades-ldap-candidate-{suffix}-data"
    auth_volume = f"hades-ldap-candidate-{suffix}-auth"
    created: list[tuple[str, str]] = []
    try:
        run(["docker", "image", "inspect", IMAGE])
        run(["docker", "image", "inspect", lldap_image])
        run(["docker", "image", "inspect", valkey_image])
        run(["docker", "network", "create", network])
        created.append(("network", network))
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
                    "groups": ["hades-household", "hades-users"] if username == "candidate-alpha" else ["hades-users"],
                }
                (users / f"{username}.json").write_text(json.dumps(user) + "\n", encoding="utf-8")
            if os.geteuid() == 0:
                for directory in (identity, users, groups):
                    os.chown(directory, 1000, 1000)
                    for path in directory.iterdir():
                        os.chown(path, 1000, 1000)

            run([
                "docker", "run", "-d", "--name", lldap, "--network", network,
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
            run(["docker", "volume", "create", auth_volume])
            created.append(("volume", auth_volume))
            run([
                "docker", "run", "-d", "--rm", "--name", valkey, "--network", network,
                "--network-alias", "redis", "-v", f"{auth_volume}:/data", valkey_image,
                "valkey-server", "--save", "", "--appendonly", "yes", "--appendfsync", "always",
            ])
            created.append(("container", valkey))
            for _ in range(40):
                probe = subprocess.run(["docker", "exec", valkey, "valkey-cli", "ping"], capture_output=True, text=True)
                if probe.returncode == 0 and probe.stdout.strip() == "PONG":
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError("Valkey did not become ready")
            run([
                "docker", "run", "-d", "--rm", "--name", webui, "--network", network,
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
                "-e", "REDIS_URL=redis://redis:6379/0", "-e", "WEBSOCKET_MANAGER=redis",
                "-e", "WEBSOCKET_REDIS_URL=redis://redis:6379/1",
                "-e", "WEBUI_SECRET_KEY=synthetic-webui-secret-00000000000000000000000000000000",
                "-v", f"{volume}:/app/backend/data", IMAGE,
            ])
            created.append(("container", webui))
            webui_url = f"http://127.0.0.1:{dynamic_port(webui, '8080/tcp')}"
            wait_health(webui_url + "/health", "Open WebUI candidate", 120)
            api(webui_url, "/api/v1/auths/signup", {
                "name": "Synthetic Admin", "email": "synthetic-admin@hades.example.invalid",
                "password": "Synthetic-Admin-123!",
            })

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
            if memberships(alpha["id"]) != expected or memberships(beta["id"]) != {"hades-users"}:
                raise RuntimeError("LDAP group membership did not match the fixture for both users")
            print("PASS Alpha/Beta LDAP login, stable subject, user role, and initial group sync")

            joined = api(lldap_url, "/api/graphql", {
                "query": (
                    'mutation { addUserToGroup(userId: "candidate-beta", '
                    f'groupId: {group_ids["hades-household"]}) {{ ok }} }}'
                )
            }, directory_token)
            if joined.get("data", {}).get("addUserToGroup", {}).get("ok") is not True:
                raise RuntimeError("LLDAP could not add Beta to the household group")
            beta_joined = ldap_login("candidate-beta")
            if beta_joined["id"] != beta["id"] or memberships(beta["id"]) != expected:
                raise RuntimeError("candidate did not reconcile a newly granted group")
            if api_status(webui_url, "GET", "/api/v1/users/user/info", beta["token"]) != 401:
                raise RuntimeError("pre-addition Beta token survived LDAP group addition")
            print("PASS LDAP group addition refreshes the old token without changing Alpha")

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
            if api_status(webui_url, "GET", "/api/v1/users/user/info", beta_joined["token"]) != 401:
                raise RuntimeError("pre-removal Beta token survived LDAP group removal")
            if memberships(alpha["id"]) != expected:
                raise RuntimeError("Beta's group change altered Alpha's memberships")
            print("PASS single-group revocation removes only Beta's revoked membership")

            membership_before_outage = memberships(beta["id"])
            if membership_before_outage != {"hades-users"}:
                raise RuntimeError("LDAP outage precondition is not a nonempty authoritative group set")
            run(["docker", "stop", lldap])
            try:
                ldap_login("candidate-beta")
            except RuntimeError as error:
                if "HTTP 503" not in str(error):
                    raise RuntimeError(f"LDAP outage was not distinguished as unavailable: {error}") from error
            else:
                raise RuntimeError("LDAP outage was accepted as an authoritative empty-group result")
            if memberships(beta["id"]) != membership_before_outage:
                raise RuntimeError("LDAP outage changed a nonempty authoritative membership set")
            run(["docker", "start", lldap])
            wait_health(lldap_url + "/health", "LLDAP after outage recovery", 60)
            print("PASS LDAP outage returns 503 and preserves nonempty authoritative membership")

            remove_group("hades-users")
            beta_last = ldap_login("candidate-beta")
            if beta_last["id"] != beta["id"]:
                raise RuntimeError("Beta's Open WebUI subject changed after all groups were revoked")
            if memberships(beta["id"]):
                raise RuntimeError("candidate retained stale groups after all LDAP groups were revoked")
            if api_status(webui_url, "GET", "/api/v1/users/user/info", beta_again["token"]) != 401:
                raise RuntimeError("pre-final-removal Beta token survived LDAP final-group removal")
            print("PASS total group revocation removes Beta's final Open WebUI membership")

    finally:
        for kind, name in reversed(created):
            command = (
                ["docker", "rm", "-f", name] if kind == "container"
                else ["docker", "volume", "rm", name] if kind == "volume"
                else ["docker", "network", "rm", name]
            )
            subprocess.run(command, capture_output=True, text=True)


if __name__ == "__main__":
    main()
