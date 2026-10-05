#!/usr/bin/env python3
"""Write the bounded machine-readable identity of a tested deployment."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(read_regular_file(path, "regular file required")).hexdigest()


def load_overlay_composition(manifest_path: Path, base_path: Path, source_repo: Path, final_bytes: bytes) -> tuple[dict, str, bytes]:
    """Verify the selected on-disk overlay against a source-bound composition record."""
    manifest_bytes = read_regular_file(manifest_path, "overlay composition manifest must be a stable regular file")
    base_bytes = read_regular_file(base_path, "overlay composition base must be a stable regular file")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate manifest key")
            result[key] = value
        return result

    try:
        manifest = json.loads(manifest_bytes, object_pairs_hook=unique_object)
    except (UnicodeError, json.JSONDecodeError, ValueError):
        raise SystemExit("overlay composition manifest is malformed") from None
    verifier_path = source_repo / "scripts/hermes-overlay-composition.py"
    if verifier_path.is_symlink() or not verifier_path.is_file():
        raise SystemExit("source revision has no tracked overlay composition verifier")
    try:
        spec = importlib.util.spec_from_file_location("_hades_overlay_composition_verifier", verifier_path)
        if spec is None or spec.loader is None:
            raise ValueError("verifier import unavailable")
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        verifier.verify_manifest(manifest, source_repo, final_bytes, base_bytes)
    except (OSError, ValueError, ImportError, SystemExit):
        raise SystemExit("overlay composition does not match the clean HADES source and selected overlay") from None
    return manifest, hashlib.sha256(manifest_bytes).hexdigest(), base_bytes


def read_regular_file(path: Path, error: str) -> bytes:
    """Read one stable regular-file snapshot without following a final symlink."""
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise OSError("not a regular file")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        before_identity = (
            before.st_dev, before.st_ino, before.st_size,
            before.st_mtime_ns, before.st_ctime_ns,
        )
        after_identity = (
            after.st_dev, after.st_ino, after.st_size,
            after.st_mtime_ns, after.st_ctime_ns,
        )
        contents = b"".join(chunks)
        if before_identity != after_identity or len(contents) != after.st_size:
            raise OSError("file changed while being read")
        return contents
    except (OSError, RuntimeError, ValueError):
        raise SystemExit(error) from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def verify_source_checkout(source_repo: Path, claimed_sha: str, label: str) -> str:
    if source_repo.is_symlink() or not source_repo.is_dir():
        raise SystemExit(f"{label} source repository must be a real directory")
    root = source_repo.resolve()

    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise SystemExit(f"{label} source repository Git identity could not be verified")
        return result.stdout.strip()

    top = Path(git("rev-parse", "--show-toplevel")).resolve()
    if top != root:
        raise SystemExit(f"{label} source repository must be the Git worktree root")
    head = git("rev-parse", "HEAD")
    if head != claimed_sha.lower():
        raise SystemExit(f"claimed {label} revision does not match source repository HEAD")
    if git("status", "--porcelain", "--untracked-files=all"):
        raise SystemExit(f"{label} source repository must be clean before recording deployment provenance")
    return git("rev-parse", "HEAD^{tree}")


def require_service_active(service: str) -> None:
    active = subprocess.run(
        ["systemctl", "is-active", "--quiet", service],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if active.returncode != 0:
        raise SystemExit(f"Hermes service is not active: {service}")


def service_main_pid(service: str) -> int:
    result = subprocess.run(
        ["systemctl", "show", "--property=MainPID", "--value", service],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip().isdigit():
        raise SystemExit("active Hermes service has no verifiable MainPID")
    pid = int(result.stdout.strip())
    if pid <= 1:
        raise SystemExit("active Hermes service has no valid MainPID")
    return pid


def process_start_time(pid: int) -> str:
    try:
        value = (Path("/proc") / str(pid) / "stat").read_text(encoding="ascii")
        end_command = value.rfind(")")
        fields_after_command = value[end_command + 2:].split()
        # /proc/<pid>/stat field 22 (starttime); field 3 starts at index zero.
        if end_command < 0 or len(fields_after_command) <= 19:
            raise ValueError("truncated process stat")
        return fields_after_command[19]
    except (OSError, UnicodeError, ValueError):
        raise SystemExit("active Hermes process identity could not be verified") from None


def running_process_snapshot(service: str) -> tuple[int, str, list[str], dict[str, str]]:
    """Capture argv and environment from one stable systemd MainPID."""
    require_service_active(service)
    pid = service_main_pid(service)
    started = process_start_time(pid)
    try:
        process_root = Path("/proc") / str(pid)
        command_line = (process_root / "cmdline").read_bytes().split(b"\0")
        arguments = [item.decode("utf-8", errors="strict") for item in command_line if item]
        items = (process_root / "environ").read_bytes().split(b"\0")
        environment: dict[str, str] = {}
        for item in items:
            if b"=" not in item:
                continue
            key, value = item.split(b"=", 1)
            environment[key.decode("utf-8", errors="strict")] = value.decode("utf-8", errors="strict")
    except (OSError, UnicodeError, RuntimeError):
        raise SystemExit("active Hermes process arguments and environment could not be verified") from None
    if not arguments:
        raise SystemExit("active Hermes process has an empty command line")
    if process_start_time(pid) != started or service_main_pid(service) != pid:
        raise SystemExit("Hermes service process changed during provenance capture")
    require_service_active(service)
    return pid, started, arguments, environment


def verify_process_snapshot_current(service: str, pid: int, started: str) -> None:
    require_service_active(service)
    if service_main_pid(service) != pid or process_start_time(pid) != started:
        raise SystemExit("Hermes service process changed during provenance capture")


def active_overlay(environment: dict[str, str]) -> Path:
    """Resolve the overlay using PYTHONPATH from the captured Hermes process."""
    pythonpath = environment.get("PYTHONPATH", "")
    if not pythonpath:
        raise SystemExit("running Hermes process has no verifiable PYTHONPATH")
    for entry in pythonpath.split(os.pathsep):
        candidate = Path(entry) / "sitecustomize.py"
        if candidate.exists():
            if not candidate.is_file() or candidate.is_symlink():
                raise SystemExit("effective Hermes sitecustomize must be a regular non-symlink file")
            return candidate
    raise SystemExit("running Hermes PYTHONPATH contains no sitecustomize.py")


def verify_selected_profile(
    arguments: list[str], environment: dict[str, str], supplied_profile: Path
) -> tuple[str, str]:
    """Bind the profile file hash to the profile name used by the live process."""
    selected_name = ""
    for index, argument in enumerate(arguments):
        if argument in {"-p", "--profile"} and index + 1 < len(arguments):
            selected_name = arguments[index + 1]
            break
        if argument.startswith("--profile="):
            selected_name = argument.split("=", 1)[1]
            break
    home = environment.get("HERMES_HOME", "").strip()
    if not selected_name or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", selected_name):
        raise SystemExit("running Hermes process has no supported named profile selection")
    if not home:
        raise SystemExit("running Hermes service has no HERMES_HOME for profile verification")
    expected = Path(home) / "profiles" / selected_name / "config.yaml"
    if supplied_profile.is_symlink() or not supplied_profile.is_file():
        raise SystemExit("Hermes profile must be a regular non-symlink file")
    try:
        same_profile = supplied_profile.resolve(strict=True) == expected.resolve(strict=True)
    except (OSError, RuntimeError):
        same_profile = False
    if not same_profile:
        raise SystemExit("Hermes profile argument differs from the active process profile")
    profile_bytes = read_regular_file(
        supplied_profile, "Hermes profile must be a stable regular non-symlink file"
    )
    try:
        profile_text = profile_bytes.decode("utf-8", errors="strict")
    except UnicodeError:
        raise SystemExit("Hermes profile must be valid UTF-8") from None
    return hashlib.sha256(profile_bytes).hexdigest(), profile_text


def profile_server_blocks(profile: str) -> dict[str, str]:
    match = re.search(r"(?m)^mcp_servers:\s*$", profile)
    if not match:
        raise SystemExit("selected Hermes profile has no top-level mcp_servers mapping")
    body = profile[match.end():]
    starts = list(re.finditer(r"(?m)^  ([A-Za-z0-9_-]+):\s*$", body))
    if not starts:
        raise SystemExit("selected Hermes profile has no MCP registrations")
    result: dict[str, str] = {}
    for index, start in enumerate(starts):
        name = start.group(1)
        if name in result:
            raise SystemExit(f"selected Hermes profile contains a duplicate MCP registration: {name}")
        end = starts[index + 1].start() if index + 1 < len(starts) else len(body)
        result[name] = body[start.end():end]
    return result


def expand_profile_value(value: str, environment: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        variable = match.group(1)
        if ":-" in variable:
            key, default = variable.split(":-", 1)
            return environment.get(key, default)
        return environment.get(variable, "")

    expanded = re.sub(r"\$\{([^}]+)\}", replace, value)
    if "${" in expanded or re.search(r"\$[A-Za-z_][A-Za-z0-9_]*", expanded):
        raise SystemExit("selected Hermes profile contains an unresolved runtime reference")
    return expanded


def profile_args(block: str, name: str) -> list[str]:
    # Keep indentation on the args line itself. A broad \s* here consumes the
    # newline and the first block-list item before the YAML list parser sees it.
    match = re.search(r"(?m)^    args:[ \t]*(.*?)[ \t]*$", block)
    if not match:
        return []
    value = match.group(1)
    if value.startswith("["):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            raise SystemExit(f"enabled MCP arguments are not a supported string array: {name}") from None
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            raise SystemExit(f"enabled MCP arguments are not a supported string array: {name}")
        return parsed
    if value:
        raise SystemExit(f"enabled MCP arguments use an unsupported YAML form: {name}")

    result: list[str] = []
    for line in block[match.end():].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if re.match(r"^    [A-Za-z_][A-Za-z0-9_-]*:", line):
            break
        item = re.match(r"^      -\s*(.*?)\s*$", line)
        if not item:
            if line.startswith("      "):
                raise SystemExit(f"enabled MCP arguments use an unsupported YAML form: {name}")
            break
        scalar = item.group(1)
        if scalar.startswith('"'):
            try:
                scalar = json.loads(scalar)
            except json.JSONDecodeError:
                raise SystemExit(f"enabled MCP argument is not a valid quoted scalar: {name}") from None
        elif scalar.startswith("'") and scalar.endswith("'") and len(scalar) >= 2:
            scalar = scalar[1:-1].replace("''", "'")
        elif " #" in scalar:
            scalar = scalar.split(" #", 1)[0].rstrip()
        if not isinstance(scalar, str):
            raise SystemExit(f"enabled MCP argument is not a string: {name}")
        result.append(scalar)
    return result


def homelab_package_identity(package_root: Path, selected_script: Path, source_repo: Path) -> dict[str, object]:
    """Verify an external homelab adapter against the exact clean Git package tree."""
    repo = source_repo.resolve(strict=True)
    if package_root.is_symlink() or not package_root.is_dir():
        raise SystemExit("homelab package root must be a real directory")
    try:
        root = package_root.resolve(strict=True)
        script = selected_script.resolve(strict=True)
    except (OSError, RuntimeError):
        raise SystemExit("homelab package paths could not be resolved") from None
    if Path(os.path.abspath(package_root)) != root or Path(os.path.abspath(selected_script)) != script:
        raise SystemExit("homelab package paths may not use symlinked parent aliases")
    if root == repo or root.is_relative_to(repo) or repo.is_relative_to(root):
        raise SystemExit("homelab package root must be separate from the HADES checkout")
    if selected_script.is_symlink() or script != root / "server.py" or not script.is_file():
        raise SystemExit("homelab profile must select the package server.py entrypoint")
    root_mode = root.stat().st_mode
    if root_mode & 0o7022:
        raise SystemExit("homelab package directory may not be group/world writable or use special mode bits")

    listing = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-r", "--name-only", "HEAD", "--", "integrations/homelab-readonly/"],
        check=False,
        capture_output=True,
    )
    if listing.returncode != 0:
        raise SystemExit("homelab package source tree could not be read from HADES Git")
    source_paths = sorted(
        item.decode("utf-8", errors="strict")
        for item in listing.stdout.splitlines()
        if item
    )
    prefix = "integrations/homelab-readonly/"
    if not source_paths or any(not item.startswith(prefix) for item in source_paths):
        raise SystemExit("HADES Git has no valid homelab adapter package tree")
    expected = {item[len(prefix):] for item in source_paths}
    if any(not item or Path(item).is_absolute() or ".." in Path(item).parts for item in expected):
        raise SystemExit("HADES Git contains an invalid homelab package path")

    actual: set[str] = set()
    for entry in root.iterdir():
        if entry.is_symlink() or not entry.is_file():
            raise SystemExit("homelab package may contain only regular top-level source files")
        actual.add(entry.name)
    if actual != expected:
        raise SystemExit("homelab package file set differs from the clean HADES Git tree")

    file_records: list[dict[str, str]] = []
    for relative in sorted(expected):
        external = root / relative
        if external.is_symlink() or not external.is_file():
            raise SystemExit("homelab package contains a non-regular source file")
        file_mode = external.stat().st_mode
        if not file_mode & 0o444 or file_mode & 0o7133:
            raise SystemExit("homelab package files must be readable and non-executable/non-writable by group or others")
        source = prefix + relative
        expected_bytes = subprocess.run(
            ["git", "-C", str(repo), "show", f"HEAD:{source}"],
            check=False,
            capture_output=True,
        )
        if expected_bytes.returncode != 0:
            raise SystemExit("homelab package source bytes could not be read from HADES Git")
        expected_sha = hashlib.sha256(expected_bytes.stdout).hexdigest()
        actual_sha = digest(external)
        if actual_sha != expected_sha:
            raise SystemExit("homelab package source differs from the clean HADES Git tree")
        file_records.append({"path": relative, "sha256": actual_sha})

    tree = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD:integrations/homelab-readonly"],
        check=False,
        capture_output=True,
        text=True,
    )
    if tree.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", tree.stdout.strip()):
        raise SystemExit("homelab package Git tree identity could not be verified")
    encoded = json.dumps(file_records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "transport": "stdio-package-source",
        "source": "integrations/homelab-readonly",
        "source_tree": tree.stdout.strip(),
        "package_tree_sha256": hashlib.sha256(encoded).hexdigest(),
        "file_count": len(file_records),
    }


def mcp_runtime_identity(
    profile_path: Path,
    environment: dict[str, str],
    source_repo: Path,
    homelab_package_root: Path | None = None,
    profile_text: str | None = None,
) -> tuple[list[dict[str, object]], str]:
    """Bind active MCP registrations to source bytes without emitting private values."""
    if profile_text is None:
        profile_bytes = read_regular_file(
            profile_path, "selected Hermes profile must be a stable regular file"
        )
        try:
            profile_text = profile_bytes.decode("utf-8", errors="strict")
        except UnicodeError:
            raise SystemExit("selected Hermes profile must be valid UTF-8") from None
    registrations = profile_server_blocks(profile_text)
    repo = source_repo.resolve(strict=True)
    records: list[dict[str, object]] = []
    homelab_package_used = False
    for name, block in sorted(registrations.items()):
        is_enabled = not bool(re.search(r"(?m)^    enabled:\s*false\s*$", block))
        row: dict[str, object] = {"name": name, "enabled": is_enabled}
        if not is_enabled:
            records.append(row)
            continue

        url_match = re.search(r"(?m)^    url:\s*(.+?)\s*$", block)
        if url_match:
            if name == "homelab-readonly":
                raise SystemExit("homelab-readonly must use a verified path-backed adapter package")
            raw = url_match.group(1).strip()
            if raw[:1] in {"'", '"'} and raw[-1:] == raw[:1]:
                raw = raw[1:-1]
            endpoint = expand_profile_value(raw, environment)
            if not endpoint:
                raise SystemExit(f"enabled HTTP MCP has no resolved endpoint: {name}")
            row.update({"transport": "http", "endpoint_sha256": hashlib.sha256(endpoint.encode()).hexdigest()})
            records.append(row)
            continue

        command_match = re.search(r"(?m)^    command:\s*(.+?)\s*$", block)
        if not command_match:
            raise SystemExit(f"enabled MCP has no supported command or URL: {name}")
        command = command_match.group(1).strip().strip("'\"")
        args = [expand_profile_value(item, environment) for item in profile_args(block, name)]

        script = next((item for item in args if item.endswith((".py", ".sh", ".js"))), "")
        if script:
            target = Path(script)
            if not target.is_absolute():
                target = repo / target
            try:
                resolved = target.resolve(strict=True)
                relative = resolved.relative_to(repo).as_posix()
            except (OSError, RuntimeError, ValueError):
                if name == "homelab-readonly" and homelab_package_root is not None:
                    executable_name = Path(command).name.strip("'\"")
                    if not re.fullmatch(r"python(?:[0-9]+(?:\.[0-9]+)*)?", executable_name):
                        raise SystemExit("homelab package mode requires a Python MCP command")
                    if len(args) != 1:
                        raise SystemExit("homelab package mode requires only the server.py argument")
                    row.update(homelab_package_identity(homelab_package_root, target, repo))
                    homelab_package_used = True
                    records.append(row)
                    continue
                raise SystemExit(f"enabled MCP source is outside the clean HADES checkout: {name}") from None
            if target.is_symlink() or not resolved.is_file():
                raise SystemExit(f"enabled MCP source is not a regular tracked file: {name}")
            blob = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", f"HEAD:{relative}"],
                check=False, capture_output=True, text=True,
            )
            file_sha = digest(resolved)
            if blob.returncode != 0 or len(blob.stdout.strip()) != 40:
                raise SystemExit(f"enabled MCP source is not tracked at the claimed HADES revision: {name}")
            expected_bytes = subprocess.run(
                ["git", "-C", str(repo), "show", f"HEAD:{relative}"],
                check=False, capture_output=True,
            )
            if expected_bytes.returncode != 0 or hashlib.sha256(expected_bytes.stdout).hexdigest() != file_sha:
                raise SystemExit(f"enabled MCP source bytes differ from the claimed HADES revision: {name}")
            row.update({"transport": "stdio-source", "source": relative, "sha256": file_sha})
        else:
            executable = expand_profile_value(command, environment)
            executable_path = Path(executable)
            if not executable_path.is_absolute():
                found = shutil.which(executable, path=environment.get("PATH"))
                if not found:
                    raise SystemExit(f"enabled MCP executable cannot be resolved: {name}")
                executable_path = Path(found)
            try:
                resolved_executable = executable_path.resolve(strict=True)
            except (OSError, RuntimeError):
                raise SystemExit(f"enabled MCP executable is unavailable: {name}") from None
            if executable_path.is_symlink() or not resolved_executable.is_file() or not os.access(resolved_executable, os.X_OK):
                raise SystemExit(f"enabled MCP executable is not a regular executable: {name}")
            row.update({"transport": "external-executable", "sha256": digest(resolved_executable)})
        records.append(row)

    if homelab_package_root is not None and not homelab_package_used:
        raise SystemExit("homelab package root was supplied but the selected profile did not use it")

    serialized = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return records, hashlib.sha256(serialized).hexdigest()


def verify_running_executable(arguments: list[str], executable: Path, module_runtime: bool) -> None:
    try:
        configured = executable.resolve()
        if module_runtime:
            running_paths = {Path(arguments[0]).resolve()} if arguments[0].startswith("/") else set()
            valid_entrypoint = len(arguments) > 2 and arguments[1:3] == ["-m", "hermes_cli.main"]
            matches = configured in running_paths and valid_entrypoint
        else:
            running_paths = {Path(item).resolve() for item in arguments if item.startswith("/")}
            matches = configured in running_paths
    except (OSError, RuntimeError):
        matches = False
    if not matches:
        raise SystemExit("running Hermes process differs from the configured service executable")


def verify_hermes_version(
    executable: Path,
    version: str,
    module_runtime: bool,
    process_environment: dict[str, str],
) -> str:
    if module_runtime:
        version_environment = dict(os.environ)
        if "PYTHONPATH" in process_environment:
            version_environment["PYTHONPATH"] = process_environment["PYTHONPATH"]
        else:
            version_environment.pop("PYTHONPATH", None)
        result = subprocess.run(
            [str(executable), "-c", "import importlib.metadata; print(importlib.metadata.version('hermes-agent'))"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env=version_environment,
        )
    else:
        result = subprocess.run(
            [str(executable), "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    reported = (result.stdout + "\n" + result.stderr).strip()
    if result.returncode != 0 or version not in reported:
        raise SystemExit("running Hermes executable version does not match the claimed runtime version")
    return reported


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--hades-sha", required=True)
    parser.add_argument(
        "--source-repo",
        required=True,
        type=Path,
        help="clean deployed HADES Git worktree whose HEAD is --hades-sha",
    )
    parser.add_argument(
        "--infra-repo",
        required=True,
        type=Path,
        help="clean deployed hades-infra Git worktree whose HEAD is --infra-sha",
    )
    parser.add_argument("--infra-sha", required=True)
    parser.add_argument("--hermes-version", required=True)
    parser.add_argument(
        "--hermes-executable",
        required=True,
        type=Path,
        help="the Hermes executable configured for the active systemd service",
    )
    parser.add_argument("--overlay", required=True, type=Path)
    parser.add_argument(
        "--overlay-composition-manifest", type=Path,
        help="optional source-bound manifest for a composed deployment-local Hermes overlay",
    )
    parser.add_argument(
        "--overlay-composition-base", type=Path,
        help="exact base overlay bytes used by the composition (required with the manifest)",
    )
    parser.add_argument(
        "--hermes-profile", required=True, type=Path,
        help="selected profiles/<name>/config.yaml under the active HERMES_HOME",
    )
    parser.add_argument("--task-store", required=True, type=Path, help="deployed integrations/task/store.py")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument(
        "--homelab-package-root",
        type=Path,
        help="external homelab adapter package directory, verified against integrations/homelab-readonly in the clean HADES tree",
    )
    parser.add_argument(
        "--epsilon-manifest",
        type=Path,
        help="optional generated config/epsilon-source/phase3-runtime-manifest.json",
    )
    parser.add_argument("--deployment-path", required=True)
    parser.add_argument("--service", required=True, help="active systemd unit that loads the overlay")
    args = parser.parse_args()
    if (args.overlay_composition_manifest is None) != (args.overlay_composition_base is None):
        raise SystemExit("overlay composition manifest and base must be supplied together")
    for name, value in (("hades SHA", args.hades_sha), ("infra SHA", args.infra_sha)):
        if len(value) != 40 or any(char not in "0123456789abcdef" for char in value.lower()):
            raise SystemExit(f"{name} must be a Git SHA")
    source_tree_sha256 = verify_source_checkout(args.source_repo, args.hades_sha, "HADES")
    infra_tree_sha256 = verify_source_checkout(args.infra_repo, args.infra_sha, "hades-infra")
    process_pid, process_started, process_arguments, process_environment = running_process_snapshot(args.service)
    configured_executable = process_environment.get("HADES_HERMES_EXECUTABLE", "")
    module_runtime = not configured_executable
    if module_runtime:
        if not (len(process_arguments) > 2 and process_arguments[1:3] == ["-m", "hermes_cli.main"]):
            raise SystemExit("service has neither a configured Hermes executable nor the supported Python-module entrypoint")
    elif Path(configured_executable).resolve() != args.hermes_executable.resolve():
        raise SystemExit("Hermes executable argument differs from the active service configuration")
    if not args.hermes_executable.is_file() or not os.access(args.hermes_executable, os.X_OK):
        raise SystemExit("running Hermes executable must be an executable regular file")
    verify_running_executable(process_arguments, args.hermes_executable, module_runtime)
    verify_hermes_version(
        args.hermes_executable, args.hermes_version, module_runtime, process_environment
    )
    hermes_profile_sha256, hermes_profile_text = verify_selected_profile(
        process_arguments, process_environment, args.hermes_profile
    )
    mcp_runtime, mcp_runtime_sha256 = mcp_runtime_identity(
        args.hermes_profile, process_environment, args.source_repo,
        args.homelab_package_root, profile_text=hermes_profile_text,
    )
    source_repo = args.source_repo.resolve()
    for supplied, relative, label in (
        (args.task_store, Path("integrations/task/store.py"), "TaskStore"),
        (args.manifest, Path("config/reconstruction-manifest.json"), "reconstruction manifest"),
    ):
        expected = source_repo / relative
        if not expected.is_file() or expected.is_symlink():
            raise SystemExit(f"source repository is missing the committed {label}")
        if not supplied.is_file() or supplied.is_symlink() or digest(supplied) != digest(expected):
            raise SystemExit(f"deployed {label} does not match the claimed source revision")
    selected_overlay = active_overlay(process_environment)
    if not args.overlay.is_file() or args.overlay.is_symlink():
        raise SystemExit(f"regular overlay file required: {args.overlay}")
    if args.overlay.resolve() != selected_overlay.resolve():
        raise SystemExit(
            "overlay argument differs from the active service PYTHONPATH sitecustomize.py"
        )
    overlay_bytes = read_regular_file(args.overlay, "regular overlay file required")
    overlay_sha256 = hashlib.sha256(overlay_bytes).hexdigest()
    composition_manifest = None
    composition_manifest_sha256 = None
    composition_base_sha256 = None
    if args.overlay_composition_manifest is not None:
        composition_manifest, composition_manifest_sha256, composition_base_bytes = load_overlay_composition(
            args.overlay_composition_manifest, args.overlay_composition_base,
            args.source_repo, overlay_bytes,
        )
        composition_base_sha256 = hashlib.sha256(composition_base_bytes).hexdigest()
    task_store_sha256 = digest(args.task_store)
    manifest_sha256 = digest(args.manifest)
    hermes_executable_sha256 = digest(args.hermes_executable.resolve())
    epsilon_manifest_sha256 = digest(args.epsilon_manifest) if args.epsilon_manifest is not None else None

    # Recheck the process identity and every source/deployment artifact before
    # writing. This rejects restart and replacement races during collection.
    verify_process_snapshot_current(args.service, process_pid, process_started)
    if digest(args.hermes_profile) != hermes_profile_sha256:
        raise SystemExit("Hermes profile changed during provenance capture")
    if digest(args.overlay) != overlay_sha256:
        raise SystemExit("Hermes overlay changed during provenance capture")
    if args.overlay_composition_manifest is not None:
        if digest(args.overlay_composition_manifest) != composition_manifest_sha256:
            raise SystemExit("overlay composition manifest changed during provenance capture")
        if digest(args.overlay_composition_base) != composition_base_sha256:
            raise SystemExit("overlay composition base changed during provenance capture")
    if digest(args.task_store) != task_store_sha256 or digest(args.manifest) != manifest_sha256:
        raise SystemExit("deployed HADES source artifact changed during provenance capture")
    if digest(args.hermes_executable.resolve()) != hermes_executable_sha256:
        raise SystemExit("Hermes executable changed during provenance capture")
    if args.epsilon_manifest is not None and digest(args.epsilon_manifest) != epsilon_manifest_sha256:
        raise SystemExit("Epsilon runtime manifest changed during provenance capture")
    current_mcp_runtime, current_mcp_runtime_sha256 = mcp_runtime_identity(
        args.hermes_profile, process_environment, args.source_repo,
        args.homelab_package_root, profile_text=hermes_profile_text,
    )
    if current_mcp_runtime != mcp_runtime or current_mcp_runtime_sha256 != mcp_runtime_sha256:
        raise SystemExit("MCP runtime artifacts changed during provenance capture")
    if verify_source_checkout(args.source_repo, args.hades_sha, "HADES") != source_tree_sha256:
        raise SystemExit("HADES source checkout changed during provenance capture")
    if verify_source_checkout(args.infra_repo, args.infra_sha, "hades-infra") != infra_tree_sha256:
        raise SystemExit("hades-infra source checkout changed during provenance capture")
    for supplied, relative, label in (
        (args.task_store, Path("integrations/task/store.py"), "TaskStore"),
        (args.manifest, Path("config/reconstruction-manifest.json"), "reconstruction manifest"),
    ):
        if digest(supplied) != digest(source_repo / relative):
            raise SystemExit(f"deployed {label} changed during provenance capture")
    verify_process_snapshot_current(args.service, process_pid, process_started)

    artifact = {
        "schema": "hades/deployed-provenance/v1",
        "hades_sha": args.hades_sha,
        "hades_tree_sha256": source_tree_sha256,
        "infra_sha": args.infra_sha,
        "infra_tree_sha256": infra_tree_sha256,
        "hermes_version": args.hermes_version,
        "hermes_runtime_kind": "python-module" if module_runtime else "configured-executable",
        "hermes_executable": str(args.hermes_executable.resolve()),
        "hermes_executable_sha256": hermes_executable_sha256,
        "overlay_sha256": overlay_sha256,
        "hermes_profile_sha256": hermes_profile_sha256,
        "mcp_runtime": mcp_runtime,
        "mcp_runtime_sha256": mcp_runtime_sha256,
        "task_store_sha256": task_store_sha256,
        "manifest_sha256": manifest_sha256,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "deployment_path": args.deployment_path,
        "classification": "tested-source-and-current-disk-artifact-identity",
    }
    if composition_manifest is not None:
        artifact["overlay_composition"] = {
            "manifest_sha256": composition_manifest_sha256,
            "schema": composition_manifest["schema"],
            "source_revision": composition_manifest["source_revision"],
            "source_tree": composition_manifest["source_tree"],
            "base_overlay_sha256": composition_manifest["base_overlay_sha256"],
            "wrapper_sha256": composition_manifest["wrapper_sha256"],
            "final_overlay_sha256": composition_manifest["final_overlay_sha256"],
        }
    if epsilon_manifest_sha256 is not None:
        artifact["epsilon_package_manifest_sha256"] = epsilon_manifest_sha256
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".hades-provenance-", dir=args.output.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(artifact, stream, sort_keys=True, indent=2)
            stream.write("\n")
        os.replace(temp_name, args.output)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    args.output.chmod(0o600)
    # The protected record contains deployment paths, executable identity,
    # private source fingerprints, and runtime registrations. Keep it in the
    # mode-0600 artifact; command logs should receive only a safe summary.
    print("PASS deployed provenance artifact written (mode=0600)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
