#!/usr/bin/env python3
"""Write the bounded machine-readable identity of a tested deployment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def digest(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise SystemExit(f"regular file required: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def active_environment(service: str) -> dict[str, str]:
    active = subprocess.run(
        ["systemctl", "is-active", "--quiet", service],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if active.returncode != 0:
        raise SystemExit(f"Hermes service is not active: {service}")
    result = subprocess.run(
        ["systemctl", "show", "--property=Environment", "--value", service],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"could not read effective environment for service: {service}")
    environment = {}
    for item in shlex.split(result.stdout):
        if "=" in item:
            key, value = item.split("=", 1)
            environment[key] = value
    return environment


def active_overlay(service: str) -> Path:
    environment = active_environment(service)
    pythonpath = environment.get("PYTHONPATH", "")
    if not pythonpath:
        raise SystemExit(f"service has no effective PYTHONPATH: {service}")
    for entry in pythonpath.split(os.pathsep):
        candidate = Path(entry) / "sitecustomize.py"
        if candidate.exists():
            if not candidate.is_file() or candidate.is_symlink():
                raise SystemExit("effective Hermes sitecustomize must be a regular non-symlink file")
            return candidate
    raise SystemExit("effective Hermes PYTHONPATH contains no sitecustomize.py")


def running_process_arguments(service: str) -> list[str]:
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
    try:
        command_line = (Path("/proc") / str(pid) / "cmdline").read_bytes().split(b"\0")
        arguments = [item.decode("utf-8", errors="strict") for item in command_line if item]
    except (OSError, UnicodeError, RuntimeError):
        raise SystemExit("active Hermes process command line could not be verified") from None
    if not arguments:
        raise SystemExit("active Hermes process has an empty command line")
    return arguments


def running_process_environment(service: str) -> dict[str, str]:
    result = subprocess.run(
        ["systemctl", "show", "--property=MainPID", "--value", service],
        check=False, capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip().isdigit():
        raise SystemExit("active Hermes service has no verifiable MainPID")
    pid = int(result.stdout.strip())
    try:
        items = (Path("/proc") / str(pid) / "environ").read_bytes().split(b"\0")
        environment = {}
        for item in items:
            if b"=" not in item:
                continue
            key, value = item.split(b"=", 1)
            environment[key.decode("utf-8", errors="strict")] = value.decode("utf-8", errors="strict")
        return environment
    except (OSError, UnicodeError, RuntimeError):
        raise SystemExit("running Hermes process environment could not be read for source resolution") from None


def verify_selected_profile(
    arguments: list[str], environment: dict[str, str], supplied_profile: Path
) -> str:
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
    return digest(supplied_profile)


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


def homelab_source_package_files(repo: Path) -> dict[str, str]:
    """Return the committed Python files that make up the homelab adapter."""
    package_relative = "integrations/homelab-readonly"
    package_directory = repo / package_relative
    for directory in (repo / "integrations", package_directory):
        if directory.is_symlink() or not directory.is_dir():
            raise SystemExit("homelab MCP source package path is missing or not a real directory")
    listed = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z", "--", package_relative],
        check=False,
        capture_output=True,
    )
    if listed.returncode != 0:
        raise SystemExit("homelab MCP package membership could not be verified")

    source_files: dict[str, str] = {}
    for raw_path in listed.stdout.split(b"\0"):
        if not raw_path:
            continue
        try:
            relative = raw_path.decode("utf-8", errors="strict")
        except UnicodeError:
            raise SystemExit("homelab MCP package has an invalid tracked path") from None
        if not relative.startswith(package_relative + "/") or not relative.endswith(".py"):
            continue
        candidate = repo / relative
        try:
            resolved_candidate = candidate.resolve(strict=True)
            resolved_candidate.relative_to(package_directory.resolve(strict=True))
        except (OSError, RuntimeError, ValueError):
            raise SystemExit("homelab MCP source package contains a missing or unsafe module path") from None
        if candidate.is_symlink() or resolved_candidate != candidate or not candidate.is_file():
            raise SystemExit("homelab MCP package contains a missing or non-regular Python module")
        committed = subprocess.run(
            ["git", "-C", str(repo), "show", f"HEAD:{relative}"],
            check=False,
            capture_output=True,
        )
        if committed.returncode != 0:
            raise SystemExit("homelab MCP package module is not present at the claimed revision")
        file_sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if hashlib.sha256(committed.stdout).hexdigest() != file_sha:
            raise SystemExit(
                "homelab MCP package contains a module that differs from the claimed revision"
            )
        source_files[relative[len(package_relative) + 1:]] = file_sha

    if "server.py" not in source_files:
        raise SystemExit("homelab MCP entrypoint is missing from its tracked Python package")
    return source_files


def homelab_package_identity(
    selected_script: Path, environment: dict[str, str], repo: Path
) -> dict[str, object]:
    """Bind the selected homelab MCP package, including generated copies, to source."""
    package_relative = "integrations/homelab-readonly"
    source_directory = repo / package_relative
    source_files = homelab_source_package_files(repo)
    script = selected_script.absolute()
    if script.is_symlink() or script.name != "server.py":
        raise SystemExit("selected homelab MCP entrypoint is not a regular server.py")

    if script == source_directory / "server.py":
        runtime_directory = source_directory
    else:
        root_value = environment.get("HADES_INTEGRATIONS_ROOT", "").strip()
        if not root_value or not Path(root_value).is_absolute():
            raise SystemExit("generated homelab MCP package has no absolute integration root")
        integration_root = Path(root_value)
        if (
            integration_root.is_symlink()
            or not integration_root.is_dir()
            or integration_root.resolve(strict=True) != integration_root
        ):
            raise SystemExit("generated homelab integration root is missing or not a real directory")
        runtime_directory = script.parent
        if not re.fullmatch(r"homelab-readonly-[A-Za-z0-9_-]{6,64}", runtime_directory.name):
            raise SystemExit("selected generated homelab MCP package has an unsupported directory name")
        try:
            relative_runtime = runtime_directory.relative_to(integration_root)
        except ValueError:
            raise SystemExit("selected generated homelab MCP package is outside the integration root") from None
        if not relative_runtime.parts:
            raise SystemExit("selected generated homelab MCP package path is invalid")
        ancestor = integration_root
        for part in relative_runtime.parts:
            ancestor = ancestor / part
            if ancestor.is_symlink() or not ancestor.is_dir():
                raise SystemExit("generated homelab MCP package path contains a symlink or missing directory")
        if runtime_directory.resolve(strict=True) != runtime_directory:
            raise SystemExit("generated homelab MCP package path is not canonical")

    for entry in runtime_directory.rglob("*"):
        if entry.is_symlink():
            raise SystemExit("selected homelab MCP package contains a symlink")
    runtime_files: dict[str, str] = {}
    for candidate in runtime_directory.rglob("*.py"):
        if candidate.is_symlink() or not candidate.is_file():
            raise SystemExit("selected homelab MCP package contains a non-regular Python module")
        relative = candidate.relative_to(runtime_directory).as_posix()
        runtime_files[relative] = digest(candidate)
    if runtime_files.keys() != source_files.keys():
        raise SystemExit("selected homelab MCP package module set differs from the claimed revision")
    if runtime_files != source_files:
        raise SystemExit("selected homelab MCP package bytes differ from the claimed revision")

    package_files = [
        {"source": f"{package_relative}/{relative}", "sha256": file_sha}
        for relative, file_sha in sorted(runtime_files.items())
    ]
    serialized = json.dumps(package_files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"files": package_files, "sha256": hashlib.sha256(serialized).hexdigest()}


def mcp_runtime_identity(
    profile_path: Path, environment: dict[str, str], source_repo: Path
) -> tuple[list[dict[str, object]], str]:
    """Bind active MCP registrations to source bytes without emitting private values."""
    registrations = profile_server_blocks(profile_path.read_text(encoding="utf-8"))
    repo = source_repo.resolve(strict=True)
    records: list[dict[str, object]] = []
    for name, block in sorted(registrations.items()):
        is_enabled = not bool(re.search(r"(?m)^    enabled:\s*false\s*$", block))
        row: dict[str, object] = {"name": name, "enabled": is_enabled}
        if not is_enabled:
            records.append(row)
            continue

        url_match = re.search(r"(?m)^    url:\s*(.+?)\s*$", block)
        if url_match:
            if name == "homelab-readonly":
                raise SystemExit(
                    "enabled homelab-readonly MCP must bind a path-backed server.py package"
                )
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
        if name == "homelab-readonly" and (
            not re.fullmatch(r"python(?:[0-9]+(?:\.[0-9]+)*)?", Path(command).name)
            or not script or not args or script != args[0] or not script.endswith(".py")
        ):
            raise SystemExit(
                "enabled homelab-readonly MCP must launch a path-backed server.py package"
            )
        if script:
            target = Path(script)
            if not target.is_absolute():
                target = repo / target
            source_homelab_entry = repo / "integrations/homelab-readonly/server.py"
            versioned_homelab_entry = (
                target.name == "server.py"
                and bool(
                    re.fullmatch(
                        r"homelab-readonly-[A-Za-z0-9_-]{6,64}", target.parent.name
                    )
                )
            )
            if (
                name == "homelab-readonly"
                or target.absolute() == source_homelab_entry
                or versioned_homelab_entry
            ):
                package_identity = homelab_package_identity(target, environment, repo)
                package_files = package_identity["files"]
                server_source = "integrations/homelab-readonly/server.py"
                server_file = next(item for item in package_files if item["source"] == server_source)
                row.update({
                    "transport": "stdio-source",
                    "source": server_source,
                    "sha256": server_file["sha256"],
                    "package": package_identity,
                })
                records.append(row)
                continue
            try:
                resolved = target.resolve(strict=True)
                relative = resolved.relative_to(repo).as_posix()
            except (OSError, RuntimeError, ValueError):
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


def verify_hermes_version(executable: Path, version: str, module_runtime: bool) -> str:
    if module_runtime:
        result = subprocess.run(
            [str(executable), "-c", "import importlib.metadata; print(importlib.metadata.version('hermes-agent'))"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
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
        "--hermes-profile", required=True, type=Path,
        help="selected profiles/<name>/config.yaml under the active HERMES_HOME",
    )
    parser.add_argument("--task-store", required=True, type=Path, help="deployed integrations/task/store.py")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument(
        "--epsilon-manifest",
        type=Path,
        help="optional generated config/epsilon-source/phase3-runtime-manifest.json",
    )
    parser.add_argument("--deployment-path", required=True)
    parser.add_argument("--service", required=True, help="active systemd unit that loads the overlay")
    args = parser.parse_args()
    for name, value in (("hades SHA", args.hades_sha), ("infra SHA", args.infra_sha)):
        if len(value) != 40 or any(char not in "0123456789abcdef" for char in value.lower()):
            raise SystemExit(f"{name} must be a Git SHA")
    source_tree_sha256 = verify_source_checkout(args.source_repo, args.hades_sha, "HADES")
    infra_tree_sha256 = verify_source_checkout(args.infra_repo, args.infra_sha, "hades-infra")
    service_environment = active_environment(args.service)
    configured_executable = service_environment.get("HADES_HERMES_EXECUTABLE", "")
    process_arguments = running_process_arguments(args.service)
    module_runtime = not configured_executable
    if module_runtime:
        if not (len(process_arguments) > 2 and process_arguments[1:3] == ["-m", "hermes_cli.main"]):
            raise SystemExit("service has neither a configured Hermes executable nor the supported Python-module entrypoint")
    elif Path(configured_executable).resolve() != args.hermes_executable.resolve():
        raise SystemExit("Hermes executable argument differs from the active service configuration")
    if not args.hermes_executable.is_file() or not os.access(args.hermes_executable, os.X_OK):
        raise SystemExit("running Hermes executable must be an executable regular file")
    verify_running_executable(process_arguments, args.hermes_executable, module_runtime)
    verify_hermes_version(args.hermes_executable, args.hermes_version, module_runtime)
    hermes_profile_sha256 = verify_selected_profile(
        process_arguments, service_environment, args.hermes_profile
    )
    runtime_environment = {**service_environment, **running_process_environment(args.service)}
    mcp_runtime, mcp_runtime_sha256 = mcp_runtime_identity(
        args.hermes_profile, runtime_environment, args.source_repo
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
    selected_overlay = active_overlay(args.service)
    if not args.overlay.is_file() or args.overlay.is_symlink():
        raise SystemExit(f"regular overlay file required: {args.overlay}")
    if args.overlay.resolve() != selected_overlay.resolve():
        raise SystemExit(
            "overlay argument differs from the active service PYTHONPATH sitecustomize.py"
        )
    artifact = {
        "schema": "hades/deployed-provenance/v1",
        "hades_sha": args.hades_sha,
        "hades_tree_sha256": source_tree_sha256,
        "infra_sha": args.infra_sha,
        "infra_tree_sha256": infra_tree_sha256,
        "hermes_version": args.hermes_version,
        "hermes_runtime_kind": "python-module" if module_runtime else "configured-executable",
        "hermes_executable": str(args.hermes_executable.resolve()),
        "hermes_executable_sha256": digest(args.hermes_executable.resolve()),
        "overlay_sha256": digest(args.overlay),
        "hermes_profile_sha256": hermes_profile_sha256,
        "mcp_runtime": mcp_runtime,
        "mcp_runtime_sha256": mcp_runtime_sha256,
        "task_store_sha256": digest(args.task_store),
        "manifest_sha256": digest(args.manifest),
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "deployment_path": args.deployment_path,
        "classification": "tested-source-and-deployment-artifact-identity",
    }
    if args.epsilon_manifest is not None:
        artifact["epsilon_package_manifest_sha256"] = digest(args.epsilon_manifest)
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
    print(json.dumps(artifact, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
