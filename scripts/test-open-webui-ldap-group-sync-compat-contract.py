#!/usr/bin/env python3
"""Prove the Open WebUI LDAP empty-group compatibility patch is fail-closed."""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


repo = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "ldap_group_sync_compat", repo / "webui" / "ldap_group_sync_compat.py"
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

with tempfile.TemporaryDirectory(prefix="hades-ldap-group-compat-") as raw:
    target = Path(raw) / "auths.py"
    target.write_text(
        "                if ENABLE_LDAP_GROUP_MANAGEMENT and user_groups:\n"
        "                    try:\n"
        "                        if ENABLE_LDAP_GROUP_CREATION:\n"
        "                            await Groups.create_groups_by_group_names(user.id, user_groups, db=db)\n"
        "                        await Groups.sync_groups_by_group_names(user.id, user_groups, db=db)\n"
        "                        log.info('Successfully synced groups for user %s: %s', user.id, user_groups)\n"
        "                    except Exception as e:\n"
        "                        log.error(f'Failed to sync groups for user {user.id}: {e}')\n",
        encoding="utf-8",
    )
    module.MAIN = target
    module.apply()
    expected = target.read_text(encoding="utf-8")
    assert "if ENABLE_LDAP_GROUP_MANAGEMENT:  # HADES_EMPTY_LDAP_GROUP_SYNC" in expected
    assert "if ENABLE_LDAP_GROUP_MANAGEMENT and user_groups:" not in expected
    module.apply()
    assert target.read_text(encoding="utf-8") == expected

    target.write_text("upstream changed\n", encoding="utf-8")
    try:
        module.apply()
    except RuntimeError:
        pass
    else:
        raise AssertionError("adapter must reject unknown upstream source")

print("PASS LDAP group adapter patches once, is idempotent, and rejects source drift")
