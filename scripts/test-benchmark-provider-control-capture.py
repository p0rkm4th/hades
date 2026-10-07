#!/usr/bin/env python3
"""Contract for privacy-safe inference-control capture in benchmark traces."""

import importlib.util
import http.client
import json
import pathlib
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


SCRIPT = pathlib.Path(__file__).with_name("benchmark-hades-owner-subset.py")
SPEC = importlib.util.spec_from_file_location("owner_subset_benchmark", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

capture = MODULE.capture_request_controls
request = {
    "temperature": 0.2,
    "top_p": 0.9,
    "max_tokens": 128,
    "reasoning_effort": "low",
    "tool_choice": {"type": "function", "function": {"name": "private-tool"}},
    "options": {"num_ctx": 65536, "num_predict": 512, "num_thread": 8},
    "messages": [{"role": "user", "content": "private synthetic message"}],
    "api_key": "do-not-capture",
    "headers": {"Authorization": "do-not-capture"},
    "arbitrary_setting": "do-not-capture",
}
result = capture(request)
assert result == {
    "temperature": 0.2,
    "top_p": 0.9,
    "max_tokens": 128,
    "reasoning_effort": "low",
    "tool_choice": "function",
    "options": {"num_ctx": 65536, "num_predict": 512, "num_thread": 8},
}, result
serialized = repr(result)
for forbidden in ("private synthetic message", "private-tool", "do-not-capture", "Authorization"):
    assert forbidden not in serialized, (forbidden, serialized)

print("PASS allowlisted sampling controls captured without prompt/tool/secret text")


PAIR_SCRIPT = pathlib.Path(__file__).with_name("benchmark-hades-memory-pair.py")
PAIR_SPEC = importlib.util.spec_from_file_location("memory_pair_benchmark", PAIR_SCRIPT)
assert PAIR_SPEC is not None and PAIR_SPEC.loader is not None
PAIR_MODULE = importlib.util.module_from_spec(PAIR_SPEC)
PAIR_SPEC.loader.exec_module(PAIR_MODULE)
MEMORY_SUPPLEMENT = PAIR_MODULE.load_memory_supplement()
assert [case["id"] for case in MEMORY_SUPPLEMENT] == [
    "core-51", "core-52", "core-53", "core-54", "core-55",
]
assert PAIR_MODULE.OWNER_CORE_09_RECALL == "What was the savings target I mentioned?"
assert PAIR_MODULE.core09_answer_matches_target("$3,000.") is True
assert PAIR_MODULE.core09_answer_matches_target("3000") is True
assert PAIR_MODULE.core09_answer_matches_target("The target is $2,500.") is False
assert PAIR_MODULE.configure_hades_scope(
    {"HADES_OWNER_SUBJECT_IDS": "inherited-owner"}, "household"
) == {}
assert PAIR_MODULE.configure_hades_scope(
    {"HADES_OWNER_SUBJECT_IDS": "inherited-owner"}, "owner"
) == {"HADES_OWNER_SUBJECT_IDS": PAIR_MODULE.SYNTHETIC_OWNER_SUBJECT}
assert PAIR_MODULE.synthetic_memory_bank("owner") == "hades-owner"
assert PAIR_MODULE.synthetic_memory_bank("household") == "hades-user-hades-synthetic"

import tempfile

with tempfile.TemporaryDirectory() as directory:
    target = pathlib.Path(directory) / "run.json"
    partial_turn = {"sample": 2, "stacks": {"hades": {"turns": [
        {"total_ms": 12.3, "answer": "private conversation secret", "metrics": {"provider_generations": 1}},
    ]}}}
    partial_path = PAIR_MODULE.write_incomplete_artifact(
        target, source_revision="abc123", failure_stage="barrier",
        error_type="RuntimeError", repetitions=[partial_turn],
        hindsight_calls=[{"route": "/api/chat", "elapsed_ms": 12.3}],
        safe_failure_detail="Hindsight pending operation status unavailable (HTTPError; status=503)",
    )
    content = partial_path.read_text()
    assert partial_path.name == "run-incomplete.json"
    assert '"sample": 2' in content and '"total_ms": 12.3' in content
    assert "no preference or stack comparison" in content
    assert "RuntimeError" in content
    assert "HTTPError" in content
    assert "status=503" in content
    assert "secret" not in content and "private" not in content
    assert '"provider_generations": 1' in content
    unsafe_path = PAIR_MODULE.write_incomplete_artifact(
        target, source_revision="abc123", failure_stage="barrier",
        error_type="RuntimeError", repetitions=[], hindsight_calls=[],
        safe_failure_detail="private secret response body",
    )
    assert "private secret response body" not in unsafe_path.read_text()


class FakeOllama(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        body = json.dumps({
            "model": "fixture-model",
            "message": {"content": "private generated marker"},
            "prompt_eval_count": 12,
            "eval_count": 3,
            "total_duration": 1000,
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        assert self.path == "/api/ps", self.path
        body = json.dumps({"models": [{
            "name": "fixture-model",
            "context_length": 40960,
            "size": 123456,
            "size_vram": 65432,
        }]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


upstream = ThreadingHTTPServer(("127.0.0.1", 0), FakeOllama)
upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
upstream_thread.start()
proxy = PAIR_MODULE.HindsightOllamaProxy(("127.0.0.1", 0), upstream.server_port)
proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
proxy_thread.start()
try:
    request_body = json.dumps({
        "model": "fixture-model",
        "messages": [{"role": "user", "content": "private input marker"}],
        "api_key": "private credential marker",
        "options": {"temperature": 0.1, "top_p": 0.95},
    }).encode()
    client = http.client.HTTPConnection("127.0.0.1", proxy.server_port, timeout=5)
    client.request("POST", "/api/chat", body=request_body, headers={"Content-Type": "application/json"})
    response = client.getresponse()
    returned = json.loads(response.read())
    assert response.status == 200
    assert returned["message"]["content"] == "private generated marker"
    deadline = time.monotonic() + 2
    rows = proxy.snapshot()
    while not rows and time.monotonic() < deadline:
        time.sleep(0.01)
        rows = proxy.snapshot()
    assert rows, "proxy should publish its safe record after the response is forwarded"
    record = rows[0]
    serialized_record = json.dumps(record)
    for marker in ("private input marker", "private generated marker", "private credential marker", "messages"):
        assert marker not in serialized_record, serialized_record
    assert record["route"] == "/api/chat"
    assert record["generation_controls"] == {"temperature": 0.1, "top_p": 0.95}
    assert record["prompt_eval_count"] == 12 and record["eval_count"] == 3
    assert record["loaded_model_context_length"] == 40960
    assert record["loaded_model_size_bytes"] == 123456
    assert record["loaded_model_size_vram_bytes"] == 65432
    assert record["loaded_model_residency"] == "resident"
    client.close()
finally:
    proxy.shutdown()
    proxy.server_close()
    proxy_thread.join(timeout=2)
    upstream.shutdown()
    upstream.server_close()
    upstream_thread.join(timeout=2)

print("PASS Hindsight Ollama proxy records aggregate usage without request/response bodies")


states = iter([
    {"operations": {"pending": {"retain": 1}, "processing": {}}},
    {"operations": {"pending": {}, "processing": {}}, "stats": {"pending_operations": 1}},
    {"operations": {"pending": {}, "processing": {}}, "stats": {"pending_operations": 0}},
    {"operations": {"pending": {}, "processing": {}}, "stats": {"pending_operations": 0}},
])
idle = PAIR_MODULE.wait_hindsight_idle(
    "unused", "synthetic-bank", timeout=1, poll_interval=0,
    lifecycle_fn=lambda *_args: next(states),
)
assert idle["idle"] and idle["polls"] == 4, idle
try:
    PAIR_MODULE.wait_hindsight_idle(
        "unused", "synthetic-bank", timeout=1, poll_interval=0,
        lifecycle_fn=lambda *_args: {"operations": {"pending": {"error": "HTTPError", "status_code": 503}}},
    )
except RuntimeError as exc:
    assert "status unavailable (HTTPError; status=503)" in str(exc)
else:
    raise AssertionError("operation status failure must not be treated as idle")


class FailedHindsightStatus(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def do_GET(self):
        body = b"private response detail must not be captured"
        self.send_response(503)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


status_server = ThreadingHTTPServer(("127.0.0.1", 0), FailedHindsightStatus)
status_thread = threading.Thread(target=status_server.serve_forever, daemon=True)
status_thread.start()
try:
    lifecycle = PAIR_MODULE.hindsight_bank_lifecycle(
        f"http://127.0.0.1:{status_server.server_port}", "synthetic-bank"
    )
    assert lifecycle["operations"]["pending"] == {
        "error": "HTTPError", "status_code": 503,
    }
    assert "private" not in repr(lifecycle)
finally:
    status_server.shutdown()
    status_server.server_close()
    status_thread.join(timeout=2)

print("PASS Hindsight arm barrier requires two idle states and fails closed")


class ArmNormalizationOllama(BaseHTTPRequestHandler):
    calls = []
    models = [{"name": "qwen3:14b", "context_length": 40960, "size_vram": 12345}]

    def log_message(self, *_args):
        return

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        type(self).calls.append((payload["model"], payload.get("keep_alive")))
        if payload["model"] == "qwen3:14b" and payload.get("keep_alive") == 0:
            type(self).models = [row for row in type(self).models if row["name"] != "qwen3:14b"]
        elif payload["model"] == "qwen3.6:35b":
            type(self).models = [{
                "name": "qwen3.6:35b", "context_length": 65536,
                "size_vram": 98765,
            }]
        body = b"{}"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        assert self.path == "/api/ps", self.path
        body = json.dumps({"models": type(self).models}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


normalize_server = ThreadingHTTPServer(("127.0.0.1", 0), ArmNormalizationOllama)
normalize_thread = threading.Thread(target=normalize_server.serve_forever, daemon=True)
normalize_thread.start()
try:
    class LocalProbe:
        @staticmethod
        def local_json(url):
            with urllib.request.urlopen(url, timeout=2) as response:
                return json.load(response)

    normalized = PAIR_MODULE.normalize_ollama_for_arm(
        f"http://127.0.0.1:{normalize_server.server_port}",
        LocalProbe,
        "qwen3.6:35b",
        "qwen3:14b",
    )
    assert normalized["interactive_model_resident"] is True
    assert normalized["interactive_context_length"] == 65536
    assert normalized["extractor_resident"] is False
    assert normalized["extractor_was_resident_before_reset"] is True
    assert normalized["normalization_calls_excluded_from_turn_timing"] is True
    assert ArmNormalizationOllama.calls == [
        ("qwen3:14b", 0), ("qwen3.6:35b", -1),
    ], ArmNormalizationOllama.calls

    # A shared extractor/answer model is intentional in the swap-isolation
    # diagnostic. Keep it resident and verify it without issuing an unload.
    ArmNormalizationOllama.calls = []
    ArmNormalizationOllama.models = []
    shared = PAIR_MODULE.normalize_ollama_for_arm(
        f"http://127.0.0.1:{normalize_server.server_port}",
        LocalProbe,
        "qwen3.6:35b",
        "qwen3.6:35b",
    )
    assert shared["extractor_shares_interactive_model"] is True
    assert shared["extractor_resident"] is True
    assert shared["extractor_unload_ms"] is None
    assert ArmNormalizationOllama.calls == [("qwen3.6:35b", -1)]
finally:
    normalize_server.shutdown()
    normalize_server.server_close()
    normalize_thread.join(timeout=2)

print("PASS paired memory arms isolate a distinct extractor and preserve intentional shared-model residency")


original_measure_turn = PAIR_MODULE.measure_turn
captured_calls = []


def synthetic_measure_turn(_gateway, _benchmark, turn, session, messages, *_args, **_kwargs):
    captured_calls.append((turn, session, messages))
    answer = "Madison was the destination." if "turn_3" in turn else "You said you were lactose intolerant."
    return {
        "turn": turn, "answer": answer, "status": 200,
        "total_ms": 12.0, "metrics": {"provider_generations": 1},
        "provider_calls": [],
    }


PAIR_MODULE.measure_turn = synthetic_measure_turn
try:
    lactose_case = next(case for case in MEMORY_SUPPLEMENT if case["id"] == "core-51")
    lactose = PAIR_MODULE.measure_memory_supplement_case(
        {}, None, lactose_case, "hades", "01"
    )
    assert lactose["answer_contains_expected_marker"] is True
    assert len(lactose["turns"]) == 2
    assert captured_calls[0][1] != captured_calls[1][1], "fresh recall must use a separate session"
    continuity_case = next(case for case in MEMORY_SUPPLEMENT if case["id"] == "core-55")
    continuity = PAIR_MODULE.measure_memory_supplement_case(
        {}, None, continuity_case, "hades", "01"
    )
    assert continuity["answer_contains_expected_marker"] is True
    assert [len(call[2]) for call in captured_calls[2:]] == [1, 3, 5]
finally:
    PAIR_MODULE.measure_turn = original_measure_turn

print("PASS memory supplement replay separates fresh recall from same-session continuity")


class AllBankStatus(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def do_GET(self):
        if self.path.startswith("/v1/default/banks?"):
            payload = {"items": [{"id": "hades-owner"}, {"id": "hermes"}], "total": 2}
        elif "/operations?" in self.path:
            bank = self.path.split("/banks/", 1)[1].split("/", 1)[0]
            status = self.path.rsplit("status=", 1)[1].split("&", 1)[0]
            operations = ([{"task_type": "batch_retain"}] if bank == "hermes" and status == "pending" else [])
            payload = {"operations": operations}
        elif "/stats?" in self.path:
            bank = self.path.split("/banks/", 1)[1].split("/", 1)[0]
            payload = {"pending_operations": 1 if bank == "hermes" else 0,
                       "operations_by_status": {"pending": 1 if bank == "hermes" else 0}}
        else:
            self.send_error(404)
            return
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


all_bank_server = ThreadingHTTPServer(("127.0.0.1", 0), AllBankStatus)
all_bank_thread = threading.Thread(target=all_bank_server.serve_forever, daemon=True)
all_bank_thread.start()
try:
    state = PAIR_MODULE.hindsight_all_bank_lifecycle(
        f"http://127.0.0.1:{all_bank_server.server_port}"
    )
    assert state["bank_count"] == 2, state
    assert state["operations"]["pending"] == {"batch_retain": 1}, state
    assert state["banks"]["hermes"]["pending"] == {"batch_retain": 1}, state
finally:
    all_bank_server.shutdown()
    all_bank_server.server_close()
    all_bank_thread.join(timeout=2)

print("PASS Hindsight barriers aggregate operations across all disposable banks")


class SequencedProxyActivity:
    def __init__(self, counts):
        self.counts = iter(counts)
        self.last = 0

    def active_requests(self):
        self.last = next(self.counts, self.last)
        return self.last


proxy_activity = SequencedProxyActivity([1, 0, 0])
proxy_idle = PAIR_MODULE.wait_hindsight_idle(
    "unused", "synthetic-bank", timeout=1, poll_interval=0,
    lifecycle_fn=lambda *_args: {
        "operations": {"pending": {}, "processing": {}},
        "stats": {"pending_operations": 0, "pending_consolidation": 0},
    },
    proxy=proxy_activity,
)
assert proxy_idle["idle"] and proxy_idle["polls"] == 3, proxy_idle
assert proxy_idle["proxy_active_requests"] == 0, proxy_idle

blocked_proxy = SequencedProxyActivity([1, 1, 1])
blocked_idle = PAIR_MODULE.wait_hindsight_idle(
    "unused", "synthetic-bank", timeout=0.01, poll_interval=0,
    lifecycle_fn=lambda *_args: {
        "operations": {"pending": {}, "processing": {}},
        "stats": {"pending_operations": 0, "pending_consolidation": 0},
    },
    proxy=blocked_proxy,
)
assert not blocked_idle["idle"] and blocked_idle["proxy_active_requests"] == 1, blocked_idle

print("PASS Hindsight drain barrier waits for active Ollama proxy requests")
