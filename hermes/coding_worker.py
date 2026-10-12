"""Host-side launcher for one isolated native Hermes coding conversation."""

from __future__ import annotations

import json
import importlib.util
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import fields
from pathlib import Path
from typing import Any

from hermes.coding_workspace_pool import resolve_session_workspace
from hermes.coding_evidence_store import (
    clear_test_evidence,
    load_test_evidence,
    store_test_evidence,
)
from hermes.workspace_contract import (
    CommitInvocation,
    HermesTerminalResult,
    TestEvidence,
    WorkspaceBinding,
    WorkspaceDenied,
    WorkspaceEvidenceError,
    _path_fingerprint,
    snapshot_repository,
    verify_commit,
    workspace_lease,
)
from hermes.workspace_sandbox import run_isolated_workspace


RESULT_PREFIX = "HADES_CODING_RESULT="
_LOGGER = logging.getLogger("hades.coding_worker")


def _coding_trace_summary(worker_result: dict[str, Any]) -> dict[str, Any]:
    """Reduce a server-generated tool trace to content-free latency counters."""
    trace = worker_result.get("tool_trace")
    rows = [row for row in trace if isinstance(row, dict)] if isinstance(trace, list) else []
    names = [row.get("tool_name") for row in rows]
    file_names = {"read_file", "read_many_files", "search_files", "list_directory"}
    edit_names = {"patch", "write_file", "create_file", "edit_file"}

    def first_start(predicate) -> int | None:
        return next(
            (row["start_ms"] for row in rows
             if isinstance(row.get("start_ms"), int) and predicate(row)),
            None,
        )

    fingerprints = [
        row.get("fingerprint") for row in rows
        if row.get("kind") == "discovery"
        and isinstance(row.get("fingerprint"), str)
        and re.fullmatch(r"[a-f0-9]{64}", row["fingerprint"])
    ]
    return {
        "tool_calls": len(rows),
        "first_tool_ms": first_start(lambda _row: True),
        "first_file_ms": first_start(lambda row: row.get("tool_name") in file_names),
        "first_edit_ms": first_start(lambda row: row.get("tool_name") in edit_names),
        "first_test_ms": first_start(lambda row: row.get("kind") == "test"),
        "test_calls": sum(row.get("kind") == "test" for row in rows),
        "test_ms": sum(
            row["elapsed_ms"] for row in rows
            if row.get("kind") == "test" and isinstance(row.get("elapsed_ms"), int)
        ),
        "tool_ms": sum(
            row["elapsed_ms"] for row in rows if isinstance(row.get("elapsed_ms"), int)
        ),
        "duplicate_discovery_calls": len(fingerprints) - len(set(fingerprints)),
    }


def _relay_metrics_summary(path: Path | None) -> dict[str, int]:
    """Reduce the private relay file to bounded counts and durations."""
    rows: list[dict[str, Any]] = []
    if path is not None:
        try:
            with path.open("r", encoding="utf-8") as stream:
                for line in stream:
                    if len(rows) >= 128 or len(line) > 1024:
                        break
                    row = json.loads(line)
                    if (isinstance(row, dict)
                            and isinstance(row.get("elapsed_ms"), int)
                            and not isinstance(row.get("elapsed_ms"), bool)
                            and 0 <= row["elapsed_ms"] <= 600_000
                            and isinstance(row.get("status"), int)
                            and not isinstance(row.get("status"), bool)):
                        rows.append(row)
        except (OSError, UnicodeError, ValueError):
            rows = []
    durations = [row["elapsed_ms"] for row in rows]
    return {
        "model_calls": len(rows),
        "model_ms": sum(durations),
        "model_max_ms": max(durations, default=0),
        "model_failures": sum(row["status"] < 200 or row["status"] >= 300 for row in rows),
    }


