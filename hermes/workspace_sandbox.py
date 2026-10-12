"""Rootless process sandbox for one authorized coding workspace.

Hermes owns coding lifecycle and dispatch. This module confines the complete
Hermes worker process without per-tool wrappers or a rootful container daemon.
Network stays denied; the opt-in inference mode mounts one fixed Unix socket
and bridges it only to isolated loopback.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Sequence


class WorkspaceSandboxUnavailable(RuntimeError):
    """Host policy prevents creation of a rootless user namespace."""


def run_isolated_workspace(
    workspace: Path,
    argv: list[str],
    *,
    timeout: int = 120,
    read_only_paths: Sequence[Path] = (),
    unix_socket: Path | None = None,
    enable_loopback: bool = False,
    writable_git_metadata: bool = False,
    workspace_read_only: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run one process with a bounded workspace and read-only runtime mounts."""
    if os.geteuid() == 0:
        raise RuntimeError("rootless workspace execution is unavailable to a root test runner")
    unshare = shutil.which("unshare", path="/usr/bin:/bin")
    if not unshare or not Path("/usr/bin/setpriv").is_file():
        raise RuntimeError("rootless user namespace execution is unavailable")
    if (
        not isinstance(argv, list)
        or not argv
        or len(argv) > 128
        or any(not isinstance(arg, str) or "\0" in arg or len(arg) > 4096 for arg in argv)
        or timeout < 1
        or timeout > 600
    ):
        raise ValueError("workspace command request is invalid")
    workspace = Path(workspace).resolve(strict=True)
    if not workspace.is_dir():
        raise ValueError("workspace must be a directory")
    git_dir = workspace / ".git"
    has_git_dir = git_dir.is_dir()
    if git_dir.is_symlink() or (git_dir.exists() and (
        not has_git_dir or git_dir.resolve(strict=True).parent != workspace
    )):
        raise ValueError("sandbox workspace must have a private Git directory inside its root")
    if writable_git_metadata and not has_git_dir:
        raise ValueError("Git metadata cannot be writable without a workspace Git directory")
    runtime_paths = tuple(Path(path).resolve(strict=True) for path in read_only_paths)
    if any(not path.is_dir() for path in runtime_paths):
        raise ValueError("read-only runtime paths must be existing directories")
    if any(path == workspace or path.is_relative_to(workspace) or workspace.is_relative_to(path)
           for path in runtime_paths):
        raise ValueError("runtime paths must not overlap the writable workspace")
    socket_path: Path | None = None
    if unix_socket is not None:
        socket_path = Path(unix_socket).resolve(strict=True)
        if not stat.S_ISSOCK(socket_path.stat().st_mode):
            raise ValueError("inference relay path must be a Unix-domain socket")
        if not enable_loopback:
            raise ValueError("an inference socket requires isolated loopback for the local HTTP bridge")
        if (not shutil.which("ncat", path="/usr/bin:/bin")
                or not Path("/usr/bin/setsid").is_file()):
            raise RuntimeError("the Unix-socket to loopback bridge requires ncat and setsid")
    root_mount = tempfile.mkdtemp(prefix="hades-workspace-root-")
    setup = r'''set -eu
mount --make-rprivate /
root="$1"
workspace="$2"
    socket_path="$3"
enable_loopback="$4"
git_writable="$5"
git_present="$6"
workspace_read_only="$7"
shift 7
mount -t tmpfs -o size=512m tmpfs "$root"
for directory in usr bin lib lib64 workspace proc dev tmp home opt run/hades-inference; do mkdir -p "$root/$directory"; done
for system_path in /usr /bin /lib /lib64; do
    if [ -e "$system_path" ]; then
        target="$root$system_path"
        mkdir -p "$target"
        mount --bind "$system_path" "$target"
        mount -o remount,bind,ro,nosuid,nodev "$target"
    fi
done
mount --bind "$workspace" "$root/workspace"
if [ "$workspace_read_only" = "1" ]; then
    mount -o remount,bind,ro,nosuid,nodev "$root/workspace"
else
    mount -o remount,bind,rw,nosuid,nodev "$root/workspace"
fi
if [ "$git_present" = "1" ]; then
    mount --bind "$workspace/.git" "$root/workspace/.git"
    if [ "$git_writable" = "1" ]; then
        mount -o remount,bind,rw,nosuid,nodev "$root/workspace/.git"
    else
        mount -o remount,bind,ro,nosuid,nodev "$root/workspace/.git"
    fi
fi
if [ "$socket_path" != "" ]; then
    : > "$root/run/hades-inference/model.sock"
    mount --bind "$socket_path" "$root/run/hades-inference/model.sock"
    mount -o remount,bind,ro,nosuid,nodev "$root/run/hades-inference/model.sock"
fi
if [ "$enable_loopback" = "1" ]; then
    /usr/sbin/ip link set lo up
fi
while [ "$1" != "--" ]; do
    runtime_path="$1"
    target="$root$runtime_path"
    mkdir -p "$(dirname "$target")"
    mkdir -p "$target"
    mount --bind "$runtime_path" "$target"
    mount -o remount,bind,ro,nosuid,nodev "$target"
    shift
done
shift
mount -t proc proc "$root/proc"
mount -t tmpfs -o size=16m tmpfs "$root/dev"
for node in null zero random urandom; do : > "$root/dev/$node"; chmod 666 "$root/dev/$node"; done
cd "$root/workspace"
exec chroot "$root" /usr/bin/setpriv --bounding-set=-all --inh-caps=-all --ambient-caps=-all -- /usr/bin/env -i HOME=/tmp PATH=/usr/local/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0 GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_ATTR_NOSYSTEM=1 HADES_MODEL_BASE_URL=http://127.0.0.1:18137/v1 /bin/bash --noprofile --norc -c '
bridge_pid=
if [ -S /run/hades-inference/model.sock ]; then
    /usr/bin/setsid /usr/bin/ncat --listen --keep-open 127.0.0.1 18137 --exec "/usr/bin/ncat --unixsock /run/hades-inference/model.sock" >/dev/null 2>&1 &
    bridge_pid=$!
fi
cd /workspace
"$@"
worker_status=$?
if [ -n "$bridge_pid" ]; then
    kill "$bridge_pid" 2>/dev/null || true
    wait "$bridge_pid" 2>/dev/null || true
fi
exit "$worker_status"
' hades-workspace-test "$@"
'''
    command = [
        unshare,
        "--user", "--map-root-user", "--mount", "--net", "--pid", "--fork", "--kill-child",
        "--", "/bin/sh", "-eu", "-c", setup,
        "hades-workspace-launcher", root_mount, str(workspace),
        str(socket_path) if socket_path else "",
        "1" if enable_loopback else "0",
        "1" if writable_git_metadata else "0",
        "1" if has_git_dir else "0",
        "1" if workspace_read_only else "0",
        *(str(path) for path in runtime_paths), "--", *argv,
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("isolated workspace test command did not complete") from exc
    finally:
        shutil.rmtree(root_mount, ignore_errors=True)
    if "write failed /proc/self/uid_map: Operation not permitted" in result.stderr:
        raise WorkspaceSandboxUnavailable("host policy denies unprivileged user namespaces")
    if len(result.stdout) > 128 * 1024 or len(result.stderr) > 128 * 1024:
        raise RuntimeError("isolated workspace test output exceeded its evidence bound")
    return result
