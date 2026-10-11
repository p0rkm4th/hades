"""Rootless offline sandbox for disposable workspace contract tests only.

Hermes owns production command lifecycle and dispatch. This harness exercises
filesystem, network, PID, and capability boundaries without invoking a host
or rootful container daemon.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Sequence


class WorkspaceSandboxUnavailable(RuntimeError):
    """The host policy prevents creation of a rootless user namespace."""


def run_isolated_workspace(
    workspace: Path,
    argv: list[str],
    *,
    timeout: int = 120,
    read_only_paths: Sequence[Path] = (),
) -> subprocess.CompletedProcess[str]:
    """Run a command with its fixture writable and explicit runtime paths read-only."""
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
    runtime_paths = tuple(Path(path).resolve(strict=True) for path in read_only_paths)
    if any(not path.is_dir() for path in runtime_paths):
        raise ValueError("read-only runtime paths must be existing directories")
    if any(path == workspace or path.is_relative_to(workspace) or workspace.is_relative_to(path)
           for path in runtime_paths):
        raise ValueError("runtime paths must not overlap the writable workspace")
    root_mount = tempfile.mkdtemp(prefix="hades-workspace-test-root-")
    setup = r'''set -eu
mount --make-rprivate /
root="$1"
workspace="$2"
shift 2
mount -t tmpfs -o size=512m tmpfs "$root"
for directory in usr bin lib lib64 workspace proc dev tmp home opt; do mkdir -p "$root/$directory"; done
for system_path in /usr /bin /lib /lib64; do
    if [ -e "$system_path" ]; then
        target="$root$system_path"
        mkdir -p "$target"
        mount --bind "$system_path" "$target"
        mount -o remount,bind,ro,nosuid,nodev "$target"
    fi
done
mount --bind "$workspace" "$root/workspace"
mount -o remount,bind,nosuid,nodev "$root/workspace"
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
exec chroot "$root" /usr/bin/setpriv --bounding-set=-all --inh-caps=-all --ambient-caps=-all -- /usr/bin/env -i HOME=/tmp PATH=/usr/local/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 /bin/bash --noprofile --norc -c 'cd /workspace; exec "$@"' hades-workspace-test "$@"
'''
    command = [
        unshare,
        "--user", "--map-root-user", "--mount", "--net", "--pid", "--fork", "--kill-child",
        "--", "/bin/sh", "-eu", "-c", setup,
        "hades-workspace-test-launcher", root_mount, str(workspace),
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
