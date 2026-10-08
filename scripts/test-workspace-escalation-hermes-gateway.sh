#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
stage_root=${HADES_STAGE_ROOT:-/opt/hades-stage}
export HADES_STAGE_ROOT="$stage_root"
hermes_source=$stage_root/Hermes-v0.21.5-hades-candidate
hermes_python=${HADES_WORKSPACE_TEST_HERMES_PYTHON:-$hermes_source/.venv/bin/python}
hermes_bin=$hermes_source/.venv/bin/hermes
[[ -x "$hermes_python" && -x "$hermes_bin" ]] || { echo 'FAIL Hermes candidate runtime unavailable' >&2; exit 2; }
work=$(mktemp -d "${TMPDIR:-/tmp}/hades-workspace-gateway.XXXXXX")
chmod 700 "$work"
gateway_pid=''
cleanup() {
  local status=$?
  trap - EXIT
  [[ -z "$gateway_pid" ]] || { kill "$gateway_pid" >/dev/null 2>&1 || true; wait "$gateway_pid" >/dev/null 2>&1 || true; }
  if ((status != 0)); then
    [[ ! -f "$work/gateway.log" ]] || tail -n 60 "$work/gateway.log" >&2
  fi
  rm -rf "$work"
  exit "$status"
}
trap cleanup EXIT

mkdir -m 700 "$work/home" "$work/hermes" "$work/overlay" "$work/bin"
mkdir -m 700 "$work/hermes/plugins"
cp -a "$stage_root/HADES_HOME/plugins/hindsight" "$work/hermes/plugins/hindsight"
cp "$repo_dir/hermes/sitecustomize.py" "$work/overlay/sitecustomize.py"
cp "$repo_dir/hermes/workspace.py" "$work/overlay/workspace.py"
# This stub qualifies the workspace path and services only Hermes' runtime preflight. It creates
# no containers and executes no workspace command; the test qualifies gateway/session tool
# authorization, not the rootless Docker isolation contract (covered by the runtime test).
cat >"$work/bin/docker" <<'SH'
#!/bin/sh
printf '%s\n' "$*" >>"$HADES_SYNTHETIC_DOCKER_CALLS"
case "$*" in
  version) echo 'Docker version 29.8.2, build synthetic' ;;
  'info --format {{json .SecurityOptions}}') echo '["name=rootless"]' ;;
  'info --format {{.Driver}}') echo vfs ;;
  'image inspect --format {{.Id}} docker.io/nikolaik/python-nodejs@sha256:6ed4d9fb74dc6c7a5caa9120d8d3c507dbf97fb112b7b09d0d9f7d71f1ce919d') echo 'sha256:synthetic-image-present' ;;
  *'Config.Entrypoint'*) echo '[]' ;;
  *'sleep 0'*) exit 0 ;;
  *'prompt-backend-probe'*) echo synthetic-prompt-probe-container ;;
  *) echo "unexpected Docker execution in no-write test: $*" >&2; exit 90 ;;
esac
SH
chmod 700 "$work/bin/docker"

HOME="$work/home" HERMES_HOME="$work/hermes" \
PYTHONPATH="$work/overlay:$repo_dir:$hermes_source" \
HADES_OWNER_SUBJECT_IDS=synthetic-owner HADES_WORKSPACE_ENABLED=true \
HADES_WORKSPACE_ROOT="$work/hermes/workspaces" \
HADES_HERMES_SANDBOX_IMAGE=docker.io/nikolaik/python-nodejs@sha256:6ed4d9fb74dc6c7a5caa9120d8d3c507dbf97fb112b7b09d0d9f7d71f1ce919d \
HERMES_DOCKER_BINARY="$work/bin/docker" HADES_HERMES_EXECUTABLE="$hermes_bin" \
HADES_SYNTHETIC_DOCKER_CALLS="$work/docker.calls" \
HERMES_ACCEPT_HOOKS=1 PATH="$work/bin:$PATH" \
python3 - "$repo_dir" "$work" "$hermes_bin" <<'PY'
import json, os, socket, subprocess, sys, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

