"""Authenticated HADES workspace routing onto Hermes' isolated terminal backend.

The workspace root and image reference are operator configuration. Neither a
model supplied path nor a browser supplied path may select a host mount.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any


_PINNED_IMAGE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:/-]*@sha256:[0-9a-f]{64}$"
)
_SUBJECT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_DIRECT_ACTION = re.compile(
    r"\b(?:read|open|show|inspect|review|edit|modify|change|write|create|patch|"
    r"delete|rename|move|format|lint|run|execute|test|debug|fix|repair|commit)\b"
    r".{0,90}\b(?:file|folder|directory|project|repo(?:sitory)?|code|script|"
    r"test|bug|function|class|workspace|branch|diff|config(?:uration)?|settings?|manifest)\b|"
    r"\b(?:file|folder|directory|project|repo(?:sitory)?|code|script|test|"
    r"bug|function|class|workspace|branch|diff|config(?:uration)?|settings?|manifest)\b.{0,90}\b"
    r"(?:read|open|show|inspect|review|edit|modify|change|write|create|patch|"
    r"delete|rename|move|format|lint|run|execute|test|debug|fix|repair|commit)\b",
    re.IGNORECASE,
)
_CODE_EXPLANATION = re.compile(
    r"\b(?:explain|describe|summari[sz]e|what\s+does|what\s+is|how\s+does|"
    r"how\s+is|why\s+does|why\s+is|where\s+is)\b[^.!?\n]{0,80}\b"
    r"(?:file|code|function|class|script|test|bug|error|traceback|exception|"
    r"project|repo(?:sitory)?|config(?:uration)?|settings?|manifest)\b|"
    r"\b(?:file|code|function|class|script|test|bug|error|traceback|exception|"
    r"project|repo(?:sitory)?|config(?:uration)?|settings?|manifest)\b[^.!?\n]{0,80}\b"
    r"(?:explain|describe|summari[sz]e|what\s+does|what\s+is|how\s+does|"
    r"how\s+is|why\s+does|why\s+is|where\s+is)\b",
    re.IGNORECASE,
)
_CODE_FAILURE_DIAGNOSIS = re.compile(
    r"\b(?:why\s+(?:is|does)|what\s+(?:is|caused|causes)|diagnos[ei])\b"
    r"[^.!?\n]{0,100}\b(?:python|javascript|typescript|code|file|function|class|"
    r"script|test|bug|error|traceback|exception|repo(?:sitory)?)\b[^.!?\n]{0,60}"
    r"\b(?:fail(?:s|ed|ing)?|break(?:s|ing)?|error|exception|wrong|crash(?:es|ed)?)\b|"
    r"\b(?:python|javascript|typescript|code|file|function|class|script|test|"
    r"bug|error|traceback|exception|repo(?:sitory)?)\b[^.!?\n]{0,100}"
    r"\b(?:fail(?:s|ed|ing)?|break(?:s|ing)?|error|exception|wrong|crash(?:es|ed)?)\b",
    re.IGNORECASE,
)
_PATH = re.compile(
    r"(?:^|\s)(?:\.?\.?/)?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\.(?:py|js|ts|tsx|jsx|go|rs|java|c|cc|cpp|h|hpp|sh|bash|toml|yaml|yml|json|md|txt|sql|html|css)(?=$|[\s?!.,])",
    re.IGNORECASE,
)
_FOLLOW_UP = re.compile(
    r"^\s*(?:fix it|do it|go ahead|try that|make that change|change it|"
    r"edit it|run it|test it|commit it|continue|keep going|do that instead)\s*[.!?]*\s*$",
    re.IGNORECASE,
)
_PRIOR_WORK = re.compile(
    r"\b(?:file|repo(?:sitory)?|workspace|code|python|javascript|typescript|"
    r"traceback|stack trace|test(?:s)?|failing|failure|bug|error|exception|"
    r"compile|build|lint|git diff|branch|commit)\b|"
    r"\b[A-Za-z0-9_.-]+\.(?:py|js|ts|tsx|jsx|go|rs|java|c|cc|cpp|h|hpp|sh|toml|yaml|yml|json|md|sql)\b",
    re.IGNORECASE,
)

WORKSPACE_TOOL_NAMES = frozenset({
    "read_file", "search_files", "write_file", "patch", "terminal",
})


def workspace_enabled() -> bool:
    """Require a deliberate deployment opt-in before exposing workspace tools."""
    return os.environ.get("HADES_WORKSPACE_ENABLED", "false").strip().lower() == "true"


def is_workspace_request(user_message: str, history: list[dict[str, Any]] | None = None) -> bool:
    """Recognize explicit file/code actions and terse continuations of them."""
    text = str(user_message or "")
    if _DIRECT_ACTION.search(text) or _PATH.search(text.strip()):
        return True
    # Code questions often need the model to ask for a missing snippet or
    # traceback. When workspace capability is disabled, keep those turns on
    # the model path instead of returning a canned workspace refusal.
    if workspace_enabled() and (
        _CODE_EXPLANATION.search(text) or _CODE_FAILURE_DIAGNOSIS.search(text)
    ):
        return True
    if not _FOLLOW_UP.fullmatch(text):
        return False
    recent = history[-6:] if isinstance(history, list) else []
    return any(
        isinstance(message, dict)
        and str(message.get("role", "")) in {"user", "assistant", "tool"}
        and _PRIOR_WORK.search(str(message.get("content", "")))
        for message in recent
    )


def _is_real_directory(path: Path, *, private: bool) -> bool:
    """Require every existing path component to be a real directory, not a symlink."""
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        try:
            info = current.lstat()
        except OSError:
            return False
        if stat.S_ISLNK(info.st_mode):
            return False
        if current != path and not stat.S_ISDIR(info.st_mode):
            return False
    try:
        info = path.lstat()
    except OSError:
        return False
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
        return False
    return not private or (stat.S_IMODE(info.st_mode) & 0o077) == 0


def resolve_workspace(subject: str, root_value: str | None = None) -> Path | None:
    """Resolve/create one private per-subject workspace beneath a trusted root."""
    if not isinstance(subject, str) or not _SUBJECT.fullmatch(subject):
        return None
    raw_root = str(root_value if root_value is not None else os.environ.get("HADES_WORKSPACE_ROOT", "")).strip()
    raw_home = os.environ.get("HERMES_HOME", "").strip()
    if not raw_home or not Path(raw_home).is_absolute():
        return None
    profile_home = Path(raw_home)
    if not _is_real_directory(profile_home, private=True):
        return None
    if raw_root:
        if not Path(raw_root).is_absolute():
            return None
        root = Path(raw_root)
        try:
            relative = root.relative_to(profile_home)
        except ValueError:
            return None
        if not relative.parts or ".." in relative.parts:
            return None
        if not _is_real_directory(root, private=True):
            return None
    else:
        root = profile_home / "workspaces"
        try:
            root.mkdir(mode=0o700, exist_ok=True)
        except OSError:
            return None
        if not _is_real_directory(root, private=True):
            return None
    workspace = root / subject
    try:
        workspace.mkdir(mode=0o700, exist_ok=True)
    except OSError:
        return None
    if not _is_real_directory(workspace, private=True):
        return None
    return workspace


def pinned_image_available(image: str | None = None) -> bool:
    """Return true only for an installed immutable image; never pull at request time."""
    value = str(image if image is not None else os.environ.get("HADES_HERMES_SANDBOX_IMAGE", "")).strip()
    binary = _container_runtime_binary()
    if not binary or not _PINNED_IMAGE.fullmatch(value):
        return False
    try:
        result = subprocess.run(
            [binary, "image", "inspect", "--format", "{{.Id}}", value],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def _container_runtime_binary() -> str | None:
    override = os.environ.get("HERMES_DOCKER_BINARY", "").strip()
    if override:
        candidate = shutil.which(override) if os.sep not in override else override
        return candidate if candidate and os.path.isfile(candidate) else None
    return shutil.which("podman") or shutil.which("docker")


def sandbox_runtime_available() -> bool:
    """Require a verified rootless container engine before allowing host mounts."""
    binary = _container_runtime_binary()
    if not binary:
        return False
    name = Path(binary).name.lower()
    try:
        if "podman" in name:
            result = subprocess.run(
                [binary, "info", "--format", "{{.Host.Security.Rootless}}"],
                capture_output=True, text=True, timeout=3, check=False,
            )
            return result.returncode == 0 and result.stdout.strip().lower() == "true"
        result = subprocess.run(
            [binary, "info", "--format", "{{json .SecurityOptions}}"],
            capture_output=True, text=True, timeout=3, check=False,
        )
        if result.returncode != 0:
            return False
        import json

        options = json.loads(result.stdout)
        return isinstance(options, list) and any(
            "rootless" in str(option).lower() for option in options
        )
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return False


def get_workspace_tools() -> list[dict[str, Any]]:
    """Load Hermes' native file/shell tools, excluding deferred discovery bridges."""
    from model_tools import get_tool_definitions

    definitions = get_tool_definitions(
        enabled_toolsets=["file", "terminal"],
        quiet_mode=True,
    )
    selected = [
        item for item in definitions
        if item.get("function", {}).get("name") in WORKSPACE_TOOL_NAMES
    ]
    names = {item.get("function", {}).get("name") for item in selected}
    if names != WORKSPACE_TOOL_NAMES:
        raise RuntimeError("Hermes native workspace tool catalog is incomplete")
    return selected


