#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

hermes_python=${HADES_HERMES_PYTHON:-}
if [[ -z "$hermes_python" ]]; then
  hermes_bin=$(command -v hermes || true)
  if [[ -n "$hermes_bin" ]]; then
    hermes_bin=$(readlink -f "$hermes_bin")
    candidate="$(dirname "$hermes_bin")/python3.11"
    [[ -x "$candidate" ]] && hermes_python=$candidate
  fi
fi
if [[ -z "$hermes_python" || ! -x "$hermes_python" ]]; then
  echo 'FAIL Hermes Python 3.11 was not found; set HADES_HERMES_PYTHON to the Hermes venv interpreter' >&2
  exit 2
fi

python3 - "$PWD" "$hermes_python" <<'PY'
import os
import subprocess
import sys
import tempfile
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
interpreter = Path(sys.argv[2]).absolute()
overlay = Path(os.environ.get("HADES_HERMES_OVERLAY_DIR", str(repo / "hermes"))).resolve()
if not (overlay / "sitecustomize.py").is_file():
    raise SystemExit(f"FAIL HADES overlay directory has no sitecustomize.py: {overlay}")
probe_env = os.environ.copy()
probe_env.pop("PYTHONPATH", None)
hermes_source = Path(subprocess.check_output(
    [str(interpreter), "-c", "import pathlib, run_agent; print(pathlib.Path(run_agent.__file__).resolve().parent)"],
    env=probe_env, text=True,
).strip())
child = r'''import inspect
import os
import run_agent
import sitecustomize as hades
from integrations.automation import LifecycleStore

owner = "synthetic-owner"
state_path = os.environ["HADES_EPSILON_STATE_FILE"]
identity = hades._hades_turn_identity
same_initial_prompt = "Run Backup Check."
if len(inspect.signature(identity).parameters) == 3:
    alpha = identity(same_initial_prompt, [], "synthetic-chat-alpha")
    beta = identity(same_initial_prompt, [], "synthetic-chat-beta")
    assert alpha != beta, "identical first prompts in separate server chats shared a confirmation key"
else:
    # Diagnostic compatibility: the legacy two-argument helper cannot
    # distinguish identical initial prompts because it has no server chat ID.
    alpha = identity(same_initial_prompt, [])
    beta = identity(same_initial_prompt, [])
    assert alpha == beta, "legacy prompt-derived identity unexpectedly changed"
history = [
    {"role": "user", "content": same_initial_prompt},
    {"role": "assistant", "content": "Shall I run the Backup Check?"},
]
store = LifecycleStore(state_path)
pending_key = f"session:{owner}:{alpha}"
store.pending_put(
    pending_key,
    owner,
    {"template_id": "hades-backup-verification", "action": "run"},
    4_000_000_000,
)
synthetic_dispatches = []
def synthetic_backup_response(text, actor, scope, conversation_id):
    normalized = str(text).strip().casefold()
    if normalized not in {"yes", "no", "no."}:
        return None
    pending = store.pending_take(pending_key, actor)
    if pending is None:
        return None
    synthetic_dispatches.append({"text": normalized, "actor": actor, "scope": scope})
    if normalized == "yes":
        return "SYNTHETIC_BACKUP_CHECK_EXECUTED"
    return "I declined the Backup Check; nothing was changed."

hades._hades_phase2_backup_response = synthetic_backup_response
kwargs = {
    "base_url": "http://127.0.0.1:9/v1",
    "api_key": "synthetic-only",
    "provider": "custom",
    "api_mode": "chat_completions",
    "model": "synthetic-no-call",
    "enabled_toolsets": [],
    "disabled_toolsets": [],
    "quiet_mode": True,
    "skip_context_files": True,
    "skip_memory": True,
    "skip_background_review": True,
    "load_soul_identity": False,
}
agent = run_agent.AIAgent(
    gateway_session_key=f"hades-user-{owner}",
    session_id="synthetic-chat-beta",
    stream_delta_callback=lambda _chunk: None,
    **kwargs,
)
assert agent._hades_subject == owner
result = agent.run_conversation(
    "yes",
    conversation_history=history,
)
assert result.get("completed") is True, result
assert result.get("api_calls") == 0, result
if os.environ.get("HADES_EXPECT_CROSS_CHAT_CONFIRMATION_BYPASS") == "1":
    assert result.get("final_response") == "SYNTHETIC_BACKUP_CHECK_EXECUTED", result
    assert store.pending_get(pending_key, owner) is None, "expected vulnerable artifact did not consume the synthetic pending action"
    assert len(synthetic_dispatches) == 1 and synthetic_dispatches[0]["text"] == "yes", synthetic_dispatches
    print("DETECTED expected cross-chat confirmation consume on the supplied overlay; synthetic stub only")
    raise SystemExit(0)
assert "couldn't match that confirmation" in result.get("final_response", "").casefold(), result
assert store.pending_get(pending_key, owner) is not None, "cross-chat confirmation consumed the other conversation's pending action"
missing_id = run_agent.AIAgent(
    gateway_session_key=f"hades-user-{owner}",
    session_id="",
    stream_delta_callback=lambda _chunk: None,
    **kwargs,
).run_conversation(
    "yes",
    conversation_history=[{"role": "assistant", "content": "Shall I run the Backup Check?"}],
)
assert missing_id.get("completed") is True and missing_id.get("api_calls") == 0, missing_id
assert "couldn't match that confirmation" in missing_id.get("final_response", "").casefold(), missing_id
assert store.pending_get(pending_key, owner) is not None, "missing conversation ID consumed the pending action"
same_chat = run_agent.AIAgent(
    gateway_session_key=f"hades-user-{owner}",
    session_id="synthetic-chat-alpha",
    stream_delta_callback=lambda _chunk: None,
    **kwargs,
).run_conversation(
    "No.",
    conversation_history=[{"role": "assistant", "content": "Shall I run the Backup Check?"}],
)
assert same_chat.get("completed") is True and same_chat.get("api_calls") == 0, same_chat
assert "nothing was changed" in same_chat.get("final_response", "").casefold(), same_chat
assert store.pending_get(pending_key, owner) is None, "same-chat decline did not clear the pending action"
print("PASS Hermes runtime rejects a same-user cross-chat confirmation without a model call or pending-state mutation")
print("PASS Hermes runtime rejects a confirmation without a server conversation ID and preserves pending state")
print("PASS Hermes runtime routes a same-chat decline without a model call and clears only that chat's pending action")
'''
with tempfile.TemporaryDirectory(prefix="hades-confirmation-runtime-") as tmp:
    root = Path(tmp)
    home = root / "home"
    hermes_home = root / "hermes"
    home.mkdir(mode=0o700)
    hermes_home.mkdir(mode=0o700)
    script = root / "probe.py"
    script.write_text(child, encoding="utf-8")
    env = {
        key: os.environ[key]
        for key in ("PATH", "LANG", "LC_ALL", "TZ")
        if key in os.environ
    }
    env.update({
        "HOME": str(home),
        "HERMES_HOME": str(hermes_home),
        "HADES_EPSILON_STATE_FILE": str(root / "epsilon.sqlite"),
        "PYTHONPATH": f"{overlay}:{repo}:{hermes_source}",
        "HADES_OWNER_SUBJECT_IDS": "synthetic-owner",
    })
    if os.environ.get("HADES_EXPECT_CROSS_CHAT_CONFIRMATION_BYPASS") == "1":
        env["HADES_EXPECT_CROSS_CHAT_CONFIRMATION_BYPASS"] = "1"
    result = subprocess.run(
        [str(interpreter), str(script)],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode:
        raise SystemExit("FAIL Hermes confirmation runtime contract\n" + result.stdout + result.stderr[-6000:])
    print(result.stdout.strip())
PY
