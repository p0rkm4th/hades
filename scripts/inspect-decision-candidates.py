#!/usr/bin/env python3
"""Report reproducible candidate readiness without downloading model artifacts."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REQUIREMENTS = {
    "SemIf-Qwen3.5-4B": ("torch", "transformers", "huggingface_hub"),
    "NanoJev": ("torch", "transformers", "huggingface_hub"),
    "GLiClass": ("torch", "transformers", "gliclass"),
}


def main() -> int:
    manifest = json.loads(Path("config/decision-backends.json").read_text())
    report = []
    for candidate in manifest["candidates"]:
        name = candidate["name"]
        requirements = REQUIREMENTS.get(name, ())
        missing = [item for item in requirements if importlib.util.find_spec(item) is None]
        runtime = candidate["runtime_status"]
        if missing:
            runtime = "not_ready"
        elif runtime == "available":
            runtime = "ready_for_adapter"
        report.append({
            "name": name,
            "status": candidate["status"],
            "revision": candidate["revision"],
            "privacy_boundary": candidate["privacy_boundary"],
            "runtime": runtime,
            "missing_dependencies": missing,
            "quality": "not_measured" if name != "CURRENT" else "control_only",
        })
    print(json.dumps({"schema": "hades-decision-candidate-readiness/v1", "candidates": report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