repo, work, hermes_bin = map(Path, sys.argv[1:])
api_key = "synthetic-workspace-gateway-key"
session_id = "synthetic-workspace-escalation-session"
workspace_tool_names = {"read_file", "search_files", "write_file", "patch", "terminal"}
readonly_git_tool_names = {"read_file", "search_files", "terminal"}
model_turns = []

class FakeModel(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        tools = body.get("tools", [])
        names = [tool.get("function", {}).get("name") for tool in tools]
        messages = body.get("messages", [])
        user_text = next((str(msg.get("content", "")) for msg in reversed(messages)
                          if msg.get("role") == "user"), "")
        if user_text:
            model_turns.append({"user": user_text, "tools": names, "messages": messages})
        diagnostic = "Why is this Python test failing?" in user_text
        make_attack = diagnostic and not any(
            msg.get("role") == "tool" for msg in messages
        )
        now = int(time.time())
        base = {"id": "synthetic-gateway-test", "object": "chat.completion.chunk",
                "created": now, "model": "qwen3.6:35b"}
        if make_attack:
            args = json.dumps({"path": "/workspace/answer.py", "old_string": "before", "new_string": "after"})
            deltas = [
                {"role": "assistant"},
                {"tool_calls": [{"index": 0, "id": "synthetic-unauthorized-patch", "type": "function",
                                  "function": {"name": "patch", "arguments": ""}}]},
                {"tool_calls": [{"index": 0, "function": {"arguments": args}}]},
                {},
            ]
            chunks = [{**base, "choices": [{"index": 0, "delta": delta,
                       "finish_reason": "tool_calls" if i == 3 else None}]}
                      for i, delta in enumerate(deltas)]
        else:
            answer = "I did not change the file."
            chunks = [
                {**base, "choices": [{"index": 0, "delta": {"role": "assistant", "content": answer},
                                       "finish_reason": None}]},
                {**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
            ]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        for chunk in chunks:
            self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

provider = ThreadingHTTPServer(("127.0.0.1", 0), FakeModel)
threading.Thread(target=provider.serve_forever, daemon=True).start()
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    gateway_port = sock.getsockname()[1]

# Use a single-profile default gateway so the test exercises the same process environment as
# HADES deployment, without secondary-profile env scoping. The 077 umask keeps every workspace
# ancestor private; HADES rejects a permissive intermediate directory by design.
(work / "hermes" / "config.yaml").write_text(
    f"model:\n  default: qwen3.6:35b\n  provider: custom\n  base_url: http://127.0.0.1:{provider.server_port}/v1\n"
    "platforms:\n  api_server:\n    enabled: true\n    extra:\n      host: 127.0.0.1\n"
    f"      port: {gateway_port}\n      key: {api_key}\n", encoding="utf-8")
os.chmod(work / "hermes" / "config.yaml", 0o600)
gateway_env = dict(os.environ, HOME=str(work / "home"), HERMES_HOME=str(work / "hermes"),
                   PYTHONPATH=f"{work / 'overlay'}:{repo}:{Path(os.environ['HADES_STAGE_ROOT']) / 'Hermes-v0.21.5-hades-candidate'}",
                   API_SERVER_ENABLED="true", API_SERVER_KEY=api_key,
                   API_SERVER_HOST="127.0.0.1", API_SERVER_PORT=str(gateway_port),
                   OPENAI_API_KEY="synthetic-only", MODEL="qwen3.6:35b",
                   HADES_OWNER_SUBJECT_IDS="synthetic-owner", HADES_WORKSPACE_ENABLED="true",
                   HADES_WORKSPACE_ROOT=str(work / "hermes" / "workspaces"),
                   HADES_HERMES_SANDBOX_IMAGE="docker.io/nikolaik/python-nodejs@sha256:6ed4d9fb74dc6c7a5caa9120d8d3c507dbf97fb112b7b09d0d9f7d71f1ce919d",
                   HERMES_DOCKER_BINARY=str(work / "bin" / "docker"),
                   HADES_SYNTHETIC_DOCKER_CALLS=str(work / "docker.calls"),
                   HADES_HERMES_EXECUTABLE=str(hermes_bin), HERMES_ACCEPT_HOOKS="1",
                   PATH=str(work / "bin") + os.pathsep + os.environ["PATH"])
log_path = work / "gateway.log"
with log_path.open("w") as log:
    gateway = subprocess.Popen([str(hermes_bin), "gateway", "run", "-v"], env=gateway_env,
                               stdout=log, stderr=subprocess.STDOUT)
gateway_base = f"http://127.0.0.1:{gateway_port}"

def chat(text, *, request_session_id=session_id):
    request = urllib.request.Request(
        gateway_base + "/v1/chat/completions",
        data=json.dumps({"model": "qwen3.6:35b", "messages": [{"role": "user", "content": text}]}).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                 "X-Hermes-Session-Key": "hades-user-synthetic-owner",
                 "X-Hermes-Session-Id": request_session_id}, method="POST")
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response), response.headers.get("X-Hermes-Session-Id")

