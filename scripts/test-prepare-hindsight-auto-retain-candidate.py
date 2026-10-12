#!/usr/bin/env python3
"""Check bounded automatic-retain composition preserves deployment-only code."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "hermes/sitecustomize.py"
COMPOSER = ROOT / "scripts/prepare-hindsight-auto-retain-candidate.py"

spec = __import__("importlib.util", fromlist=["spec_from_file_location"])
module_spec = spec.spec_from_file_location("hades_auto_retain_composer", COMPOSER)
composer = spec.module_from_spec(module_spec)
sys.modules[module_spec.name] = composer
module_spec.loader.exec_module(composer)

source = SOURCE.read_text(encoding="utf-8")
source_lines = source.splitlines(keepends=True)
_, source_defs = composer.definitions(source, "canonical source")
remove_names = (*composer.CONSTANTS, *composer.FUNCTIONS)
removals = sorted(
    (source_defs[name].lineno - 1, source_defs[name].end_lineno)
    for name in remove_names
)
active_lines = source_lines[:]
for start, end in reversed(removals):
    active_lines[start:end] = []
active = "".join(active_lines)
old_hook = '''    def _hades_sync_turn(self, user_content, assistant_content, *, session_id=""):
        if _hades_should_skip_automatic_memory(user_content, assistant_content):
            return None
        return _hades_original_sync_turn(self, user_content, assistant_content, session_id=session_id)
'''
_, active_defs = composer.definitions(active, "active fixture")
old_nonpersonal = "def _hades_nonpersonal_state_turn(user_text):\n    return False\n"
old_skip = "def _hades_should_skip_automatic_memory(user_content, assistant_content):\n    return True\n"
active_lines = active.splitlines(keepends=True)
edits = [
    (active_defs[composer.RUNTIME_HOOK].lineno - 1, active_defs[composer.RUNTIME_HOOK].end_lineno, old_hook),
    (active_defs["_hades_nonpersonal_state_turn"].lineno - 1,
     active_defs["_hades_nonpersonal_state_turn"].end_lineno, old_nonpersonal),
    (active_defs["_hades_should_skip_automatic_memory"].lineno - 1,
     active_defs["_hades_should_skip_automatic_memory"].end_lineno, old_skip),
]
for start, end, replacement in sorted(edits, reverse=True):
    active_lines[start:end] = [replacement]
active = "# deployment-local-before\n" + "".join(active_lines) + "\n# deployment-local-after\n"

candidate = composer.compose(active.encode(), source.encode()).decode()
assert candidate.startswith("# deployment-local-before\n")
assert candidate.endswith("\n# deployment-local-after\n")
for name in (*composer.CONSTANTS, *composer.REPLACED_CONSTANTS, *composer.FUNCTIONS, *composer.REPLACED_FUNCTIONS):
    assert candidate.count(name) >= 1
assert "def _hades_nonpersonal_state_turn(user_text):\n    return False" not in candidate
assert "def _hades_should_skip_automatic_memory(user_content, assistant_content):\n    return True" not in candidate
compile(candidate, "<test-composed-overlay>", "exec")

with tempfile.TemporaryDirectory(prefix="hades-auto-retain-compose-") as temporary:
    root = Path(temporary)
    active_path, output = root / "active.py", root / "candidate.py"
    active_path.write_text(active, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(COMPOSER), "--active-overlay", str(active_path), "--output", str(output)],
        check=True, capture_output=True, text=True,
    )
    assert "PASS composed only" in result.stdout
    assert output.read_text(encoding="utf-8") == candidate
    assert output.stat().st_mode & 0o777 == 0o600
    before = output.read_bytes()
    refused = subprocess.run(
        [sys.executable, str(COMPOSER), "--active-overlay", str(active_path), "--output", str(output)],
        capture_output=True, text=True,
    )
    assert refused.returncode != 0
    assert output.read_bytes() == before

print("PASS automatic-retain candidate adds only canonical policy/hook and preserves deployment-local code")
print("PASS candidate is syntax-checked, mode 0600, and refuses overwrite")
