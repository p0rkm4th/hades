#!/usr/bin/env python3
"""Reject raw conversational or tool payloads in public benchmark artifacts."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = ROOT / "benchmarks"
RAW_CONTENT_KEY_TERMS = (
    "prompt", "answer", "response", "question", "query", "input", "instruction",
    "message", "conversation", "transcript", "assistant_text", "user_text", "content",
    "tool_call", "tool_result", "tool_arg", "argument", "provider_call", "provider_request", "request",
    "fixture", "source_content", "file", "test_output", "stdout", "stderr", "command",
    "trace", "memory", "fact", "retain_input", "output_text", "result_text",
)


def inspect(value: object, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            name = str(key).casefold()
            if isinstance(item, (str, list, dict)) and any(term in name for term in RAW_CONTENT_KEY_TERMS):
                findings.append(f"{path}.{key}")
            findings.extend(inspect(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(inspect(item, f"{path}[{index}]"))
    return findings


def main() -> int:
    artifacts = sorted(BENCHMARKS.rglob("*.json"))
    findings: list[str] = []
    for artifact in artifacts:
        try:
            data = json.loads(artifact.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            findings.append(str(artifact.relative_to(ROOT)))
            continue
        for field in inspect(data):
            findings.append(f"{artifact.relative_to(ROOT)}:{field}")
    if findings:
        print(f"FAIL raw-content fields in public benchmark artifacts (findings={len(findings)}; paths redacted)")
        return 1
    print(f"PASS public benchmark artifacts contain no raw-content fields (files={len(artifacts)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