def terminal_policy(workspace: Path, image: str) -> dict[str, str]:
    """Complete minimum terminal scope for a single isolated workspace turn."""
    return {
        "TERMINAL_ENV": "docker",
        "TERMINAL_CWD": str(workspace),
        "TERMINAL_DOCKER_IMAGE": image,
        "TERMINAL_DOCKER_MOUNT_CWD_TO_WORKSPACE": "true",
        "TERMINAL_CONTAINER_PERSISTENT": "false",
        "TERMINAL_DOCKER_PERSIST_ACROSS_PROCESSES": "false",
        "TERMINAL_DOCKER_NETWORK": "false",
        "TERMINAL_DOCKER_FORWARD_ENV": "[]",
        "TERMINAL_DOCKER_VOLUMES": "[]",
        "TERMINAL_DOCKER_EXTRA_ARGS": "[]",
        "TERMINAL_DOCKER_ORPHAN_REAPER": "false",
        "TERMINAL_CONTAINER_CPU": "2",
        "TERMINAL_CONTAINER_MEMORY": "8192",
    }


def register_workspace_session(task_id: str, workspace: Path, image: str) -> bool:
    """Bind Hermes file and terminal tools to this chat's authenticated workspace."""
    if not isinstance(task_id, str) or not task_id or len(task_id) > 255:
        return False
    try:
        from tools.terminal_tool import register_task_env_overrides

        register_task_env_overrides(task_id, {
            "cwd": str(workspace),
            "cwd_source": "session",
            "env_type": "docker",
            "docker_image": image,
        })
    except Exception:
        return False
    return True


