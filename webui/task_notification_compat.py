"""Install the authenticated HADES Task notification snapshot endpoint."""

import os
from pathlib import Path


MAIN = Path(os.environ.get("HADES_OPEN_WEBUI_MAIN_FILE", "/app/backend/open_webui/main.py"))
MARKER = "\n\n##################################\n#\n# Chat Endpoints"
TASK_ROUTE_DECL = "async def hades_task_notification_snapshot("
RESULT_ROUTE_DECL = "async def hades_phase3_notification_snapshot("
TASK_ROUTE_PATH = "@app.get('/api/v1/hades/tasks/notifications')"
RESULT_ROUTE_PATH = "@app.get('/api/v1/hades/automations/notifications')"
ROUTE = r'''

# HADES-local Task notification snapshot. Open WebUI authenticates the caller;
# the server derives the Hermes subject from that verified account and keeps
# the Hermes API key out of the browser.
@app.get('/api/v1/hades/tasks/notifications')
async def hades_task_notification_snapshot(user=Depends(get_verified_user)):
    import asyncio as _hades_asyncio
    import json as _hades_json
    import os as _hades_os
    import re as _hades_re
    import urllib.error as _hades_error
    import urllib.request as _hades_request

    subject = str(getattr(user, 'id', '') or '').strip()
    if not _hades_re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', subject):
        raise HTTPException(status_code=401, detail='Authenticated HADES identity is unavailable.')
    base = _hades_os.environ.get('HADES_TASK_NOTIFICATIONS_HERMES_API_BASE_URL', '').strip().rstrip('/')
    api_key = _hades_os.environ.get('HADES_TASK_NOTIFICATIONS_HERMES_API_KEY', '').strip()
    model = _hades_os.environ.get('HADES_TASK_NOTIFICATIONS_MODEL', 'hermes-agent').strip()
    if not base or not api_key or not model:
        raise HTTPException(status_code=503, detail='HADES Task notifications are not configured.')
    endpoint = base + ('/chat/completions' if base.endswith('/v1') else '/v1/chat/completions')
    payload = _hades_json.dumps({
        'model': model,
        'messages': [{'role': 'user', 'content': 'HADES_TASK_NOTIFICATION_FEED_V1'}],
        'stream': False,
        'temperature': 0,
        'max_tokens': 2048,
    }).encode('utf-8')

    def _read_snapshot():
        request = _hades_request.Request(endpoint, data=payload, headers={
            'Authorization': 'Bearer ' + api_key,
            'Content-Type': 'application/json',
            'X-Hermes-Session-Key': 'hades-user-' + subject,
        }, method='POST')
        with _hades_request.urlopen(request, timeout=12) as response:
            envelope = _hades_json.loads(response.read(1024 * 1024))
        content = envelope.get('choices', [{}])[0].get('message', {}).get('content', '')
        result = _hades_json.loads(content)
        if not isinstance(result, dict) or result.get('version') != 1 or not isinstance(result.get('tasks'), list):
            raise ValueError('invalid Task notification snapshot')
        if result.get('error'):
            raise RuntimeError('Task store unavailable')
        tasks = []
        for item in result['tasks'][:100]:
            if not isinstance(item, dict):
                continue
            task_id = str(item.get('task_id') or '')
            status = str(item.get('status') or '')
            if not _hades_re.fullmatch(r'task-[A-Za-z0-9][A-Za-z0-9-]{2,127}', task_id):
                continue
            if status not in {'AWAITING_APPROVAL', 'BLOCKED', 'FAILED', 'OUTCOME_UNKNOWN', 'COMPLETED'}:
                continue
            tasks.append({
                'task_id': task_id,
                'revision': max(0, int(item.get('revision') or 0)),
                'status': status,
                'goal': ' '.join(str(item.get('goal') or '').split())[:180],
                'updated_at': max(0, int(item.get('updated_at') or 0)),
            })
        return {'version': 1, 'tasks': tasks}

    try:
        result = await _hades_asyncio.to_thread(_read_snapshot)
    except (_hades_error.URLError, TimeoutError, ValueError, RuntimeError, KeyError, TypeError, IndexError) as exc:
        # Do not return upstream response bodies, keys, or endpoint details.
        raise HTTPException(status_code=503, detail='HADES Task notifications are temporarily unavailable.') from exc
    response = JSONResponse(result)
    response.headers['Cache-Control'] = 'no-store'
    return response
'''


