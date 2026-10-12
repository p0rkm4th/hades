"""Fail-closed workspace binding and coding completion evidence.

This module deliberately stays below Hermes' native file, terminal, and Git
tools. It resolves authority from operator-owned configuration and verifies
repository outcomes from Git state rather than model prose.
"""

from __future__ import annotations

import hashlib
import fcntl
import json
import os
import re
import shutil
import shlex
import stat
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping


Outcome = Literal["SUCCEEDED", "FAILED", "VERIFY", "DENIED"]
_SUBJECT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@-]{0,254}$")
_TEST_COMMANDS = (
    re.compile(r"^(?:python(?:3(?:\.\d+)?)?\s+-m\s+)?pytest(?:\s|$)", re.IGNORECASE),
    re.compile(r"^uv\s+run\s+pytest(?:\s|$)", re.IGNORECASE),
    re.compile(r"^python(?:3(?:\.\d+)?)?\s+-m\s+unittest(?:\s|$)", re.IGNORECASE),
    re.compile(r"^go\s+test(?:\s|$)", re.IGNORECASE),
    re.compile(r"^cargo\s+test(?:\s|$)", re.IGNORECASE),
    re.compile(r"^npm\s+test(?:\s|$)", re.IGNORECASE),
)
def _recognized_test_command(command: str) -> str | None:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    # Hermes' local terminal backend prefixes its configured cwd in some
    # 0.21.2 dispatches. Accept only this exact workspace prefix; an arbitrary
    # directory or additional shell composition remains unrecognized.
    if tokens[:3] == ["cd", "/workspace", "&&"]:
        tokens = tokens[3:]
    if tokens and tokens[-1] == "2>&1":
        tokens = tokens[:-1]
    if (
        not tokens
        or any(re.search(r"[;&|<>$`\\\n\r]", token) for token in tokens)
        or any(token in {"-c", "--command"} for token in tokens)
    ):
        return None
    normalized = " ".join(tokens)
    return normalized if any(pattern.match(normalized) for pattern in _TEST_COMMANDS) else None


class WorkspaceDenied(ValueError):
    """The authenticated actor has no unambiguous authorized workspace."""


class WorkspaceEvidenceError(RuntimeError):
    """Canonical workspace or Git evidence could not be obtained safely."""


@contextmanager
def workspace_lease(binding: WorkspaceBinding):
    """Serialize writers using the repository's kernel-managed Git-directory lock."""
    repository = binding.repository.resolve(strict=True)
    common_dir = Path(git_text(repository, "rev-parse", "--git-common-dir"))
    if not common_dir.is_absolute():
        common_dir = repository / common_dir
    common_dir = common_dir.resolve(strict=True)
    if not common_dir.is_dir():
        raise WorkspaceEvidenceError("repository common Git directory is unavailable")
    descriptor = os.open(common_dir, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def terminal_result_from_hermes_hook(
    *,
    tool_name: str,
    args: Any,
    result: Any,
    task_id: str,
    session_id: str,
    turn_id: str,
    tool_call_id: str,
) -> HermesTerminalResult:
    """Normalize one Hermes post_tool_call payload; never accept model prose."""
    if (
        tool_name != "terminal"
        or not isinstance(args, dict)
        or not isinstance(args.get("command"), str)
        or not all(isinstance(value, str) and value for value in
                   (task_id, session_id, turn_id, tool_call_id))
    ):
        raise WorkspaceEvidenceError("Hermes terminal hook identity is incomplete")
    payload = result
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError) as exc:
            raise WorkspaceEvidenceError("Hermes terminal result was not structured") from exc
    if not isinstance(payload, dict):
        raise WorkspaceEvidenceError("Hermes terminal result was not structured")
    code = payload.get("exit_code")
    if isinstance(code, bool) or (code is not None and not isinstance(code, int)):
        raise WorkspaceEvidenceError("Hermes terminal exit state was malformed")
    output = payload.get("output", "")
    if not isinstance(output, str) or len(output) > 128 * 1024:
        raise WorkspaceEvidenceError("Hermes terminal output was unavailable or oversized")
    status = str(payload.get("status") or "").lower()
    error = str(payload.get("error") or "").lower()
    completed = code is not None and status not in {"running", "background"} and "timed out" not in error
    return HermesTerminalResult(
        task_id=task_id,
        session_id=session_id,
        turn_id=turn_id,
        tool_call_id=tool_call_id,
        command=args["command"],
        exit_code=code,
        output=output,
        completed=completed,
    )