def _attach_worker_diagnostics(
    result: dict[str, Any], *, task_id: str, started_at: float
) -> dict[str, Any]:
    """Attach content-free per-turn diagnostics; emit them only when opted in."""
    result["task_id"] = task_id
    result["elapsed_ms"] = max(0, int((time.perf_counter() - started_at) * 1000))
    raw_trace = result.pop("tool_trace", None)
    raw_relay_metrics = result.pop("model_metrics", None)
    relay_metrics = {
        key: raw_relay_metrics.get(key, 0) if isinstance(raw_relay_metrics, dict) else 0
        for key in ("model_calls", "model_ms", "model_max_ms", "model_failures")
    }
    raw_names = result.get("tool_call_names")
    names = [
        name for name in raw_names[:128]
        if isinstance(name, str)
        and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", name)
    ] if isinstance(raw_names, list) else []
    if os.environ.get("HADES_CODING_WORKER_DIAGNOSTICS", "").strip() == "1":
        trace = _coding_trace_summary({"tool_trace": raw_trace})
        _LOGGER.info(
            "coding worker trace task=%s elapsed_ms=%d first_tool_ms=%s "
            "first_file_ms=%s first_edit_ms=%s first_test_ms=%s test_calls=%d "
            "test_ms=%d tool_ms=%d duplicate_discovery_calls=%d tool_calls=%d tools=%s "
            "model_calls=%d model_ms=%d model_max_ms=%d model_failures=%d",
            task_id,
            result["elapsed_ms"],
            trace["first_tool_ms"],
            trace["first_file_ms"],
            trace["first_edit_ms"],
            trace["first_test_ms"],
            trace["test_calls"],
            trace["test_ms"],
            trace["tool_ms"],
            trace["duplicate_discovery_calls"],
            trace["tool_calls"] or len(names),
            ",".join(names),
            relay_metrics["model_calls"],
            relay_metrics["model_ms"],
            relay_metrics["model_max_ms"],
            relay_metrics["model_failures"],
        )
    return result


class CodingWorkerError(RuntimeError):
    """The isolated coding execution was not proven complete."""


def _validate_worker_result_identity(
    worker_result: Any,
    *,
    subject: str,
    session_id: str,
    task_id: str,
    turn_id: str,
) -> dict[str, Any]:
    """Validate the HADES-generated identities bound to this worker turn.

    Hermes' optional result turn ID is not an authority or evidence source;
    HADES task/session/turn IDs and terminal call records bind the execution.
    """
    if not isinstance(worker_result, dict) or worker_result.get("subject") != subject:
        raise CodingWorkerError(
            "isolated Hermes worker identity did not match the authenticated owner"
        )
    if any(worker_result.get(key) != expected for key, expected in (
        ("session_id", session_id), ("task_id", task_id), ("turn_id", turn_id),
    )):
        raise CodingWorkerError(
            "isolated Hermes worker task identity did not match the server request"
        )
    return worker_result


_CODING_OBJECT = re.compile(
    r"\b(?:repo(?:sitory)?|project|workspace|file|tests?|code|bug|function|script|"
    r"patch|diff|commit|command|python|javascript|typescript|rust|go)\b",
    re.IGNORECASE,
)
_CODING_ACTION = re.compile(
    r"\b(?:inspect|explain|fix|edit|change|write|run|test|debug|commit|revert|"
    r"continue|show|review|check|make)\b",
    re.IGNORECASE,
)
_CODING_CONTINUATION = re.compile(
    r"\b(?:continue|retry|try\s+again|check\s+(?:whether|if)|revert|show\s+me\s+what\s+changed)\b",
    re.IGNORECASE,
)
_CODING_EDIT_REQUEST = re.compile(
    r"^\s*(?:(?:please|now|go\s+ahead\s+and)\s+)?"
    r"(?:fix|edit|change|modify|write|add|remove|delete|create|implement|revert|undo)\b"
    r"|\b(?:make|apply)\s+(?:the\s+)?(?:change|fix|patch)\b"
    r"|^\s*(?:(?:please|now)\s+){0,2}make\s+(?:a|an|the)\s+(?:(?:small|minor|partial|incomplete|deliberate(?:ly)?|wrong|first|plausible|temporary)\s+)*(?:change|correction|edit|patch)\b"
    r"|\b(?:can|could|would|will|need|want)\s+you\s+(?:to\s+)?(?:please\s+)?"
    r"(?:fix|edit|change|modify|write|add|remove|delete|create|implement|revert|undo)\b",
    re.IGNORECASE,
)
_CODING_TEST_REQUEST = re.compile(
    r"\b(?:run|rerun|execute)\b.{0,80}\btests?\b"
    r"|\btest\s+(?:it|this|the\s+(?:change|fix|code))\b",
    re.IGNORECASE,
)
_CODING_READ_ONLY_REQUEST = re.compile(
    r"^\s*(?:(?:please|just)\s+)?(?:inspect|explain|show|review|check|analyze|summarize)\b",
    re.IGNORECASE,
)
_CODING_SENSITIVE_DOMAIN = re.compile(
    r"\b(?:memory|remember|recall|forget|grocy|grocery|groceries|recipe|"
    r"ingredient|pantry|kitchen|stock|homelab|network|proxmox|netbox|"
    r"finance|bank|transaction|spending|budget|credit\s+card|web\s+search)\b",
    re.IGNORECASE,
)