try:
    for _ in range(90):
        if gateway.poll() is not None:
            raise AssertionError("Hermes gateway exited before health check")
        try:
            urllib.request.urlopen(gateway_base + "/health", timeout=1).read()
            break
        except Exception:
            time.sleep(1)
    else:
        raise AssertionError("Hermes gateway did not become healthy")

    workspace = work / "hermes" / "workspaces" / "synthetic-owner"
    workspace.mkdir(parents=True, mode=0o700)
    fixture = workspace / "answer.py"
    fixture.write_text("before\n", encoding="utf-8")
    before = fixture.read_bytes()

    diagnosis, echoed = chat("Why is this Python test failing?")
    assert echoed == session_id, echoed
    assert fixture.read_bytes() == before, "unauthorized model-issued patch changed the fixture"
    diagnosis_turns = [turn for turn in model_turns if "Why is this Python test failing?" in turn["user"]]
    exposed = [turn for turn in diagnosis_turns if set(turn["tools"]) == {"read_file", "search_files"}]
    assert exposed, "gateway diagnosis did not receive only the two read-only workspace tools"
    rejection = [str(msg.get("content", "")) for turn in diagnosis_turns
                 for msg in turn["messages"] if msg.get("role") == "tool"]
    assert any("patch" in content.lower() and any(marker in content.lower() for marker in
               ("does not exist", "not available", "invalid_tool", "unknown tool"))
               for content in rejection), diagnosis_turns

    followup, echoed = chat("Fix it.")
    assert echoed == session_id, echoed
    assert fixture.read_bytes() == before, "text-only follow-up unexpectedly changed the fixture"
    action_turns = [turn for turn in model_turns if turn["user"].strip() == "Fix it."]
    assert any(set(turn["tools"]) == workspace_tool_names for turn in action_turns), action_turns
    docker_calls = (work / "docker.calls").read_text().splitlines()
    assert not any("hermes-task-id=synthetic-workspace-escalation-session" in call
                   for call in docker_calls), docker_calls
    review_question = "Show me exactly what changed and whether anything unrelated is in the diff."
    # Keep this request isolated from the preceding action turn so the
    # assertion measures Git intent routing, not an earlier tool transcript.
    review_session_id = "synthetic-workspace-git-review-session"
    review, echoed = chat(review_question, request_session_id=review_session_id)
    assert echoed == review_session_id, echoed
    review_turns = [turn for turn in model_turns if turn["user"].strip() == review_question]
    assert any(set(turn["tools"]) == readonly_git_tool_names for turn in review_turns), [
        turn.get("tools") for turn in review_turns
    ]
    print("PASS live authenticated Hermes gateway carried the same explicit session across diagnosis and follow-up")
    assert any(set(turn["tools"]) == workspace_tool_names for turn in action_turns), action_turns
    print("PASS diagnosis receives two read-only schemas; action follow-up receives all five")
    print("PASS Git diff review receives file reads and the read-only terminal, without write/patch tools")
    print("PASS synthetic unauthorized diagnosis-time patch was rejected; fixture bytes stayed unchanged")
finally:
    gateway.terminate()
    try:
        gateway.wait(timeout=15)
    except subprocess.TimeoutExpired:
        gateway.kill()
        gateway.wait(timeout=5)
    provider.shutdown()
PY