def _git_env() -> dict[str, str]:
    """Run evidence queries without inherited Git config or repository helpers."""
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_ATTR_NOSYSTEM": "1",
            "LC_ALL": "C",
        }
    )
    return env


def _git_argv(root: Path, *args: str) -> list[str]:
    git = shutil.which("git", path=_git_env().get("PATH"))
    if not git:
        raise WorkspaceEvidenceError("Git executable is unavailable")
    return [
        git,
        "-c", "core.fsmonitor=false",
        "-c", "core.hooksPath=" + os.devnull,
        "-c", "diff.external=",
        "-c", "core.pager=cat",
        "-C", str(root),
        *args,
    ]


@dataclass(frozen=True)
class WorkspaceBinding:
    subject: str
    root: Path
    repository: Path


@dataclass(frozen=True)
class RepositorySnapshot:
    root: Path
    branch: str
    head: str
    status_entries: frozenset[tuple[str, str]]
    task_id: str
    session_id: str
    turn_id: str


@dataclass(frozen=True)
class HermesTerminalResult:
    """Terminal execution receipt assembled from Hermes' post-tool hook."""

    task_id: str
    session_id: str
    turn_id: str
    tool_call_id: str
    command: str
    exit_code: int | None
    output: str
    completed: bool


@dataclass(frozen=True)
class TestEvidence:
    subject: str
    workspace: Path
    repository: Path
    branch: str
    head: str
    paths: frozenset[str]
    source_fingerprint: str
    command: str
    exit_code: int
    output: str
    task_id: str
    session_id: str
    turn_id: str
    tool_call_id: str

    @property
    def passed(self) -> bool:
        return (
            self.exit_code == 0
            and _recognized_test_command(self.command) is not None
            and bool(self.task_id and self.session_id and self.turn_id and self.tool_call_id)
        )


@dataclass(frozen=True)
class TestInvocation:
    subject: str
    workspace: Path
    repository: Path
    branch: str
    head: str
    paths: frozenset[str]
    source_fingerprint: str
    command: str
    task_id: str
    session_id: str
    turn_id: str
    tool_call_id: str


@dataclass(frozen=True)
class CommitInvocation:
    """Pre-dispatch snapshot for one explicit Hermes terminal commit call."""

    subject: str
    workspace: Path
    repository: Path
    branch: str
    head: str
    status_entries: frozenset[tuple[str, str]]
    expected_paths: frozenset[str]
    source_fingerprint: str
    command: str
    task_id: str
    session_id: str
    turn_id: str
    tool_call_id: str


@dataclass(frozen=True)
class CommitVerification:
    outcome: Outcome
    reason: str
    before_head: str
    after_head: str
    committed_paths: frozenset[str]


def load_workspace_bindings(path: str | Path) -> dict[str, str]:
    """Load a small operator-owned JSON map; reject writable or oversized files."""
    config_path = Path(path)
    try:
        if config_path.is_symlink():
            raise WorkspaceDenied("workspace binding file must not be a symlink")
        info = config_path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 64 * 1024:
            raise WorkspaceDenied("workspace binding file is not a small regular file")
        if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise WorkspaceDenied("workspace binding file is group/world writable")
        if info.st_uid not in {0, os.geteuid()}:
            raise WorkspaceDenied("workspace binding file has an untrusted owner")
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except WorkspaceDenied:
        raise
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise WorkspaceDenied("workspace binding file is unavailable or invalid") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise WorkspaceDenied("workspace binding file has an unsupported shape")
    raw = payload.get("bindings")
    if not isinstance(raw, dict) or len(raw) > 256:
        raise WorkspaceDenied("workspace binding map is invalid")
    result: dict[str, str] = {}
    for subject, root in raw.items():
        if (
            not isinstance(subject, str)
            or not _SUBJECT.fullmatch(subject)
            or not isinstance(root, str)
            or not Path(root).is_absolute()
        ):
            raise WorkspaceDenied("workspace binding entry is invalid")
        result[subject] = root
    return result


