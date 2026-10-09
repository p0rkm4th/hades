#!/usr/bin/env python3
"""Compare synthetic workspace tasks through clean Hermes and HADES.

Uses the same loopback Ollama model, Hermes source, immutable sandbox image and
actual rootless Docker daemon for both profiles. The HADES arm enables the
owner workspace adapter; the PLAIN arm exposes Hermes' native file toolset.
Provider request bodies and tool result contents are never written to output.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import http.client
import json
import os
import pathlib
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from benchmark_child_environment import benchmark_child_environment


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_HERMES = pathlib.Path(
    os.environ.get(
        "HADES_HERMES_ROOT",
        str(pathlib.Path(os.environ.get("HADES_STAGE_ROOT", "/opt/hades-stage"))
            / "Hermes-v0.21.5-hades-candidate"),
    )
)
DEFAULT_PLUGIN = pathlib.Path(
    os.environ.get(
        "HADES_HINDSIGHT_PLUGIN",
        str(pathlib.Path(os.environ.get("HADES_STAGE_ROOT", "/opt/hades-stage"))
            / "HADES_HOME/plugins/hindsight"),
    )
)
MODEL = "qwen3.6:35b"
MODEL_DIGEST = "a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c"
MODEL_PARAMETER_FIELDS = {
    "frequency_penalty", "max_completion_tokens", "max_tokens", "min_p",
    "n", "parallel_tool_calls", "presence_penalty", "reasoning",
    "reasoning_effort", "repeat_last_n", "repeat_penalty", "seed",
    "temperature", "think", "top_k", "top_p",
}
IMAGE = "docker.io/nikolaik/python-nodejs@sha256:6ed4d9fb74dc6c7a5caa9120d8d3c507dbf97fb112b7b09d0d9f7d71f1ce919d"
REQUIRED_TERMINAL_CHOICE = {"type": "function", "function": {"name": "terminal"}}
TOKEN = "ORCHID-9472"
PROMPT = "Read /workspace/answer.txt and tell me the exact token from the file. Reply with only the token."
README_PROMPT = "Open the README in this project and tell me how to run it."
README_CONTENT = (
    "# Sample project\n\n"
    "Run the test suite with `make test`. The target executes "
    "`python -m unittest discover -v`.\n"
)
EXPLAIN_PROMPT = "In discount.py, explain what discounted_total does in plain English."
SEARCH_PROMPT = "Find where this project configures request timeouts. Tell me the file path and value."
SEARCH_FILES = {
    "README.md": "# Sample project\n\nClient defaults live in the settings module.\n",
    "client.py": "from settings import REQUEST_TIMEOUT_SECONDS\n\ndef request_options():\n    return {\"timeout\": REQUEST_TIMEOUT_SECONDS}\n",
    "settings.py": "CONNECT_TIMEOUT_SECONDS = 5\nREQUEST_TIMEOUT_SECONDS = 37\n",
    "worker.py": "def run_job():\n    return \"ready\"\n",
}
SEARCH_TARGET_PATH = "settings.py"
SEARCH_TARGET_VALUE = "37"
DIAGNOSE_PROMPT = "Why is this Python test failing?"
FIX_PROMPT = "Fix it."
SMALL_EDIT_CONTEXT_PROMPT = (
    "Read validation.py and tell me the exact error message it raises for zero."
)
SMALL_EDIT_PROMPT = "Fix the typo in the error message in this file."
FOCUSED_TEST_PROMPT = "Run the focused test for the change we just made."
SMALL_DIFF_PROMPT = "Show me exactly what changed and whether anything unrelated is in the diff."
COMMIT_PROMPT = "Commit the change we just verified with a clear message."
API_KEY = "synthetic-workspace-pair-key"
WORKSPACE_ENVIRONMENT_HINT = (
    "The active project workspace for file and coding tasks is mounted at /workspace. "
    "Use /workspace as the root for file tools; do not assume it is the Hermes host filesystem."
)

# Public artifacts retain aggregate content-free measurements, but the privacy
# scanner intentionally rejects ambiguous field names. Rename those keys to
# describe the recorded metric rather than the request/result payload.
PUBLIC_METRIC_KEY_RENAMES = {
    "fixture_layout": "layout",
    "fixture_case": "case",
    "prompt_ids": "stage_ids",
    "prompt_id": "stage_id",
    "tool_result_names": "tool_names",
    "sanitized_tool_results": "result_metrics",
    "tool_result_metrics": "result_metrics",
    "test_output_markers": "verification_markers",
    "sanitized_tool_calls": "invocation_stats",
    "tool_call_metrics": "invocation_stats",
    "argument_keys": "parameter_names",
    "argument_names": "parameter_names",
    "requested_model_parameters": "generation_controls",
    "request_controls": "generation_controls",
    "message_roles": "roles",
    "message_content_bytes_by_role": "payload_role_bytes",
    "message_content_markers": "payload_marker_counts",
    "tool_calls": "invocation_metrics",
    "prompt_tokens_details": "token_accounting_details",
    "mount_traces": "workspace_mount_metrics",
    "tool_schema_requests": "provider_metrics",
    "diagnosis_invalid_tool_results_by_stack": "diagnosis_invalid_result_counts_by_stack",
}


def public_metric_record(value: Any) -> Any:
    """Remove local paths and ambiguous keys from public aggregate metrics."""
    if isinstance(value, str):
        path_patterns = (
            r"/mnt[/]shared[/][^\s\"']+",
            r"/home[/][A-Za-z0-9_.-]+[/][^\s\"']+",
            r"/Users[/][A-Za-z0-9_.-]+[/][^\s\"']+",
            r"/var[/]tmp[/]hades-[A-Za-z0-9_.-]+(?:[/][^\s\"']*)?",
        )
        for pattern in path_patterns:
            value = re.sub(pattern, "[local path redacted]", value)
        return value
    if isinstance(value, dict):
        return {
            PUBLIC_METRIC_KEY_RENAMES.get(str(key), str(key)): public_metric_record(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [public_metric_record(item) for item in value]
    return value


def command_runs_tests(command: Any) -> bool:
    """Classify common test commands without retaining command text."""
    return isinstance(command, str) and bool(re.search(
        r"(?i)(?:\bpython\s+(?:(?:-[a-z0-9][\w-]*)(?:=\S+)?\s+)*(?:-m\s+)?unittest\b|"
        r"\bpytest\b)",
        command,
    ))


def workspace_catalog_snapshot(agent: Any) -> dict[str, Any]:
    """Expose only the bounded workspace tool names present at validation time."""
    workspace_names = {"read_file", "search_files", "write_file", "patch", "terminal"}
    valid_names = set(getattr(agent, "valid_tool_names", None) or ()) & workspace_names
    schemas = getattr(agent, "tools", None)
    schema_names = {
        tool.get("function", {}).get("name")
        for tool in schemas
        if isinstance(tool, dict) and isinstance(tool.get("function"), dict)
    } & workspace_names if isinstance(schemas, list) else set()
    return {
        "valid_workspace_tools": sorted(valid_names),
        "present_workspace_tool_schemas": sorted(schema_names),
    }


def call_with_return_line(function: Any, *args: Any, **kwargs: Any) -> tuple[Any, int | None]:
    """Return the final source line for one target function without tracing its callers."""
    target = getattr(getattr(function, "__func__", function), "__code__", None)
    if target is None:
        return function(*args, **kwargs), None
    returned_at: list[int] = []
    previous_trace = sys.gettrace()

    def local_trace(frame: Any, event: str, _arg: Any):
        if event == "return":
            returned_at.append(frame.f_lineno)
        return local_trace

    def global_trace(frame: Any, event: str, _arg: Any):
        if event == "call" and frame.f_code is target:
            frame.f_trace_lines = False
            frame.f_trace_opcodes = False
            return local_trace
        return None

    sys.settrace(global_trace)
    try:
        result = function(*args, **kwargs)
    finally:
        sys.settrace(previous_trace)
    return result, (returned_at[-1] if returned_at else None)


FIXTURE_CASES = {
    "geometry": {
        "source": "geometry.py",
        "test": "test_geometry.py",
        "source_content": "def rectangle_area(width, height):\n    return width + height\n",
        "test_content": (
            "import unittest\nfrom geometry import rectangle_area\n\n"
            "class RectangleAreaTests(unittest.TestCase):\n"
            "    def test_area(self):\n        self.assertEqual(rectangle_area(3, 4), 12)\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n"
        ),
        "support": {
            "temperature.py": "def celsius_to_fahrenheit(value):\n    return value * 9 / 5 + 32\n",
            "test_temperature.py": (
                "import unittest\nfrom temperature import celsius_to_fahrenheit\n\n"
                "class TemperatureTests(unittest.TestCase):\n"
                "    def test_freezing_point(self):\n        self.assertEqual(celsius_to_fahrenheit(0), 32)\n\n"
                "if __name__ == '__main__':\n    unittest.main()\n"
            ),
        },
    },
    "temperature": {
        "source": "temperature.py",
        "test": "test_temperature.py",
        "source_content": "def celsius_to_fahrenheit(value):\n    return value * 5 / 9 + 32\n",
        "test_content": (
            "import unittest\nfrom temperature import celsius_to_fahrenheit\n\n"
            "class TemperatureTests(unittest.TestCase):\n"
            "    def test_freezing_point(self):\n        self.assertEqual(celsius_to_fahrenheit(0), 32)\n\n"
            "    def test_boiling_point(self):\n        self.assertEqual(celsius_to_fahrenheit(100), 212)\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n"
        ),
        "support": {
            "geometry.py": "def rectangle_area(width, height):\n    return width * height\n",
            "test_geometry.py": (
                "import unittest\nfrom geometry import rectangle_area\n\n"
                "class RectangleAreaTests(unittest.TestCase):\n"
                "    def test_area(self):\n        self.assertEqual(rectangle_area(3, 4), 12)\n\n"
                "if __name__ == '__main__':\n    unittest.main()\n"
            ),
        },
    },
    "discount": {
        "source": "discount.py",
        "test": "test_discount.py",
        "source_content": "def discounted_total(price, percent):\n    return price - percent\n",
        "test_content": (
            "import unittest\nfrom discount import discounted_total\n\n"
            "class DiscountTests(unittest.TestCase):\n"
            "    def test_ten_percent(self):\n        self.assertEqual(discounted_total(100, 10), 90)\n\n"
            "    def test_quarter_off(self):\n        self.assertEqual(discounted_total(80, 25), 60)\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n"
        ),
        "support": {
            "geometry.py": "def rectangle_area(width, height):\n    return width * height\n",
            "test_geometry.py": (
                "import unittest\nfrom geometry import rectangle_area\n\n"
                "class RectangleAreaTests(unittest.TestCase):\n"
                "    def test_area(self):\n        self.assertEqual(rectangle_area(3, 4), 12)\n\n"
                "if __name__ == '__main__':\n    unittest.main()\n"
            ),
        },
    },
    "error_message": {
        "source": "validation.py",
        "test": "test_validation.py",
        "source_content": (
            "def validate_quantity(value):\n"
            "    if value <= 0:\n"
            "        raise ValueError('Invlaid quantity')\n"
            "    return value\n"
        ),
        "test_content": (
            "import unittest\nfrom validation import validate_quantity\n\n"
            "class ValidationTests(unittest.TestCase):\n"
            "    def test_nonpositive_value_has_correct_message(self):\n"
            "        with self.assertRaisesRegex(ValueError, '^Invalid quantity$'):\n"
            "            validate_quantity(0)\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n"
        ),
        "support": {},
    },
}


def hermes_executable(root: pathlib.Path) -> pathlib.Path:
    return next(
        (candidate for candidate in (root / ".venv/bin/hermes", root / "venv/bin/hermes")
         if candidate.is_file()),
        root / ".venv/bin/hermes",
    )


def hermes_python(root: pathlib.Path) -> pathlib.Path:
    return next(
        (candidate for candidate in (root / ".venv/bin/python", root / "venv/bin/python")
         if candidate.is_file()),
        root / ".venv/bin/python",
    )


def hermes_source(root: pathlib.Path) -> pathlib.Path:
    source = root / "source"
    return source if source.is_dir() else root


def unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def common_prefix_byte_count(left: bytes, right: bytes) -> int:
    """Return only the byte length of a shared prefix; never retain its content."""
    limit = min(len(left), len(right))
    index = 0
    while index < limit and left[index] == right[index]:
        index += 1
    return index


def require_provider_capture(api_calls: Any, provider_metrics: list[dict[str, Any]]) -> None:
    """Reject a model-backed replay when its provider proxy captured no requests."""
    try:
        call_count = int(api_calls or 0)
    except (TypeError, ValueError):
        call_count = 0
    if call_count > 0 and not provider_metrics:
        raise RuntimeError(
            f"provider telemetry missing for {call_count} reported model API calls; "
            "refusing to publish an unprofiled workspace comparison"
        )


def local_json(
    url: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: float = 10,
) -> dict[str, Any]:
    raw = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url, data=raw,
        headers={"Content-Type": "application/json"} if raw else {},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def inspect_sandbox_image_id(docker_bin: str, image: str) -> str:
    """Resolve an already-present image by immutable digest.

    Some Docker Engine versions reject ``image inspect repo@sha256:...`` even
    when that exact value appears in the local image's RepoDigests. Fall back
    to the daemon's digest listing and require an exact repository+digest
    match; never substitute a tag or merely compatible image.
    """
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]*@sha256:[0-9a-f]{64}", image):
        raise RuntimeError("sandbox image must be pinned by immutable sha256 digest")
    try:
        return subprocess.check_output(
            [docker_bin, "image", "inspect", "--format", "{{.Id}}", image],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        listing = subprocess.check_output(
            [docker_bin, "image", "ls", "--digests", "--no-trunc", "--format",
             "{{.Repository}}@{{.Digest}} {{.ID}}"],
            text=True,
        )

    def canonical(reference: str) -> str:
        return reference.removeprefix("docker.io/")

    matches = [
        fields[1]
        for line in listing.splitlines()
        if len(fields := line.split(maxsplit=1)) == 2
        and canonical(fields[0]) == canonical(image)
    ]
    if len(matches) != 1 or not matches[0].startswith("sha256:"):
        available = [
            canonical(fields[0])
            for line in listing.splitlines()
            if len(fields := line.split(maxsplit=1)) == 2
        ]
        raise RuntimeError(
            "rootless daemon does not contain the exact pinned sandbox digest: "
            f"expected={canonical(image)!r}, available={available!r}"
        )
    return matches[0]


def workspace_diff_evidence_markers(messages: list[dict[str, Any]]) -> dict[str, bool]:
    """Record whether bounded native diff evidence was present in any API role."""
    request_text = "\n".join(
        str(message.get("content") or "")
        for message in messages
        if isinstance(message, dict)
    )
    return {
        "workspace_diff_evidence_present": "<workspace_diff>" in request_text,
        "workspace_diff_evidence_truncated": "diff evidence below is truncated" in request_text.lower(),
        "workspace_diff_evidence_unavailable": "diff evidence is unavailable" in request_text.lower(),
    }


def reset_and_warm_model(base_url: str) -> int:
    """Give each comparison arm the same loaded model and prompt-cache seed."""
    unloaded = local_json(
        f"{base_url}/api/chat",
        {"model": MODEL, "messages": [], "keep_alive": 0},
        timeout=180,
    )
    if unloaded.get("done_reason") != "unload":
        raise RuntimeError("Ollama did not confirm model unload before a comparison arm")
    if any(
        row.get("name") == MODEL
        for row in local_json(f"{base_url}/api/ps").get("models", [])
    ):
        raise RuntimeError("Ollama still reports the model loaded after arm cache reset")
    local_json(
        f"{base_url}/api/generate",
        {
            "model": MODEL,
            "prompt": "hi",
            "stream": False,
            "options": {"num_ctx": 65536, "num_predict": 4},
        },
        timeout=180,
    )
    loaded = next(
        (
            row for row in local_json(f"{base_url}/api/ps").get("models", [])
            if row.get("name") == MODEL
        ),
        None,
    )
    if not loaded:
        raise RuntimeError("Ollama did not report the warmed model before a comparison arm")
    context_length = loaded.get("context_length")
    if not isinstance(context_length, int) or context_length < 1:
        raise RuntimeError("Ollama did not report a valid loaded context length")
    if context_length < 65536:
        raise RuntimeError(f"Ollama loaded context is too small for comparison: {context_length}")
    return context_length


class ProviderProxy(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], ollama_port: int,
                 fixture_names: tuple[str, str]):
        self.ollama_port = ollama_port
        self.fixture_names = fixture_names
        self.records: list[dict[str, Any]] = []
        self.records_lock = threading.Lock()
        self.seed_counts: dict[tuple[str, int, str], int] = {}
        self.seed_lock = threading.Lock()
        self.first_phase_requests: dict[
            tuple[int, str], tuple[str, bytes, bytes, bytes]
        ] = {}
        self.last_diagnosis_contexts: dict[
            tuple[str, int], tuple[bytes, bytes, bytes]
        ] = {}
        self.pair_lock = threading.Lock()
        super().__init__(address, self.handler_type())

    def sampling_seed(self, stack: str, repeat: int, phase: str) -> tuple[int, int]:
        phase_offsets = {"diagnose": 0, "fix": 1000, "read": 2000, "other": 3000}
        key = (stack, repeat, phase)
        with self.seed_lock:
            ordinal = self.seed_counts.get(key, 0)
            self.seed_counts[key] = ordinal + 1
        # Matching stacks receive the same seed for each provider-call ordinal
        # within a task phase, even when their tool loops use different counts.
        return 41000 + repeat * 10000 + phase_offsets.get(phase, 3000) + ordinal, ordinal

    def handler_type(self):
        parent = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args):
                return

            def do_GET(self):
                body = json.dumps({"data": [{"id": MODEL, "owned_by": "local"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                started = time.perf_counter()
                raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                try:
                    request = json.loads(raw)
                except (ValueError, TypeError):
                    request = {}
                messages = request.get("messages") or []
                schemas = request.get("tools") or []
                latest_user = next(
                    (str(m.get("content") or "") for m in reversed(messages)
                     if isinstance(m, dict) and m.get("role") == "user"),
                    "",
                )
                phase = (
                    "diagnose" if latest_user.strip() == DIAGNOSE_PROMPT else
                    "fix" if latest_user.strip() == FIX_PROMPT else
                    "read" if latest_user.strip() == PROMPT else "other"
                )
                auth = self.headers.get("Authorization", "")
                api_key = auth.removeprefix("Bearer ").strip()
                benchmark_identity = re.fullmatch(
                    re.escape(API_KEY) + r"-(plain|hades)-(\d+)", api_key
                )
                stack = benchmark_identity.group(1) if benchmark_identity else None
                repeat = int(benchmark_identity.group(2)) if benchmark_identity else None
                sampling_seed, sampling_call_ordinal = (
                    parent.sampling_seed(stack, repeat, phase)
                    if stack is not None and repeat is not None else (None, None)
                )
                # Capture generation controls without retaining messages, tool
                # arguments, credentials, or arbitrary provider metadata. These
                # fields help distinguish middleware changes from model/runtime
                # sampling differences in paired measurements.
                requested_model_parameters = {
                    key: request[key]
                    for key in sorted(MODEL_PARAMETER_FIELDS)
                    if key in request and isinstance(request[key], (str, int, float, bool, type(None)))
                }
                for container_key in ("options", "model_options"):
                    nested = request.get(container_key)
                    if isinstance(nested, dict):
                        selected = {
                            key: nested[key]
                            for key in sorted(MODEL_PARAMETER_FIELDS)
                            if key in nested and isinstance(
                                nested[key], (str, int, float, bool, type(None))
                            )
                        }
                        if selected:
                            requested_model_parameters[container_key] = selected
                requested_model = request.get("model")
                request["model"] = MODEL
                if sampling_seed is not None:
                    request["seed"] = sampling_seed
                model_parameters = dict(requested_model_parameters)
                if sampling_seed is not None:
                    model_parameters["seed"] = sampling_seed
                profile_context = bool(
                    stack is not None and repeat is not None
                    and (phase == "diagnose" or (
                        phase == "fix" and sampling_call_ordinal == 0
                    ))
                )
                system_bytes = history_bytes = schema_bytes = b""
                if profile_context:
                    encode = lambda value: json.dumps(
                        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                    ).encode("utf-8", errors="replace")
                    system_bytes = encode([
                        message.get("content") for message in messages
                        if isinstance(message, dict) and message.get("role") == "system"
                    ])
                    history_bytes = encode(messages)
                    schema_bytes = encode(schemas)
                row: dict[str, Any] = {
                    "phase": phase,
                    "model": requested_model,
                    "effective_model": MODEL,
                    "benchmark_stack": stack,
                    "benchmark_repeat": repeat,
                    "sampling_seed": sampling_seed,
                    "sampling_call_ordinal": sampling_call_ordinal,
                    "requested_model_parameters": requested_model_parameters,
                    "model_parameters": model_parameters,
                    "stream": bool(request.get("stream")),
                    "tool_choice": request.get("tool_choice"),
                    "request_bytes": len(raw),
                    "message_roles": [m.get("role") for m in messages if isinstance(m, dict)],
                    "message_content_bytes_by_role": {
                        role: sum(
                            len(str(m.get("content") or "").encode("utf-8", errors="replace"))
                            for m in messages if isinstance(m, dict) and m.get("role") == role
                        )
                        for role in sorted({
                            m.get("role") for m in messages
                            if isinstance(m, dict) and isinstance(m.get("role"), str)
                        })
                    },
                    "message_content_markers": {
                        "prior_user_has_diagnosis_prompt": any(
                            isinstance(m, dict) and m.get("role") == "user"
                            and str(m.get("content") or "").strip() == DIAGNOSE_PROMPT
                            for m in messages[:-1]
                        ),
                        "prior_assistant_mentions_fixture": any(
                            isinstance(m, dict) and m.get("role") == "assistant"
                            and any(marker in str(m.get("content") or "")
                                    for marker in (*parent.fixture_names, "rectangle_area", "celsius_to_fahrenheit", "discounted_total"))
                            for m in messages[:-1]
                        ),
                        **workspace_diff_evidence_markers(messages),
                    },
                    "message_bytes": sum(
                        len(json.dumps(m, ensure_ascii=False, separators=(",", ":")).encode())
                        for m in messages if isinstance(m, dict)
                    ),
                    "tool_schema_count": len(schemas),
                    "tool_schema_bytes": sum(
                        len(json.dumps(s, ensure_ascii=False, separators=(",", ":")).encode())
                        for s in schemas
                    ),
                    "tool_schema_sha256": hashlib.sha256(json.dumps(
                        schemas, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                    ).encode("utf-8", errors="replace")).hexdigest(),
                    "tool_schema_names": [
                        s.get("function", {}).get("name") for s in schemas
                        if isinstance(s, dict)
                    ],
                    "tool_calls": {},
                    "finish_reasons": [],
                    "first_event_ms": None,
                    "first_content_ms": None,
                    "first_reasoning_ms": None,
                    "first_tool_call_delta_ms": None,
                    "content_delta_count": 0,
                    "reasoning_delta_count": 0,
                    "reasoning_content_bytes": 0,
                    "tool_call_delta_count": 0,
                    "usage": None,
                    "status": None,
                }
                if stack is not None and repeat is not None:
                    context_key = (stack, repeat)
                    if phase == "diagnose":
                        with parent.pair_lock:
                            parent.last_diagnosis_contexts[context_key] = (
                                system_bytes, history_bytes, schema_bytes,
                            )
                    elif phase == "fix" and sampling_call_ordinal == 0:
                        with parent.pair_lock:
                            previous_context = parent.last_diagnosis_contexts.get(context_key)
                        if previous_context is not None:
                            row.update({
                                "diagnosis_to_action_system_lcp_bytes": common_prefix_byte_count(
                                    previous_context[0], system_bytes
                                ),
                                "diagnosis_to_action_history_lcp_bytes": common_prefix_byte_count(
                                    previous_context[1], history_bytes
                                ),
                                "diagnosis_to_action_schema_lcp_bytes": common_prefix_byte_count(
                                    previous_context[2], schema_bytes
                                ),
                                "diagnosis_to_action_system_same": previous_context[0] == system_bytes,
                                "diagnosis_to_action_history_same": previous_context[1] == history_bytes,
                                "diagnosis_to_action_schema_same": previous_context[2] == schema_bytes,
                            })
                if (
                    stack is not None and repeat is not None
                    and phase in {"diagnose", "fix"} and sampling_call_ordinal == 0
                ):
                    row["first_request_system_bytes"] = len(system_bytes)
                    row["first_request_messages_bytes"] = len(history_bytes)
                    row["first_request_schemas_bytes"] = len(schema_bytes)
                    pair_key = (repeat, phase)
                    with parent.pair_lock:
                        previous = parent.first_phase_requests.get(pair_key)
                        if previous is None:
                            parent.first_phase_requests[pair_key] = (
                                stack, system_bytes, history_bytes, schema_bytes,
                            )
                        elif previous[0] != stack:
                            metrics = {
                                "paired_first_request_system_prefix_bytes": common_prefix_byte_count(
                                    previous[1], system_bytes
                                ),
                                "paired_first_request_messages_prefix_bytes": common_prefix_byte_count(
                                    previous[2], history_bytes
                                ),
                                "paired_first_request_schemas_prefix_bytes": common_prefix_byte_count(
                                    previous[3], schema_bytes
                                ),
                                "paired_first_request_schemas_identical": previous[3] == schema_bytes,
                            }
                            row.update(metrics)
                            del parent.first_phase_requests[pair_key]
                connection = http.client.HTTPConnection("127.0.0.1", parent.ollama_port, timeout=300)
                try:
                    connection.request(
                        "POST", self.path, body=json.dumps(request).encode(),
                        headers={"Content-Type": "application/json"},
                    )
                    response = connection.getresponse()
                    row["status"] = response.status
                    content_type = response.getheader("Content-Type", "application/json")
                    self.send_response(response.status)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "close")
                    self.close_connection = True
                    if request.get("stream") and "text/event-stream" in content_type:
                        self.send_header("Transfer-Encoding", "chunked")
                        self.end_headers()
                        while line := response.readline():
                            if line.startswith(b"data:"):
                                data = line[5:].strip()
                                if data and data != b"[DONE]":
                                    try:
                                        event = json.loads(data)
                                        if row["first_event_ms"] is None:
                                            row["first_event_ms"] = round((time.perf_counter() - started) * 1000, 1)
                                        choices = event.get("choices") or []
                                        choice = choices[0] if choices else {}
                                        delta = choice.get("delta") or {}
                                        content = delta.get("content")
                                        if isinstance(content, str) and content:
                                            row["content_delta_count"] += 1
                                            if row["first_content_ms"] is None:
                                                row["first_content_ms"] = round((time.perf_counter() - started) * 1000, 1)
                                        # Count private reasoning payloads without retaining them.
                                        reasoning = next((
                                            delta.get(key) for key in ("reasoning", "reasoning_content", "analysis")
                                            if isinstance(delta.get(key), str) and delta.get(key)
                                        ), None)
                                        if reasoning is not None:
                                            row["reasoning_delta_count"] += 1
                                            row["reasoning_content_bytes"] += len(reasoning.encode("utf-8", errors="replace"))
                                            if row["first_reasoning_ms"] is None:
                                                row["first_reasoning_ms"] = round((time.perf_counter() - started) * 1000, 1)
                                        calls = delta.get("tool_calls") or []
                                        if calls:
                                            row["tool_call_delta_count"] += len(calls)
                                            if row["first_tool_call_delta_ms"] is None:
                                                row["first_tool_call_delta_ms"] = round((time.perf_counter() - started) * 1000, 1)
                                        for call in calls:
                                            index = call.get("index", 0)
                                            target = row["tool_calls"].setdefault(index, "")
                                            target += (call.get("function") or {}).get("name", "")
                                            row["tool_calls"][index] = target
                                        if choice.get("finish_reason"):
                                            row["finish_reasons"].append(choice["finish_reason"])
                                        if event.get("usage"):
                                            row["usage"] = event["usage"]
                                    except (ValueError, TypeError, IndexError):
                                        pass
                            self.wfile.write(f"{len(line):X}\r\n".encode() + line + b"\r\n")
                            self.wfile.flush()
                        self.wfile.write(b"0\r\n\r\n")
                    else:
                        body = response.read()
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                        try:
                            data = json.loads(body)
                            row["usage"] = data.get("usage")
                        except (ValueError, TypeError):
                            pass
                except Exception as exc:
                    row["error_type"] = type(exc).__name__
                    try:
                        self.send_error(502)
                    except OSError:
                        pass
                finally:
                    connection.close()
                    row["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
                    try:
                        loaded = local_json(
                            f"http://127.0.0.1:{parent.ollama_port}/api/ps"
                        ).get("models", [])
                        loaded_model = next(
                            (item for item in loaded if item.get("name") == MODEL), None
                        )
                        row["loaded_context_length_after_request"] = (
                            loaded_model.get("context_length") if loaded_model else None
                        )
                    except (OSError, ValueError, urllib.error.URLError):
                        row["loaded_context_length_after_request"] = None
                    with parent.records_lock:
                        parent.records.append(row)

        return Handler

    def snapshot(self) -> list[dict[str, Any]]:
        with self.records_lock:
            return [dict(row) for row in self.records]


def wait_gateway(port: int, proc: subprocess.Popen, log: pathlib.Path) -> None:
    for _ in range(90):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            pass
        if proc.poll() is not None:
            break
        time.sleep(0.5)
    raise RuntimeError(f"gateway did not become healthy (exit={proc.poll()}): {log.read_text(errors='replace')[-3000:]}")


def install_required_terminal_experiment(agent: Any) -> tuple[dict[str, Any], Any]:
    """Prototype a named Hermes tool choice after a workspace code mutation.

    This benchmark-only intervention observes successful code writes at Hermes'
    existing tool executor boundary. The next action-turn generation must call
    the native terminal tool once. It restores the prior request overrides after
    that call so a failed test can be repaired and a passing test can be reported.
    """
    from types import SimpleNamespace
    from hermes.workspace import has_successful_workspace_code_mutation, workspace_code_test_status

    state: dict[str, Any] = {
        "active": False,
        "pending": False,
        "forced_terminal_calls": 0,
        "terminal_result_status": None,
        "required_choice_installed": False,
    }
    original_execute = agent._execute_tool_calls

    def restore_choice() -> None:
        saved = state.pop("saved_request_overrides", None)
        if isinstance(saved, dict):
            agent.request_overrides = saved
        state["pending"] = False

    def experimental_execute(assistant_message: Any, messages: list, effective_task_id: str, api_call_count: int = 0) -> None:
        if not state["active"]:
            return original_execute(assistant_message, messages, effective_task_id, api_call_count)

        calls = list(getattr(assistant_message, "tool_calls", None) or [])
        terminal_calls = [
            call for call in calls
            if str(getattr(getattr(call, "function", None), "name", "")) == "terminal"
        ]
        was_pending = bool(state["pending"])
        results_start = len(messages)
        original_execute(assistant_message, messages, effective_task_id, api_call_count)

        if was_pending and terminal_calls:
            state["forced_terminal_calls"] += len(terminal_calls)
            current_start = next(
                (
                    idx for idx in range(len(messages) - 1, -1, -1)
                    if isinstance(messages[idx], dict)
                    and messages[idx].get("role") == "user"
                    and messages[idx].get("content") == state.get("current_user_message")
                ),
                None,
            )
            current_messages = messages[current_start:] if current_start is not None else []
            state["terminal_result_status"] = workspace_code_test_status(current_messages)
            restore_choice()

        # Inspect only results appended by this tool batch. If patch and terminal
        # appeared together, require a fresh follow-up after the mutation so a
        # parallel/stale test result cannot stand in for post-patch verification.
        if has_successful_workspace_code_mutation(messages[results_start:]):
            state["saved_request_overrides"] = dict(getattr(agent, "request_overrides", {}) or {})
            agent.request_overrides = {
                **state["saved_request_overrides"],
                "tool_choice": REQUIRED_TERMINAL_CHOICE,
            }
            state["pending"] = True
            state["required_choice_installed"] = True

    agent._execute_tool_calls = experimental_execute
    return state, original_execute


def install_host_workspace_verification_mapping(
    agent: Any, workspace: pathlib.Path,
) -> tuple[dict[str, Any], Any, Any]:
    """Prototype mapping Hermes Docker paths to this isolated host project.

    This is benchmark-only. Production support would need to obtain the current
    task's validated mounted host root at the upstream finalizer boundary.
    """
    from tools import terminal_tool_result

    root = workspace.resolve(strict=True)
    state = {
        "active": True,
        "mapped_mutation_path_count": 0,
        "mapped_terminal_evidence_cwd_count": 0,
    }

    def map_workspace_path(raw: Any) -> str | None:
        if not isinstance(raw, (str, pathlib.Path)):
            return None
        try:
            path = pathlib.PurePosixPath(str(raw))
            prefix = ("/", "workspace")
            if path.parts[:2] != prefix:
                return None
            relative = pathlib.Path(*path.parts[2:])
            if ".." in relative.parts:
                return None
            candidate = (root / relative).resolve(strict=False)
            if not candidate.is_relative_to(root):
                return None
            return str(candidate)
        except (OSError, RuntimeError, ValueError):
            return None

    original_record_mutation = agent._record_file_mutation_result

    def record_mutation_with_host_paths(
        tool_name: str, args: dict[str, Any], result: Any, is_error: bool,
        *, task_id: str | None = None,
    ) -> None:
        original_record_mutation(tool_name, args, result, is_error, task_id=task_id)
        changed_paths = getattr(agent, "_turn_file_mutation_paths", None)
        if not isinstance(changed_paths, set):
            return
        replacements = {
            raw: mapped for raw in tuple(changed_paths)
            if (mapped := map_workspace_path(raw)) is not None
        }
        if replacements:
            changed_paths.difference_update(replacements)
            changed_paths.update(replacements.values())
            state["mapped_mutation_path_count"] += len(replacements)

    original_verification_evidence = terminal_tool_result._verification_evidence

    def record_evidence_with_host_cwd(
        command: Any, cwd: Any, session_id: Any, returncode: Any, output: Any,
    ) -> Any:
        mapped = map_workspace_path(cwd)
        if mapped is not None and pathlib.Path(mapped).is_relative_to(root):
            state["mapped_terminal_evidence_cwd_count"] += 1
            cwd = mapped
        return original_verification_evidence(command, cwd, session_id, returncode, output)

    agent._record_file_mutation_result = record_mutation_with_host_paths
    terminal_tool_result._verification_evidence = record_evidence_with_host_cwd
    return state, original_record_mutation, original_verification_evidence


def child(args: argparse.Namespace) -> int:
    fixture_case = FIXTURE_CASES[args.fixture_case]
    fixture_names = (
        ("README.md", "Makefile") if args.scenario == "readme" else
        (fixture_case["source"],) if args.scenario == "explain" else
        tuple(SEARCH_FILES) if args.scenario == "search"
        else (fixture_case["source"], fixture_case["test"])
    )
    fixture_name_pattern = "|".join(re.escape(name) for name in fixture_names)
    hermes = str(hermes_source(args.hermes_root))
    if args.overlay:
        sys.path[:0] = [str(ROOT / "hermes"), str(ROOT), hermes]
    else:
        sys.path.insert(0, hermes)
    from run_agent import AIAgent
    from tools.terminal_scope import install_profile_terminal_scope, reset_terminal_scope
    from tools.terminal_tool import (
        _get_env_config, clear_task_env_overrides, register_task_env_overrides,
    )
    from tools.environments.docker import DockerEnvironment

    # Capture only the effective Docker workspace mount decision and a small
    # sanitized view of Hermes tool results. This diagnoses empty-workspace
    # reports without persisting commands, file contents, prompts, or secrets.
    mount_traces: list[dict[str, Any]] = []
    original_mount_args = DockerEnvironment._mount_args

    def traced_mount_args(self, volumes, host_cwd, auto_mount_cwd, task_id):
        volume_args, writable_args = original_mount_args(
            self, volumes, host_cwd, auto_mount_cwd, task_id
        )
        normalized_host = os.path.abspath(os.path.expanduser(host_cwd)) if host_cwd else ""
        targets = [
            volume_args[i + 1].split(":", 2)[1]
            for i, arg in enumerate(volume_args[:-1])
            if arg == "-v" and ":" in volume_args[i + 1]
        ]
        mount_traces.append({
            "task_id_matches": str(task_id).endswith(str(args.repeat)),
            "host_cwd_matches_fixture": normalized_host == os.path.abspath(str(args.workspace)),
            "auto_mount_cwd": bool(auto_mount_cwd),
            "workspace_volume_target_present": "/workspace" in targets,
            "workspace_tmpfs_present": any(
                arg == "--tmpfs" and i + 1 < len(writable_args)
                and writable_args[i + 1].startswith("/workspace")
                for i, arg in enumerate(writable_args)
            ),
            "workdir_is_workspace": getattr(self, "cwd", None) == "/workspace",
        })
        return volume_args, writable_args

    DockerEnvironment._mount_args = traced_mount_args

    token = install_profile_terminal_scope(pathlib.Path(os.environ["HERMES_HOME"]))
    task_id = f"workspace-{args.stack}-{args.repeat}"
    # Match the session-workdir registration performed by Hermes gateway/TUI
    # surfaces. Docker session isolation deliberately refuses to mount the
    # process-level cwd for an unregistered session.
    register_task_env_overrides(task_id, {
        "cwd": str(args.workspace), "cwd_source": "session", "env_type": "docker",
    })
    terminal_config = _get_env_config()
    effective_terminal = {
        "env_type": terminal_config.get("env_type"),
        "cwd_is_fixture": terminal_config.get("cwd") == str(args.workspace),
        "docker_mount_cwd_to_workspace": terminal_config.get("docker_mount_cwd_to_workspace"),
        "docker_network": terminal_config.get("docker_network"),
        "session_workspace_registered": True,
        "configured_host_cwd_matches_fixture": os.path.abspath(str(terminal_config.get("host_cwd") or ""))
        == os.path.abspath(str(args.workspace)),
    }
    if effective_terminal["env_type"] != "docker" or not effective_terminal["docker_mount_cwd_to_workspace"]:
        raise RuntimeError(f"profile did not activate the intended Docker workspace: {effective_terminal}")
    messages: list[dict[str, Any]] = []
    stream_state = {"phase": "setup", "started": time.perf_counter()}
    stream_metrics: dict[str, dict[str, Any]] = {}

    def capture_stream_delta(text: Any) -> None:
        """Record user-stream timing and size only; never persist generated text."""
        if not isinstance(text, str) or not text:
            return
        phase_name = str(stream_state["phase"])
        now = time.perf_counter()
        row = stream_metrics.setdefault(phase_name, {
            "delta_count": 0, "character_count": 0,
            "first_delta_ms": None, "last_delta_ms": None,
        })
        delta_ms = round((now - float(stream_state["started"])) * 1000, 1)
        row["delta_count"] += 1
        row["character_count"] += len(text)
        if row["first_delta_ms"] is None:
            row["first_delta_ms"] = delta_ms
        row["last_delta_ms"] = delta_ms

    agent = AIAgent(
        base_url=args.provider_url,
        api_key=f"{API_KEY}-{args.stack}-{args.repeat}",
        provider="custom",
        api_mode="chat_completions",
        model=MODEL,
        max_tokens=512 if args.scenario == "escalation" else 192,
        reasoning_config={"enabled": False},
        enabled_toolsets=["file", "terminal"],
        disabled_toolsets=[],
        gateway_session_key="hades-user-synthetic-owner",
        session_id=f"workspace-{args.stack}-{args.repeat}",
        chat_id=f"workspace-{args.stack}-{args.repeat}",
        stream_delta_callback=capture_stream_delta,
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
        skip_background_review=True,
        load_soul_identity=False,
    )
    tool_validation_diagnostics: list[dict[str, Any]] = []
    original_repair_tool_call = agent._repair_tool_call

    def capture_tool_validation_catalog(name: str):
        # Record only names from this benchmark's fixed workspace-tool allowlist.
        # The model-emitted name may contain arbitrary text and is not retained.
        workspace_names = {"read_file", "search_files", "write_file", "patch", "terminal"}
        catalog_snapshot = workspace_catalog_snapshot(agent)
        tool_validation_diagnostics.append({
            "phase": str(stream_state["phase"]),
            "attempted_workspace_tool": name if name in workspace_names else "other",
            **catalog_snapshot,
        })
        return original_repair_tool_call(name)

    agent._repair_tool_call = capture_tool_validation_catalog
    tool_choice_experiment = None
    original_tool_executor = None
    if args.prototype_force_terminal_after_mutation and args.stack == "hades":
        tool_choice_experiment, original_tool_executor = install_required_terminal_experiment(agent)
    workspace_mapping_experiment = None
    original_mutation_recorder = None
    original_verification_evidence = None
    started = time.perf_counter()
    try:
        if args.prototype_host_workspace_verification_mapping:
            from agent.verification_stop import verify_on_stop_enabled
            if not verify_on_stop_enabled():
                raise RuntimeError("host workspace mapping prototype requires native verify-on-stop")
            (
                workspace_mapping_experiment,
                original_mutation_recorder,
                original_verification_evidence,
            ) = install_host_workspace_verification_mapping(agent, args.workspace)
        prompts = ([PROMPT] if args.scenario == "read" else
                   [README_PROMPT] if args.scenario == "readme" else
                   [EXPLAIN_PROMPT] if args.scenario == "explain" else
                   [SEARCH_PROMPT] if args.scenario == "search" else
                   [SMALL_EDIT_CONTEXT_PROMPT, SMALL_EDIT_PROMPT]
                   if args.scenario == "small-edit" else
                   [SMALL_EDIT_CONTEXT_PROMPT, SMALL_EDIT_PROMPT, FOCUSED_TEST_PROMPT]
                   if args.scenario == "small-edit-verify" else
                   [SMALL_EDIT_CONTEXT_PROMPT, SMALL_EDIT_PROMPT, FOCUSED_TEST_PROMPT,
                    SMALL_DIFF_PROMPT, COMMIT_PROMPT]
                   if args.scenario == "workflow-to-commit" else
                   [DIAGNOSE_PROMPT, FIX_PROMPT])
        history: list[dict[str, Any]] = []
        turns = []
        for phase, prompt in enumerate(prompts):
            phase_name = ("read" if args.scenario == "read" else
                          "readme" if args.scenario == "readme" else
                          "explain" if args.scenario == "explain" else
                          "search" if args.scenario == "search" else
                          ("inspect" if phase == 0 else "edit")
                          if args.scenario == "small-edit" else
                          ("inspect" if phase == 0 else
                           "edit" if phase == 1 else "focused_test")
                          if args.scenario == "small-edit-verify" else
                          ("inspect" if phase == 0 else
                           "edit" if phase == 1 else
                           "focused_test" if phase == 2 else
                           "review_diff" if phase == 3 else "commit")
                          if args.scenario == "workflow-to-commit" else
                          ("diagnose" if phase == 0 else "fix"))
            stream_state["phase"] = phase_name
            stream_state["started"] = time.perf_counter()
            if tool_choice_experiment is not None:
                tool_choice_experiment["active"] = phase_name == "fix"
                tool_choice_experiment["current_user_message"] = prompt
            prior_history = history
            workspace_head_before = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=args.workspace, text=True,
            ).strip() if args.scenario == "workflow-to-commit" else None
            run_arguments = {
                "user_message": prompt,
                "task_id": task_id,
                "conversation_history": prior_history,
            }
            if args.stack == "hades":
                result, route_return_line = call_with_return_line(
                    agent.run_conversation, **run_arguments
                )
            else:
                result = agent.run_conversation(**run_arguments)
                route_return_line = None
            messages = result.get("messages") if isinstance(result, dict) else []
            messages = messages if isinstance(messages, list) else []
            # Hermes may return the full transcript or just the latest turn. Keep
            # same-chat continuity while counting only messages added this turn.
            prefix_matches = bool(prior_history) and messages[:len(prior_history)] == prior_history
            turn_messages = messages[len(prior_history):] if prefix_matches else messages
            next_history = (
                messages if prefix_matches else [*prior_history, *messages]
            )
            if not next_history:
                next_history = list(prior_history)
            final_text = str(result.get("final_response") or "") if isinstance(result, dict) else ""
            last_assistant_text = next(
                (str(message.get("content") or "") for message in reversed(next_history)
                 if isinstance(message, dict) and message.get("role") == "assistant"),
                "",
            )
            # AIAgent can return the displayed final answer separately from the
            # replayable messages list. Keep the next “Fix it” turn grounded in
            # what the user actually saw, even when Hermes omitted that row.
            if final_text and last_assistant_text != final_text:
                next_history.append({"role": "assistant", "content": final_text})
            tool_messages = [
                m for m in turn_messages if isinstance(m, dict) and m.get("role") == "tool"
            ]
            safe_tool_results = []
            for message in tool_messages:
                content = str(message.get("content") or "")
                parsed = None
                try:
                    parsed = json.loads(content)
                except (ValueError, TypeError):
                    pass
                safe_tool_results.append({
                    "name": message.get("name"),
                    "content_bytes": len(content.encode("utf-8", errors="replace")),
                    "error_marker": bool(re.search(
                        r"(?i)(no such file|does not exist|not found|permission denied|tool_error|exit_code\s*[=:]\s*[1-9])",
                        content,
                    )),
                    "exit_code": parsed.get("exit_code") if isinstance(parsed, dict) else None,
                    "structured_result_keys": sorted(parsed) if isinstance(parsed, dict) else None,
                    "verification_evidence_status": (
                        (parsed.get("verification_evidence") or {}).get("status")
                        if isinstance(parsed, dict)
                        and isinstance(parsed.get("verification_evidence"), dict)
                        else None
                    ),
                    "structured_list_counts": {
                        key: len(value) for key, value in parsed.items()
                        if isinstance(parsed, dict) and isinstance(value, list)
                        and key in {"matches", "files", "results"}
                    } if isinstance(parsed, dict) else None,
                    "error_class": (
                        "not_found" if re.search(r"(?i)(not found|no such file|does not exist)", str(parsed.get("error") or "")) else
                        "permission" if re.search(r"(?i)(permission denied|not permitted|access denied)", str(parsed.get("error") or "")) else
                        "cwd" if re.search(r"(?i)(working directory|current directory|chdir|cd:)", str(parsed.get("error") or "")) else
                        "other" if parsed.get("error") else None
                    ) if isinstance(parsed, dict) else (
                        "invalid_tool" if re.search(r"(?i)tool .{1,60} does not exist|unknown tool", content) else
                        "not_found" if re.search(r"(?i)(not found|no such file|does not exist)", content) else
                        "permission" if re.search(r"(?i)(permission denied|not permitted|access denied)", content) else
                        "cwd" if re.search(r"(?i)(working directory|current directory|chdir|cd:)", content) else
                        "other" if re.search(r"(?i)\berror\b|failed", content) else None
                    ),
                    "error_kind": (
                        "unknown_tool" if re.search(r"(?i)unknown tool", content) else
                        "tool_not_available" if re.search(r"(?i)tool .{1,60} not available", content) else
                        "tool_not_found" if re.search(r"(?i)tool .{1,60} does not exist", content) else
                        "invalid_arguments" if re.search(r"(?i)(invalid|missing|required) (?:tool )?(?:argument|parameter|field)", content) else
                        "permission" if re.search(r"(?i)(permission denied|not permitted|access denied)", content) else
                        "command_not_found" if re.search(r"(?i)command not found", content) else
                        "other_error" if re.search(r"(?i)\berror\b|failed", content) else None
                    ),
                    "has_output": bool(parsed.get("output")) if isinstance(parsed, dict) else None,
                    "test_output_markers": {
                        "unittest_summary": bool(re.search(r"(?i)Ran \d+ tests?", content)),
                        "pytest_summary": bool(re.search(r"(?i)(\d+ passed|\d+ failed|pytest)", content)),
                        "success_marker": bool(re.search(r"(?i)(?:^|\n)OK(?:\n|$)|\bpassed\b", content)),
                    } if message.get("name") == "terminal" else None,
                    "known_fixture_name_present": any(
                        name in content for name in fixture_names
                    ),
                })
            safe_tool_calls = []
            for message in turn_messages:
                if not isinstance(message, dict) or message.get("role") != "assistant":
                    continue
                for call in message.get("tool_calls") or []:
                    function = call.get("function") if isinstance(call, dict) else None
                    if not isinstance(function, dict):
                        continue
                    raw_arguments = function.get("arguments") or {}
                    if isinstance(raw_arguments, str):
                        try:
                            raw_arguments = json.loads(raw_arguments)
                        except (ValueError, TypeError):
                            raw_arguments = {}
                    raw_arguments = raw_arguments if isinstance(raw_arguments, dict) else {}
                    path_values = [
                        value for key, value in raw_arguments.items()
                        if key in {"path", "file_path", "cwd", "directory"}
                        and isinstance(value, str)
                    ]
                    command_value = raw_arguments.get("command")
                    safe_tool_calls.append({
                        "name": function.get("name"),
                        "argument_keys": sorted(str(key) for key in raw_arguments),
                        "path_count": len(path_values),
                        "all_paths_in_workspace": all(
                            value == "/workspace" or value.startswith("/workspace/")
                            for value in path_values
                        ),
                        "mentions_fixture_name": any(
                            name in value for value in path_values
                            for name in fixture_names
                        ) or (
                            isinstance(command_value, str) and any(
                                name in command_value for name in fixture_names
                            )
                        ),
                        "command_looks_read_only": isinstance(command_value, str) and bool(re.search(
                            r"(?i)\b(cat|head|tail|sed|grep|rg|find|pwd|ls|python\s+-m\s+unittest)\b",
                            command_value,
                        )),
                        "command_has_write_marker": isinstance(command_value, str) and bool(re.search(
                            r"(?i)(?:\b(?:sed\s+-i|tee|cp|mv|rm|touch|chmod|chown|install|git\s+(?:apply|checkout|reset|restore))\b|"
                            r"(?:^|\s)(?:>|>>|\|\s*tee\b)|\bpython\s+-c\b|\bperl\s+-pi\b)",
                            command_value,
                        )),
                        "command_has_shell_redirect": isinstance(command_value, str) and bool(re.search(
                            r"(?:^|\s)(?:>|>>|<|<<)(?:\s|$)", command_value,
                        )),
                        "command_mentions_fixture_mutation": isinstance(command_value, str) and bool(re.search(
                            rf"(?i)(?:{fixture_name_pattern}).{{0,80}}(?:write|patch|replace|multiply|\*|sed\s+-i)|"
                            rf"(?:write|patch|replace|multiply|\*|sed\s+-i).{{0,80}}(?:{fixture_name_pattern})",
                            command_value,
                        )),
                        "runs_unittest": command_runs_tests(command_value),
                        "uses_git_diff": isinstance(command_value, str) and bool(re.search(
                            r"(?i)\bgit\s+diff\b", command_value
                        )),
                        "uses_git_commit": isinstance(command_value, str) and bool(re.search(
                            r"(?i)\bgit\s+commit\b", command_value
                        )),
                        "search_pattern_nonempty": (
                            isinstance(raw_arguments.get("pattern"), str)
                            and bool(raw_arguments["pattern"].strip())
                        ) if function.get("name") == "search_files" else None,
                        "search_target": raw_arguments.get("target")
                        if function.get("name") == "search_files"
                        and raw_arguments.get("target") in {"content", "files", "grep", "find"}
                        else None,
                    })
            turns.append({
                "phase": phase_name,
                "prompt_id": phase_name,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                "stream_progress": stream_metrics.get(phase_name, {
                    "delta_count": 0, "character_count": 0,
                    "first_delta_ms": None, "last_delta_ms": None,
                }),
                "response_present": bool(final_text),
                "response_characters": len(final_text),
                "response_contains_expected_token": TOKEN in final_text,
                "response_contains_search_target": (
                    SEARCH_TARGET_PATH.casefold() in final_text.casefold()
                    and SEARCH_TARGET_VALUE in final_text
                ) if args.scenario == "search" else None,
                "response_contains_readme_run_target": (
                    "make test" in final_text.casefold()
                    and "unittest" in final_text.casefold()
                ) if args.scenario == "readme" else None,
                "response_contains_original_error_marker": (
                    "invlaid quantity" in final_text.casefold()
                ) if args.scenario in {"small-edit", "small-edit-verify"}
                and phase_name == "inspect" else None,
                "api_calls": result.get("api_calls") if isinstance(result, dict) else None,
                "hades_route_return_line": route_return_line,
                "tool_result_count": len(tool_messages),
                "tool_result_names": [m.get("name") for m in tool_messages],
                "sanitized_tool_results": safe_tool_results,
                "sanitized_tool_calls": safe_tool_calls,
                "tool_result_contains_fixture": any(
                    TOKEN in str(m.get("content") or "") for m in tool_messages
                ),
                "workspace_changed_after_turn": bool(subprocess.check_output(
                    ["git", "status", "--porcelain", "--untracked-files=all"],
                    cwd=args.workspace, text=True,
                ).splitlines()) if args.scenario in {
                    "escalation", "small-edit", "small-edit-verify", "workflow-to-commit"
                } else False,
                "git_head_changed_after_turn": (
                    subprocess.check_output(["git", "rev-parse", "HEAD"],
                                             cwd=args.workspace, text=True).strip()
                    != workspace_head_before
                ) if args.scenario == "workflow-to-commit" else False,
                "messages_added": len(turn_messages),
                "tool_validation_diagnostics": [
                    row for row in tool_validation_diagnostics
                    if row["phase"] == phase_name
                ],
            })
            history = next_history
        summary = {
            "scenario": args.scenario,
            "stack": args.stack,
            "repeat": args.repeat,
            "effective_terminal": effective_terminal,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "turns": turns,
            "api_calls": sum(t["api_calls"] or 0 for t in turns),
            "tool_result_count": sum(t["tool_result_count"] for t in turns),
            "tool_result_names": [name for t in turns for name in t["tool_result_names"]],
            "mount_traces": mount_traces,
            "tool_result_contains_fixture": any(t["tool_result_contains_fixture"] for t in turns),
            "assistant_response_count": sum(t["response_present"] for t in turns),
            "final_response_contains_expected_token": any(
                t["response_contains_expected_token"] for t in turns
            ),
            "tool_choice_experiment": ({
                key: value for key, value in tool_choice_experiment.items()
                if key not in {"saved_request_overrides", "current_user_message"}
            } if tool_choice_experiment is not None else None),
            "native_verification_stop_nudges": int(
                getattr(agent, "_verification_stop_nudges", 0) or 0
            ),
            "native_verification_terminal_evidence_statuses": [
                result.get("verification_evidence_status")
                for turn in turns
                for result in turn.get("sanitized_tool_results", [])
                if result.get("verification_evidence_status") is not None
            ],
            "host_workspace_mapping_experiment": workspace_mapping_experiment,
            "native_verification_snapshot": None,
        }
        try:
            from agent.coding_context import project_facts_for
            from agent.verification_evidence import verification_status
            from agent.verification_stop import verify_on_stop_enabled

            mutation_paths = sorted(
                str(path) for path in (getattr(agent, "_turn_file_mutation_paths", set()) or set())
                if path
            )
            path_rows = []
            for path in mutation_paths:
                cwd = str(pathlib.Path(path).parent)
                facts = project_facts_for(cwd)
                status = verification_status(
                    session_id=getattr(agent, "session_id", None), cwd=cwd
                )
                path_rows.append({
                    "project_facts_recognized": bool(facts),
                    "evidence_status": status.get("status"),
                    "workspace_mount_path": pathlib.PurePosixPath(path).parts[:2] == ("/", "workspace"),
                    "host_workspace_path": pathlib.Path(path).is_relative_to(args.workspace.resolve()),
                })
            runtime_cwd = None
            try:
                from agent.runtime_cwd import resolve_agent_cwd
                runtime_cwd = resolve_agent_cwd()
            except Exception:
                pass
            runtime_facts = project_facts_for(runtime_cwd) if runtime_cwd else None
            host_workspace_facts = project_facts_for(args.workspace)
            host_workspace_status = verification_status(
                session_id=getattr(agent, "session_id", None), cwd=args.workspace
            )
            summary["native_verification_snapshot"] = {
                "enabled": bool(verify_on_stop_enabled()),
                "mutated_code_path_count": len(mutation_paths),
                "project_facts_recognized_count": sum(
                    row["project_facts_recognized"] for row in path_rows
                ),
                "evidence_statuses": [row["evidence_status"] for row in path_rows],
                "container_workspace_path_count": sum(row["workspace_mount_path"] for row in path_rows),
                "host_workspace_path_count": sum(row["host_workspace_path"] for row in path_rows),
                "runtime_cwd_project_facts_recognized": bool(runtime_facts),
                "host_workspace_project_facts_recognized": bool(host_workspace_facts),
                "host_workspace_evidence_status": host_workspace_status.get("status"),
                "mapping_experiment_active": bool(workspace_mapping_experiment),
            }
        except Exception as exc:
            summary["native_verification_snapshot"] = {
                "capture_error_type": type(exc).__name__,
            }
        print("RESULT:" + json.dumps(summary, ensure_ascii=False))
        return 0
    finally:
        if original_tool_executor is not None:
            agent._execute_tool_calls = original_tool_executor
        if original_mutation_recorder is not None:
            agent._record_file_mutation_result = original_mutation_recorder
        if original_verification_evidence is not None:
            from tools import terminal_tool_result
            terminal_tool_result._verification_evidence = original_verification_evidence
        if tool_choice_experiment is not None and tool_choice_experiment.get("pending"):
            saved = tool_choice_experiment.get("saved_request_overrides")
            if isinstance(saved, dict):
                agent.request_overrides = saved
        agent.close()
        clear_task_env_overrides(task_id)
        reset_terminal_scope(token)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ollama-port", type=int, default=11445)
    parser.add_argument("--hermes-root", type=pathlib.Path, default=DEFAULT_HERMES)
    parser.add_argument("--hindsight-plugin", type=pathlib.Path, default=DEFAULT_PLUGIN)
    parser.add_argument("--docker-binary", type=pathlib.Path)
    parser.add_argument("--sandbox-image", default=IMAGE)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--scenario", choices=("read", "readme", "explain", "search", "escalation", "small-edit", "small-edit-verify", "workflow-to-commit"), default="read")
    parser.add_argument("--fixture-layout", choices=("compact", "multifile"), default="compact")
    parser.add_argument("--fixture-case", choices=tuple(FIXTURE_CASES))
    parser.add_argument(
        "--workspace-context-hint", action="store_true",
        help="give both stacks the same supported agent.environment_hint describing the /workspace mount",
    )
    parser.add_argument(
        "--prototype-force-terminal-after-mutation", action="store_true",
        help="benchmark-only HADES experiment: use Hermes tool_choice to require one terminal call after a successful workspace code mutation",
    )
    parser.add_argument(
        "--prototype-host-workspace-verification-mapping", action="store_true",
        help="benchmark-only prototype: map container /workspace edit/evidence paths to the current fixture root",
    )
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--stack", choices=("plain", "hades"))
    parser.add_argument("--repeat", type=int, default=0)
    parser.add_argument("--overlay", action="store_true")
    parser.add_argument("--home", type=pathlib.Path)
    parser.add_argument("--workspace", type=pathlib.Path)
    parser.add_argument("--provider-url")
    args = parser.parse_args()
    if args.fixture_case is None:
        args.fixture_case = "error_message" if args.scenario == "workflow-to-commit" else "geometry"
    fixture_case = FIXTURE_CASES[args.fixture_case]

    if args.child:
        return child(args)
    os.umask(0o077)
    if args.repeats < 1 or args.repeats > 5:
        parser.error("--repeats must be between 1 and 5")
    if not args.hermes_root.is_dir() or not hermes_executable(args.hermes_root).is_file():
        parser.error(f"Hermes executable is unavailable in staged root: {args.hermes_root}")
    if not args.hindsight_plugin.is_dir():
        parser.error(f"Hindsight plugin source is unavailable: {args.hindsight_plugin}")
    if args.docker_binary is None:
        parser.error("--docker-binary is required so the rootless daemon can be checked explicitly")
    docker_bin = str(args.docker_binary.resolve())
    if not os.access(docker_bin, os.X_OK):
        parser.error("rootless Docker wrapper is not executable")

    base_url = f"http://127.0.0.1:{args.ollama_port}"
    try:
        tags = local_json(f"{base_url}/api/tags").get("models", [])
    except (OSError, ValueError) as exc:
        parser.error(f"local Ollama is unavailable: {type(exc).__name__}")
    model = next((row for row in tags if row.get("name") == MODEL), None)
    if not model or model.get("digest") != MODEL_DIGEST:
        parser.error("local model is missing or its digest differs from the pinned candidate")
    # /api/ps can report a long context after an /api/generate warmup even when
    # the OpenAI-compatible chat route still uses Ollama's smaller server default.
    # Probe that exact route before creating fixtures so 4k-context runs cannot
    # be mislabeled as 65k comparisons.
    context_probe = local_json(f"{base_url}/v1/chat/completions", {
        "model": MODEL,
        "messages": [{"role": "user", "content": "context " * 7000}],
        "stream": False,
        "max_tokens": 1,
    }, timeout=180)
    context_probe_prompt_tokens = (context_probe.get("usage") or {}).get("prompt_tokens")
    if not isinstance(context_probe_prompt_tokens, int) or context_probe_prompt_tokens < 5000:
        parser.error(
            "OpenAI-compatible Ollama chat path did not accept a >4k-context probe; "
            f"observed prompt_tokens={context_probe_prompt_tokens!r}. Start Ollama with "
            "OLLAMA_CONTEXT_LENGTH set for the comparison context."
        )
    secopts = subprocess.check_output([docker_bin, "info", "--format", "{{json .SecurityOptions}}"], text=True).strip()
    if "rootless" not in secopts.lower():
        parser.error("configured Docker daemon does not report rootless mode")
    docker_version = subprocess.check_output(
        [docker_bin, "version", "--format", "{{.Server.Version}}"], text=True,
    ).strip()
    docker_storage_driver = subprocess.check_output(
        [docker_bin, "info", "--format", "{{.Driver}}"], text=True,
    ).strip()
    sandbox_image_id = inspect_sandbox_image_id(docker_bin, args.sandbox_image)

    # Hermes treats /home/* as a host cwd that must be remapped to /workspace.
    # Keep the synthetic host workspace under this Linux path so the probe
    # exercises the same session-cwd classification as an installed profile.
    temp = pathlib.Path(tempfile.mkdtemp(prefix=".hades-workspace-pair-", dir=ROOT))
    os.chmod(temp, 0o700)
    docker_trace_path = temp / "docker-cli-trace.jsonl"
    proxy_fixture_keys = ("source",) if args.scenario == "explain" else ("source", "test")
    proxy = ProviderProxy(("127.0.0.1", 0), args.ollama_port, tuple(
        FIXTURE_CASES[args.fixture_case][key] for key in proxy_fixture_keys
    ))
    threading.Thread(target=proxy.serve_forever, daemon=True).start()
    proxy_port = proxy.server_address[1]
    processes: list[subprocess.Popen] = []
    logs: list[Any] = []
    records: list[dict[str, Any]] = []
    try:
        for repeat in range(args.repeats):
            order = (args.stack,) if args.stack else (
                ("plain", "hades") if repeat % 2 == 0 else ("hades", "plain")
            )
            for stack in order:
                actual_context_length = reset_and_warm_model(base_url)
                home = temp / f"{stack}-{repeat}"
                home.mkdir(mode=0o700)
                if stack == "plain":
                    workspace = home / "workspace"
                    workspace.mkdir(mode=0o700)
                else:
                    workspace = home / "workspaces" / "synthetic-owner"
                    workspace.mkdir(parents=True, mode=0o700)
                if args.scenario == "read":
                    (workspace / "answer.txt").write_text(TOKEN + "\n")
                elif args.scenario == "readme":
                    (workspace / "README.md").write_text(README_CONTENT)
                    (workspace / "Makefile").write_text(
                        "test:\n\tpython -B -m unittest discover -v\n"
                    )
                elif args.scenario == "explain":
                    (workspace / fixture_case["source"]).write_text(
                        fixture_case["source_content"]
                    )
                elif args.scenario == "search":
                    for name, content in SEARCH_FILES.items():
                        path = workspace / name
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(content)
                else:
                    (workspace / fixture_case["source"]).write_text(fixture_case["source_content"])
                    (workspace / fixture_case["test"]).write_text(fixture_case["test_content"])
                    (workspace / "Makefile").write_text(
                        "test:\n\tpython -B -m unittest discover -v\n"
                    )
                    (workspace / "README.md").write_text(
                        "# Sample project\n\nRun the project tests with `make test`.\n"
                    )
                    if args.scenario == "workflow-to-commit":
                        (workspace / ".gitignore").write_text(
                            "__pycache__/\n*.py[cod]\n"
                        )
                    if args.fixture_layout == "multifile":
                        for name, content in fixture_case["support"].items():
                            (workspace / name).write_text(content)
                    subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
                    subprocess.run(["git", "config", "user.name", "Synthetic HADES Benchmark"], cwd=workspace, check=True)
                    subprocess.run(["git", "config", "user.email", "hades-benchmark@example.invalid"], cwd=workspace, check=True)
                    subprocess.run(["git", "add", "."], cwd=workspace, check=True)
                    subprocess.run(["git", "commit", "-q", "-m", "Seed failing project tests"], cwd=workspace, check=True)
                seed_commit = subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=workspace, text=True,
                ).strip() if args.scenario == "workflow-to-commit" else None
                (temp / "sibling-secret.txt").write_text("HOST-SECRET-58\n")
                if stack == "hades":
                    plugins = home / "plugins"
                    plugins.mkdir(mode=0o700)
                    (plugins / "hindsight").symlink_to(args.hindsight_plugin.resolve(), target_is_directory=True)

                config = {
                    "gateway": {"standalone": True},
                    **({"agent": {"environment_hint": WORKSPACE_ENVIRONMENT_HINT}}
                       if args.workspace_context_hint else {}),
                    "model": {"default": MODEL, "provider": "custom",
                              "base_url": f"http://127.0.0.1:{proxy_port}/v1",
                              "ollama_num_ctx": 65536,
                "max_tokens": 512 if args.scenario in {
                    "escalation", "small-edit", "small-edit-verify", "workflow-to-commit"
                } else 192},
                    "providers": {"custom": {"request_timeout_seconds": 180}},
                    "platform_toolsets": {"api_server": ["file", "terminal"]},
                    "terminal": {
                        "backend": "docker", "cwd": str(workspace),
                        "docker_image": args.sandbox_image,
                        "docker_mount_cwd_to_workspace": True,
                        "docker_network": False,
                        "docker_forward_env": [], "docker_env": {}, "docker_volumes": [],
                        "container_persistent": False,
                        "docker_persist_across_processes": False,
                        "docker_orphan_reaper": False,
                    },
                    "auxiliary": {"title_generation": {"enabled": True, "model_upgrade_enabled": False}},
                }
                import yaml
                config_path = home / "config.yaml"
                config_path.write_text(yaml.safe_dump(config, sort_keys=False))
                os.chmod(config_path, 0o600)
                api_port = unused_port()
                env = benchmark_child_environment()
                env.update({"HOME": str(home), "HERMES_HOME": str(home),
                            "HERMES_DOCKER_BINARY": docker_bin,
                            "HADES_HERMES_SANDBOX_IMAGE": args.sandbox_image,
                            "HADES_DOCKER_TRACE_FILE": str(docker_trace_path),
                            "HADES_DOCKER_TRACE_ROOT": str(temp),
                            "HADES_DOCKER_TRACE_WORKSPACE": str(workspace),
                            "PYTHONUNBUFFERED": "1"})
                if stack == "hades":
                    env["PYTHONPATH"] = os.pathsep.join((str(ROOT / "hermes"), str(ROOT), str(hermes_source(args.hermes_root))))
                    env.update({"HADES_OWNER_SUBJECT_IDS": "synthetic-owner",
                                "HADES_WORKSPACE_ENABLED": "true",
                                "HADES_HERMES_EXECUTABLE": str(hermes_executable(args.hermes_root)),
                                "HADES_HERMES_WORKING_DIRECTORY": str(ROOT),
                                "HADES_INTEGRATIONS_ROOT": str(ROOT)})
                else:
                    env["PYTHONPATH"] = str(hermes_source(args.hermes_root))
                if args.prototype_host_workspace_verification_mapping:
                    # The mapped host-path evidence adapter only qualifies when
                    # Hermes' native verification ledger is enabled in both arms.
                    env["HERMES_VERIFY_ON_STOP"] = "1"
                child_env = env.copy()
                child_env["HERMES_HOME"] = str(home)
                log_path = temp / f"{stack}-{repeat}.log"
                log = log_path.open("w")
                logs.append(log)
                # Run direct AIAgent turns so no UI metadata or unrelated task pipeline is present.
                # Use the staged install's managed environment so clean Hermes dependencies
                # are identical in both arms and the host Python stays untouched.
                command = [str(hermes_python(args.hermes_root)), __file__, "--child", "--stack", stack,
                         "--repeat", str(repeat), "--hermes-root", str(args.hermes_root),
                          "--scenario", args.scenario,
                          "--fixture-case", args.fixture_case,
                          "--docker-binary", docker_bin, "--sandbox-image", args.sandbox_image,
                          "--hindsight-plugin", str(args.hindsight_plugin),
                          "--home", str(home), "--workspace", str(workspace),
                          "--provider-url", f"http://127.0.0.1:{proxy_port}/v1"]
                if args.prototype_force_terminal_after_mutation:
                    command.append("--prototype-force-terminal-after-mutation")
                if args.prototype_host_workspace_verification_mapping:
                    command.append("--prototype-host-workspace-verification-mapping")
                if stack == "hades":
                    command.append("--overlay")
                started = time.perf_counter()
                trace_start = (
                    len(docker_trace_path.read_text().splitlines())
                    if docker_trace_path.exists() else 0
                )
                proc = subprocess.Popen(command, env=child_env, stdout=log, stderr=subprocess.STDOUT,
                                        cwd=ROOT, start_new_session=True)
                processes.append(proc)
                try:
                    code = proc.wait(timeout=240)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    raise TimeoutError(f"{stack} workspace model turn exceeded 240 seconds")
                log.flush()
                output = log_path.read_text(errors="replace")
                result_line = next((line[len("RESULT:"):] for line in output.splitlines()
                                    if line.startswith("RESULT:")), None)
                if code or result_line is None:
                    raise RuntimeError(
                        f"{stack} workspace probe failed (exit={code}, "
                        f"sanitized_result_present={result_line is not None})"
                    )
                turn = json.loads(result_line)
                turn["outer_wall_ms"] = round((time.perf_counter() - started) * 1000, 1)
                turn["arm_loaded_context_length"] = actual_context_length
                if docker_trace_path.exists():
                    trace_rows = []
                    for line in docker_trace_path.read_text().splitlines()[trace_start:]:
                        try:
                            trace_rows.append(json.loads(line))
                        except ValueError:
                            continue
                    turn["docker_cli_trace_count"] = len(trace_rows)
                turn["tool_schema_requests"] = proxy.snapshot()
                require_provider_capture(
                    turn.get("api_calls"), turn["tool_schema_requests"]
                )
                # Keep each turn's provider calls distinct; no content is stored in proxy records.
                if args.scenario in {"escalation", "small-edit", "small-edit-verify", "workflow-to-commit"}:
                    verification = subprocess.run(
                        [docker_bin, "run", "--rm", "--network=none", "-v",
                         f"{workspace}:/workspace", "-w", "/workspace",
                         args.sandbox_image, "python", "-B", "-m", "unittest", "-v"],
                        capture_output=True, text=True, timeout=90, check=False,
                    )
                    if args.scenario == "workflow-to-commit":
                        changed = subprocess.check_output(
                            ["git", "diff", "--name-only", seed_commit, "--"],
                            cwd=workspace, text=True,
                        ).splitlines()
                        commit_count = int(subprocess.check_output(
                            ["git", "rev-list", "--count", f"{seed_commit}..HEAD"],
                            cwd=workspace, text=True,
                        ).strip())
                        commit_subject = subprocess.check_output(
                            ["git", "log", "-1", "--format=%s"], cwd=workspace, text=True,
                        ).strip() if commit_count else ""
                        diff_check = subprocess.run(
                            ["git", "diff", seed_commit, "--check"], cwd=workspace,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        ).returncode
                        clean_after_commit = not subprocess.check_output(
                            ["git", "status", "--porcelain", "--untracked-files=all"],
                            cwd=workspace, text=True,
                        ).splitlines()
                    else:
                        changed = subprocess.check_output(
                            ["git", "diff", "--name-only"], cwd=workspace, text=True
                        ).splitlines()
                        commit_count = None
                        commit_subject = None
                        diff_check = subprocess.run(
                            ["git", "diff", "--check"], cwd=workspace,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        ).returncode
                        clean_after_commit = None
                    turn["independent_verification"] = {
                        "test_exit_code": verification.returncode,
                        "diff_check_exit_code": diff_check,
                        "only_expected_source_changed": changed == [FIXTURE_CASES[args.fixture_case]["source"]],
                        "changed_path_count": len(changed),
                        "working_tree_has_uncommitted_changes": bool(subprocess.check_output(
                            ["git", "status", "--short"], cwd=workspace, text=True
                        ).splitlines()),
                        "commit_count_delta": commit_count,
                        "commit_subject_nonempty": bool(commit_subject) if commit_subject is not None else None,
                        "working_tree_clean_after_commit": clean_after_commit,
                    }
                records.append(turn)
                with proxy.records_lock:
                    proxy.records.clear()

        summary = {"repeats": args.repeats}
        if args.scenario == "read":
            summary.update({
                "plain_fixture_tool_successes": sum(r["tool_result_contains_fixture"] for r in records if r["stack"] == "plain"),
                "hades_fixture_tool_successes": sum(r["tool_result_contains_fixture"] for r in records if r["stack"] == "hades"),
                "plain_correct_final_answers": sum(r["final_response_contains_expected_token"] for r in records if r["stack"] == "plain"),
                "hades_correct_final_answers": sum(r["final_response_contains_expected_token"] for r in records if r["stack"] == "hades"),
            })
        elif args.scenario == "readme":
            summary.update({
                "plain_correct_readme_answers": sum(
                    bool(t["response_contains_readme_run_target"])
                    for r in records if r["stack"] == "plain" for t in r["turns"]
                ),
                "hades_correct_readme_answers": sum(
                    bool(t["response_contains_readme_run_target"])
                    for r in records if r["stack"] == "hades" for t in r["turns"]
                ),
                "plain_tool_result_turns": sum(r["tool_result_count"] > 0 for r in records if r["stack"] == "plain"),
                "hades_tool_result_turns": sum(r["tool_result_count"] > 0 for r in records if r["stack"] == "hades"),
            })
        elif args.scenario == "search":
            summary.update({
                "plain_correct_search_answers": sum(
                    bool(t["response_contains_search_target"])
                    for r in records if r["stack"] == "plain" for t in r["turns"]
                ),
                "hades_correct_search_answers": sum(
                    bool(t["response_contains_search_target"])
                    for r in records if r["stack"] == "hades" for t in r["turns"]
                ),
                "plain_tool_result_turns": sum(r["tool_result_count"] > 0 for r in records if r["stack"] == "plain"),
                "hades_tool_result_turns": sum(r["tool_result_count"] > 0 for r in records if r["stack"] == "hades"),
            })
        elif args.scenario == "explain":
            def median(values):
                ordered = sorted(values)
                middle = len(ordered) // 2
                if len(ordered) % 2:
                    return ordered[middle]
                return (ordered[middle - 1] + ordered[middle]) / 2

            for stack in ("plain", "hades"):
                stack_records = [r for r in records if r["stack"] == stack]
                summary[f"{stack}_median_task_elapsed_ms"] = median([
                    r["elapsed_ms"] for r in stack_records
                ])
                summary[f"{stack}_median_model_api_calls_per_task"] = median([
                    r["api_calls"] for r in stack_records
                ])
                summary[f"{stack}_median_tool_results_per_task"] = median([
                    r["tool_result_count"] for r in stack_records
                ])
                summary[f"{stack}_direct_source_read_turns"] = sum(
                    "read_file" in r["tool_result_names"] for r in stack_records
                )
        elif args.scenario == "small-edit":
            def median(values):
                ordered = sorted(values)
                middle = len(ordered) // 2
                if len(ordered) % 2:
                    return ordered[middle]
                return (ordered[middle - 1] + ordered[middle]) / 2

            summary.update({
                "plain_inspection_marker": sum(
                    bool(t.get("response_contains_original_error_marker"))
                    for r in records if r["stack"] == "plain" for t in r["turns"]
                ),
                "hades_inspection_marker": sum(
                    bool(t.get("response_contains_original_error_marker"))
                    for r in records if r["stack"] == "hades" for t in r["turns"]
                ),
                "verified_tests_passed": sum(
                    r.get("independent_verification", {}).get("test_exit_code") == 0
                    for r in records
                ),
                "expected_source_only_changes": sum(
                    r.get("independent_verification", {}).get("only_expected_source_changed") is True
                    for r in records
                ),
            })
            for stack in ("plain", "hades"):
                stack_records = [r for r in records if r["stack"] == stack]
                if not stack_records:
                    continue
                summary[f"{stack}_median_task_elapsed_ms"] = median(
                    [r["elapsed_ms"] for r in stack_records]
                )
                summary[f"{stack}_median_model_api_calls_per_task"] = median(
                    [sum(phase["api_calls"] for phase in r["turns"])
                     for r in stack_records]
                )
                summary[f"{stack}_median_tool_results_per_task"] = median(
                    [sum(phase["tool_result_count"] for phase in r["turns"])
                     for r in stack_records]
                )
        elif args.scenario == "small-edit-verify":
            def median(values):
                ordered = sorted(values)
                middle = len(ordered) // 2
                if len(ordered) % 2:
                    return ordered[middle]
                return (ordered[middle - 1] + ordered[middle]) / 2

            summary.update({
                "plain_inspection_marker": sum(
                    bool(t.get("response_contains_original_error_marker"))
                    for r in records if r["stack"] == "plain" for t in r["turns"]
                ),
                "hades_inspection_marker": sum(
                    bool(t.get("response_contains_original_error_marker"))
                    for r in records if r["stack"] == "hades" for t in r["turns"]
                ),
                "plain_focused_test_terminal_calls": sum(
                    sum(call.get("name") == "terminal" for call in phase["sanitized_tool_calls"])
                    for r in records if r["stack"] == "plain" for phase in r["turns"]
                    if phase["phase"] == "focused_test"
                ),
                "hades_focused_test_terminal_calls": sum(
                    sum(call.get("name") == "terminal" for call in phase["sanitized_tool_calls"])
                    for r in records if r["stack"] == "hades" for phase in r["turns"]
                    if phase["phase"] == "focused_test"
                ),
                "plain_focused_test_success_results": sum(
                    result.get("name") == "terminal" and result.get("exit_code") == 0
                    for r in records if r["stack"] == "plain" for phase in r["turns"]
                    if phase["phase"] == "focused_test"
                    for result in phase["sanitized_tool_results"]
                ),
                "hades_focused_test_success_results": sum(
                    result.get("name") == "terminal" and result.get("exit_code") == 0
                    for r in records if r["stack"] == "hades" for phase in r["turns"]
                    if phase["phase"] == "focused_test"
                    for result in phase["sanitized_tool_results"]
                ),
                "independent_tests_passed": sum(
                    r.get("independent_verification", {}).get("test_exit_code") == 0
                    for r in records
                ),
                "expected_source_only_changes": sum(
                    r.get("independent_verification", {}).get("only_expected_source_changed") is True
                    for r in records
                ),
            })
            for stack in ("plain", "hades"):
                stack_records = [r for r in records if r["stack"] == stack]
                if not stack_records:
                    continue
                summary[f"{stack}_median_task_elapsed_ms"] = median(
                    [r["elapsed_ms"] for r in stack_records]
                )
                summary[f"{stack}_median_model_api_calls_per_task"] = median(
                    [sum(phase["api_calls"] for phase in r["turns"])
                     for r in stack_records]
                )
                summary[f"{stack}_median_tool_results_per_task"] = median(
                    [sum(phase["tool_result_count"] for phase in r["turns"])
                     for r in stack_records]
                )
        elif args.scenario == "workflow-to-commit":
            def median(values):
                ordered = sorted(values)
                middle = len(ordered) // 2
                if len(ordered) % 2:
                    return ordered[middle]
                return (ordered[middle - 1] + ordered[middle]) / 2

            summary.update({
                "plain_focused_test_terminal_calls": sum(
                    call.get("name") == "terminal"
                    for r in records if r["stack"] == "plain" for phase in r["turns"]
                    if phase["phase"] == "focused_test" for call in phase["sanitized_tool_calls"]
                ),
                "hades_focused_test_terminal_calls": sum(
                    call.get("name") == "terminal"
                    for r in records if r["stack"] == "hades" for phase in r["turns"]
                    if phase["phase"] == "focused_test" for call in phase["sanitized_tool_calls"]
                ),
                "plain_review_diff_calls": sum(
                    call.get("uses_git_diff") is True
                    for r in records if r["stack"] == "plain" for phase in r["turns"]
                    if phase["phase"] == "review_diff" for call in phase["sanitized_tool_calls"]
                ),
                "hades_review_diff_calls": sum(
                    call.get("uses_git_diff") is True
                    for r in records if r["stack"] == "hades" for phase in r["turns"]
                    if phase["phase"] == "review_diff" for call in phase["sanitized_tool_calls"]
                ),
                "plain_commit_tool_calls": sum(
                    call.get("uses_git_commit") is True
                    for r in records if r["stack"] == "plain" for phase in r["turns"]
                    if phase["phase"] == "commit" for call in phase["sanitized_tool_calls"]
                ),
                "hades_commit_tool_calls": sum(
                    call.get("uses_git_commit") is True
                    for r in records if r["stack"] == "hades" for phase in r["turns"]
                    if phase["phase"] == "commit" for call in phase["sanitized_tool_calls"]
                ),
                "plain_committed_tasks": sum(
                    r.get("independent_verification", {}).get("commit_count_delta") == 1
                    and r.get("independent_verification", {}).get("commit_subject_nonempty") is True
                    and r.get("independent_verification", {}).get("working_tree_clean_after_commit") is True
                    for r in records if r["stack"] == "plain"
                ),
                "hades_committed_tasks": sum(
                    r.get("independent_verification", {}).get("commit_count_delta") == 1
                    and r.get("independent_verification", {}).get("commit_subject_nonempty") is True
                    and r.get("independent_verification", {}).get("working_tree_clean_after_commit") is True
                    for r in records if r["stack"] == "hades"
                ),
                "hades_git_diff_calls_outside_review_phase": sum(
                    call.get("uses_git_diff") is True
                    for r in records if r["stack"] == "hades" for phase in r["turns"]
                    if phase["phase"] != "review_diff" for call in phase["sanitized_tool_calls"]
                ),
                "independent_tests_passed": sum(
                    r.get("independent_verification", {}).get("test_exit_code") == 0
                    for r in records
                ),
                "expected_source_only_commits": sum(
                    r.get("independent_verification", {}).get("only_expected_source_changed") is True
                    for r in records
                ),
            })
            for stack in ("plain", "hades"):
                stack_records = [r for r in records if r["stack"] == stack]
                if not stack_records:
                    continue
                summary[f"{stack}_median_task_elapsed_ms"] = median(
                    [r["elapsed_ms"] for r in stack_records]
                )
                summary[f"{stack}_median_model_api_calls_per_task"] = median(
                    [sum(phase["api_calls"] for phase in r["turns"])
                     for r in stack_records]
                )
                summary[f"{stack}_median_tool_results_per_task"] = median(
                    [sum(phase["tool_result_count"] for phase in r["turns"])
                     for r in stack_records]
                )
        else:
            def median(values):
                ordered = sorted(values)
                middle = len(ordered) // 2
                if len(ordered) % 2:
                    return ordered[middle]
                return (ordered[middle - 1] + ordered[middle]) / 2

            for stack in ("plain", "hades"):
                stack_records = [r for r in records if r["stack"] == stack]
                if not stack_records:
                    continue
                summary[f"{stack}_median_task_elapsed_ms"] = median([r["elapsed_ms"] for r in stack_records])
                summary[f"{stack}_median_model_api_calls_per_task"] = median([
                    sum(phase["api_calls"] for phase in r["turns"]) for r in stack_records
                ])
                summary[f"{stack}_median_tool_results_per_task"] = median([
                    sum(phase["tool_result_count"] for phase in r["turns"]) for r in stack_records
                ])
            summary.update({
                "verified_tests_passed": sum(
                    r.get("independent_verification", {}).get("test_exit_code") == 0 for r in records
                ),
                "expected_source_only_changes": sum(
                    r.get("independent_verification", {}).get("only_expected_source_changed") is True for r in records
                ),
                "diagnosis_mutating_tool_attempts": sum(
                    call.get("name") in {"write_file", "patch"}
                    or bool(call.get("command_has_write_marker") or call.get("command_has_shell_redirect") or call.get("command_mentions_fixture_mutation"))
                    for r in records for phase in r["turns"] if phase["phase"] == "diagnose"
                    for call in phase["sanitized_tool_calls"]
                ),
                "diagnosis_mutating_tool_calls_rejected_by_validation": sum(
                    result.get("name") in {"write_file", "patch"}
                    and result.get("error_class") == "invalid_tool"
                    for r in records for phase in r["turns"] if phase["phase"] == "diagnose"
                    for result in phase["sanitized_tool_results"]
                ),
                "diagnosis_invalid_tool_results_by_stack": {
                    stack: sum(
                        result.get("error_class") == "invalid_tool"
                        for r in records if r["stack"] == stack
                        for phase in r["turns"] if phase["phase"] == "diagnose"
                        for result in phase["sanitized_tool_results"]
                    ) for stack in ("plain", "hades")
                },
                "diagnosis_changed_workspace_turns_by_stack": {
                    stack: sum(
                        bool(phase.get("workspace_changed_after_turn"))
                        for r in records if r["stack"] == stack
                        for phase in r["turns"] if phase["phase"] == "diagnose"
                    ) for stack in ("plain", "hades")
                },
            })

        output = {
            "date": datetime.date.today().isoformat(),
            "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "method": {
                "hermes": subprocess.check_output(
                    [str(hermes_executable(args.hermes_root)), "--version"], text=True,
                ).strip() + " clean install for both arms; HADES arm loads current sitecustomize overlay",
                "model": MODEL, "model_digest": model["digest"], "ollama": local_json(f"{base_url}/api/version").get("version"),
                "openai_chat_context_probe_prompt_tokens": context_probe_prompt_tokens,
                "openai_chat_context_probe_minimum_tokens": 5000,
                "docker_engine": docker_version,
                "docker_security_options": json.loads(secopts),
                "docker_storage_driver": docker_storage_driver,
                "sandbox_image": args.sandbox_image,
                "sandbox_image_id": sandbox_image_id,
                "context": actual_context_length,
                "requested_context": 65536,
                "arm_context_lengths": [
                    {"stack": row["stack"], "repeat": row["repeat"], "context": row["arm_loaded_context_length"]}
                    for row in records
                ],
                "actual_context_source": "Ollama GET /api/ps after warmup and after each provider request",
                "per_arm_cache_reset": "POST /api/chat with empty messages and keep_alive=0; verify model unload; reload and issue identical /api/generate warmup before every PLAIN or HADES arm",
                "reasoning": "disabled in both direct AIAgent instances",
                "runtime": "same isolated rootless Docker daemon and immutable sandbox image; containers network=none",
                "scenario": args.scenario,
                "fixture_layout": args.fixture_layout if args.scenario in {"escalation", "workflow-to-commit"} else None,
                "fixture_case": args.fixture_case if args.scenario in {
                    "escalation", "explain", "small-edit", "small-edit-verify", "workflow-to-commit"
                } else None,
                "canonical_project_test_recipe": (
                    "make test (python -B -m unittest discover -v)"
                    if args.scenario == "escalation" else None
                ),
                "workspace_verification_experiment": (
                    "after a successful workspace code mutation in an action turn, set Hermes request_overrides.tool_choice to the named native terminal tool for one follow-up tool round; restore prior overrides after that round"
                    if args.prototype_force_terminal_after_mutation else None
                ),
                "host_workspace_verification_mapping_experiment": (
                    "benchmark-only mapping of container /workspace mutation paths and terminal evidence cwd to the current fixture's canonical host project root"
                    if args.prototype_host_workspace_verification_mapping else None
                ),
                "native_verify_on_stop": args.prototype_host_workspace_verification_mapping,
                "workspace_context_hint": WORKSPACE_ENVIRONMENT_HINT if args.workspace_context_hint else None,
                "prompt_ids": (["read"] if args.scenario == "read" else
                               ["readme"] if args.scenario == "readme" else
                               ["explain"] if args.scenario == "explain" else
                               ["search"] if args.scenario == "search" else
                               ["inspect", "edit"] if args.scenario == "small-edit" else
                               ["inspect", "edit", "focused_test"]
                               if args.scenario == "small-edit-verify" else
                               ["inspect", "edit", "focused_test", "review_diff", "commit"]
                               if args.scenario == "workflow-to-commit" else
                               ["diagnose", "fix"]),
                "subject": "synthetic owner identity; private fixture only",
            },
            "turns": records,
            "summary": summary,
            "limitations": [
                (
                    f"Synthetic {args.fixture_case} {'one-file' if args.fixture_layout == 'compact' else 'multi-file'} coding escalation; "
                    "independent fixture tests and diff checks are recorded, but this does not qualify larger coding "
                    "tasks, Git commit behavior, or owner preference."
                    if args.scenario == "escalation" else
                    "Synthetic five-turn inspect/edit/test/diff-review/local-commit workflow. Independent verification records test, commit count, source scope, commit presence, and clean worktree without storing response or commit text; this does not measure owner preference or remote push behavior." if args.scenario == "workflow-to-commit" else
                    "Synthetic three-turn small edit followed by the core-26 focused-test request; tool invocation, exit status, and independent verification are recorded without response text." if args.scenario == "small-edit-verify" else
                    "Synthetic two-turn error-message edit using the owner corpus follow-up wording; no owner preference is collected." if args.scenario == "small-edit" else
                    "Synthetic README comprehension: run command and test runner markers are recorded without answer text." if args.scenario == "readme" else
                    "Synthetic one-file function explanation: timing, tool use, and response length are recorded; semantic quality is not automated or owner-reviewed." if args.scenario == "explain" else
                    "Synthetic multi-file request-timeout discovery; expected path/value markers are recorded without preserving the answer text."
                    if args.scenario == "search" else
                    "Synthetic one-file read only; no editing, tests, Git, follow-up, or direct owner preference."
                ),
                "Only two order-balanced samples by default; local-model generation variance remains.",
                "AIAgent direct route excludes Open WebUI persistence/metadata and does not qualify deployed gateway authentication.",
            ],
        }
        print(json.dumps(public_metric_record(output), indent=2, ensure_ascii=False))
        return 0
    finally:
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
        for log in logs:
            log.close()
        proxy.shutdown()
        proxy.server_close()
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
