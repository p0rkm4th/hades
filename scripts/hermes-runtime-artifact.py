#!/usr/bin/env python3
"""Build and verify the canonical Hermes runtime source bundle.

The current production contract is an identity composition: the runtime file is
an exact copy of the tracked ``hermes/sitecustomize.py`` source. Deployment
configuration is fingerprinted separately and never copied into public source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
import grp
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA = "hades/hermes-runtime-overlay/v2"
SOURCE = "hermes/sitecustomize.py"
SUPPORT_SOURCE = "integrations/homelab_views.py"
SUPPORT_FILENAME = "homelab_views.py"
TOOL = "scripts/hermes-runtime-artifact.py"
MANIFEST_FIELDS = {
    "schema", "hades_git_sha", "hades_tree_sha256", "hermes_version",
    "input_artifact_sha256", "supporting_artifacts", "composition", "composition_tool",
    "configuration_inputs", "runtime_configuration_id", "generated_artifact", "manifest_id",
}
VERSION_RE = re.compile(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
LABEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")


class RuntimeUnknown(ValueError):
    """Live identity could not be observed well enough to classify drift."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def read_regular(path: Path) -> bytes:
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("not regular")
        chunks = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(fd)
        before_key = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        after_key = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        data = b"".join(chunks)
        if before_key != after_key or len(data) != after.st_size:
            raise ValueError("changed during read")
        return data
    except (OSError, ValueError):
        raise ValueError(f"required file is unavailable or unstable: {path.name}") from None
    finally:
        if fd is not None:
            os.close(fd)