def coding_worker_conversation_allowed(
    *, scope: str, conversation_id: str, prompt: str, environ: Any = None,
) -> bool:
    """Apply the temporary server-side dogfood allowlist and domain boundary."""
    environment = os.environ if environ is None else environ
    allowed_conversation = str(
        environment.get("HADES_CODING_WORKER_CONVERSATION_ID", "") or ""
    ).strip()
    return bool(
        environment.get("HADES_CODING_WORKER_ENABLED", "").strip() == "1"
        and scope == "owner"
        and allowed_conversation
        and conversation_id == allowed_conversation
        and isinstance(prompt, str)
        and not _CODING_SENSITIVE_DOMAIN.search(prompt)
    )


def should_route_to_coding_worker(prompt: str, history: Any = None) -> bool:
    """Recognize workspace coding tasks and clear follow-ups without noun capture."""
    if not isinstance(prompt, str) or not prompt.strip():
        return False
    current = prompt[:16_000]
    if _CODING_OBJECT.search(current) and _CODING_ACTION.search(current):
        return True
    if not _CODING_CONTINUATION.search(current) or not isinstance(history, list):
        return False
    recent = " ".join(
        str(row.get("content") or "")[:4000]
        for row in history[-12:]
        if isinstance(row, dict) and row.get("role") in {"user", "assistant"}
    )
    return bool(_CODING_OBJECT.search(recent) and _CODING_ACTION.search(recent))


def _dataclass(type_: type, raw: Any, binding: WorkspaceBinding):
    if not isinstance(raw, dict):
        return None
    values = dict(raw)
    for field in fields(type_):
        if field.name in {"workspace", "repository"}:
            values[field.name] = binding.root if field.name == "workspace" else binding.repository
        elif field.name in {"paths", "expected_paths"}:
            values[field.name] = frozenset(values.get(field.name) or ())
        elif field.name == "status_entries":
            values[field.name] = frozenset(tuple(item) for item in values.get(field.name) or ())
    try:
        return type_(**values)
    except (TypeError, ValueError):
        return None


def _model_relay_socket(
    relay_script: Path, temp_root: Path, upstream: str, model: str,
    metrics_file: Path | None = None,
) -> tuple[subprocess.Popen, Path]:
    socket_dir = temp_root / "relay"
    socket_dir.mkdir(mode=0o700)
    socket_path = socket_dir / "model.sock"
    command = [sys.executable, str(relay_script), "--socket", str(socket_path),
               "--upstream", upstream, "--model", model]
    if metrics_file is not None:
        command.extend(("--metrics-file", str(metrics_file)))
    relay = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True, close_fds=True,
    )
    for _ in range(50):
        if socket_path.is_socket():
            return relay, socket_path
        if relay.poll() is not None:
            raise CodingWorkerError("bounded inference relay failed to start")
        time.sleep(0.1)
    relay.terminate()
    try:
        relay.wait(timeout=3)
    except subprocess.TimeoutExpired:
        relay.kill()
        relay.wait(timeout=3)
    raise CodingWorkerError("bounded inference relay did not become ready")


