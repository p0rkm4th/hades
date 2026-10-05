#!/usr/bin/env python3
"""Synthetic contracts for the deterministic homelab package composer."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts/compose-homelab-package.py"
PROVENANCE = ROOT / "scripts/write-deployed-provenance.py"


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, text=True, capture_output=True)


def make_repo(root: Path, *, symlink: bool = False) -> tuple[Path, str]:
    repo = root / "source"
    (repo / "integrations/homelab-readonly").mkdir(parents=True)
    package = repo / "integrations/homelab-readonly"
    (package / "server.py").write_text("import config\nVALUE = config.VALUE\n", encoding="utf-8")
    (package / "config.py").write_text("VALUE = 'synthetic'\n", encoding="utf-8")
    (repo / "config").mkdir()
    (repo / "config/operator-input.env").write_text("PRIVATE_SENTINEL=synthetic-only\n", encoding="utf-8")
    if symlink:
        (package / "linked.py").symlink_to("config.py")
    run("git", "-C", str(repo), "init", "-q")
    run("git", "-C", str(repo), "config", "user.name", "Synthetic Test")
    run("git", "-C", str(repo), "config", "user.email", "synthetic@example.invalid")
    run("git", "-C", str(repo), "add", "integrations/homelab-readonly", "config/operator-input.env")
    run("git", "-C", str(repo), "commit", "-qm", "fixture")
    revision = run("git", "-C", str(repo), "rev-parse", "HEAD").stdout.strip()
    return repo, revision


def compose(repo: Path, revision: str, output: Path, manifest: Path | None = None, *, check: bool = True):
    args = [sys.executable, str(COMPOSER), "--source-repo", str(repo), "--revision", revision, "--output", str(output)]
    if manifest is not None:
        args += ["--manifest", str(manifest)]
    return run(*args, check=check)


def load_provenance_module():
    spec = importlib.util.spec_from_file_location("deployed_provenance", PROVENANCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_deterministic_exact_package_and_import() -> None:
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        repo, revision = make_repo(base)
        out_a, out_b = base / "package-a", base / "package-b"
        manifest_a, manifest_b = base / "manifest-a.json", base / "manifest-b.json"
        compose(repo, revision, out_a, manifest_a)
        compose(repo, revision, out_b, manifest_b)
        assert sorted(path.name for path in out_a.iterdir()) == ["config.py", "server.py"]
        assert {path.name: path.read_bytes() for path in out_a.iterdir()} == {
            path.name: path.read_bytes() for path in out_b.iterdir()
        }
        assert manifest_a.read_bytes() == manifest_b.read_bytes()
        value = json.loads(manifest_a.read_text(encoding="utf-8"))
        assert value["schema"] == "hades/homelab-package/v1"
        assert value["source_revision"] == revision
        assert [row["path"] for row in value["files"]] == ["config.py", "server.py"]
        claimed_package_sha = value.pop("package_sha256")
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        assert claimed_package_sha == hashlib.sha256(canonical).hexdigest()
        value["package_sha256"] = claimed_package_sha
        assert all(row["size_bytes"] == (out_a / row["path"]).stat().st_size for row in value["files"])
        assert all(row["sha256"] == hashlib.sha256((out_a / row["path"]).read_bytes()).hexdigest() for row in value["files"])
        assert "source" not in value and str(repo) not in manifest_a.read_text(encoding="utf-8")
        assert "PRIVATE_SENTINEL" not in manifest_a.read_text(encoding="utf-8")
        assert not (out_a / "operator-input.env").exists()
        assert not (out_a / "__pycache__").exists()

        # Import with the source checkout absent from cwd and sys.path.
        code = (
            "import sys; package=sys.argv[1]; sys.path=[package]+[p for p in sys.path if p not in ('', sys.argv[2])]; "
            "import server; assert server.VALUE == 'synthetic'; assert sys.argv[2] not in sys.path"
        )
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [sys.executable, "-c", code, str(out_a), str(repo)], cwd=base,
            env=env, text=True, capture_output=True,
        )
        assert result.returncode == 0, result.stderr

        identity = load_provenance_module().homelab_package_identity(
            out_a, out_a / "server.py", repo
        )
        assert identity["file_count"] == 2
        assert identity["source_tree"] == run("git", "-C", str(repo), "rev-parse", f"{revision}:integrations/homelab-readonly").stdout.strip()
        assert (out_a.stat().st_mode & 0o777) == 0o750
        assert all((path.stat().st_mode & 0o777) == 0o640 for path in out_a.iterdir())
    print("PASS deterministic package, exact tracked set, clean-source import, and provenance compatibility")


def test_dirty_and_revision_mismatch_rejected() -> None:
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        repo, revision = make_repo(base)
        output = base / "dirty-output"
        (repo / "untracked-secret.env").write_text("SYNTHETIC_ONLY=1\n", encoding="utf-8")
        failed = compose(repo, revision, output, check=False)
        assert failed.returncode != 0 and "must be clean" in failed.stderr
        assert not output.exists()
        (repo / "untracked-secret.env").unlink()
        failed = compose(repo, "0" * 40, output, check=False)
        assert failed.returncode != 0 and "does not match" in failed.stderr
        assert not output.exists()
    print("PASS dirty source and revision mismatch fail before output creation")


def test_existing_paths_and_source_overlap_rejected() -> None:
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        repo, revision = make_repo(base)
        existing = base / "existing"
        existing.mkdir()
        failed = compose(repo, revision, existing, check=False)
        assert failed.returncode != 0 and "already exists" in failed.stderr
        inside = repo / "generated-package"
        failed = compose(repo, revision, inside, check=False)
        assert failed.returncode != 0 and "separate from" in failed.stderr
        output = base / "new-package"
        manifest = base / "already.json"
        manifest.write_text("{}\n", encoding="utf-8")
        failed = compose(repo, revision, output, manifest, check=False)
        assert failed.returncode != 0 and "manifest output already exists" in failed.stderr
        assert not output.exists()
    print("PASS existing output, source overlap, and existing manifest fail closed")


def test_tracked_symlink_rejected() -> None:
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        repo, revision = make_repo(base, symlink=True)
        failed = compose(repo, revision, base / "package", check=False)
        assert failed.returncode != 0 and "unsupported path or file type" in failed.stderr
        assert not (base / "package").exists()
    print("PASS tracked package symlink rejected")


def main() -> None:
    test_deterministic_exact_package_and_import()
    test_dirty_and_revision_mismatch_rejected()
    test_existing_paths_and_source_overlap_rejected()
    test_tracked_symlink_rejected()


if __name__ == "__main__":
    main()
