#!/usr/bin/env python3
"""Guard the isolated Open WebUI 0.12.0 qualification inputs."""

from __future__ import annotations

import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parents[1]


def main() -> None:
    candidate = {}
    for line in (ROOT / "config/openwebui-0.12.0-qualification.pins").read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        candidate[key] = value

    assert candidate["HADES_OPEN_WEBUI_012_QUAL_VERSION"] == "0.12.0"
    assert candidate["HADES_OPEN_WEBUI_012_UPSTREAM_COMMIT"] == "15818d88fd7bde1b73de33590f50d15d21e8d7c1"
    assert re.fullmatch(r"ghcr\.io/open-webui/open-webui@sha256:[0-9a-f]{64}", candidate["HADES_OPEN_WEBUI_012_OCI_INDEX"])
    assert re.fullmatch(r"ghcr\.io/open-webui/open-webui@sha256:[0-9a-f]{64}", candidate["HADES_OPEN_WEBUI_012_AMD64_IMAGE"])
    assert re.fullmatch(r"moby/buildkit@sha256:[0-9a-f]{64}", candidate["HADES_OPEN_WEBUI_012_BUILDKIT_IMAGE"])
    assert candidate["HADES_OPEN_WEBUI_012_PLATFORM"] == "linux/amd64"

    production = {}
    for line in (ROOT / "config/versions.env").read_text().splitlines():
        if line.startswith("HADES_OPEN_WEBUI_VERSION="):
            production[line.split("=", 1)[0]] = line.split("=", 1)[1]
    assert production["HADES_OPEN_WEBUI_VERSION"] == "0.11.4", "qualification must not alter production pin"

    dockerfile = (ROOT / "webui/Dockerfile.openwebui-012-qualification").read_text()
    assert "ARG OPEN_WEBUI_BASE_IMAGE=" in dockerfile
    assert "auth_revocation_fail_closed_compat.py" in dockerfile
    assert "authority_revocation_routes_compat.py" in dockerfile
    assert "ldap_group_sync_compat.py" in dockerfile
    assert "socket_disconnect_fail_closed_compat.py" in dockerfile
    assert dockerfile.count("PYTHONDONTWRITEBYTECODE=1 python3") == 9, "build-time bytecode must not make candidate layers time-dependent"
    assert "channel_response_compat.py" not in dockerfile, "0.12 native Channels behavior made this HADES patch unnecessary"
    for opt_in in ("ENABLE_MFA", "AUDIO_REALTIME_ENABLED", "ENABLE_TOOL_SEARCH"):
        assert opt_in not in dockerfile, f"new optional upstream feature was enabled: {opt_in}"

    auth = (ROOT / "webui/auth_revocation_fail_closed_compat.py").read_text()
    authority = (ROOT / "webui/authority_revocation_routes_compat.py").read_text()
    sockets = (ROOT / "webui/socket_disconnect_fail_closed_compat.py").read_text()
    assert "apply_session_stamp_profile" in auth and "Session verification unavailable" in auth
    assert "apply_session_stamp_profile" in authority and "revoke_user_tokens" in authority
    assert "include_inherited=True" in authority, "nested-group changes must revoke inherited authority"
    assert "LDAP group membership could not be verified" in authority
    assert "refresh_access: bool = False" in sockets and "Session revocation incomplete" in sockets

    for test_script in (
        "scripts/test-grocy-authenticated-household-ui.sh",
        "scripts/test-hindsight-explicit-memory-authenticated-ui.sh",
        "scripts/test-task-attention-authenticated-ui.sh",
    ):
        script = (ROOT / test_script).read_text()
        assert "open-webui-candidate-test-runtime.sh" in script
        assert '"${HADES_CANDIDATE_RUNTIME_ARGS[@]}"' in script

    chat_ui = (ROOT / "scripts/test-openwebui-012-chat-lifecycle-ui.sh").read_text()
    for lifecycle_contract in (
        "synthetic-ui",
        "#confirm-edit-message-button",
        "Try Again",
        "button[aria-label=\"Fork chat\"]",
        "#new-chat-button",
        "long synthetic thread turn",
        "#delete-chat-button",
        "HADES_CANDIDATE_RUNTIME_ARGS",
    ):
        assert lifecycle_contract in chat_ui, f"candidate browser lifecycle coverage is missing {lifecycle_contract}"
    assert "hades-openwebui-012-ui." in chat_ui and "127.0.0.1:${webui_port}:8080" in chat_ui

    migration = (ROOT / "scripts/test-openwebui-012-populated-migration.sh").read_text()
    for migration_contract in (
        '[[ "$old_version" == 0.11.4 ]]',
        '[[ "$new_version" == 0.12.0 ]]',
        "/api/v1/users/user/settings/update",
        "/api/v1/users/user/settings?raw=true",
        "/openai/config/update",
        "/openai/config",
        "/openai/models",
        "/api/v1/tools/create",
        "/api/v1/tools/id/${tool_id}",
        "/api/v1/chats/${chat_id}/fork",
        "original and forked chat branches",
    ):
        assert migration_contract in migration, f"populated migration coverage is missing {migration_contract}"
    assert "HADES_OPEN_WEBUI_VERSION=0.11.4" in (ROOT / "config/versions.env").read_text()

    build = (ROOT / "scripts/build-openwebui-012-qualification.sh").read_text()
    assert "git -C \"$repo_dir\" status --porcelain" in build, "candidate build must bind to a clean source tree"
    assert "--platform \"$HADES_OPEN_WEBUI_012_PLATFORM\"" in build
    assert "SOURCE_DATE_EPOCH=$source_epoch" in build
    assert "rewrite-timestamp=true" in build
    assert "--no-cache" in build and "--provenance=false" in build
    assert "org.hades.open-webui.upstream-source-commit" in build
    print("PASS isolated Open WebUI 0.12.0 pins, adapter contracts, migration state coverage, disabled opt-ins, and production version boundary")


if __name__ == "__main__":
    main()