def resolve_workspace_binding(
    *,
    subject: str,
    scope: str,
    bindings: Mapping[str, str],
    allowed_root: str | Path,
    forbidden_roots: tuple[str | Path, ...] = (),
) -> WorkspaceBinding:
    """Resolve one trusted subject mapping; request text cannot select a path."""
    if scope != "owner" or not isinstance(subject, str) or not _SUBJECT.fullmatch(subject):
        raise WorkspaceDenied("coding workspace is owner-only")
    configured = bindings.get(subject)
    if not configured:
        raise WorkspaceDenied("no workspace is bound to this authenticated subject")
    try:
        base = Path(allowed_root).resolve(strict=True)
        workspace = Path(configured).resolve(strict=True)
        if not workspace.is_dir() or not workspace.is_relative_to(base):
            raise WorkspaceDenied("workspace is outside the configured workspace root")
        for forbidden_value in forbidden_roots:
            forbidden = Path(forbidden_value).resolve(strict=True)
            if workspace == forbidden or workspace.is_relative_to(forbidden) or forbidden.is_relative_to(workspace):
                raise WorkspaceDenied("workspace overlaps a protected source checkout")
        for other_subject, other_path in bindings.items():
            if other_subject == subject:
                continue
            try:
                if Path(other_path).resolve(strict=True) == workspace:
                    raise WorkspaceDenied("workspace is ambiguously mapped to multiple subjects")
            except OSError:
                continue
        root = git_text(workspace, "rev-parse", "--show-toplevel")
        repository = Path(root).resolve(strict=True)
        if repository != workspace:
            raise WorkspaceDenied("a workspace binding must name exactly one repository")
    except WorkspaceDenied:
        raise
    except (OSError, WorkspaceEvidenceError) as exc:
        raise WorkspaceDenied("bound workspace is unavailable or is not a Git repository") from exc
    return WorkspaceBinding(subject, workspace, repository)


