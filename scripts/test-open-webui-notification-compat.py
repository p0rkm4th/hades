#!/usr/bin/env python3
"""Verify Task/Phase 3 notification route composition is additive and idempotent."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


repo = Path(__file__).resolve().parents[1]
installer = repo / "webui/task_notification_compat.py"
marker = "\n\n##################################\n#\n# Chat Endpoints"
task_decl = "async def hades_task_notification_snapshot("
task_path = "@app.get('/api/v1/hades/tasks/notifications')"
result_decl = "async def hades_phase3_notification_snapshot("
result_path = "@app.get('/api/v1/hades/automations/notifications')"


def apply(path: Path) -> str:
    environment = dict(os.environ)
    environment["HADES_OPEN_WEBUI_MAIN_FILE"] = str(path)
    result = subprocess.run(
        [sys.executable, str(installer)],
        cwd=repo,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


with tempfile.TemporaryDirectory(prefix="hades-webui-route-compat-") as tmp:
    root = Path(tmp)
    fixtures = {
        "clean": "",
        "task-only": task_path + "\n" + task_decl + "\npass\n",
        "result-only": result_path + "\n" + result_decl + "\npass\n",
        "both": task_path + "\n" + task_decl + "\npass\n" + result_path + "\n" + result_decl + "\npass\n",
    }
    for name, existing in fixtures.items():
        target = root / f"{name}.py"
        target.write_text(existing + marker, encoding="utf-8")
        apply(target)
        installed = target.read_text(encoding="utf-8")
        assert installed.count(task_decl) == 1, name
        assert installed.count(task_path) == 1, name
        assert installed.count(result_decl) == 1, name
        assert installed.count(result_path) == 1, name
        apply(target)
        assert target.read_text(encoding="utf-8") == installed, name

    broken = root / "broken.py"
    broken.write_text(task_path + marker, encoding="utf-8")
    environment = dict(os.environ)
    environment["HADES_OPEN_WEBUI_MAIN_FILE"] = str(broken)
    rejected = subprocess.run([sys.executable, str(installer)], cwd=repo, env=environment, capture_output=True)
    assert rejected.returncode != 0

print("PASS Open WebUI notification routes compose additively and are idempotent")
