"""Keep Open WebUI LDAP group membership in sync when LDAP returns no groups.

Open WebUI 0.11.4 calls its native membership reconciler only when the LDAP
group list is non-empty. That leaves stale local memberships after the final
directory group is removed. The native reconciler already handles an empty
list by removing all memberships, so retain only the missing call condition.

Delete this adapter once upstream invokes sync_groups_by_group_names for an
empty LDAP group list too.
"""

from __future__ import annotations

import os
from pathlib import Path


MAIN = Path(
    os.environ.get(
        "HADES_OPEN_WEBUI_AUTHS_FILE",
        "/app/backend/open_webui/routers/auths.py",
    )
)
NATIVE_BLOCK = """                if ENABLE_LDAP_GROUP_MANAGEMENT and user_groups:
                    try:
                        if ENABLE_LDAP_GROUP_CREATION:"""
COMPAT_BLOCK = """                if ENABLE_LDAP_GROUP_MANAGEMENT:  # HADES_EMPTY_LDAP_GROUP_SYNC
                    try:
                        if ENABLE_LDAP_GROUP_CREATION:"""


def apply() -> None:
    source = MAIN.read_text(encoding="utf-8")
    if source.count(NATIVE_BLOCK) == 1:
        MAIN.write_text(source.replace(NATIVE_BLOCK, COMPAT_BLOCK, 1), encoding="utf-8")
    elif source.count(NATIVE_BLOCK) == 0 and source.count("HADES_EMPTY_LDAP_GROUP_SYNC") == 1:
        return
    else:
        raise RuntimeError(
            "Open WebUI LDAP group-sync guard changed; review upstream and remove or revise this adapter"
        )


if __name__ == "__main__":
    apply()