def git_text(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            _git_argv(root, *args),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            env=_git_env(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkspaceEvidenceError("Git evidence query did not complete") from exc
    if result.returncode != 0:
        raise WorkspaceEvidenceError("Git evidence query failed")
    return result.stdout.strip()


def _status_entries(root: Path) -> frozenset[tuple[str, str]]:
    try:
        result = subprocess.run(
            _git_argv(root, "status", "--porcelain=v1", "-z", "--untracked-files=all"),
            check=False,
            capture_output=True,
            timeout=5,
            env=_git_env(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkspaceEvidenceError("Git status query did not complete") from exc
    if result.returncode != 0:
        raise WorkspaceEvidenceError("Git status query failed")
    fields = result.stdout.split(b"\0")
    entries: set[tuple[str, str]] = set()
    index = 0
    while index < len(fields):
        field = fields[index]
        index += 1
        if not field:
            continue
        if len(field) < 4:
            raise WorkspaceEvidenceError("Git status output was malformed")
        status = field[:2]
        entries.add((os.fsdecode(status), os.fsdecode(field[3:])))
        if b"R" in status or b"C" in status:
            if index >= len(fields) or not fields[index]:
                raise WorkspaceEvidenceError("Git rename status was incomplete")
            entries.add((os.fsdecode(status), os.fsdecode(fields[index])))
            index += 1
    return frozenset(entries)


def snapshot_repository(
    binding: WorkspaceBinding,
    *,
    task_id: str,
    session_id: str,
    turn_id: str,
) -> RepositorySnapshot:
    """Read canonical workspace, branch, HEAD, and working-path state."""
    try:
        root = Path(git_text(binding.repository, "rev-parse", "--show-toplevel")).resolve(strict=True)
        branch = git_text(binding.repository, "branch", "--show-current")
        head = git_text(binding.repository, "rev-parse", "--verify", "HEAD^{commit}")
        entries = _status_entries(binding.repository)
    except (OSError, WorkspaceEvidenceError) as exc:
        raise WorkspaceEvidenceError("repository snapshot is incomplete") from exc
    if (
        root != binding.repository
        or not branch
        or not re.fullmatch(r"[0-9a-f]{40,64}", head)
        or not isinstance(task_id, str)
        or not task_id
        or len(task_id) > 256
        or not isinstance(session_id, str)
        or not session_id
        or len(session_id) > 256
        or not isinstance(turn_id, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{12,128}", turn_id)
    ):
        raise WorkspaceEvidenceError("repository identity is ambiguous")
    return RepositorySnapshot(
        root,
        branch,
        head,
        entries,
        task_id,
        session_id,
        turn_id,
    )


def _validate_paths(paths: set[str] | frozenset[str]) -> frozenset[str]:
    normalized: set[str] = set()
    for raw in paths:
        path = Path(raw)
        if (
            not isinstance(raw, str)
            or not raw
            or path.is_absolute()
            or ".." in path.parts
            or ".git" in path.parts
        ):
            raise WorkspaceEvidenceError("expected path set was invalid")
        normalized.add(path.as_posix())
    return frozenset(normalized)


def _path_fingerprint(root: Path, paths: frozenset[str], revision: str | None = None) -> str:
    digest = hashlib.sha256()
    for relative in sorted(paths):
        try:
            if revision is None:
                path = (root / relative).resolve(strict=True)
                if not path.is_relative_to(root):
                    raise WorkspaceEvidenceError("workspace path escaped its root")
                content = path.read_bytes()
            else:
                shown = subprocess.run(
                    _git_argv(root, "--no-pager", "show", f"{revision}:{relative}"),
                    check=False,
                    capture_output=True,
                    timeout=5,
                    env=_git_env(),
                )
                content = shown.stdout
                result = subprocess.run(
                    _git_argv(root, "cat-file", "-e", f"{revision}:{relative}"),
                    check=False,
                    capture_output=True,
                    timeout=5,
                    env=_git_env(),
                )
                if result.returncode != 0 or shown.returncode != 0:
                    raise WorkspaceEvidenceError("committed source path was unavailable")
            if len(content) > 8 * 1024 * 1024:
                raise WorkspaceEvidenceError("source path is too large to verify")
        except WorkspaceEvidenceError:
            raise
        except (OSError, subprocess.SubprocessError) as exc:
            raise WorkspaceEvidenceError("source fingerprint could not be collected") from exc
        digest.update(relative.encode("utf-8", "surrogateescape"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(content).digest())
        digest.update(b"\0")
    return digest.hexdigest()


def begin_test_invocation(
    binding: WorkspaceBinding,
    snapshot: RepositorySnapshot,
    *,
    paths: set[str] | frozenset[str],
    command: str,
    tool_call_id: str,
) -> TestInvocation:
    """Capture source immediately before a trusted terminal test call starts."""
    selected = _validate_paths(paths)
    if (
        not selected
        or snapshot.root != binding.repository
        or len(command) > 2048
        or not isinstance(tool_call_id, str)
        or not tool_call_id
        or len(tool_call_id) > 256
    ):
        raise WorkspaceEvidenceError("test evidence lacks a bound source set")
    recognized = _recognized_test_command(command)
    if not recognized:
        raise WorkspaceEvidenceError("test evidence is incomplete")
    fingerprint = _path_fingerprint(binding.repository, selected)
    return TestInvocation(
        subject=binding.subject,
        workspace=binding.root,
        repository=binding.repository,
        branch=snapshot.branch,
        head=snapshot.head,
        paths=selected,
        source_fingerprint=fingerprint,
        command=command,
        task_id=snapshot.task_id,
        session_id=snapshot.session_id,
        turn_id=snapshot.turn_id,
        tool_call_id=tool_call_id,
    )


def complete_test_invocation(
    binding: WorkspaceBinding,
    invocation: TestInvocation,
    after: RepositorySnapshot,
    *,
    result: HermesTerminalResult,
) -> TestEvidence:
    """Bind Hermes' actual post-tool result to its pre-tool invocation and source."""
    if (
        result.task_id != invocation.task_id
        or result.session_id != invocation.session_id
        or result.turn_id != invocation.turn_id
        or result.tool_call_id != invocation.tool_call_id
        or result.command != invocation.command
        or not result.completed
        or not isinstance(result.exit_code, int)
        or invocation.subject != binding.subject
        or invocation.workspace != binding.root
        or invocation.repository != binding.repository
        or after.root != binding.repository
        or after.task_id != invocation.task_id
        or after.session_id != invocation.session_id
        or after.turn_id != invocation.turn_id
        or after.head != invocation.head
        or after.branch != invocation.branch
        or len(result.output) > 128 * 1024
    ):
        raise WorkspaceEvidenceError("terminal result did not match its trusted test invocation")
    fingerprint = _path_fingerprint(binding.repository, invocation.paths)
    if fingerprint != invocation.source_fingerprint:
        raise WorkspaceEvidenceError("source changed while or after the focused test ran")
    return TestEvidence(
        subject=invocation.subject,
        workspace=invocation.workspace,
        repository=invocation.repository,
        branch=invocation.branch,
        head=invocation.head,
        paths=invocation.paths,
        source_fingerprint=invocation.source_fingerprint,
        command=invocation.command,
        exit_code=result.exit_code,
        output=result.output,
        task_id=invocation.task_id,
        session_id=invocation.session_id,
        turn_id=invocation.turn_id,
        tool_call_id=invocation.tool_call_id,
    )


def _commit_paths(root: Path, before: str, after: str) -> frozenset[str]:
    try:
        result = subprocess.run(
            _git_argv(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", "--no-renames", before, after),
            check=False,
            capture_output=True,
            timeout=5,
            env=_git_env(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkspaceEvidenceError("commit path query did not complete") from exc
    if result.returncode != 0:
        raise WorkspaceEvidenceError("commit path query failed")
    return frozenset(os.fsdecode(item) for item in result.stdout.split(b"\0") if item)


def _staged_paths(root: Path) -> frozenset[str]:
    try:
        result = subprocess.run(
            _git_argv(root, "diff", "--cached", "--name-only", "-z", "--no-renames"),
            check=False,
            capture_output=True,
            timeout=5,
            env=_git_env(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkspaceEvidenceError("staged path query did not complete") from exc
    if result.returncode != 0:
        raise WorkspaceEvidenceError("staged path query failed")
    return frozenset(os.fsdecode(item) for item in result.stdout.split(b"\0") if item)


def _literal_paths_added_by_commit_command(command: str) -> frozenset[str] | None:
    """Accept only an explicit ``git add PATHS && git commit`` sequence.

    This lets the pre-tool verifier bind a common native Hermes shell command
    before it executes, without treating broad forms such as ``git add -A`` or
    shell-expanded paths as user-authorized commit scope.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    if tokens[:3] == ["cd", "/workspace", "&&"]:
        tokens = tokens[3:]
    if tokens and tokens[-1] == "2>&1":
        tokens = tokens[:-1]
    if "&&" not in tokens:
        return None
    if tokens.count("&&") != 1:
        return frozenset()
    split = tokens.index("&&")
    add, commit = tokens[:split], tokens[split + 1:]
    if len(add) < 3 or add[:2] != ["git", "add"] or commit[:2] != ["git", "commit"]:
        return frozenset()
    raw_paths = add[2:]
    if raw_paths and raw_paths[0] == "--":
        raw_paths = raw_paths[1:]
    if not raw_paths or any(
        not item or item.startswith("-") or Path(item).is_absolute()
        or ".." in Path(item).parts or any(char in item for char in "*?[]{};$`\\\n\r")
        for item in raw_paths
    ):
        return frozenset()
    try:
        paths = _validate_paths(raw_paths)
    except WorkspaceEvidenceError:
        return frozenset()
    return paths


def begin_commit_invocation(
    binding: WorkspaceBinding,
    snapshot: RepositorySnapshot,
    *,
    command: str,
    tool_call_id: str,
) -> CommitInvocation:
    """Capture the staged intent before Hermes dispatches this terminal call."""
    if (
        snapshot.root != binding.repository
        or snapshot.task_id == ""
        or not tool_call_id
        or len(command) > 2048
        or not re.search(r"(?:^|[;&|]\s*)git\s+commit(?:\s|$)", command)
    ):
        raise WorkspaceEvidenceError("commit invocation is not a bound Hermes terminal request")
    staged_paths = _staged_paths(binding.repository)
    command_paths = _literal_paths_added_by_commit_command(command)
    if command_paths == frozenset():
        raise WorkspaceEvidenceError("combined commit command does not specify literal source paths")
    if command_paths and not staged_paths.issubset(command_paths):
        raise WorkspaceEvidenceError("combined commit command would include unstated staged paths")
    paths = _validate_paths(staged_paths | (command_paths or frozenset()))
    if not paths:
        raise WorkspaceEvidenceError("commit request has no staged paths")
    source_fingerprint = _path_fingerprint(binding.repository, paths)
    return CommitInvocation(
        subject=binding.subject,
        workspace=binding.root,
        repository=binding.repository,
        branch=snapshot.branch,
        head=snapshot.head,
        status_entries=snapshot.status_entries,
        expected_paths=paths,
        source_fingerprint=source_fingerprint,
        command=command,
        task_id=snapshot.task_id,
        session_id=snapshot.session_id,
        turn_id=snapshot.turn_id,
        tool_call_id=tool_call_id,
    )


def verify_commit(
    binding: WorkspaceBinding,
    *,
    invocation: CommitInvocation | None,
    after: RepositorySnapshot | None,
    test_evidence: TestEvidence | None,
    operation: HermesTerminalResult | None,
    commit_requested: bool,
) -> CommitVerification:
    """Verify the requested commit from current Git state, never command prose."""
    if invocation is None:
        if commit_requested:
            return CommitVerification("FAILED", "no Hermes terminal commit invocation occurred", "", "", frozenset())
        return CommitVerification("VERIFY", "no explicit commit request was bound to this operation", "", "", frozenset())
    before_head = invocation.head
    selected = invocation.expected_paths
    if after is None:
        return CommitVerification("VERIFY", "post-operation repository state is unavailable", before_head, "", frozenset())
    if (
        invocation.subject != binding.subject
        or invocation.workspace != binding.root
        or invocation.repository != binding.repository
        or after.root != binding.repository
        or after.task_id != invocation.task_id
        or after.session_id != invocation.session_id
        or after.turn_id != invocation.turn_id
    ):
        return CommitVerification("VERIFY", "repository or task identity changed or did not match the bound workspace", before_head, after.head, frozenset())
    if invocation.branch != after.branch:
        return CommitVerification("VERIFY", "branch changed during the requested commit", before_head, after.head, frozenset())
    if operation is not None and (
        operation.task_id != invocation.task_id
        or operation.session_id != invocation.session_id
        or operation.turn_id != invocation.turn_id
        or operation.tool_call_id != invocation.tool_call_id
        or operation.command != invocation.command
        or not re.search(r"(?:^|[;&|]\s*)git\s+commit(?:\s|$)", operation.command)
    ):
        return CommitVerification(
            "VERIFY",
            "terminal result belongs to a different task or commit tool call",
            invocation.head,
            after.head,
            frozenset(),
        )
    if operation is None:
        operation_state: Literal["SUCCEEDED", "FAILED", "UNKNOWN"] = "UNKNOWN"
    elif not operation.completed or operation.exit_code is None:
        operation_state = "UNKNOWN"
    elif operation.exit_code == 0:
        operation_state = "SUCCEEDED"
    else:
        operation_state = "FAILED"
    if invocation.head == after.head:
        if operation_state == "UNKNOWN":
            try:
                source_unchanged = (
                    _path_fingerprint(binding.repository, selected)
                    == invocation.source_fingerprint
                )
            except WorkspaceEvidenceError:
                source_unchanged = False
            before_unselected = frozenset(
                row for row in invocation.status_entries if row[1] not in selected
            )
            after_unselected = frozenset(
                row for row in after.status_entries if row[1] not in selected
            )
            if not source_unchanged or before_unselected != after_unselected:
                return CommitVerification(
                    "VERIFY",
                    "HEAD is unchanged but source or unrelated workspace state changed during the ambiguous operation",
                    invocation.head,
                    after.head,
                    frozenset(),
                )
            # This is a fresh canonical repository snapshot bound to the
            # invocation. It proves no requested commit occurred and that the
            # intended source did not change; a controlled retry is safe.
            return CommitVerification("FAILED", "canonical repository state proves no new commit exists", invocation.head, after.head, frozenset())
        return CommitVerification("FAILED", "no new commit exists in the bound repository", invocation.head, after.head, frozenset())
    if operation_state == "FAILED":
        return CommitVerification(
            "VERIFY",
            "repository advanced despite a failed terminal result; reconcile before any retry",
            invocation.head,
            after.head,
            frozenset(),
        )
    # A missing or interrupted Hermes response is not success by itself. It
    # may nevertheless be reconciled as success below when canonical Git
    # state proves the exact requested direct-child commit and tested source.
    if not selected:
        return CommitVerification("VERIFY", "no intended source paths were bound to this commit request", invocation.head, after.head, frozenset())
    try:
        parent = git_text(binding.repository, "rev-parse", "--verify", f"{after.head}^1")
        committed = _commit_paths(binding.repository, invocation.head, after.head)
    except WorkspaceEvidenceError:
        return CommitVerification("VERIFY", "commit ancestry or changed paths could not be verified", invocation.head, after.head, frozenset())
    if parent != invocation.head:
        return CommitVerification("VERIFY", "new HEAD is not a direct child of the captured pre-operation HEAD", invocation.head, after.head, committed)
    if committed != selected:
        return CommitVerification("VERIFY", "commit paths do not exactly match the staged intent captured for this call", invocation.head, after.head, committed)
    if test_evidence is None or not test_evidence.passed:
        return CommitVerification("VERIFY", "passing focused-test evidence is absent", invocation.head, after.head, committed)
    # A coding conversation may span isolated Hermes task IDs. Prior-turn test
    # receipts are accepted only when they remain bound to this same session,
    # pre-commit HEAD, exact selected paths, and committed source fingerprint.
    if (
        test_evidence.subject != binding.subject
        or test_evidence.workspace != binding.root
        or test_evidence.repository != binding.repository
        or test_evidence.branch != invocation.branch
        or test_evidence.head != invocation.head
        or test_evidence.session_id != invocation.session_id
        or test_evidence.paths != selected
    ):
        return CommitVerification("VERIFY", "test evidence belongs to a different actor, workspace, operation, or source set", invocation.head, after.head, committed)
    try:
        committed_fingerprint = _path_fingerprint(binding.repository, selected, after.head)
    except WorkspaceEvidenceError:
        return CommitVerification("VERIFY", "committed source could not be matched to test evidence", invocation.head, after.head, committed)
    if committed_fingerprint != test_evidence.source_fingerprint:
        return CommitVerification("VERIFY", "tested source differs from committed source", invocation.head, after.head, committed)
    expected_status = frozenset(
        (status, path)
        for status, path in invocation.status_entries
        if path not in selected
    )
    if after.status_entries != expected_status:
        return CommitVerification("VERIFY", "post-commit working tree differs from its captured baseline", invocation.head, after.head, committed)
    return CommitVerification("SUCCEEDED", "new direct-child commit, exact paths, tested source, branch, and worktree verified", invocation.head, after.head, committed)
