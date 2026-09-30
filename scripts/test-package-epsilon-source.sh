#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

source = Path.cwd()
with tempfile.TemporaryDirectory(prefix="hades-epsilon-package-") as tmp:
    root = Path(tmp)
    generated = root / "generated-full"
    generated.mkdir()
    private = generated / "secrets" / "preserve-me"
    private.parent.mkdir()
    private.write_text("synthetic private sentinel", encoding="utf-8")
    private.chmod(0o600)

    command = [sys.executable, "scripts/package-epsilon-source.py", str(source), str(generated)]
    first = subprocess.run(command, cwd=source, check=True, capture_output=True, text=True)
    manifest_path = generated / "config/epsilon-source/phase3-runtime-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["package"] == "hades-epsilon-source"
    assert "integrations/automation/phase3_request.py" in manifest["files"]
    assert "integrations/automation/phase3_authority_policy.py" in manifest["files"]
    assert "integrations/automation/phase3_lldap_authority.py" in manifest["files"]
    for relative, record in manifest["files"].items():
        content = (generated / relative).read_bytes()
        assert hashlib.sha256(content).hexdigest() == record["sha256"]
    assert private.read_text(encoding="utf-8") == "synthetic private sentinel"
    assert private.stat().st_mode & 0o777 == 0o600

    # Import from the packaged root with the checkout removed from sys.path.
    # server.py must locate its sibling `integrations/` package itself.
    probe = "import runpy; runpy.run_path('config/epsilon-source/server.py', run_name='epsilon-source-package-probe'); print('IMPORT_OK')"
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    imported = subprocess.run([sys.executable, "-c", probe], cwd=generated, env=env, check=True, capture_output=True, text=True)
    assert "IMPORT_OK" in imported.stdout

    second = subprocess.run(command, cwd=source, check=True, capture_output=True, text=True)
    assert first.stdout == second.stdout
    assert private.read_text(encoding="utf-8") == "synthetic private sentinel"

    # Refuse a symlinked package directory rather than writing outside root.
    unsafe = root / "unsafe-generated"
    unsafe.mkdir()
    outside = root / "outside"
    outside.mkdir()
    (unsafe / "integrations").symlink_to(outside, target_is_directory=True)
    rejected = subprocess.run([sys.executable, "scripts/package-epsilon-source.py", str(source), str(unsafe)], cwd=source, capture_output=True, text=True)
    assert rejected.returncode != 0
    assert not list(outside.iterdir())

print("PASS Epsilon source packaging: complete imports, deterministic manifest, state/private-file preservation, symlink rejection")
PY
