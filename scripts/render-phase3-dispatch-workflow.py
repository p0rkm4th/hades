#!/usr/bin/env python3
"""Bind the fixed dispatcher artifact to an existing n8n Crypto credential."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credential-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{4,128}", args.credential_id):
        parser.error("credential ID has an invalid shape")
    output = Path(args.output)
    if not output.is_absolute() or output.exists():
        parser.error("output must be a new absolute path")
    source = Path(__file__).resolve().parents[1] / "config/epsilon-workflows/phase3-runner-dispatch.json"
    workflow = json.loads(source.read_text(encoding="utf-8"))
    crypto_nodes = [node for node in workflow["nodes"] if node["type"] == "n8n-nodes-base.crypto"]
    if len(crypto_nodes) != 2:
        raise ValueError("fixed dispatcher Crypto node contract changed")
    for node in crypto_nodes:
        node["credentials"]["crypto"]["id"] = args.credential_id
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(workflow, stream, indent=2)
        stream.write("\n")
    output.chmod(0o600)
    print(f"PASS rendered inactive fixed dispatcher for n8n credential ID into {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL could not render fixed dispatcher: {exc}", file=sys.stderr)
        raise SystemExit(1)
