#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
compose="$repo_dir/deploy/templates/open-webui.compose.yaml"
dockerfile="$repo_dir/webui/Dockerfile"
auth="$repo_dir/webui/auth_revocation_fail_closed_compat.py"
socket_adapter="$repo_dir/webui/socket_disconnect_fail_closed_compat.py"
routes="$repo_dir/webui/authority_revocation_routes_compat.py"
cutover_revocations="$repo_dir/scripts/seed-open-webui-session-revocations.py"

grep -Fq 'HADES_OPEN_WEBUI_VALKEY_IMAGE:?set a pinned HADES_OPEN_WEBUI_VALKEY_IMAGE' "$compose" || { echo 'FAIL auth-state image is not required'; exit 1; }
grep -Fq -- '--appendfsync' "$compose" && grep -Fq '      - always' "$compose" || { echo 'FAIL Valkey revocation writes are not configured for durable fsync'; exit 1; }
grep -Fq 'internal: true' "$compose" || { echo 'FAIL Valkey network is not internal'; exit 1; }
grep -Fq 'REDIS_URL: redis://hades-open-webui-auth-state:6379/0' "$compose" || { echo 'FAIL JWT revocation store is not wired'; exit 1; }
grep -Fq 'WEBSOCKET_MANAGER: redis' "$compose" || { echo 'FAIL cross-worker Socket.IO manager is not wired'; exit 1; }
grep -Fq 'WEBSOCKET_REDIS_URL: redis://hades-open-webui-auth-state:6379/1' "$compose" || { echo 'FAIL Socket.IO Redis database is not isolated'; exit 1; }
grep -Fq 'open-webui-auth-state:/data' "$compose" || { echo 'FAIL Valkey persistence volume is absent'; exit 1; }
grep -Fq 'auth-state:' "$compose" || { echo 'FAIL private auth-state service is absent'; exit 1; }
grep -Fq 'depends_on:' "$compose" && grep -Fq 'condition: service_healthy' "$compose" || { echo 'FAIL Open WebUI does not wait for auth-state health'; exit 1; }

for marker in 'def is_valid_token' 'def invalidate_token' 'def revoke_user_tokens' 'disconnect_user_sessions' 'HTTPException(503' 'await redis.set'; do
  grep -Fq "$marker" "$auth" || { echo "FAIL auth adapter omits $marker"; exit 1; }
done
for marker in 'update_password' 'create_session_response' 'int(time.time()) <= revoked_at_ts' 'update_user_by_id' 'delete_user_by_id' 'update_group_by_id' 'add_user_to_group' 'remove_users_from_group' 'delete_group_by_id' 'membership_changed' 'LDAP group membership could not be verified'; do
  grep -Fq "$marker" "$routes" || { echo "FAIL authority adapter omits $marker"; exit 1; }
done
grep -Fq 'Session revocation incomplete' "$socket_adapter" && grep -Fq 'HTTPException(503' "$socket_adapter" || { echo 'FAIL socket revocation failures are not visible'; exit 1; }
for adapter in auth_revocation_fail_closed_compat.py ldap_group_sync_compat.py authority_revocation_routes_compat.py socket_disconnect_fail_closed_compat.py; do
  grep -Fq "$adapter" "$dockerfile" || { echo "FAIL candidate image omits $adapter"; exit 1; }
done
grep -Fq 'org.hades.open-webui.security-adapters' "$repo_dir/scripts/build-open-webui-artifact.sh" || { echo 'FAIL candidate image omits security adapter provenance'; exit 1; }
grep -Fq 'org.hades.open-webui.security-adapters' "$repo_dir/scripts/verify-openwebui-candidate-artifact.sh" || { echo 'FAIL candidate verifier omits security adapter provenance'; exit 1; }
grep -Fq 'open-webui-auth-state.rdb' "$repo_dir/scripts/backup-sqlite-state.sh" && grep -Fq 'valkey-check-rdb' "$repo_dir/scripts/backup-sqlite-state.sh" && grep -Fq 'HADES_REQUIRE_OPEN_WEBUI_AUTH_STATE_BACKUP' "$repo_dir/scripts/backup-sqlite-state.sh" || { echo 'FAIL recovery helper omits required validated Valkey revocation backup'; exit 1; }
for marker in 'confirm-quiesced' 'mode=ro&immutable=1' 'PRAGMA integrity_check' 'revoked_at' 'PTTL' 'time.time() + 5.0'; do
  grep -Fq "$marker" "$cutover_revocations" || { echo "FAIL cutover session invalidation omits $marker"; exit 1; }
done
grep -Fq 'seed-open-webui-session-revocations.py' "$repo_dir/scripts/test-open-webui-populated-migration.sh" || { echo 'FAIL populated migration does not exercise legacy-session invalidation'; exit 1; }

echo 'PASS Open WebUI P0 auth, authority, storage, and artifact security contract'
