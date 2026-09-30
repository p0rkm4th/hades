#!/usr/bin/env python3
"""Create or remove isolated household login fixtures on an authorized test guest."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


USERS = {
    "hades-reconstruction-alpha": ("Alpha", "hades-owner"),
    "hades-reconstruction-beta": ("Beta", "hades-household"),
    "hades-reconstruction-gamma": ("Gamma", "hades-household"),
}
CONTAINER = "hades-lldap"
PASSWORD_TOOL = "/app/lldap_set_password"
OUTPUT_RELATIVE = Path("acceptance/synthetic-household-credentials.json")


class FixtureError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise FixtureError(message)


def require_authorized_target(repo: Path, inputs: Path) -> dict[str, str]:
    if os.geteuid() != 0:
        fail("run as root on the explicitly authorized synthetic guest")
    target_script = repo / "scripts/synthetic-deployment-target.sh"
    if not target_script.is_file():
        fail("synthetic deployment target guard is missing")
    subprocess.run(["bash", str(target_script), "verify"], check=True)
    if inputs.is_symlink() or not inputs.is_file():
        fail("operator inputs must be a regular non-symlink file")
    info = inputs.stat()
    if stat.S_IMODE(info.st_mode) not in (0o600, 0o640):
        fail("operator inputs must be mode 0600 or 0640")
    values: dict[str, str] = {}
    for raw in inputs.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            fail("operator input contains unsupported syntax")
        if key in values:
            fail("operator input contains a duplicate key")
        values[key] = value
    if values.get("HADES_SYNTHETIC_FIXTURE") != "true" or values.get("HADES_INPUTS_VERSION") != "2":
        fail("full household fixtures require explicit synthetic v2 inputs")
    identity = Path(values.get("HADES_IDENTITY_SECRETS_DIR", ""))
    if not identity.is_absolute() or identity.is_symlink():
        fail("identity secret directory must be an absolute non-symlink path")
    state_root = Path(values.get("HADES_STATE_ROOT", ""))
    if not state_root.is_absolute() or state_root.is_symlink() or not state_root.is_dir():
        fail("synthetic state root must be an absolute existing non-symlink directory")
    if state_root.stat().st_uid != info.st_uid:
        fail("operator inputs and synthetic state must have the same owner")
    admin_password = identity / "admin_password"
    if admin_password.is_symlink() or not admin_password.is_file():
        fail("synthetic identity admin password file is missing")
    secret_info = admin_password.stat()
    if secret_info.st_uid != info.st_uid or stat.S_IMODE(secret_info.st_mode) != 0o600:
        fail("synthetic identity admin password must share the input owner and use mode 0600")
    values["_identity_dir"] = str(identity)
    return values


def post_json(url: str, payload: dict, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            result = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        fail(f"LLDAP request failed ({type(error).__name__})")
    if result.get("errors"):
        fail("LLDAP rejected the bounded household fixture request")
    return result


def ensure_private_acceptance_dir(state_root: Path) -> Path:
    if state_root.is_symlink() or not state_root.is_dir():
        fail("synthetic state root must be a real existing directory")
    state_info = state_root.stat()
    if state_info.st_mode & 0o022:
        fail("synthetic state root must not be group/world writable")
    parent = state_root / "acceptance"
    if parent.is_symlink():
        fail("acceptance directory must not be a symlink")
    parent.mkdir(mode=0o700, exist_ok=True)
    info = parent.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
        fail("acceptance directory must be root-owned mode 0700")
    return parent


def directory_login(admin_password: str) -> tuple[str, str]:
    base = "http://127.0.0.1:17170"
    result = post_json(f"{base}/auth/simple/login", {"username": "admin", "password": admin_password})
    token = result.get("token")
    if not isinstance(token, str) or not token:
        fail("LLDAP admin login returned no token")
    return base, token


def verify_pinned_password_helper(repo: Path) -> None:
    versions = repo / "config/versions.env"
    if versions.is_symlink() or not versions.is_file():
        fail("pinned component versions file is missing")
    expected = None
    for raw in versions.read_text(encoding="utf-8").splitlines():
        key, separator, value = raw.partition("=")
        if separator and key.strip() == "HADES_LLDAP_IMAGE":
            expected = value.strip().strip("\"'")
            break
    if not expected or "@sha256:" not in expected:
        fail("LLDAP version is not pinned by an immutable digest")
    try:
        actual = subprocess.run(
            ["docker", "inspect", CONTAINER, "--format", "{{.Config.Image}}"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        if actual != expected:
            fail("running LLDAP image does not match the repository pin")
        subprocess.run(
            ["docker", "exec", CONTAINER, "test", "-x", PASSWORD_TOOL],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        fail(f"pinned LLDAP/password helper is unavailable ({type(error).__name__})")


def graphql(base: str, token: str, query: str, variables: dict | None = None) -> dict:
    result = post_json(f"{base}/api/graphql", {"query": query, "variables": variables or {}}, token)
    data = result.get("data")
    if not isinstance(data, dict):
        fail("LLDAP returned no GraphQL data")
    return data


def remove_owned_groups(base: str, token: str, groups: list[dict]) -> None:
    """Remove only fixture-created groups that are still empty and unchanged."""
    if not groups:
        return
    current = graphql(base, token, "query { groups { id displayName users { id } } }")["groups"]
    by_id = {group["id"]: group for group in current}
    for owned in reversed(groups):
        group = by_id.get(owned.get("id"))
        if group is None:
            continue
        if group.get("displayName") != owned.get("display_name"):
            fail("refusing to remove a fixture group whose identity changed")
        if group.get("users"):
            fail("refusing to remove a fixture group that now has other members")
        graphql(base, token,
                "mutation Delete($id: Int!) { deleteGroup(groupId: $id) { ok } }",
                {"id": owned["id"]})


def run_password_tool(username: str, password: str, token: str) -> None:
    environment = os.environ.copy()
    environment["LLDAP_USER_PASSWORD"] = password
    try:
        subprocess.run(
            ["docker", "exec", "-e", "LLDAP_USER_PASSWORD", CONTAINER, PASSWORD_TOOL,
             "--base-url", "http://127.0.0.1:17170", "--token", token, "--username", username],
            env=environment, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        fail(f"pinned LLDAP password helper failed ({type(error).__name__})")


def prepare(values: dict[str, str], output: Path) -> None:
    if output.exists() or output.is_symlink():
        fail("synthetic household credentials already exist; refusing to rotate or overwrite")
    if output.parent != ensure_private_acceptance_dir(Path(values["HADES_STATE_ROOT"])):
        fail("unexpected synthetic acceptance credential path")
    repo = Path(values.get("_repo", "/opt/hades"))
    verify_pinned_password_helper(repo)
    base, token = directory_login((Path(values["_identity_dir"]) / "admin_password").read_text().strip())
    groups = graphql(base, token, "query { groups { id displayName } }")["groups"]
    group_ids = {group["displayName"]: group["id"] for group in groups}
    existing = graphql(base, token, "query { users { id email } }")["users"]
    existing_ids = {user["id"] for user in existing}
    collisions = sorted(existing_ids.intersection(USERS))
    if collisions:
        fail("fixture identities already exist; refusing to modify them")
    created_groups: list[dict] = []
    try:
        for group_name in sorted(set(group for _name, group in USERS.values())):
            if group_name in group_ids:
                continue
            created = graphql(
                base,
                token,
                "mutation Create($name: String!) { createGroup(name: $name) { id displayName } }",
                {"name": group_name},
            )["createGroup"]
            if created.get("displayName") != group_name or not isinstance(created.get("id"), int):
                fail("LLDAP did not create the required synthetic household group")
            group_ids[group_name] = created["id"]
            created_groups.append({"id": created["id"], "display_name": group_name})
    except Exception:
        remove_owned_groups(base, token, created_groups)
        raise
    created: list[str] = []
    credentials = {"schema": 2, "synthetic_only": True, "created_groups": created_groups, "users": {}}
    try:
        for user_id, (display_name, group_name) in USERS.items():
            email = f"{user_id}@hades.local"
            password = secrets.token_urlsafe(32)
            graphql(base, token,
                    "mutation Create($user: CreateUserInput!) { createUser(user: $user) { id } }",
                    {"user": {"id": user_id, "email": email, "displayName": display_name}})
            created.append(user_id)
            graphql(base, token,
                    "mutation Join($userId: String!, $groupId: Int!) { addUserToGroup(userId: $userId, groupId: $groupId) { ok } }",
                    {"userId": user_id, "groupId": group_ids[group_name]})
            run_password_tool(user_id, password, token)
            credentials["users"][user_id] = {
                "display_name": display_name,
                "email": email,
                "password": password,
                "group": group_name,
            }
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(output, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(credentials, stream, indent=2)
            stream.write("\n")
        os.chmod(output, 0o600)
    except Exception:
        for user_id in reversed(created):
            try:
                graphql(base, token,
                        "mutation Remove($id: String!) { deleteUser(userId: $id) { ok } }",
                        {"id": user_id})
            except Exception:
                pass
        try:
            remove_owned_groups(base, token, created_groups)
        except Exception:
            pass
        if output.exists() and not output.is_symlink():
            output.unlink()
        raise
    os.chown(output, 0, 0)
    print(f"PASS created three disposable synthetic household logins; credentials stored mode 0600 at {output}")


def remove(values: dict[str, str], output: Path) -> None:
    if output.is_symlink() or not output.is_file():
        fail("recorded synthetic credential file is missing or unsafe")
    info = output.stat()
    if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
        fail("synthetic credential file must be root-owned mode 0600")
    credentials = json.loads(output.read_text(encoding="utf-8"))
    if credentials.get("schema") not in (1, 2) or credentials.get("synthetic_only") is not True:
        fail("credential file is not a recognized synthetic fixture")
    if set(credentials.get("users", {})) != set(USERS):
        fail("credential file does not match the fixed reconstruction fixture IDs")
    for user_id, row in credentials["users"].items():
        expected_name, expected_group = USERS[user_id]
        if row.get("display_name") != expected_name or row.get("group") != expected_group or row.get("email") != f"{user_id}@hades.local":
            fail("credential file contains a fixture identity mismatch")
    created_groups = credentials.get("created_groups", [])
    if not isinstance(created_groups, list) or any(
        not isinstance(group, dict)
        or not isinstance(group.get("id"), int)
        or group.get("display_name") not in {name for _display, name in USERS.values()}
        for group in created_groups
    ):
        fail("credential file contains an invalid fixture-created group record")
    if len({group["id"] for group in created_groups}) != len(created_groups) or len({group["display_name"] for group in created_groups}) != len(created_groups):
        fail("credential file contains duplicate fixture-created group records")
    base, token = directory_login((Path(values["_identity_dir"]) / "admin_password").read_text().strip())
    users = graphql(base, token, "query { users { id email } }")["users"]
    by_id = {user["id"]: user for user in users}
    for user_id in USERS:
        row = by_id.get(user_id)
        if row and row.get("email") != f"{user_id}@hades.local":
            fail("refusing to remove a same-ID account with a different email")
    for user_id in USERS:
        if user_id in by_id:
            graphql(base, token,
                    "mutation Remove($id: String!) { deleteUser(userId: $id) { ok } }",
                    {"id": user_id})
    remove_owned_groups(base, token, created_groups)
    output.unlink()
    print("PASS removed only the three recorded synthetic reconstruction accounts and their credential file")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("/opt/hades"))
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--remove", action="store_true", help="remove only this script's fixed synthetic identities")
    args = parser.parse_args()
    try:
        values = require_authorized_target(args.repo.resolve(), args.inputs)
        values["_repo"] = str(args.repo.resolve())
        state_root = Path(values.get("HADES_STATE_ROOT", ""))
        if not state_root.is_absolute() or state_root.is_symlink():
            fail("synthetic state root must be an absolute non-symlink path")
        output = state_root / OUTPUT_RELATIVE
        if args.remove:
            remove(values, output)
        else:
            prepare(values, output)
    except (FixtureError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"FAIL synthetic household credentials: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
