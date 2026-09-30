#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/hades-failure-honesty-ui.XXXXXX")
report="$work/browser-output.log"
cleanup() { find "$work" -depth -mindepth 1 -delete 2>/dev/null || true; rmdir "$work" 2>/dev/null || true; }
trap cleanup EXIT

image=${HADES_HINDSIGHT_UI_WEBUI_IMAGE:-}
[[ -n "$image" ]] || { echo 'FAIL set HADES_HINDSIGHT_UI_WEBUI_IMAGE to the locally built HADES Open WebUI image' >&2; exit 2; }

set +e
HADES_HINDSIGHT_UI_WEBUI_IMAGE="$image" \
HADES_FAILURE_UI_REPORT="$work/legacy-runner-report.json" \
  bash "$repo_dir/scripts/test-dependency-failure-recovery-authenticated-ui.sh" >"$report" 2>&1
runner_status=$?
set -e

python3 - "$report" "$runner_status" <<'PY'
import json, pathlib, sys
log = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
runner_status = int(sys.argv[2])
rows = []
for line in log.splitlines():
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        continue
    if isinstance(value, dict) and 'chatRequests' in value and 'state' in value:
        rows.append(value)
assert rows, f'authenticated browser runner produced no acceptance record (exit {runner_status})\n{log[-5000:]}'
result = rows[-1]
body = result['state']['bodyTail'].lower()
assert 'your request may have completed' in body and 'check before trying again' in body, 'UI did not explain uncertain completion and advise checking before retry'
assert 'nothing was changed' not in body, 'UI made an unverified no-change promise'
assert 'failed to fetch' not in body, 'raw browser transport error leaked to the user'
assert not result['state']['stop'] and not result['state']['composer'], 'composer remained stuck after failure'
assert result['recovery'] and result['recovery']['new_response'] and result['recovery']['text'] == 'Synthetic recovery succeeded.', 'fresh chat did not recover through the synthetic responder'
requests = result['chatRequests']
assert len(requests) >= 2 and 'ERR_FAILED' in (requests[0].get('failure') or ''), 'first chat request was not proven interrupted'
assert not result['errors'], f'browser raised page errors: {result["errors"]}'
print('PASS authenticated synthetic UI explains uncertain completion, avoids unsafe retry claims, and recovers in a fresh chat')
PY
