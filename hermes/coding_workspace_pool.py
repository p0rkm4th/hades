"""Resolve authenticated coding sessions to isolated disposable Git copies."""

from __future__ import annotations

import fcntl
import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from hermes.workspace_contract import (
    WorkspaceBinding,
    WorkspaceDenied,
    load_workspace_bindings,
    resolve_workspace_binding,
)


def _private_directory(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_symlink():
        raise WorkspaceDenied("coding workspace root must not be a symlink")
    try:
        info = candidate.stat()
    except OSError as exc:
        raise WorkspaceDenied("coding workspace root is unavailable") from exc
    if (
        not candidate.is_dir()
        or info.st_uid not in {0, os.geteuid()}
        or info.st_mode & 0o077
    ):
        raise WorkspaceDenied("coding workspace root must be private and operator-owned")
    return candidate.resolve(strict=True)


def _git_env() -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C",
        "HOME": "/nonexistent",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_ATTR_NOSYSTEM": "1",
    }


def _source_repository(source: Path, forbidden_roots: tuple[Path, ...]) -> Path:
    try:
        resolved = source.resolve(strict=True)
    except OSError as exc:
        raise WorkspaceDenied("authorized source repository is unavailable") from exc
    if not resolved.is_dir() or any(
        resolved == item or resolved.is_relative_to(item) or item.is_relative_to(resolved)
        for item in forbidden_roots
    ):
        raise WorkspaceDenied("authorized source overlaps a protected path")
    try:
        root = subprocess.run(
            ["/usr/bin/git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
             "-C", str(resolved), "rev-parse", "--show-toplevel"],
            check=True, capture_output=True, text=True, timeout=5, env=_git_env(),
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise WorkspaceDenied("authorized source is not a readable Git repository") from exc
    if Path(root).resolve(strict=True) != resolved:
        raise WorkspaceDenied("authorized source must name exactly one repository")
    return resolved


def _copy_commit_identity(source: Path, destination: Path) -> None:
    """Copy only the mapped repository's local Git author identity."""
    for key in ("user.name", "user.email"):
        result = subprocess.run(
            ["/usr/bin/git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
             "-C", str(source), "config", "--local", "--get", key],
            check=False, capture_output=True, text=True, timeout=5, env=_git_env(),
        )
        if result.returncode == 0 and result.stdout.strip():
            subprocess.run(
                ["/usr/bin/git", "-c", "core.hooksPath=/dev/null", "-C", str(destination),
                 "config", "--local", key, result.stdout.strip()],
                check=True, capture_output=True, text=True, timeout=5, env=_git_env(),
            )


def _session_key(subject: str, conversation_id: str) -> str:
    if not conversation_id or len(conversation_id) > 256 or "\0" in conversation_id:
        raise WorkspaceDenied("coding conversation identity is unavailable")
    return hashlib.sha256((subject + "\0" + conversation_id).encode()).hexdigest()


def resolve_session_workspace(
    *,
    subject: str,
    scope: str,
    conversation_id: str,
    bindings_file: str | Path,
    workspace_root: str | Path,
    forbidden_roots: tuple[str | Path, ...] = (),
) -> WorkspaceBinding:
    """Clone the configured source once per authenticated conversation.

    The caller supplies identity and conversation IDs from Hermes' server-side
    request context. Neither a model argument nor browser path participates in
    selecting the source or workspace.
    """
    if scope != "owner" or not subject:
        raise WorkspaceDenied("coding workspace is owner-only")
    bindings = load_workspace_bindings(bindings_file)
    configured_source = bindings.get(subject)
    if not configured_source:
        raise WorkspaceDenied("no coding source is bound to this authenticated owner")
    forbidden = tuple(Path(item).resolve(strict=True) for item in forbidden_roots)
    source = _source_repository(Path(configured_source), forbidden)
    root = _private_directory(workspace_root)
    key = _session_key(subject, conversation_id)
    destination = root / key
    lock_path = root / (key + ".lock")
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        if destination.is_symlink():
            raise WorkspaceDenied("coding workspace mapping is not a real directory")
        if not destination.exists():
            staging = Path(tempfile.mkdtemp(prefix=".coding-clone-", dir=root))
            try:
                staging.rmdir()
                subprocess.run(
                    ["/usr/bin/git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
                     "clone", "--no-hardlinks", "--", str(source), str(staging)],
                    check=True, capture_output=True, timeout=60, env=_git_env(),
                )
                _copy_commit_identity(source, staging)
                os.chmod(staging, 0o700)
                os.rename(staging, destination)
            except (OSError, subprocess.SubprocessError) as exc:
                shutil.rmtree(staging, ignore_errors=True)
                raise WorkspaceDenied("disposable coding workspace could not be created") from exc
        return resolve_workspace_binding(
            subject=subject,
            scope=scope,
            bindings={subject: str(destination)},
            allowed_root=root,
            forbidden_roots=tuple(str(item) for item in forbidden),
        )
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
