#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path

route = Path('webui/task_notification_compat.py').read_text(encoding='utf-8')
theme = Path('webui/hades-theme.js').read_text(encoding='utf-8')
compose = Path('deploy/templates/open-webui.compose.yaml').read_text(encoding='utf-8')
dockerfile = Path('webui/Dockerfile').read_text(encoding='utf-8')

for expected in (
    "@app.get('/api/v1/hades/tasks/notifications')",
    'Depends(get_verified_user)',
    "getattr(user, 'id', '')",
    "'X-Hermes-Session-Key': 'hades-user-' + subject",
    "'Authorization': 'Bearer ' + api_key",
    "response.headers['Cache-Control'] = 'no-store'",
):
    assert expected in route, expected
assert 'request:' not in route and 'actor_subject_id' not in route
assert 'HADES_TASK_NOTIFICATIONS_HERMES_API_KEY' in compose
assert 'HADES_TASK_NOTIFICATIONS_HERMES_API_BASE_URL' in compose
assert 'python3 /opt/hades/task_notification_compat.py' in dockerfile
for expected in (
    "@app.get('/api/v1/hades/automations/notifications')",
    "'HADES_PHASE3_NOTIFICATION_FEED_V1'",
    "'X-Hermes-Session-Key': 'hades-user-' + subject",
    "response.headers['Cache-Control'] = 'no-store'",
    "status_code=403",
):
    assert expected in route, expected
for expected in (
    "'/api/v1/hades/tasks/notifications'",
    'taskNotificationStateKey(userId)',
    'Notification.requestPermission()',
    "review.textContent = 'Review in HADES'",
    'Show me the status of task ${item.task_id}',
    'credentials: \'same-origin\'',
    'taskNotificationRecipient !== userId',
    'sessionUserId() !== userId',
    'taskDesktopNotifications.clear()',
    'response.status === 401 || response.status === 403',
    'if (sessionUserId() === userId)',
    'taskNotificationAuthorizationEpoch',
    'requestEpoch !== taskNotificationAuthorizationEpoch',
    'taskNotificationReviewKey(userId)',
    "'/api/v1/hades/automations/notifications'",
    'automationNotificationStateKey(userId)',
    'automationNotificationAuthorizationEpoch',
    'item.actionable && prior !== item.state_key',
    'notice.dataset.hadesSources',
    'currentBySource.set(item.source_key, item)',
    'delivery.notification.close()',
    'current?.actionable && current.state_key === displayed.state_key',
    'Show me my latest automation results',
    'automationNotificationRecipient !== userId',
):
    assert expected in theme, expected
print('PASS Task notifications require verified Open WebUI identity, actor-bound Hermes subject, local dedup, and explicit desktop permission')
PY
