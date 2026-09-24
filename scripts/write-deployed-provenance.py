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
    parser.add_argument("--hades-version", default="")
    parser.add_argument("--overlay", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--deployment-path", required=True)
    parser.add_argument("--profile", default="standalone")
    parser.add_argument("--deployment-id", default="")
    parser.add_argument("--config-schema", default="1")
    args = parser.parse_args()
    for name, value in (("hades SHA", args.hades_sha), ("infra SHA", args.infra_sha)):
        if value not in {"unknown", "not-applicable"} and (len(value) != 40 or any(char not in "0123456789abcdef" for char in value.lower())):
            raise SystemExit(f"{name} must be a Git SHA")
    deployment_id = args.deployment_id or f"hades-{args.hades_sha[:12]}"
    built_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    artifact = {
        "schema": "hades/deployed-provenance/v1",
        "hades_version": args.hades_version or args.hermes_version,
        "hades_commit": args.hades_sha,
        "infra_commit": args.infra_sha,
        "profile": args.profile,
        "deployment_id": deployment_id,
        "built_at": built_at,
        "config_schema": int(args.config_schema),
        "hades_sha": args.hades_sha,
        "infra_sha": args.infra_sha,
        "hermes_version": args.hermes_version,
        "overlay_sha256": digest(args.overlay),
        "manifest_sha256": digest(args.manifest),
        "generated_at": built_at,
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
