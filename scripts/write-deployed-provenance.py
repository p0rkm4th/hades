#!/usr/bin/env python3
"""Write the bounded machine-readable identity of a tested deployment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def digest(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise SystemExit(f"regular file required: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--hades-sha", required=True)
    parser.add_argument("--infra-sha", required=True)
    parser.add_argument("--hermes-version", required=True)
    parser.add_argument("--overlay", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--deployment-path", required=True)
    args = parser.parse_args()
    for name, value in (("hades SHA", args.hades_sha), ("infra SHA", args.infra_sha)):
        if len(value) != 40 or any(char not in "0123456789abcdef" for char in value.lower()):
            raise SystemExit(f"{name} must be a Git SHA")
    artifact = {
        "schema": "hades/deployed-provenance/v1",
        "hades_sha": args.hades_sha,
        "infra_sha": args.infra_sha,
        "hermes_version": args.hermes_version,
        "overlay_sha256": digest(args.overlay),
        "manifest_sha256": digest(args.manifest),
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "deployment_path": args.deployment_path,
        "classification": "tested-source-and-deployment-artifact-identity",
    }
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
