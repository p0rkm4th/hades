"""Require durable session revocation before Open WebUI authority changes.

This adapter patches only the pinned 0.11.4 route shapes. Any upstream source
drift fails the build so the security behavior can be reviewed explicitly.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path


ROOT = Path(os.environ.get("HADES_OPEN_WEBUI_BACKEND", "/app/backend/open_webui"))
USERS = ROOT / "routers/users.py"
GROUPS = ROOT / "routers/groups.py"
AUTHS = ROOT / "routers/auths.py"
MARKER = "HADES_AUTHORITY_REVOCATION_COMPAT"


def bounds(source: str, name: str) -> tuple[int, int]:
    tree = ast.parse(source)
    nodes = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    if len(nodes) != 1:
        raise RuntimeError(f"Expected exactly one top-level {name} function")
    return nodes[0].lineno - 1, nodes[0].end_lineno


def patch_function(path: Path, name: str, old: str, new: str) -> None:
    source = path.read_text(encoding="utf-8")
    start, end = bounds(source, name)
    lines = source.splitlines(keepends=True)
    segment = "".join(lines[start:end])
    if MARKER in segment:
        return
    if segment.count(old) != 1:
        raise RuntimeError(f"{path.name}:{name} source shape changed; review this adapter")
    segment = segment.replace(old, new, 1)
    lines[start:end] = segment.splitlines(keepends=True)
    patched = "".join(lines)
    ast.parse(patched)
    path.write_text(patched, encoding="utf-8")


def apply_users() -> None:
    old_update = '''        if form_data.password:
            try:
                validate_password(form_data.password)
            except Exception as e:
                raise HTTPException(400, detail=str(e))

            hashed = await get_password_hash(form_data.password)
            if await Auths.update_user_password_by_id(user_id, hashed, db=db):
                await revoke_user_tokens(request, user_id)
'''
    new_update = '''        # HADES_AUTHORITY_REVOCATION_COMPAT: validate, then persist revocation before authority mutation.
        if form_data.password:
            try:
                validate_password(form_data.password)
            except Exception as e:
                raise HTTPException(400, detail=str(e))

        hades_authority_change = bool(form_data.password) or (
            form_data.role is not None and form_data.role != user.role
        )
        if hades_authority_change:
            await revoke_user_tokens(request, user_id)

        if form_data.password:
            hashed = await get_password_hash(form_data.password)
            await Auths.update_user_password_by_id(user_id, hashed, db=db)
'''
    patch_function(USERS, "update_user_by_id", old_update, new_update)

    old_delete = "        result = await Auths.delete_auth_by_id(user_id, db=db)\n"
    new_delete = '''        # HADES_AUTHORITY_REVOCATION_COMPAT: revoke HTTP and live socket sessions before deletion.
        await revoke_user_tokens(request, user_id)
        result = await Auths.delete_auth_by_id(user_id, db=db)
'''
    patch_function(USERS, "delete_user_by_id", old_delete, new_delete)


def apply_groups() -> None:
    patch_function(
        GROUPS,
        "update_group_by_id",
        "        group = await Groups.update_group_by_id(id, form_data, db=db)\n",
        '''        # HADES_AUTHORITY_REVOCATION_COMPAT: group policy changes refresh all member sessions.
        from open_webui.utils.auth import revoke_user_tokens as hades_revoke_user_tokens

        for member_id in await Groups.get_group_user_ids_by_id(id, db=db):
            await hades_revoke_user_tokens(request, member_id)
        group = await Groups.update_group_by_id(id, form_data, db=db)
''',
    )
    patch_function(
        GROUPS,
        "add_user_to_group",
        "        group = await Groups.add_users_to_group(id, form_data.user_ids, db=db)\n",
        '''        # HADES_AUTHORITY_REVOCATION_COMPAT: refresh cached member authority before adding membership.
        from open_webui.utils.auth import revoke_user_tokens as hades_revoke_user_tokens

        for member_id in set(form_data.user_ids or []):
            await hades_revoke_user_tokens(request, member_id)
        group = await Groups.add_users_to_group(id, form_data.user_ids, db=db)
''',
    )
    patch_function(
        GROUPS,
        "remove_users_from_group",
        "        group = await Groups.remove_users_from_group(id, form_data.user_ids, db=db)\n",
        '''        # HADES_AUTHORITY_REVOCATION_COMPAT: revoke every affected member before removal.
        from open_webui.utils.auth import revoke_user_tokens as hades_revoke_user_tokens

        for member_id in set(form_data.user_ids or []):
            await hades_revoke_user_tokens(request, member_id)
        group = await Groups.remove_users_from_group(id, form_data.user_ids, db=db)
''',
    )
    patch_function(
        GROUPS,
        "delete_group_by_id",
        "        result = await Groups.delete_group_by_id(id, db=db)\n",
        '''        # HADES_AUTHORITY_REVOCATION_COMPAT: revoke all members before deleting the group.
        from open_webui.utils.auth import revoke_user_tokens as hades_revoke_user_tokens

        for member_id in await Groups.get_group_user_ids_by_id(id, db=db):
            await hades_revoke_user_tokens(request, member_id)
        result = await Groups.delete_group_by_id(id, db=db)
''',
    )


def apply_auths() -> None:
    patch_function(
        AUTHS,
        "update_password",
        """            hashed = await get_password_hash(form_data.new_password)
            success = await Auths.update_user_password_by_id(user.id, hashed, db=db)
            if success:
                await revoke_user_tokens(request, user.id)
                await publish_event(
                    request,
                    EVENTS.AUTH_PASSWORD_CHANGED,
                    actor=user,
                    subject_id=user.id,
                    subject_type='user',
                )