def clear_workspace_session(task_id: str) -> None:
    """Remove per-turn workspace task metadata after model work completes."""
    try:
        from tools.terminal_tool import clear_task_env_overrides

        clear_task_env_overrides(task_id)
    except Exception:
        pass


def has_workspace_tool_result(messages: Any) -> bool:
    """Require a returned native workspace-tool result before claiming action."""
    if not isinstance(messages, list):
        return False
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "tool":
            continue
        name = str(message.get("name") or message.get("tool_name") or "")
        if name not in WORKSPACE_TOOL_NAMES:
            continue
        content = message.get("content")
        if isinstance(content, list):
            content = " ".join(
                str(part.get("text", "")) if isinstance(part, dict) else str(part)
                for part in content
            )
        body = str(content or "").strip()
        if not body:
            continue
        try:
            import json

            payload = json.loads(body)
        except Exception:
            payload = None
        if isinstance(payload, dict):
            status = str(payload.get("status") or "").lower()
            if status in {"error", "failed", "failure"} or payload.get("error"):
                continue
            if payload.get("returncode") not in (None, 0):
                continue
            if payload.get("success") is False:
                continue
        elif re.search(r"\b(?:tool call failed|permission denied|file not found|no such file or directory)\b", body, re.IGNORECASE):
            continue
        return True
    return False
