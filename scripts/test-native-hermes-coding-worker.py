#!/usr/bin/env python3
"""Opt-in real-model test of the authenticated isolated coding worker."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(_ROOT))
from hermes.coding_worker import run_coding_worker  # noqa: E402


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True,
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-root", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=_ROOT)
    args = parser.parse_args()
    runtime = yaml.safe_load(args.model_config.read_text(encoding="utf-8"))
    model_config = runtime.get("model") if isinstance(runtime, dict) else None
    if not isinstance(model_config, dict) or model_config.get("provider") != "custom":
        raise SystemExit("FAIL candidate test requires the approved custom inference profile")
    model = model_config.get("default")
    upstream = model_config.get("base_url")
    if not isinstance(model, str) or not isinstance(upstream, str):
        raise SystemExit("FAIL candidate model identity is incomplete")

    with tempfile.TemporaryDirectory(prefix="hades-coding-worker-fixture-") as temp_name:
        root = Path(temp_name)
        source = root / "source"
        source.mkdir(mode=0o700)
        workspace_root = root / "sessions"
        workspace_root.mkdir(mode=0o700)
        _git(source, "init", "-q", "-b", "main")
        _git(source, "config", "user.name", "HADES Coding Fixture")
        _git(source, "config", "user.email", "coding-fixture@example.invalid")
        (source / "calc.py").write_text("def answer():\n    return 41\n", encoding="utf-8")
        (source / "test_calc.py").write_text(
            "import unittest\nfrom calc import answer\n\n"
            "class AnswerTest(unittest.TestCase):\n"
            "    def test_answer(self):\n        self.assertEqual(answer(), 42)\n",
            encoding="utf-8",
        )
        _git(source, "add", "calc.py", "test_calc.py")
        _git(source, "commit", "-qm", "fixture")
        initial_head = _git(source, "rev-parse", "HEAD")
        mapping = root / "bindings.json"
        mapping.write_text(json.dumps({"version": 1, "bindings": {"owner-fixture": str(source)}}))
        mapping.chmod(0o600)

        result = run_coding_worker(
            subject="owner-fixture", scope="owner", conversation_id="owner-coding-fixture-001",
            prompt=(
                "Inspect calc.py and test_calc.py, fix the failing test by changing only calc.py, "
                "run the focused test, inspect the diff, and commit the fix."
            ),
            history=[], model=model, upstream=upstream,
            repo_root=args.repo_root.resolve(strict=True),
            hermes_root=args.hermes_root.resolve(strict=True),
            bindings_file=mapping, workspace_root=workspace_root,
            forbidden_roots=(args.repo_root.resolve(strict=True),),
        )
        if result.get("outcome") != "SUCCEEDED" or result.get("commit") != "SUCCEEDED":
            raise SystemExit(
                "FAIL isolated native Hermes coding worker did not verify the requested commit; "
                f"outcome={result.get('outcome')} commit={result.get('commit')} "
                f"reason={result.get('commit_reason')} test={result.get('test_verified')} "
                f"paths={result.get('changed_paths')} calls={result.get('tool_call_names')} "
                f"response={result.get('final_response')}"
            )
        if result.get("changed_paths") != [] or len(result.get("head_after", "")) < 40:
            raise SystemExit("FAIL committed clone worktree or canonical HEAD evidence is invalid")
        clone_path = next(path for path in workspace_root.iterdir() if path.is_dir())
        if _git(clone_path, "show", "--pretty=format:", "--name-only", "HEAD").splitlines() != ["calc.py"]:
            raise SystemExit("FAIL candidate commit includes unintended fixture paths")
        if _git(source, "rev-parse", "HEAD") != initial_head:
            raise SystemExit("FAIL source fixture history was modified")
        if _git(clone_path, "rev-parse", "HEAD") == initial_head:
            raise SystemExit("FAIL disposable coding workspace has no new verified commit")
        if (source / "calc.py").read_text(encoding="utf-8") != "def answer():\n    return 41\n":
            raise SystemExit("FAIL source fixture was modified")
        print(
            "PASS: real model used Hermes native tools in an isolated conversation workspace; "
            f"commit={result['head_after'][:12]} tests={result['test_verified']} "
            f"changed_paths={result.get('changed_paths')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