""",
        """            # HADES_AUTHORITY_REVOCATION_COMPAT: revoke before changing credentials.
            await revoke_user_tokens(request, user.id)
            hashed = await get_password_hash(form_data.new_password)
            success = await Auths.update_user_password_by_id(user.id, hashed, db=db)
            if success:
                await publish_event(
                    request,
                    EVENTS.AUTH_PASSWORD_CHANGED,
                    actor=user,
                    subject_id=user.id,
                    subject_type='user',
                )
""",
    )

    source = AUTHS.read_text(encoding="utf-8")
    start, end = bounds(source, "create_session_response")
    lines = source.splitlines(keepends=True)
    segment = "".join(lines[start:end])
    if MARKER not in segment:
        anchor = "    token = create_token(\n        data={'id': user.id},\n"
        replacement = """    from open_webui.utils.auth import REDIS_KEY_PREFIX

    # HADES_AUTHORITY_REVOCATION_COMPAT: do not issue a JWT whose integer iat
    # predates the fractional marker written during an authority change.
    redis = getattr(request.app.state, 'redis', None)
    if redis is None:
        raise HTTPException(503, detail='Session verification unavailable.')
    try:
        revoked_at = await redis.get(f'{REDIS_KEY_PREFIX}:auth:user:{user.id}:revoked_at')
        if revoked_at:
            revoked_at_ts = float(revoked_at)
            while int(time.time()) <= revoked_at_ts:
                await asyncio.sleep(0.05)
    except Exception as error:
        raise HTTPException(503, detail='Session verification unavailable.') from error

    token = create_token(
        data={'id': user.id},
"""
        if segment.count(anchor) != 1:
            raise RuntimeError("create_session_response token source changed; review adapter")
        segment = segment.replace(anchor, replacement, 1)
        lines[start:end] = segment.splitlines(keepends=True)
        source = "".join(lines)
        ast.parse(source)
        AUTHS.write_text(source, encoding="utf-8")

    source = AUTHS.read_text(encoding="utf-8")
    start, end = bounds(source, "ldap_auth")
    lines = source.splitlines(keepends=True)
    segment = "".join(lines[start:end])
    if MARKER in segment:
        return

    missing_attribute = '''        user_groups = []
        # HADES_AUTHORITY_REVOCATION_COMPAT: missing LDAP group data is not an empty set.
        if ENABLE_LDAP_GROUP_MANAGEMENT and LDAP_ATTRIBUTE_FOR_GROUPS not in entry:
            raise HTTPException(503, detail='LDAP group membership could not be verified.')
'''
    if segment.count("        user_groups = []\n") != 1:
        raise RuntimeError("ldap_auth user_groups initialization changed; review adapter")
    segment = segment.replace("        user_groups = []\n", missing_attribute, 1)

    old_sync = '''                if ENABLE_LDAP_GROUP_MANAGEMENT:  # HADES_EMPTY_LDAP_GROUP_SYNC
                    try:
                        if ENABLE_LDAP_GROUP_CREATION:
                            await Groups.create_groups_by_group_names(user.id, user_groups, db=db)
                        await Groups.sync_groups_by_group_names(user.id, user_groups, db=db)
                        log.info('Successfully synced groups for user %s: %s', user.id, user_groups)
                    except Exception as e:
                        log.error(f'Failed to sync groups for user {user.id}: {e}')
'''
    new_sync = '''                if ENABLE_LDAP_GROUP_MANAGEMENT:  # HADES_EMPTY_LDAP_GROUP_SYNC
                    try:
                        if ENABLE_LDAP_GROUP_CREATION:
                            await Groups.create_groups_by_group_names(user.id, user_groups, db=db)
                        current_groups = await Groups.get_groups_by_member_id(user.id, db=db)
                        current_names = {group.name for group in current_groups}
                        target_names = set(user_groups)
                        membership_changed = current_names != target_names
                        if membership_changed:
                            await revoke_user_tokens(request, user.id)
                        if not await Groups.sync_groups_by_group_names(user.id, user_groups, db=db):
                            raise RuntimeError('LDAP group reconciliation did not complete')
                        log.info('Successfully synced groups for user %s: %s', user.id, user_groups)
                    except Exception as e:
                        log.error(f'Failed to sync groups for user {user.id}: {e}')
                        raise HTTPException(503, detail='LDAP group reconciliation unavailable.') from e
'''
    if segment.count(old_sync) == 1:
        segment = segment.replace(old_sync, new_sync, 1)
    elif (
        segment.count("current_groups = await Groups.get_groups_by_member_id(user.id, db=db)") == 1
        and segment.count("await Groups.sync_groups_by_group_names(user.id, user_groups, db=db)") == 1
        and segment.count("HADES_EMPTY_LDAP_GROUP_SYNC") == 1
    ):
        # The empty-group adapter was already applied in this exact source tree.
        # Continue adding the revocation and outage behavior around its reconciler.
        old_reconcile = """                if ENABLE_LDAP_GROUP_MANAGEMENT:  # HADES_EMPTY_LDAP_GROUP_SYNC
                    try:
                        if ENABLE_LDAP_GROUP_CREATION:
                            await Groups.create_groups_by_group_names(user.id, user_groups, db=db)
                        current_groups = await Groups.get_groups_by_member_id(user.id, db=db)
                        current_names = {group.name for group in current_groups}
                        target_names = set(user_groups)
                        membership_changed = current_names != target_names
                        if membership_changed:
                            await revoke_user_tokens(request, user.id)
                        await Groups.sync_groups_by_group_names(user.id, user_groups, db=db)
                        log.info('Successfully synced groups for user %s: %s', user.id, user_groups)
                    except Exception as e:
                        log.error(f'Failed to sync groups for user {user.id}: {e}')
"""
        if segment.count(old_reconcile) != 1:
            raise RuntimeError("Existing LDAP reconciliation source changed; review adapter")
        segment = segment.replace(old_reconcile, new_sync, 1)
    else:
        raise RuntimeError("ldap_auth group reconciliation block changed; review adapter")
    outer_catch = """    except Exception as e:
        log.error(f'LDAP authentication error: {str(e)}')
        raise HTTPException(400, detail='LDAP authentication failed.')
"""
    outer_catch_safe = """    except HTTPException:
        raise
    except Exception as e:
        log.error(f'LDAP authentication error: {str(e)}')
        raise HTTPException(503, detail='LDAP authentication service unavailable.')
"""
    if segment.count(outer_catch) != 1:
        raise RuntimeError("ldap_auth outer error handler changed; review adapter")
    segment = segment.replace(outer_catch, outer_catch_safe, 1)
    lines[start:end] = segment.splitlines(keepends=True)
    patched = "".join(lines)
    ast.parse(patched)
    AUTHS.write_text(patched, encoding="utf-8")


def apply() -> None:
    apply_users()
    apply_groups()
    apply_auths()


if __name__ == "__main__":
    apply()