def _stop_process(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def _explicit_commit(text: str) -> bool:
    import re
    # A nearby positive verb such as “make the change” must not override an
    # explicit current-turn instruction to defer or avoid committing.
    if re.search(
        r"\b(?:do\s+not|don't|dont|never|no)\s+commit\b|"
        r"\bwithout\s+committing\b|\bhold\s+off\s+(?:on\s+)?committing\b|"
        r"\bwait\s+to\s+commit\b",
        text,
        re.IGNORECASE,
    ):
        return False
    return bool(re.search(
        r"^\s*(?:please\s+)?commit\s+only\s+(?:the\s+)?[\w./-]+(?:\s+now)?(?=\s*(?:[.!?]|[,;]|$))|"
        r"(?:^\s*|[,;]\s*(?:and\s+)?|\bthen\s+)(?:please\s+)?commit\s+only\s+(?:the\s+)?[\w./-]+\s+(?:once|after|when|if)\b|"
        r"\b(?:commit\s+(?:the\s+)?(?:fix|change|result|work)|"
        r"make\b.{0,120}\bcommit\b|commit\s+it|please\s+commit|"
        r"commit\s+this)\b",
        text,
        re.IGNORECASE | re.DOTALL,
    ))


def _workspace_mutation_authorized(prompt: str, history: list[dict[str, str]]) -> bool:
    """Authorize workspace writes only for current edit/test intent or its continuation."""
    if _CODING_EDIT_REQUEST.search(prompt) or _CODING_TEST_REQUEST.search(prompt):
        return True
    # A read-only request such as "show me the diff" remains read-only even
    # when it follows an edit in this conversation.  Context continuity must
    # not silently grant the current turn a writable mount.
    if _CODING_READ_ONLY_REQUEST.search(prompt):
        return False
    if not _CODING_CONTINUATION.search(prompt):
        return False
    previous_user_request = next(
        (row["content"] for row in reversed(history) if row.get("role") == "user"),
        "",
    )
    return bool(
        _CODING_EDIT_REQUEST.search(previous_user_request)
        or _CODING_TEST_REQUEST.search(previous_user_request)
    )


def run_coding_worker(
    *,
    subject: str,
    scope: str,
    conversation_id: str,
    prompt: str,
    history: Any,
    model: str,
    upstream: str,
    repo_root: str | Path,
    hermes_root: str | Path,
    bindings_file: str | Path,
    workspace_root: str | Path,
    forbidden_roots: tuple[str | Path, ...] = (),
    timeout: int = 600,
) -> dict[str, Any]:
    """Run a single turn with trusted workspace selection and host verification."""
    started_at = time.perf_counter()
    diagnostics_enabled = os.environ.get("HADES_CODING_WORKER_DIAGNOSTICS", "").strip() == "1"
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 16_000:
        raise WorkspaceDenied("coding request is missing or exceeds the bounded turn size")
    if not isinstance(history, list) or len(history) > 64:
        history = []
    history = [
        {"role": row["role"], "content": row["content"][:8000]}
        for row in history[-16:]
        if isinstance(row, dict)
        and row.get("role") in {"user", "assistant"}
        and isinstance(row.get("content"), str)
        and row["content"].strip()
    ]
    if not isinstance(model, str) or not model.strip() or len(model) > 256:
        raise CodingWorkerError("approved coding model is unavailable")
    if not isinstance(timeout, int) or timeout < 1 or timeout > 600:
        raise ValueError("coding worker timeout is outside the supported range")

    repo_root = Path(repo_root).resolve(strict=True)
    hermes_root = Path(hermes_root).resolve(strict=True)
    hermes_source = hermes_root / "source"
    python = hermes_root / "venv" / "bin" / "python"
    relay_script = repo_root / "scripts" / "model_inference_relay.py"
    driver_script = repo_root / "scripts" / "hades_coding_worker_driver.py"
    contract_source = repo_root / "hermes" / "workspace_contract.py"
    required = (hermes_source / "run_agent.py", python, relay_script, driver_script, contract_source)
    if any(not path.exists() for path in required):
        raise CodingWorkerError("qualified Hermes coding runtime files are unavailable")
    if not (hermes_source / "run_agent.py").is_file() or not python.is_file():
        raise CodingWorkerError("Hermes runtime identity is incomplete")
    if repo_root == Path("/") or hermes_root.is_relative_to(repo_root):
        raise CodingWorkerError("HADES source and Hermes runtime mounts overlap")
    relay_spec = importlib.util.spec_from_file_location(
        "hades_coding_relay_policy", relay_script,
    )
    if relay_spec is None or relay_spec.loader is None:
        raise CodingWorkerError("approved inference relay policy is unavailable")
    relay_policy = importlib.util.module_from_spec(relay_spec)
    relay_spec.loader.exec_module(relay_policy)
    relay_policy.parse_upstream(upstream)

    binding = resolve_session_workspace(
        subject=subject,
        scope=scope,
        conversation_id=conversation_id,
        bindings_file=bindings_file,
        workspace_root=workspace_root,
        forbidden_roots=tuple(forbidden_roots),
    )
    commit_authorized = _explicit_commit(prompt)
    workspace_mutation_authorized = _workspace_mutation_authorized(prompt, history)
    session_id = conversation_id
    task_id = uuid.uuid4().hex
    turn_id = uuid.uuid4().hex

    with workspace_lease(binding):
        before = snapshot_repository(
            binding, task_id=task_id, session_id=session_id, turn_id=turn_id,
        )
        try:
            cached_test_evidence = load_test_evidence(binding, session_id)
        except (OSError, WorkspaceEvidenceError):
            cached_test_evidence = None
        relay_metrics: dict[str, int] = {
            "model_calls": 0, "model_ms": 0, "model_max_ms": 0, "model_failures": 0,
        }
        with tempfile.TemporaryDirectory(prefix="hades-coding-run-") as temp_name:
            temp_root = Path(temp_name)
            support = temp_root / "support"
            support.mkdir(mode=0o700)
            driver = support / "hades_coding_worker_driver.py"
            contract = support / "workspace_contract.py"
            shutil.copyfile(driver_script, driver)
            shutil.copyfile(contract_source, contract)
            config = support / "worker.json"
            config.write_text(json.dumps({
                "model": model,
                "hermes_source": str(hermes_source),
                "subject": subject,
                "session_id": session_id,
                "task_id": task_id,
                "turn_id": turn_id,
                "commit_authorized": commit_authorized,
                "diagnostics_enabled": diagnostics_enabled,
                "prompt": prompt,
                "history": history,
            }, separators=(",", ":")), encoding="utf-8")
            config.chmod(0o400)
            driver.chmod(0o500)
            contract.chmod(0o400)
            relay_metrics_file = temp_root / "relay" / "metrics.jsonl" if diagnostics_enabled else None
            relay, socket_path = _model_relay_socket(
                relay_script, temp_root, upstream, model, relay_metrics_file,
            )
            try:
                try:
                    execution = run_isolated_workspace(
                        binding.repository,
                        [str(python), str(driver), str(config)],
                        timeout=timeout,
                        read_only_paths=(hermes_root, support),
                        unix_socket=socket_path,
                        enable_loopback=True,
                        writable_git_metadata=commit_authorized,
                        workspace_read_only=not workspace_mutation_authorized,
                    )
                except Exception as exc:
                    after = snapshot_repository(
                        binding, task_id=task_id, session_id=session_id, turn_id=turn_id,
                    )
                    changed_paths = sorted(path for _, path in after.status_entries)
                    changed = before.head != after.head or before.status_entries != after.status_entries
                    return _attach_worker_diagnostics({
                        "outcome": "VERIFY" if changed else "FAILED",
                        "reason": "isolated worker did not complete; canonical state was reconciled",
                        "final_response": (
                            "The isolated coding worker did not finish. "
                            f"Current state is on {after.branch} at {after.head[:12]}; "
                            f"changed paths: {', '.join(changed_paths) if changed_paths else 'none'}."
                        ),
                        "head_before": before.head,
                        "head_after": after.head,
                        "branch": after.branch,
                        "changed_paths": changed_paths,
                        "mutated": changed,
                        "failure_type": type(exc).__name__,
                    }, task_id=task_id, started_at=started_at)
            finally:
                _stop_process(relay)
                relay_metrics = _relay_metrics_summary(relay_metrics_file)

        after = snapshot_repository(
            binding, task_id=task_id, session_id=session_id, turn_id=turn_id,
        )
        lines = [line for line in execution.stdout.splitlines() if line.startswith(RESULT_PREFIX)]
        if not lines:
            if before.head != after.head:
                return {
                    "outcome": "VERIFY",
                    "reason": "worker ended without a result record after repository state changed",
                    "head": after.head,
                    "branch": after.branch,
                    "changed_paths": sorted(path for _, path in after.status_entries),
                    "mutated": True,
                }
            raise CodingWorkerError("isolated Hermes worker did not return a completion record")
        try:
            worker_result = json.loads(lines[-1][len(RESULT_PREFIX):])
        except (ValueError, TypeError) as exc:
            raise CodingWorkerError("isolated Hermes worker result was malformed") from exc
        worker_result = _validate_worker_result_identity(
            worker_result,
            subject=subject,
            session_id=session_id,
            task_id=task_id,
            turn_id=turn_id,
        )
        if worker_result.get("completed") is not True:
            if before.head != after.head or before.status_entries != after.status_entries:
                return {
                    "outcome": "VERIFY",
                    "reason": "Hermes ended without a completed result after repository state changed",
                    "head_before": before.head,
                    "head_after": after.head,
                    "branch": after.branch,
                    "changed_paths": sorted(path for _, path in after.status_entries),
                    "mutated": True,
                }
            raise CodingWorkerError("Hermes coding turn did not complete")

        records = worker_result.get("tool_records")
        if not isinstance(records, dict):
            records = {}
        test_evidence = None
        current_turn_test_evidence = None
        current_test_attempted = False
        commit_invocation = None
        commit_result = None
        for record in records.values():
            if not isinstance(record, dict):
                continue
            if (record.get("event_task_id") != task_id
                    or record.get("event_session_id") != session_id
                    or not record.get("event_tool_call_id")):
                continue
            if record.get("test_invocation") or record.get("test_evidence_error"):
                current_test_attempted = True
            raw_operation = record.get("terminal_result")
            raw_evidence = record.get("test_evidence")
            evidence = _dataclass(TestEvidence, raw_evidence, binding)
            if evidence is not None and evidence.passed:
                test_evidence = evidence
                current_turn_test_evidence = evidence
            raw_commit = record.get("commit_invocation")
            if raw_commit:
                commit_invocation = _dataclass(CommitInvocation, raw_commit, binding)
                commit_result = _dataclass(HermesTerminalResult, raw_operation, binding)

        if (
            commit_invocation is not None
            and test_evidence is None
            and not current_test_attempted
        ):
            test_evidence = cached_test_evidence

        verification = verify_commit(
            binding,
            invocation=commit_invocation,
            after=after,
            test_evidence=test_evidence,
            operation=commit_result,
            commit_requested=commit_authorized,
        )
        changed_paths = sorted(path for _, path in after.status_entries)
        answer = str(worker_result.get("final_response") or "").strip()
        tests_requested = bool(re.search(
            r"\b(?:run|rerun|execute)\b.{0,80}\btests?\b|\btest\s+it\b",
            prompt,
            re.IGNORECASE,
        ))
        if test_evidence is not None and commit_invocation is None:
            try:
                test_verified = (
                    test_evidence.subject == subject
                    and test_evidence.workspace == binding.root
                    and test_evidence.repository == binding.repository
                    and test_evidence.task_id == task_id
                    and test_evidence.session_id == session_id
                    and test_evidence.turn_id == turn_id
                    and test_evidence.head == after.head
                    and test_evidence.branch == after.branch
                    and _path_fingerprint(binding.repository, test_evidence.paths)
                    == test_evidence.source_fingerprint
                )
            except WorkspaceEvidenceError:
                test_verified = False
        elif test_evidence is not None and commit_invocation is not None:
            try:
                tested_revision = after.head if after.head != commit_invocation.head else None
                test_verified = (
                    test_evidence.passed
                    and test_evidence.subject == subject
                    and test_evidence.workspace == binding.root
                    and test_evidence.repository == binding.repository
                    and test_evidence.session_id == session_id
                    and test_evidence.branch == commit_invocation.branch
                    and test_evidence.head == commit_invocation.head
                    and commit_invocation.expected_paths.issubset(test_evidence.paths)
                    and set(test_evidence.path_fingerprints) == set(test_evidence.paths)
                    and all(
                        test_evidence.path_fingerprints.get(path)
                        == _path_fingerprint(binding.repository, frozenset({path}), tested_revision)
                        for path in commit_invocation.expected_paths
                    )
                )
            except WorkspaceEvidenceError:
                test_verified = False
        else:
            test_verified = False

        head_changed = before.head != after.head
        try:
            if head_changed or (current_test_attempted and current_turn_test_evidence is None):
                clear_test_evidence(binding, session_id)
            if (
                current_turn_test_evidence is not None
                and test_verified
                and not (commit_authorized and verification.outcome == "SUCCEEDED")
            ):
                store_test_evidence(binding, session_id, current_turn_test_evidence)
            if commit_authorized and verification.outcome == "SUCCEEDED":
                clear_test_evidence(binding, session_id)
        except (OSError, WorkspaceEvidenceError):
            # Persistence improves cross-turn continuity, but never substitutes
            # for the current operation's canonical Git post-condition checks.
            pass
        if commit_authorized and verification.outcome != "SUCCEEDED":
            answer = (
                "I could not verify the requested commit, so I won't report it as complete. "
                f"Current Git state is on branch {after.branch} at {after.head[:12]}; "
                f"verification: {verification.outcome} ({verification.reason})."
            )
        elif commit_authorized:
            answer = (
                (answer + "\n\n" if answer else "")
                + f"Verified commit {verification.after_head[:12]} on {after.branch}; "
                + f"committed paths: {', '.join(sorted(verification.committed_paths))}."
            )
        elif tests_requested and not test_verified:
            answer = (
                "I could not independently verify a passing test run against the current workspace "
                f"state. The workspace remains on {after.branch} at {after.head[:12]}; "
                f"changed paths: {', '.join(changed_paths) if changed_paths else 'none'}."
            )
        elif not commit_authorized and before.head != after.head:
            answer = (
                "The workspace Git history changed even though this request did not explicitly "
                "authorize a commit. I will not report the task as complete; the current HEAD is "
                f"{after.head[:12]} on {after.branch}."
            )
        elif not answer:
            answer = "The isolated coding worker returned no final answer."
        outcome = "SUCCEEDED" if worker_result.get("completed") and execution.returncode == 0 else "FAILED"
        if (commit_authorized and verification.outcome != "SUCCEEDED") or (tests_requested and not test_verified):
            outcome = "FAILED"
        if outcome == "FAILED" and not (
            (commit_authorized and verification.outcome != "SUCCEEDED")
            or (tests_requested and not test_verified)
        ):
            answer = (
                "The isolated Hermes turn did not complete successfully. "
                f"Current state is on {after.branch} at {after.head[:12]}; "
                f"changed paths: {', '.join(changed_paths) if changed_paths else 'none'}."
            )
        return _attach_worker_diagnostics({
            "outcome": outcome,
            "final_response": answer[:24_000],
            "commit": verification.outcome if commit_authorized else "NOT_REQUESTED",
            "commit_reason": verification.reason if commit_authorized else "",
            "head_before": before.head,
            "head_after": after.head,
            "branch": after.branch,
            "changed_paths": changed_paths,
            "test_verified": bool(test_evidence and test_evidence.passed),
            "mutated": before.head != after.head or before.status_entries != after.status_entries,
            "evidence_call_count": len(records),
            "tool_call_names": worker_result.get("tool_call_names", [])[:128],
            "tool_trace": worker_result.get("tool_trace", [])[:128],
            "model_metrics": relay_metrics,
        }, task_id=task_id, started_at=started_at)


__all__ = [
    "CodingWorkerError",
    "coding_worker_conversation_allowed",
    "run_coding_worker",
    "should_route_to_coding_worker",
]