def git(repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        raise ValueError("source repository identity is unavailable") from None
    return result.stdout.strip()


def tracked_bytes(repo: Path, relative: str) -> bytes:
    try:
        expected = subprocess.run(
            ["git", "-C", str(repo), "show", f"HEAD:{relative}"],
            check=True, capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        raise ValueError(f"tracked source is unavailable: {relative}") from None
    actual = read_regular(repo / relative)
    if actual != expected:
        raise ValueError(f"working file differs from tracked source: {relative}")
    return actual


def config_inputs(specifications: list[str]) -> list[dict[str, str]]:
    values: dict[str, str] = {}
    for specification in specifications:
        if "=" not in specification:
            raise ValueError("configuration inputs must use NAME=PATH or NAME=sha256:HEX")
        name, value = specification.split("=", 1)
        if not LABEL_RE.fullmatch(name) or name in values:
            raise ValueError("configuration input names must be unique safe labels")
        if value.startswith("sha256:"):
            digest = value[7:]
            if not SHA256_RE.fullmatch(digest):
                raise ValueError("configuration input digest is malformed")
        else:
            digest = sha256(read_regular(Path(value)))
        values[name] = digest
    if not values:
        raise ValueError("at least one deployment configuration identity is required")
    return [{"name": name, "sha256": values[name]} for name in sorted(values)]


def manifest_for(repo: Path, hermes_version: str, inputs: list[dict[str, str]]) -> tuple[dict[str, Any], bytes, bytes]:
    if not VERSION_RE.fullmatch(hermes_version):
        raise ValueError("Hermes version must be explicit and version-shaped")
    root = repo.resolve(strict=True)
    if git(root, "rev-parse", "--show-toplevel") != str(root):
        raise ValueError("source repository must be its Git worktree root")
    if git(root, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("source repository must be clean")
    revision = git(root, "rev-parse", "HEAD")
    tree = git(root, "rev-parse", "HEAD^{tree}")
    source = tracked_bytes(root, SOURCE)
    support = tracked_bytes(root, SUPPORT_SOURCE)
    tool = tracked_bytes(root, TOOL)
    compile(source, SOURCE, "exec")
    compile(support, SUPPORT_SOURCE, "exec")
    artifact_sha = sha256(source)
    support_sha = sha256(support)
    core: dict[str, Any] = {
        "schema": SCHEMA,
        "hades_git_sha": revision,
        "hades_tree_sha256": tree,
        "hermes_version": hermes_version,
        "input_artifact_sha256": {SOURCE: artifact_sha, SUPPORT_SOURCE: support_sha},
        "supporting_artifacts": {SUPPORT_SOURCE: {"path": SUPPORT_FILENAME, "sha256": support_sha}},
        "composition": "runtime-source-bundle-copy",
        "composition_tool": {"path": TOOL, "sha256": sha256(tool)},
        "configuration_inputs": inputs,
        "runtime_configuration_id": sha256(canonical_json(inputs)),
        "generated_artifact": {"path": "sitecustomize.py", "sha256": artifact_sha},
    }
    core["manifest_id"] = sha256(canonical_json(core))
    return core, source, support


def write_new(path: Path, data: bytes) -> None:
    if not path.is_absolute() or not path.parent.is_dir() or path.exists() or path.is_symlink():
        raise ValueError("outputs must be new absolute paths in existing directories")
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def load_manifest(path: Path) -> dict[str, Any]:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate manifest key")
            result[key] = value
        return result
    try:
        value = json.loads(read_regular(path), object_pairs_hook=unique)
    except (UnicodeError, json.JSONDecodeError, ValueError):
        raise ValueError("runtime artifact manifest is malformed") from None
    if not isinstance(value, dict):
        raise ValueError("runtime artifact manifest must be an object")
    return value


def support_artifact_sha(manifest: dict[str, Any]) -> str:
    supporting = manifest.get("supporting_artifacts")
    support = supporting.get(SUPPORT_SOURCE) if isinstance(supporting, dict) else None
    digest = support.get("sha256") if isinstance(support, dict) else None
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest) or support.get("path") != SUPPORT_FILENAME:
        raise ValueError("runtime manifest support-artifact identity is invalid")
    return digest


def command_build(args: argparse.Namespace) -> int:
    root = args.source_repo.resolve(strict=True)
    inputs = config_inputs(args.config_input)
    manifest, artifact, support = manifest_for(root, args.hermes_version, inputs)
    support_output = args.artifact.absolute().with_name(SUPPORT_FILENAME)
    if len({args.artifact.absolute(), args.manifest.absolute(), support_output}) != 3:
        raise ValueError("bundle artifacts and manifest must use distinct output files")
    artifact_created = support_created = False
    try:
        write_new(args.artifact.absolute(), artifact)
        artifact_created = True
        write_new(support_output, support)
        support_created = True
        write_new(args.manifest.absolute(), json.dumps(manifest, sort_keys=True, indent=2).encode() + b"\n")
    except BaseException:
        if support_created:
            support_output.unlink(missing_ok=True)
        if artifact_created:
            args.artifact.unlink(missing_ok=True)
        raise
    print(f"PASS runtime artifact built: sha256={manifest['generated_artifact']['sha256']} manifest={manifest['manifest_id']}")
    return 0


def command_verify(args: argparse.Namespace) -> int:
    manifest, source, support = manifest_for(args.source_repo.resolve(strict=True), args.hermes_version, config_inputs(args.config_input))
    actual_manifest = load_manifest(args.manifest)
    actual_artifact = read_regular(args.artifact)
    if actual_manifest != manifest:
        raise ValueError("runtime artifact manifest differs from canonical source/configuration")
    if actual_artifact != source:
        raise ValueError("runtime artifact differs from the canonical tracked source")
    support_path = args.artifact.absolute().with_name(SUPPORT_FILENAME)
    if read_regular(support_path) != support:
        raise ValueError("runtime support artifact differs from canonical tracked source")
    expected_digest = manifest["generated_artifact"]["sha256"]
    if sha256(actual_artifact) != expected_digest:
        raise ValueError("runtime artifact checksum differs from manifest")
    if args.installed is not None and sha256(read_regular(args.installed)) != expected_digest:
        raise ValueError("installed runtime file differs from the qualified artifact")
    if args.installed_support is not None and sha256(read_regular(args.installed_support)) != manifest["supporting_artifacts"][SUPPORT_SOURCE]["sha256"]:
        raise ValueError("installed runtime support file differs from the qualified artifact")
    print(f"EXPECTED source={manifest['hades_git_sha'][:12]} hermes={manifest['hermes_version']} artifact_sha256={expected_digest} support_sha256={manifest['supporting_artifacts'][SUPPORT_SOURCE]['sha256']} manifest={manifest['manifest_id']}")
    return 0


def command_fingerprint(args: argparse.Namespace) -> int:
    inputs = config_inputs(args.config_input)
    print("\n".join(f"{item['name']}=sha256:{item['sha256']}" for item in inputs))
    print(f"runtime_configuration_id=sha256:{sha256(canonical_json(inputs))}")
    return 0


def command_verify_config(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    if set(manifest) != MANIFEST_FIELDS:
        raise ValueError("runtime manifest fields differ from the supported schema")
    core = {key: value for key, value in manifest.items() if key != "manifest_id"}
    if manifest.get("schema") != SCHEMA or manifest.get("manifest_id") != sha256(canonical_json(core)):
        raise ValueError("runtime manifest identity is invalid")
    supplied = config_inputs(args.config_input)
    if supplied != manifest.get("configuration_inputs"):
        raise ValueError("live deployment configuration differs from the qualified manifest")
    if sha256(canonical_json(supplied)) != manifest.get("runtime_configuration_id"):
        raise ValueError("live deployment configuration identity differs from the manifest")
    print(f"EXPECTED manifest={manifest['manifest_id']} runtime_configuration_id={manifest['runtime_configuration_id']}")
    return 0


def _systemctl(*args: str) -> str:
    result = subprocess.run(["systemctl", *args], check=False, capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise RuntimeUnknown("systemd runtime identity is unavailable")
    return result.stdout.strip()


def _pid_snapshot(service: str) -> tuple[int, list[str], dict[str, str], float]:
    if _systemctl("is-active", service) != "active":
        raise RuntimeUnknown("Hermes service is not active; loaded runtime identity is unknown")
    raw_pid = _systemctl("show", "--property=MainPID", "--value", service)
    if not raw_pid.isdigit() or int(raw_pid) <= 1:
        raise ValueError("Hermes service has no valid MainPID")
    pid = int(raw_pid)
    root = Path("/proc") / str(pid)
    try:
        command = [part.decode("utf-8", "strict") for part in (root / "cmdline").read_bytes().split(bytes([0])) if part]
        environment = {}
        for part in (root / "environ").read_bytes().split(bytes([0])):
            if b"=" in part:
                key, value = part.split(b"=", 1)
                environment[key.decode("utf-8", "strict")] = value.decode("utf-8", "strict")
        raw_stat = (root / "stat").read_text(encoding="ascii")
        close = raw_stat.rfind(")")
        fields = raw_stat[close + 2:].split()
        ticks = int(fields[19])
        boot = next(int(line.split()[1]) for line in Path("/proc/stat").read_text().splitlines() if line.startswith("btime "))
        started = boot + ticks / os.sysconf("SC_CLK_TCK")
        exe = (root / "exe").resolve()
        cwd = (root / "cwd").resolve()
    except (OSError, ValueError, IndexError, UnicodeError, StopIteration):
        raise RuntimeUnknown("Hermes process identity could not be read") from None
    if not command or _systemctl("show", "--property=MainPID", "--value", service) != str(pid):
        raise RuntimeUnknown("Hermes process changed during inspection")
    return pid, command, environment, started


def command_verify_live(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest) if args.manifest is not None else None
    expected_id = None
    expected_support_sha = None
    if manifest is not None:
        if args.expected_manifest_sha256 and sha256(read_regular(args.manifest)) != args.expected_manifest_sha256:
            raise ValueError("runtime manifest checksum differs from the approved identity")
        if set(manifest) != MANIFEST_FIELDS:
            raise ValueError("runtime manifest fields differ from the supported schema")
        supplied_inputs = config_inputs(args.config_input)
        expected_id = manifest.get("manifest_id")
        core = {key: value for key, value in manifest.items() if key != "manifest_id"}
        if not isinstance(expected_id, str) or sha256(canonical_json(core)) != expected_id:
            raise ValueError("runtime artifact manifest identity is invalid")
        if manifest.get("schema") != SCHEMA or manifest.get("configuration_inputs") != supplied_inputs:
            raise ValueError("runtime artifact configuration differs from the approved manifest")
        if sha256(canonical_json(supplied_inputs)) != manifest.get("runtime_configuration_id"):
            raise ValueError("runtime configuration identity differs from the approved manifest")
        generated = manifest.get("generated_artifact")
        source_hashes = manifest.get("input_artifact_sha256")
        expected_sha = generated.get("sha256") if isinstance(generated, dict) else None
        expected_support_sha = support_artifact_sha(manifest)
        if (
            manifest.get("composition") != "runtime-source-bundle-copy"
            or not isinstance(source_hashes, dict)
            or source_hashes.get(SOURCE) != expected_sha
            or source_hashes.get(SUPPORT_SOURCE) != expected_support_sha
            or not isinstance(expected_sha, str)
            or not SHA256_RE.fullmatch(expected_sha)
        ):
            raise ValueError("runtime manifest source/artifact relationship is invalid")
        if args.expected_sha256 and args.expected_sha256 != expected_sha:
            raise ValueError("explicit expected checksum differs from the manifest")
    else:
        expected_sha = args.expected_sha256
        if not isinstance(expected_sha, str) or not SHA256_RE.fullmatch(expected_sha):
            raise ValueError("a valid expected checksum is required when no manifest is supplied")
        if not args.hermes_version or not VERSION_RE.fullmatch(args.hermes_version):
            raise ValueError("an explicit Hermes version is required when no manifest is supplied")
    if args.artifact is not None:
        candidate = read_regular(args.artifact)
        if sha256(candidate) != expected_sha:
            raise ValueError("candidate artifact checksum differs from the approved identity")
    if manifest is not None:
        installed_support = args.installed.parent / SUPPORT_FILENAME
        if sha256(read_regular(installed_support)) != expected_support_sha:
            raise ValueError("installed runtime support file differs from the approved identity")
        if args.artifact is not None and sha256(read_regular(args.artifact.parent / SUPPORT_FILENAME)) != expected_support_sha:
            raise ValueError("candidate runtime support file differs from the approved identity")
    installed = read_regular(args.installed)
    if sha256(installed) != expected_sha:
        raise ValueError("installed artifact checksum differs from the approved identity")

    pid, command, environment, started = _pid_snapshot(args.service)
    if not command or "-S" in command or "-I" in command or "hermes_cli.main" not in command:
        raise ValueError("Hermes process does not use the expected Python module entrypoint")
    python_path = args.python.resolve(strict=True)
    process_exe = (Path("/proc") / str(pid) / "exe").resolve(strict=True)
    if process_exe != python_path:
        raise ValueError("Hermes process executable differs from the qualified interpreter")
    loaded_path = None
    pythonpath = environment.get("PYTHONPATH", "")
    if not pythonpath:
        raise ValueError("Hermes process PYTHONPATH is unavailable")
    for entry in pythonpath.split(os.pathsep):
        candidate_path = Path(entry) / "sitecustomize.py"
        if candidate_path.exists():
            loaded_path = candidate_path.resolve(strict=True)
            break
    if loaded_path is None or loaded_path != args.installed.resolve(strict=True):
        raise ValueError("installed artifact is not the sitecustomize selected by the service PYTHONPATH")
    installed_stat = args.installed.stat()
    if installed_stat.st_ctime > started + 1.0:
        raise ValueError("installed artifact changed after the current Hermes process started")
    if expected_support_sha is not None:
        support_stat = (args.installed.parent / SUPPORT_FILENAME).stat()
        if support_stat.st_ctime > started + 1.0:
            raise ValueError("installed runtime support changed after the Hermes process started")

    # Re-run the same interpreter entry environment as the service. The import
    # probe reports only module identity; deployment values remain in memory.
    user_name = _systemctl("show", "--property=User", "--value", args.service)
    group_name = _systemctl("show", "--property=Group", "--value", args.service)
    if os.geteuid() != 0:
        raise ValueError("live verification must run with permission to inspect the service process")
    try:
        uid = pwd.getpwnam(user_name).pw_uid if user_name else 0
        gid = grp.getgrnam(group_name).gr_gid if group_name else 0
        groups = os.getgrouplist(user_name, gid) if user_name else []
        cwd = (Path("/proc") / str(pid) / "cwd").resolve(strict=True)
    except (KeyError, OSError):
        raise ValueError("Hermes service identity could not be resolved") from None
    probe = (
        "import hashlib,importlib.metadata,json,sitecustomize; "
        "p=sitecustomize.__file__; "
        "report={'path':p,'sha256':hashlib.sha256(open(p,'rb').read()).hexdigest(),"
        "'version':importlib.metadata.version('hermes-agent')}"
    )
    if expected_support_sha is not None:
        probe += (
            "; m=__import__('homelab_views'); report.update({'support_path':m.__file__,"
            "'support_sha256':hashlib.sha256(open(m.__file__,'rb').read()).hexdigest()})"
        )
    probe += "; print(json.dumps(report))"
    result = subprocess.run(
        [str(args.python), "-c", probe], check=False, capture_output=True, text=True,
        timeout=45, cwd=cwd, env=environment, user=uid, group=gid, extra_groups=groups,
    )
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        raise ValueError("runtime import identity probe did not return a valid result") from None
    if result.returncode or report.get("path") != str(loaded_path) or report.get("sha256") != expected_sha:
        raise ValueError("Python import selected a different runtime artifact")
    if expected_support_sha is not None:
        expected_support_path = str((args.installed.parent / SUPPORT_FILENAME).resolve(strict=True))
        if report.get("support_path") != expected_support_path or report.get("support_sha256") != expected_support_sha:
            raise ValueError("Python import selected a different runtime support module")
    expected_version = manifest.get("hermes_version") if manifest is not None else args.hermes_version
    if report.get("version") != expected_version:
        raise ValueError("running Hermes version differs from the approved manifest")
    if _systemctl("show", "--property=MainPID", "--value", args.service) != str(pid):
        raise ValueError("Hermes restarted during live verification")
    if args.health_url:
        health = subprocess.run(
            ["curl", "--fail", "--silent", "--show-error", "--max-time", "8", "--output", os.devnull, args.health_url],
            check=False, capture_output=True, text=True,
        )
        if health.returncode:
            raise ValueError("Hermes health endpoint did not pass")
    print(
        f"EXPECTED source={(manifest or {}).get('hades_git_sha','')[:12]} hermes={report['version']} "
        f"artifact_sha256={expected_sha} loaded_sha256={report['sha256']} "
        f"support_sha256={report.get('support_sha256')} "
        f"manifest={expected_id} pid={pid}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    verify = sub.add_parser("verify")
    live = sub.add_parser("verify-live")
    fingerprint = sub.add_parser("fingerprint")
    fingerprint.add_argument("--config-input", action="append", default=[], metavar="NAME=PATH|NAME=sha256:HEX")
    verify_config = sub.add_parser("verify-config")
    verify_config.add_argument("--manifest", type=Path, required=True)
    verify_config.add_argument("--config-input", action="append", default=[], metavar="NAME=PATH|NAME=sha256:HEX")
    for command in (build, verify):
        command.add_argument("--source-repo", type=Path, required=True)
        command.add_argument("--hermes-version", required=True)
        command.add_argument("--config-input", action="append", default=[], metavar="NAME=PATH|NAME=sha256:HEX")
    build.add_argument("--artifact", type=Path, required=True)
    build.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--artifact", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--installed", type=Path)
    verify.add_argument("--installed-support", type=Path)
    live.add_argument("--artifact", type=Path)
    live.add_argument("--manifest", type=Path)
    live.add_argument("--installed", type=Path, required=True)
    live.add_argument("--service", required=True)
    live.add_argument("--python", type=Path, required=True)
    live.add_argument("--expected-sha256")
    live.add_argument("--hermes-version")
    live.add_argument("--expected-manifest-sha256")
    live.add_argument("--config-input", action="append", default=[], metavar="NAME=PATH|NAME=sha256:HEX")
    live.add_argument("--health-url")
    args = parser.parse_args()
    try:
        if args.command == "fingerprint":
            return command_fingerprint(args)
        if args.command == "verify-config":
            return command_verify_config(args)
        if args.command == "build":
            return command_build(args)
        if args.command == "verify":
            return command_verify(args)
        return command_verify_live(args)
    except (OSError, ValueError, SystemExit) as exc:
        if isinstance(exc, SystemExit):
            raise
        if isinstance(exc, RuntimeUnknown):
            raise SystemExit(f"UNKNOWN {exc}") from None
        raise SystemExit(f"DRIFTED {exc}") from None


if __name__ == "__main__":
    raise SystemExit(main())
