#!/usr/bin/env python3
"""Verify generated HADES packages override only matching checkout modules."""
from __future__ import annotations

import ast
import os
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "hermes/sitecustomize.py"


def prepare_function():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_hades_prepare_generated_integrations_path"
    ]
    assert len(functions) == 1
    namespace = {"os": os, "sys": sys, "Path": Path}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace[functions[0].name]


with tempfile.TemporaryDirectory(prefix="hades-generated-integrations-") as raw:
    root = Path(raw)
    generated = root / "generated"
    legacy = root / "legacy-checkout"
    generated_package = generated / "integrations"
    legacy_package = legacy / "integrations"
    (generated_package / "automation").mkdir(parents=True)
    (legacy_package / "task").mkdir(parents=True)
    shutil.copy2(ROOT / "integrations/__init__.py", generated_package / "__init__.py")
    (generated_package / "automation" / "__init__.py").write_text("", encoding="utf-8")
    (generated_package / "automation" / "phase3_self_service.py").write_text(
        "SOURCE = 'generated'\n", encoding="utf-8",
    )
    (legacy_package / "__init__.py").write_text('"""Legacy checkout adapters."""\n', encoding="utf-8")
    (legacy_package / "task" / "__init__.py").write_text("", encoding="utf-8")
    (legacy_package / "task" / "adapter.py").write_text(
        "SOURCE = 'checkout'\n", encoding="utf-8",
    )

    original_path = list(sys.path)
    original_env = os.environ.get("HADES_INTEGRATIONS_ROOT")
    try:
        sys.modules.pop("integrations", None)
        sys.modules.pop("integrations.automation", None)
        sys.modules.pop("integrations.automation.phase3_self_service", None)
        sys.modules.pop("integrations.task", None)
        sys.modules.pop("integrations.task.adapter", None)
        sys.path[:] = [str(legacy), *original_path]
        os.environ["HADES_INTEGRATIONS_ROOT"] = str(generated)
        prepare_function()()
        assert sys.path[0] == str(generated.resolve())

        import integrations
        from integrations.automation.phase3_self_service import SOURCE as phase3_source
        from integrations.task.adapter import SOURCE as adapter_source

        assert phase3_source == "generated"
        assert adapter_source == "checkout"
        package_paths = [Path(item).resolve() for item in integrations.__path__]
        assert package_paths[:2] == [generated_package.resolve(), legacy_package.resolve()]
    finally:
        sys.path[:] = original_path
        if original_env is None:
            os.environ.pop("HADES_INTEGRATIONS_ROOT", None)
        else:
            os.environ["HADES_INTEGRATIONS_ROOT"] = original_env
        for name in tuple(sys.modules):
            if name == "integrations" or name.startswith("integrations."):
                sys.modules.pop(name, None)

print("PASS generated Phase 3 module precedence preserves legacy adapter lookup")