RESULT_ROUTE = r'''
# HADES-local Phase 3 result notifications use the requester-scoped result API
# through Hermes. The verified Open WebUI subject is server-set; the browser
# never receives the separate result HMAC key.
@app.get('/api/v1/hades/automations/notifications')
async def hades_phase3_notification_snapshot(user=Depends(get_verified_user)):
    import asyncio as _hades_asyncio
    import json as _hades_json
    import os as _hades_os
    import re as _hades_re
    import urllib.request as _hades_request

    subject = str(getattr(user, 'id', '') or '').strip()
    if not _hades_re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', subject):
        raise HTTPException(status_code=401, detail='Authenticated HADES identity is unavailable.')
    base = _hades_os.environ.get('HADES_TASK_NOTIFICATIONS_HERMES_API_BASE_URL', '').strip().rstrip('/')
    api_key = _hades_os.environ.get('HADES_TASK_NOTIFICATIONS_HERMES_API_KEY', '').strip()
    model = _hades_os.environ.get('HADES_TASK_NOTIFICATIONS_MODEL', 'hermes-agent').strip()
    if not base or not api_key or not model:
        raise HTTPException(status_code=503, detail='HADES automation notifications are not configured.')
    endpoint = base + ('/chat/completions' if base.endswith('/v1') else '/v1/chat/completions')
    payload = _hades_json.dumps({
        'model': model,
        'messages': [{'role': 'user', 'content': 'HADES_PHASE3_NOTIFICATION_FEED_V1'}],
        'stream': False,
        'temperature': 0,
        'max_tokens': 2048,
    }).encode('utf-8')

    def _read_snapshot():
        request = _hades_request.Request(endpoint, data=payload, headers={
            'Authorization': 'Bearer ' + api_key,
            'Content-Type': 'application/json',
            'X-Hermes-Session-Key': 'hades-user-' + subject,
        }, method='POST')
        with _hades_request.urlopen(request, timeout=12) as response:
            envelope = _hades_json.loads(response.read(1024 * 1024))
        content = envelope.get('choices', [{}])[0].get('message', {}).get('content', '')
        result = _hades_json.loads(content)
        if not isinstance(result, dict) or result.get('version') != 1 or not isinstance(result.get('notifications'), list):
            raise ValueError('invalid Phase 3 notification snapshot')
        if result.get('error') == 'access_unavailable':
            raise PermissionError('current result access is unavailable')
        if result.get('error'):
            raise RuntimeError('Phase 3 result store unavailable')
        notifications = []
        for item in result['notifications'][:5]:
            if not isinstance(item, dict):
                continue
            source_key = str(item.get('source_key') or '')
            state_key = str(item.get('state_key') or '')
            title = ' '.join(str(item.get('title') or '').split())[:80]
            message = ' '.join(str(item.get('message') or '').split())[:240]
            actionable = item.get('actionable')
            if not _hades_re.fullmatch(r'[a-f0-9]{64}', source_key) or not _hades_re.fullmatch(r'[a-f0-9]{64}', state_key):
                continue
            if not title or type(actionable) is not bool or any(ord(char) < 32 for char in title + message):
                continue
            notifications.append({
                'source_key': source_key,
                'state_key': state_key,
                'actionable': actionable,
                'title': title,
                'message': message,
            })
        return {'version': 1, 'notifications': notifications}

    try:
        result = await _hades_asyncio.to_thread(_read_snapshot)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail='Current HADES access does not permit these results.') from exc
    except Exception as exc:
        # Never forward result service bodies, credentials, or endpoint details.
        raise HTTPException(status_code=503, detail='HADES automation notifications are temporarily unavailable.') from exc
    response = JSONResponse(result)
    response.headers['Cache-Control'] = 'no-store'
    return response
'''


source = MAIN.read_text(encoding="utf-8")
if source.count(MARKER) != 1:
    raise SystemExit("expected exactly one Open WebUI chat endpoint marker")
task_declared = source.count(TASK_ROUTE_DECL)
result_declared = source.count(RESULT_ROUTE_DECL)
task_paths = source.count(TASK_ROUTE_PATH)
result_paths = source.count(RESULT_ROUTE_PATH)
if task_declared > 1 or result_declared > 1 or task_paths > 1 or result_paths > 1:
    raise SystemExit("duplicate HADES notification route exists")
if bool(task_declared) != bool(task_paths) or bool(result_declared) != bool(result_paths):
    raise SystemExit("partial HADES notification route exists")

routes = []
if not task_declared:
    routes.append(ROUTE)
if not result_declared:
    routes.append(RESULT_ROUTE)
if routes:
    MAIN.write_text(source.replace(MARKER, "\n".join(routes) + MARKER), encoding="utf-8")
print("PASS authenticated HADES notification routes ready")
