#!/usr/bin/env python3
"""Run a counterbalanced local PLAIN/HADES ordinary-chat and memory comparison.

The runner reuses the owner-subset aggregate provider proxy. It records aggregate
request shape, timings, model generations, tool schemas/calls, and token use;
assistant response text stays in memory and is never printed or persisted.
"""
from __future__ import annotations

import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import math
import os
import pathlib
import re
import shutil
import socket
import statistics
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from typing import Any

from benchmark_child_environment import benchmark_child_environment


ROOT = pathlib.Path(__file__).resolve().parents[1]
SHARED = pathlib.Path(os.environ.get("HADES_STAGE_ROOT", "/opt/hades-stage"))
# Keep the default aligned with the current stable release qualified by this
# campaign. Historical replays can still select an older install explicitly
# with --hermes-root; the artifact records the actual runtime version.
DEFAULT_HERMES = SHARED / "Hermes-v0.21.5-hades-candidate"
DEFAULT_PLUGIN = SHARED / "HADES_HOME/plugins/hindsight"
DEFAULT_IMAGE = (
    "ghcr.io/vectorize-io/hindsight"
    "@sha256:d1840062a5b79940ab7a9f4809ceb90fc776d4ad737cd9329e9b5836cc64ab70"
)
MODEL = "qwen3.6:35b"
CONTEXT_LENGTH = 65536
DEFAULT_HINDSIGHT_MODEL = "qwen3:14b"
OWNER_CORE_01_GREETING = "Hey, how's your morning going?"
OWNER_CORE_09_RECALL = "What was the savings target I mentioned?"
SYNTHETIC_OWNER_SUBJECT = "hades-synthetic"
MEMORY_SUPPLEMENT_PATH = ROOT / "benchmarks/hades-core-owner-corpus-v2.json"


def load_memory_supplement() -> list[dict[str, Any]]:
    data = json.loads(MEMORY_SUPPLEMENT_PATH.read_text(encoding="utf-8"))
    cases = [row for row in data.get("cases", []) if row.get("id") in {
        "core-51", "core-52", "core-53", "core-54", "core-55",
    }]
    expected = {f"core-{index}" for index in range(51, 56)}
    if {row.get("id") for row in cases} != expected:
        raise RuntimeError("owner memory supplement corpus is incomplete")
    for row in cases:
        review = row.get("review_check")
        if not isinstance(review, dict) or not review.get("visibility_bank") or not review.get("visibility_needle"):
            raise RuntimeError(f"owner memory supplement case {row.get('id')} lacks visibility checks")
        if row.get("id") != "core-55" and not review.get("probe_text"):
            raise RuntimeError(f"owner memory supplement case {row.get('id')} lacks a fresh probe")
    return cases


def load_owner_benchmark():
    path = ROOT / "scripts/benchmark-hades-owner-subset.py"
    spec = importlib.util.spec_from_file_location("hades_owner_subset_benchmark", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the aggregate gateway benchmark helpers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hermes_executable(root: pathlib.Path) -> pathlib.Path:
    for candidate in (
        root / ".venv/bin/hermes",
        root / "bin/hermes",
        root / "venv/bin/hermes",
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise ValueError(f"Hermes executable not found under staged root: {root}")


def configure_hades_scope(env: dict[str, str], scope: str) -> dict[str, str]:
    """Set only the synthetic test identity's owner authority when requested."""
    env.pop("HADES_OWNER_SUBJECT_IDS", None)
    if scope == "owner":
        env["HADES_OWNER_SUBJECT_IDS"] = SYNTHETIC_OWNER_SUBJECT
    elif scope != "household":
        raise ValueError("unsupported synthetic HADES scope")
    return env


def safe_turn_record(turn: dict[str, Any]) -> dict[str, Any]:
    """Keep only aggregate turn metrics; never persist model or provider text."""
    return {
        key: turn[key]
        for key in ("turn", "status", "ttft_ms", "total_ms", "metrics", "error_type")
        if key in turn
    }


def read_safe_recall_diagnostics(log_path: pathlib.Path, offset: int = 0):
    """Read only allowlisted rank/type/numeric scores from HADES debug logs."""
    marker = "HADES memory recall score diagnostics stage="
    allowed_stages = {"automatic", "automatic_raw_fallback", "direct:False", "direct:True"}
    rows = []
    try:
        with log_path.open("rb") as stream:
            stream.seek(max(0, offset))
            while True:
                raw_line = stream.readline()
                if not raw_line:
                    break
                line = raw_line.decode("utf-8", errors="replace")
                start = line.find(marker)
                if start < 0:
                    continue
                record = line[start + len(marker):].strip()
                stage, separator, payload = record.partition(" rows=")
                if not separator or stage not in allowed_stages:
                    continue
                try:
                    parsed = json.loads(payload)
                except (TypeError, ValueError):
                    continue
                if not isinstance(parsed, list):
                    continue
                safe_items = []
                for item in parsed[:8]:
                    if not isinstance(item, dict):
                        continue
                    rank = item.get("rank")
                    result_type = item.get("type")
                    scores = item.get("scores")
                    if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
                        continue
                    if result_type not in {None, "world", "experience", "observation"}:
                        result_type = None
                    if not isinstance(scores, dict):
                        scores = {}
                    safe_scores = {
                        key: value for key, value in scores.items()
                        if key in {"final", "reranker", "semantic", "keyword"}
                        and isinstance(value, (int, float))
                        and not isinstance(value, bool)
                        and math.isfinite(value)
                    }
                    safe_items.append({"rank": rank, "type": result_type, "scores": safe_scores})
                rows.append({"stage": stage, "results": safe_items})
            next_offset = stream.tell()
    except OSError:
        return [], offset
    return rows, next_offset


def read_safe_recall_timings(log_path: pathlib.Path, offset: int = 0):
    """Read allowlisted automatic-recall timing fields, never log text fields."""
    marker = "HADES timing stage=automatic_recall "
    allowed_phases = {"operation_visibility", "semantic_lookup", "raw_fact_fallback"}
    allowed_states = {"active", "clear", "unknown"}
    rows = []
    try:
        with log_path.open("rb") as stream:
            stream.seek(max(0, offset))
            while True:
                raw_line = stream.readline()
                if not raw_line:
                    break
                line = raw_line.decode("utf-8", errors="replace")
                start = line.find(marker)
                if start < 0:
                    continue
                fields = dict(re.findall(
                    r"([a-z_]+)=([A-Za-z0-9_.,:-]+)",
                    line[start + len(marker):],
                ))
                phase = fields.get("phase") or fields.get("operation_visibility")
                # Operation-visibility lines encode the phase as the first
                # bare token, followed by key/value fields.
                if phase is None:
                    phase_match = re.match(
                        r"([a-z_]+)\s+", line[start + len(marker):]
                    )
                    phase = phase_match.group(1) if phase_match else None
                if phase not in allowed_phases:
                    continue
                row: dict[str, Any] = {
                    "stage": "automatic_recall",
                    "phase": phase,
                }
                state = fields.get("state")
                if state in allowed_states:
                    row["state"] = state
                operation_types = fields.get("operation_types", "").split(",")
                safe_types = sorted({
                    value for value in operation_types
                    if value in {"retain", "consolidation"}
                })
                if safe_types:
                    row["operation_types"] = safe_types
                result_count = fields.get("results")
                if result_count and result_count.isdecimal():
                    row["results"] = int(result_count)
                elapsed = fields.get("elapsed_ms")
                if elapsed:
                    try:
                        value = float(elapsed)
                    except ValueError:
                        value = math.nan
                    if math.isfinite(value) and value >= 0:
                        row["elapsed_ms"] = round(value, 1)
                outcome = fields.get("outcome")
                if outcome == "error" or (
                    phase == "operation_visibility"
                    and state == "unknown"
                    and fields.get("error")
                ):
                    row["outcome"] = "error"
                    error_type = fields.get("error")
                    if error_type and error_type.isidentifier():
                        row["error_type"] = error_type
                rows.append(row)
            next_offset = stream.tell()
    except OSError:
        return [], offset
    return rows, next_offset


def safe_repetitions(repetitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Serialize outcomes without answers, prompts, schemas, or raw provider calls."""
    sample_keys = (
        "sample", "first_stack", "hindsight_idle_after_hades", "runtime_normalization",
        "runtime_after_automatic_retain",
    )
    outcome_keys = (
        "fresh_recall_expected_marker_present", "fresh_recall_stale_mango_present",
        "implicit_recall_expected_marker_present", "implicit_recall_stale_mango_present",
        "automatic_recall_expected_marker_present", "automatic_retained_fact_visible",
        "automatic_retained_fact_visible_after_drain",
        "automatic_recall_after_idle_expected_marker_present",
        "core09_recall_expected_marker_present",
        "core09_recall_after_idle_expected_marker_present",
        "core09_fact_visibility_after_drain",
    )
    safe_samples = []
    for sample in repetitions:
        safe_sample = {key: sample[key] for key in sample_keys if key in sample}
        safe_stacks: dict[str, Any] = {}
        for stack, stack_data in sample.get("stacks", {}).items():
            safe_stack = {
                "turns": [safe_turn_record(row) for row in stack_data.get("turns", [])]
            }
            for key in outcome_keys:
                if key in stack_data:
                    safe_stack[key] = stack_data[key]
            for key in (
                "automatic_retention_state_before_recall",
                "memory_supplement_visibility_after_drain",
            ):
                if key in stack_data:
                    safe_stack[key] = stack_data[key]
            if "memory_supplement" in stack_data:
                safe_stack["memory_supplement"] = [
                    {
                        key: row[key]
                        for key in ("case_id", "answer_contains_expected_marker", "continuity_only")
                        if key in row
                    }
                    for row in stack_data["memory_supplement"]
                ]
            safe_stacks[stack] = safe_stack
        safe_sample["stacks"] = safe_stacks
        safe_samples.append(safe_sample)
    return safe_samples


def synthetic_memory_bank(scope: str) -> str:
    """Mirror sitecustomize's server-selected bank for the synthetic subject."""
    if scope == "owner":
        return "hades-owner"
    if scope == "household":
        return f"hades-user-{SYNTHETIC_OWNER_SUBJECT}"
    raise ValueError("unsupported synthetic HADES scope")


def core09_answer_matches_target(answer: str) -> bool:
    """Accept the exact synthetic amount without requiring a phrase match."""
    normalized = re.sub(r"[$,\s]", "", str(answer or ""))
    return re.search(r"(?<!\d)3000(?!\d)", normalized) is not None


def docker_json(*args: str) -> Any:
    result = subprocess.run(
        ["docker", *args], check=True, text=True, capture_output=True, timeout=30
    )
    return json.loads(result.stdout)


def docker_bridge_gateway() -> str:
    networks = docker_json("network", "inspect", "bridge")
    configs = networks[0].get("IPAM", {}).get("Config", []) if networks else []
    gateway = next((row.get("Gateway") for row in configs if row.get("Gateway")), None)
    if not gateway:
        raise RuntimeError("Docker bridge has no gateway address for loopback Ollama forwarding")
    return str(gateway)


class HindsightOllamaProxy(ThreadingHTTPServer):
    """Forward Hindsight's local Ollama traffic and retain aggregate metrics only."""
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], upstream_port: int):
        self.upstream_port = upstream_port
        self.records: list[dict[str, Any]] = []
        self.records_lock = threading.Lock()
        self.in_flight = 0
        self.in_flight_lock = threading.Lock()
        super().__init__(address, self.handler_type())

    def handler_type(self):
        parent = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args):
                return

            def do_POST(self):
                started = time.perf_counter()
                raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                try:
                    request = json.loads(raw)
                except (ValueError, TypeError):
                    request = {}
                route = urllib.parse.urlsplit(self.path).path
                upstream = http.client.HTTPConnection(
                    "127.0.0.1", parent.upstream_port, timeout=360
                )
                with parent.in_flight_lock:
                    parent.in_flight += 1
                try:
                    upstream.request(
                        "POST", self.path, body=raw,
                        headers={"Content-Type": self.headers.get("Content-Type", "application/json")},
                    )
                    response = upstream.getresponse()
                    payload = response.read()
                    status = response.status
                    content_type = response.getheader("Content-Type", "application/json")
                except OSError:
                    payload, status, content_type = b"", 502, "application/json"
                finally:
                    upstream.close()
                    with parent.in_flight_lock:
                        parent.in_flight -= 1

                try:
                    result = json.loads(payload)
                except (ValueError, TypeError):
                    result = {}
                options = request.get("options")
                option_controls = {}
                if isinstance(options, dict):
                    option_controls = {
                        key: options[key]
                        for key in ("num_ctx", "num_predict", "temperature", "top_k", "top_p", "seed")
                        if isinstance(options.get(key), (bool, int, float))
                    }
                record = {
                    "route": route if route in {"/api/chat", "/api/generate", "/api/embeddings", "/api/embed"} else "other",
                    "model": request.get("model") if isinstance(request.get("model"), str) else None,
                    "stream": request.get("stream") is True,
                    "request_bytes": len(raw),
                    "status": status,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                    "response_bytes": len(payload),
                    "prompt_eval_count": result.get("prompt_eval_count") if isinstance(result.get("prompt_eval_count"), int) else None,
                    "eval_count": result.get("eval_count") if isinstance(result.get("eval_count"), int) else None,
                    "total_duration_ns": result.get("total_duration") if isinstance(result.get("total_duration"), int) else None,
                    "load_duration_ns": result.get("load_duration") if isinstance(result.get("load_duration"), int) else None,
                    "generation_controls": option_controls,
                }
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(payload)
                self.wfile.flush()
                self.close_connection = True
                model_name = record.get("model")
                if isinstance(model_name, str):
                    residency = http.client.HTTPConnection(
                        "127.0.0.1", parent.upstream_port, timeout=5
                    )
                    try:
                        residency.request("GET", "/api/ps")
                        ps_response = residency.getresponse()
                        ps_payload = ps_response.read()
                        if ps_response.status != 200:
                            record["loaded_model_residency"] = f"api_status_{ps_response.status}"
                            loaded = None
                        else:
                            ps_data = json.loads(ps_payload)
                            loaded = next(
                                (row for row in ps_data.get("models", [])
                                 if row.get("name") == model_name),
                                None,
                            )
                            record["loaded_model_residency"] = (
                                "resident" if isinstance(loaded, dict) else "not_resident"
                            )
                        if isinstance(loaded, dict):
                            record["loaded_model_context_length"] = loaded.get("context_length")
                            record["loaded_model_size_bytes"] = loaded.get("size")
                            record["loaded_model_size_vram_bytes"] = loaded.get("size_vram")
                        else:
                            record["loaded_model_context_length"] = None
                            record["loaded_model_size_bytes"] = None
                            record["loaded_model_size_vram_bytes"] = None
                    except (OSError, ValueError, TypeError) as exc:
                        record["loaded_model_residency"] = f"unavailable_{type(exc).__name__}"
                        record["loaded_model_context_length"] = None
                        record["loaded_model_size_bytes"] = None
                        record["loaded_model_size_vram_bytes"] = None
                    finally:
                        residency.close()
                with parent.records_lock:
                    parent.records.append(record)

            def do_GET(self):
                upstream = http.client.HTTPConnection(
                    "127.0.0.1", parent.upstream_port, timeout=30
                )
                try:
                    upstream.request("GET", self.path)
                    response = upstream.getresponse()
                    payload = response.read()
                    status = response.status
                    content_type = response.getheader("Content-Type", "application/json")
                except OSError:
                    payload, status, content_type = b"", 502, "application/json"
                finally:
                    upstream.close()
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(payload)
                self.close_connection = True

        return Handler

    def snapshot(self) -> list[dict[str, Any]]:
        with self.records_lock:
            return [dict(row) for row in self.records]

    def active_requests(self) -> int:
        with self.in_flight_lock:
            return self.in_flight


def start_hindsight_ollama_proxy(gateway: str, ollama_port: int):
    probe = socket.socket()
    probe.bind((gateway, 0))
    port = int(probe.getsockname()[1])
    probe.close()
    server = HindsightOllamaProxy((gateway, port), ollama_port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, port


def wait_hindsight(url: str, container: str, timeout: int = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            pass
        time.sleep(1)
    logs = subprocess.run(
        ["docker", "logs", "--tail", "60", container],
        capture_output=True,
        text=True,
        timeout=20,
    ).stdout[-6000:]
    raise RuntimeError(f"Hindsight startup timed out:\n{logs}")


def retained_fact_visible(url: str, bank_id: str, needle: str,
                          required_tag: str | None = None) -> bool:
    query = urllib.parse.urlencode({"state": "valid", "limit": 100})
    endpoint = (
        f"{url.rstrip('/')}/v1/default/banks/"
        f"{urllib.parse.quote(bank_id, safe='-_')}/memories/list?{query}"
    )
    try:
        with urllib.request.urlopen(endpoint, timeout=3) as response:
            payload = json.load(response)
        rows = payload.get("items", []) if isinstance(payload, dict) else []
        return any(
            needle.casefold() in str(row.get("text") or "").casefold()
            and (
                required_tag is None
                or required_tag in (row.get("tags") or [])
            )
            for row in rows if isinstance(row, dict)
        )
    except Exception:
        return False


def hindsight_recall_candidate_diagnostic(url: str,
                                         bank_id: str) -> list[dict[str, Any]]:
    """Compare synthetic candidate retrieval without persisting result text."""
    cases = [
        {"case": "denver", "query": "Where did I say I moved?", "markers": ["denver"]},
        {"case": "place_preference", "query": "What kind of places do I usually prefer?", "markers": ["quiet"]},
    ]
    modes = [
        {"name": "observation", "types": ["observation"], "prefer_observations": False},
        {"name": "raw", "types": ["world", "experience"], "prefer_observations": False},
        {"name": "all", "types": ["observation", "world", "experience"], "prefer_observations": False},
        {"name": "all_prefer_observations", "types": ["observation", "world", "experience"], "prefer_observations": True},
    ]
    endpoint = (
        f"{url.rstrip('/')}/v1/default/banks/"
        f"{urllib.parse.quote(bank_id, safe='-_')}/memories/recall"
    )
    rows = []
    for case in cases:
        for mode in modes:
            started = time.monotonic()
            body = json.dumps({
                "query": case["query"], "types": mode["types"],
                "budget": "mid", "max_tokens": 4096,
                "prefer_observations": mode["prefer_observations"],
            }).encode()
            request = urllib.request.Request(
                endpoint, data=body,
                headers={
                    "Authorization": "Bearer synthetic-local-benchmark",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    payload = json.load(response)
                results = payload.get("results", []) if isinstance(payload, dict) else []
                rank = next((index + 1 for index, item in enumerate(results)
                             if isinstance(item, dict)
                             if any(marker in str(item.get("text") or "").casefold()
                                    for marker in case["markers"])), None)
                type_counts: dict[str, int] = {}
                for item in results:
                    if isinstance(item, dict):
                        kind = str(item.get("type") or "unknown")
                        type_counts[kind] = type_counts.get(kind, 0) + 1
                row = {
                    "case": case["case"], "mode": mode["name"],
                    "result_count": len(results), "result_type_counts": type_counts,
                    "expected_marker_first_rank": rank,
                }
            except urllib.error.HTTPError as exc:
                row = {"case": case["case"], "mode": mode["name"],
                       "error_type": "HTTPError", "status_code": int(exc.code)}
            except Exception as exc:
                row = {"case": case["case"], "mode": mode["name"],
                       "error_type": type(exc).__name__}
            row["elapsed_ms"] = round((time.monotonic() - started) * 1000, 1)
            rows.append(row)
    return rows


def hindsight_bank_lifecycle(url: str, bank_id: str) -> dict[str, Any]:
    """Return aggregate async-operation and fact-type counts for synthetic probes."""
    base = (
        f"{url.rstrip('/')}/v1/default/banks/"
        f"{urllib.parse.quote(bank_id, safe='-_')}"
    )
    result: dict[str, Any] = {"operations": {}, "stats": {}}
    for status in ("pending", "processing"):
        query = urllib.parse.urlencode({"status": status, "limit": 100})
        try:
            with urllib.request.urlopen(f"{base}/operations?{query}", timeout=2) as response:
                payload = json.load(response)
            rows = payload.get("operations", []) if isinstance(payload, dict) else []
            counts: dict[str, int] = {}
            for row in rows:
                if isinstance(row, dict):
                    name = str(row.get("task_type") or "unknown")
                    counts[name] = counts.get(name, 0) + 1
            result["operations"][status] = counts
        except Exception as exc:
            error = {"error": type(exc).__name__}
            if isinstance(exc, urllib.error.HTTPError) and isinstance(exc.code, int):
                error["status_code"] = exc.code
            result["operations"][status] = error
    try:
        with urllib.request.urlopen(f"{base}/stats?refresh=true", timeout=2) as response:
            stats = json.load(response)
        if isinstance(stats, dict):
            result["stats"] = {
                key: stats.get(key)
                for key in (
                    "nodes_by_fact_type", "pending_operations", "operations_by_status",
                    "pending_consolidation", "total_observations",
                )
            }
    except Exception as exc:
        result["stats"] = {"error": type(exc).__name__}
    return result


def hindsight_all_bank_lifecycle(url: str, _bank_id: str = "") -> dict[str, Any]:
    """Aggregate operation state across this benchmark's disposable Hindsight DB."""
    base = f"{url.rstrip('/')}/v1/default/banks"
    rows = []
    offset = 0
    total = None
    try:
        while total is None or offset < total:
            query = urllib.parse.urlencode({"limit": 100, "offset": offset})
            with urllib.request.urlopen(f"{base}?{query}", timeout=3) as response:
                payload = json.load(response)
            if (not isinstance(payload, dict)
                    or not isinstance(payload.get("banks"), list)
                    or not isinstance(payload.get("total"), int)):
                raise ValueError("UnexpectedBankListShape")
            page = payload["banks"]
            page_total = payload["total"]
            if total is not None and page_total != total:
                raise ValueError("BankListTotalChanged")
            total = page_total
            if any(
                not isinstance(row, dict)
                or not isinstance(row.get("bank_id"), str)
                or not row["bank_id"]
                for row in page
            ):
                raise ValueError("UnexpectedBankListShape")
            rows.extend(page)
            if not page and offset < total:
                raise ValueError("IncompleteBankListPage")
            offset += len(page)
        if len(rows) != total:
            raise ValueError("IncompleteBankListPage")
    except Exception as exc:
        return {"operations": {
            "pending": {"error": type(exc).__name__},
            "processing": {"error": type(exc).__name__},
        }}
    result: dict[str, Any] = {
        "banks": {}, "operations": {"pending": {}, "processing": {}},
        "stats": {"pending_operations": 0, "operations_by_status": {}},
    }
    for row in rows:
        bank_id = row["bank_id"]
        lifecycle = hindsight_bank_lifecycle(url, bank_id)
        for status in ("pending", "processing"):
            counts = lifecycle.get("operations", {}).get(status, {})
            if isinstance(counts, dict) and counts.get("error"):
                result["operations"][status] = {
                    "error": counts["error"],
                    "status_code": counts.get("status_code"),
                    "bank_count": len(rows),
                }
                return result
            result["banks"].setdefault(bank_id, {})[status] = counts
            for task, count in counts.items():
                result["operations"][status][task] = (
                    result["operations"][status].get(task, 0) + count
                )
        stats = lifecycle.get("stats", {})
        pending = stats.get("pending_operations") if isinstance(stats, dict) else None
        if isinstance(pending, int):
            result["stats"]["pending_operations"] += pending
        by_status = stats.get("operations_by_status", {}) if isinstance(stats, dict) else {}
        if isinstance(by_status, dict):
            for status, count in by_status.items():
                if isinstance(count, int):
                    result["stats"]["operations_by_status"][status] = (
                        result["stats"]["operations_by_status"].get(status, 0) + count
                    )
    result["bank_count"] = len(rows)
    return result


def wait_hindsight_idle(url: str, bank_id: str, timeout: int = 180,
                        poll_interval: float = 1.0, lifecycle_fn=None,
                        proxy=None) -> dict[str, Any]:
    """Wait for Hindsight jobs and their proxied inference requests to drain."""
    lifecycle_fn = lifecycle_fn or hindsight_all_bank_lifecycle
    deadline = time.monotonic() + timeout
    consecutive_idle = 0
    last_state: dict[str, Any] = {}
    polls = 0
    while time.monotonic() < deadline:
        last_state = lifecycle_fn(url, bank_id)
        polls += 1
        active_requests = proxy.active_requests() if proxy is not None else 0
        operations = last_state.get("operations", {})
        counts: dict[str, int] = {}
        for status in ("pending", "processing"):
            current = operations.get(status, {})
            if "error" in current:
                error_type = current.get("error")
                safe_type = error_type if isinstance(error_type, str) and error_type.isidentifier() else "UnknownError"
                status_code = current.get("status_code")
                suffix = f"; status={status_code}" if isinstance(status_code, int) and 100 <= status_code <= 599 else ""
                raise RuntimeError(
                    f"Hindsight {status} operation status unavailable ({safe_type}{suffix})"
                )
            counts[status] = sum(value for value in current.values() if isinstance(value, int))
        if any(counts.values()) or active_requests:
            consecutive_idle = 0
        else:
            stats = last_state.get("stats", {})
            if "error" in stats:
                raise RuntimeError("Hindsight refreshed bank statistics unavailable")
            pending = stats.get("pending_operations")
            status_counts = stats.get("operations_by_status")
            if isinstance(status_counts, dict):
                pending = sum(
                    status_counts.get(status, 0)
                    for status in ("pending", "processing")
                    if isinstance(status_counts.get(status, 0), int)
                )
            consolidation = stats.get("pending_consolidation", 0)
            if ((isinstance(pending, int) and pending > 0)
                    or (isinstance(consolidation, int) and consolidation > 0)):
                consecutive_idle = 0
            else:
                consecutive_idle += 1
            if consecutive_idle >= 2:
                return {
                    "idle": True,
                    "polls": polls,
                    "proxy_active_requests": active_requests,
                    "elapsed_ms": round((timeout - max(0, deadline - time.monotonic())) * 1000, 1),
                    "last_state": last_state,
                }
        time.sleep(poll_interval)
    return {
        "idle": False,
        "polls": polls,
        "proxy_active_requests": proxy.active_requests() if proxy is not None else 0,
        "elapsed_ms": round(timeout * 1000, 1),
        "last_state": last_state,
    }


def normalize_ollama_for_arm(ollama_url: str, benchmark, interactive_model: str,
                             extractor_model: str, context: int = CONTEXT_LENGTH) -> dict[str, Any]:
    """Start each comparison arm with only the interactive model resident."""
    base = ollama_url.rstrip("/")
    unload = None
    initial_rows = benchmark.local_json(f"{base}/api/ps").get("models", [])
    extractor_was_resident = any(
        row.get("name") == extractor_model for row in initial_rows
    )
    if extractor_model != interactive_model and extractor_was_resident:
        payload = json.dumps({
            "model": extractor_model,
            "prompt": "",
            "stream": False,
            "keep_alive": 0,
            "options": {"num_predict": 1},
        }).encode()
        request = urllib.request.Request(
            f"{base}/api/generate", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        started = time.monotonic()
        with urllib.request.urlopen(request, timeout=360) as response:
            if response.status != 200:
                raise RuntimeError("Ollama extractor unload failed")
        unload = round((time.monotonic() - started) * 1000, 1)

    payload = json.dumps({
        "model": interactive_model,
        "prompt": " ",
        "stream": False,
        "keep_alive": -1,
        "options": {"num_ctx": context, "num_predict": 1, "temperature": 0.1},
    }).encode()
    request = urllib.request.Request(
        f"{base}/api/generate", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=360) as response:
        if response.status != 200:
            raise RuntimeError("Ollama interactive-model warmup failed")
    warmup_ms = round((time.monotonic() - started) * 1000, 1)
    rows = benchmark.local_json(f"{base}/api/ps").get("models", [])
    resident = next((row for row in rows if row.get("name") == interactive_model), None)
    if not resident:
        raise RuntimeError("Ollama interactive model is not resident after arm normalization")
    shared_model = extractor_model == interactive_model
    extractor_resident = any(row.get("name") == extractor_model for row in rows)
    if extractor_resident and not shared_model:
        raise RuntimeError("Ollama extractor remains resident after arm normalization")
    return {
        "interactive_model_resident": True,
        "interactive_context_length": resident.get("context_length"),
        "interactive_size_vram_bytes": resident.get("size_vram"),
        "extractor_shares_interactive_model": shared_model,
        "extractor_resident": extractor_resident,
        "extractor_was_resident_before_reset": extractor_was_resident,
        "extractor_unload_ms": unload,
        "interactive_warmup_ms": warmup_ms,
        "normalization_calls_excluded_from_turn_timing": True,
    }


def summarize_runtime_residency(rows: list[dict[str, Any]],
                                interactive_model: str,
                                extractor_model: str) -> dict[str, Any]:
    """Keep only role-based runtime residency needed for latency diagnosis."""
    def matching(name: str):
        return next((row for row in rows if isinstance(row, dict) and row.get("name") == name), None)

    interactive = matching(interactive_model)
    extractor = matching(extractor_model)
    return {
        "interactive_model_loaded": isinstance(interactive, dict),
        "interactive_context_length": (
            interactive.get("context_length") if isinstance(interactive, dict)
            and isinstance(interactive.get("context_length"), int) else None
        ),
        "interactive_vram_bytes": (
            interactive.get("size_vram") if isinstance(interactive, dict)
            and isinstance(interactive.get("size_vram"), int) else None
        ),
        "memory_model_loaded": isinstance(extractor, dict),
        "memory_model_context_length": (
            extractor.get("context_length") if isinstance(extractor, dict)
            and isinstance(extractor.get("context_length"), int) else None
        ),
        "memory_model_vram_bytes": (
            extractor.get("size_vram") if isinstance(extractor, dict)
            and isinstance(extractor.get("size_vram"), int) else None
        ),
    }


def runtime_residency_snapshot(ollama_url: str, benchmark,
                               interactive_model: str,
                               extractor_model: str) -> dict[str, Any]:
    rows = benchmark.local_json(
        f"{ollama_url.rstrip('/')}/api/ps"
    ).get("models", [])
    if not isinstance(rows, list):
        rows = []
    return summarize_runtime_residency(rows, interactive_model, extractor_model)


def measure_memory_supplement_case(gateway: dict[str, Any], benchmark,
                                   case: dict[str, Any], stack: str,
                                   sample_id: str) -> dict[str, Any]:
    """Replay a synthetic memory case and a fresh-session recall where defined."""
    case_id = str(case["id"])
    review = case.get("review_check", {})
    turns = case.get("turns", [])
    rows: list[dict[str, Any]] = []
    if case_id == "core-55":
        session = f"memory-supplement-{stack}-{sample_id}-{case_id}"
        history: list[dict[str, str]] = []
        for index, prompt in enumerate(turns):
            turn = measure_turn(
                gateway, benchmark, f"supplement_{case_id}_turn_{index + 1}",
                session, history + [{"role": "user", "content": prompt}],
            )
            rows.append(turn)
            history.extend([
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": turn["answer"]},
            ])
        answer = rows[int(review.get("recall_turn_index", len(rows) - 1))]["answer"]
    else:
        if not turns or not review.get("probe_text"):
            raise RuntimeError(f"memory supplement case {case_id} lacks seed turns or a recall probe")
        seed_session = f"memory-supplement-{stack}-{sample_id}-{case_id}-seed"
        history: list[dict[str, str]] = []
        for index, prompt in enumerate(turns):
            seed = measure_turn(
                gateway, benchmark, f"supplement_{case_id}_seed_{index + 1}",
                seed_session, history + [{"role": "user", "content": prompt}],
            )
            rows.append(seed)
            history.extend([
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": seed["answer"]},
            ])
        probe = measure_turn(
            gateway, benchmark, f"supplement_{case_id}_probe",
            f"memory-supplement-{stack}-{sample_id}-{case_id}-probe",
            [{"role": "user", "content": review["probe_text"]}],
        )
        rows.append(probe)
        answer = probe["answer"]
    folded = str(answer or "").casefold()
    required_markers = [str(marker).casefold() for marker in review.get("must_contain_any", [])]
    required_all = [str(marker).casefold() for marker in review.get("must_contain_all", [])]
    forbidden_markers = [str(marker).casefold() for marker in review.get("must_not_contain_any", [])]
    marker_present = (
        (not required_markers or any(marker in folded for marker in required_markers))
        and all(marker in folded for marker in required_all)
        and not any(marker in folded for marker in forbidden_markers)
    )
    return {
        "case_id": case_id,
        "turns": rows,
        "probe_text": review.get("probe_text"),
        "expected_markers": required_markers or required_all,
        "forbidden_markers": forbidden_markers,
        "answer_contains_expected_marker": marker_present,
        "continuity_only": bool(review.get("continuity_only", False)),
    }


def start_hindsight(image: str, ollama_bridge_url: str, run_id: str, volume: str,
    hindsight_model: str, network_mode: str = "bridge",
    llm_max_concurrent: int = 1, retain_mode: str = "concise",
    enable_observations: bool = True):
    subprocess.run(["docker", "volume", "create", volume], check=True, capture_output=True)
    api_port = 8888
    control_port = 9999
    if network_mode == "host":
        # Rootless gvisor-tap-vsock disables host-loopback access from bridge
        # containers. Host mode is an explicit staging-only escape hatch; bind
        # both Hindsight listeners to loopback and select ephemeral ports.
        api_port = unused_local_port()
        control_port = unused_local_port()
        network_args = ["--network", "host"]
        host = "127.0.0.1"
    elif network_mode == "bridge":
        network_args = [
            "--add-host", "host.docker.internal:host-gateway",
            "-p", "127.0.0.1::8888", "-p", "127.0.0.1::9999",
        ]
        host = "0.0.0.0"
    else:
        raise ValueError("unsupported Hindsight staging network mode")
    subprocess.run(
        [
            "docker", "run", "-d", "--name", run_id,
            *network_args,
            "-v", f"{volume}:/home/hindsight/.pg0",
            "-e", f"HINDSIGHT_API_HOST={host}",
            "-e", f"HINDSIGHT_API_PORT={api_port}",
            "-e", f"HINDSIGHT_CP_HOSTNAME={host}",
            "-e", f"HINDSIGHT_CP_PORT={control_port}",
            "-e", f"HINDSIGHT_API_ENABLE_OBSERVATIONS={'true' if enable_observations else 'false'}",
            "-e", "HINDSIGHT_API_ENABLE_BANK_CONFIG_API=true",
            "-e", f"HINDSIGHT_API_WORKER_ID={run_id}",
            "-e", "HINDSIGHT_API_LLM_PROVIDER=ollama",
            "-e", f"HINDSIGHT_API_LLM_BASE_URL={ollama_bridge_url}",
            "-e", f"HINDSIGHT_API_LLM_MODEL={hindsight_model}",
            "-e", f"HINDSIGHT_API_LLM_MAX_CONCURRENT={llm_max_concurrent}",
            "-e", f"HINDSIGHT_API_RETAIN_EXTRACTION_MODE={retain_mode}",
            "-e", "HINDSIGHT_API_LLM_API_KEY=synthetic-local-benchmark",
            "-e", "HINDSIGHT_API_EMBEDDINGS_PROVIDER=local",
            image,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if network_mode == "host":
        url = f"http://127.0.0.1:{api_port}"
    else:
        mapped = subprocess.run(
            [
                "docker", "inspect", run_id,
                "--format", '{{(index (index .NetworkSettings.Ports "8888/tcp") 0).HostPort}}',
            ],
            check=True,
            text=True,
            capture_output=True,
            timeout=15,
        ).stdout.strip()
        url = f"http://127.0.0.1:{mapped}"
    wait_hindsight(url, run_id)
    return url


def unused_local_port() -> int:
    probe = socket.socket()
    try:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])
    finally:
        probe.close()


def create_gateway(stack: str, root: pathlib.Path, plugin: pathlib.Path,
                   proxy_module, hindsight_url: str | None, temp: pathlib.Path,
                   ollama_url: str, hermes_root: pathlib.Path,
                   hades_scope: str, hades_recall_types: str,
                   hades_recall_budget: str,
                   hades_prefer_observations: bool,
                   capture_recall_diagnostics: bool = False):
    executable = hermes_executable(hermes_root)
    provider_port = proxy_module.unused_port()
    proxy = proxy_module.AggregateProxy(
        ("127.0.0.1", provider_port), stack, ollama_url
    )
    # Pin identical user-facing sampler values through the common proxy. The
    # isolated benchmark should not inherit different Hermes defaults.
    proxy.generation_overrides = {
        "temperature": 0.1,
        "top_p": 0.95,
        "options": {"num_ctx": CONTEXT_LENGTH},
    }
    proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    proxy_thread.start()

    api_port = proxy_module.unused_port()
    home = temp / stack
    home.mkdir(mode=0o700)
    config: dict[str, Any] = {
        "gateway": {"standalone": True},
        "model": {
            "default": MODEL,
            "provider": "custom",
            "base_url": f"http://127.0.0.1:{provider_port}/v1",
            "context_length": CONTEXT_LENGTH,
            "ollama_num_ctx": CONTEXT_LENGTH,
            "max_tokens": 512,
        },
        "providers": {"custom": {"request_timeout_seconds": 360}},
        "platform_toolsets": {"api_server": ["memory"] if stack == "plain" else []},
        "auxiliary": {"title_generation": {"enabled": False}},
    }
    if stack == "plain":
        config["memory"] = {
            "memory_enabled": True,
            "user_profile_enabled": True,
            "nudge_interval": 0,
        }
    else:
        config["memory"] = {"provider": "hindsight"}
        hindsight_home = home / "hindsight"
        hindsight_home.mkdir(mode=0o700)
        hindsight_config = {
            "mode": "local_external",
            "api_url": hindsight_url or "",
            "api_key": "synthetic-local-benchmark",
            "bank_id": "hades-synthetic",
            "recall_budget": hades_recall_budget,
        }
        if hades_recall_types == "all":
            hindsight_config["recall_types"] = ["observation", "world", "experience"]
        if hades_prefer_observations:
            hindsight_config["prefer_observations"] = True
        (hindsight_home / "config.json").write_text(
            json.dumps(hindsight_config, indent=2) + "\n", encoding="utf-8"
        )
        os.chmod(hindsight_home / "config.json", 0o600)
        bundled_provider = hermes_root / "source/plugins/memory/hindsight"
        if not bundled_provider.is_dir():
            # Hermes 0.21.5 moved Hindsight out of core. For that candidate,
            # install/enable the separate upstream integration explicitly.
            config["plugins"] = {"enabled": ["hindsight"]}
            plugins = home / "plugins"
            plugins.mkdir()
            (plugins / "hindsight").symlink_to(plugin.resolve(), target_is_directory=True)

    import yaml

    (home / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    os.chmod(home / "config.yaml", 0o600)
    env = benchmark_child_environment()
    env.update(
        {
            "HOME": str(home),
            "HERMES_HOME": str(home),
            "API_SERVER_KEY": proxy_module.API_KEY,
            "API_SERVER_HOST": "127.0.0.1",
            "API_SERVER_PORT": str(api_port),
            "API_SERVER_ENABLED": "true",
            "HERMES_ACCEPT_HOOKS": "1",
            "PYTHONUNBUFFERED": "1",
            "PYTHONPATH": str(root / "scripts/.."),
        }
    )
    if stack == "plain":
        env["PYTHONPATH"] = str(hermes_root)
    else:
        env["PYTHONPATH"] = os.pathsep.join(
            (str(root / "hermes"), str(root), str(hermes_root))
        )
        env.update(
            {
                "HADES_HINDSIGHT_URL": hindsight_url or "",
                "HADES_MEMORY_SCORE_DIAGNOSTICS": "1" if stack == "hades" else "0",
                "HINDSIGHT_MODE": "local_external",
                "HINDSIGHT_API_URL": hindsight_url or "",
                "HINDSIGHT_API_KEY": "synthetic-local-benchmark",
                "HADES_HERMES_EXECUTABLE": str(executable),
                "HADES_HERMES_WORKING_DIRECTORY": str(root),
                "HADES_INTEGRATIONS_ROOT": str(root),
            }
        )
        configure_hades_scope(env, hades_scope)

    log_path = temp / f"{stack}.log"
    log = log_path.open("w", encoding="utf-8")
    gateway_command = [str(executable), "gateway", "run"]
    if capture_recall_diagnostics and stack == "hades":
        gateway_command.append("-v")
    gateway_command.append("--accept-hooks")
    process = subprocess.Popen(
        gateway_command,
        cwd=root,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        proxy_module.wait_health(api_port, process, log_path)
    except Exception:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        log.close()
        proxy.shutdown()
        proxy.server_close()
        proxy_thread.join(timeout=2)
        raise
    proxy.api_port = api_port
    return {
        "stack": stack,
        "api_port": api_port,
        "home": home,
        "proxy": proxy,
        "proxy_thread": proxy_thread,
        "process": process,
        "log": log,
        "log_path": log_path,
    }


def summarize_calls(calls: list[dict[str, Any]]) -> dict[str, Any]:
    usage = [call.get("usage") or {} for call in calls]
    return {
        "provider_generations": len(calls),
        "tool_schema_exposures": sum(call.get("tool_schema_count", 0) for call in calls),
        "tool_schema_bytes_exposed": sum(call.get("tool_schema_bytes", 0) for call in calls),
        "tool_calls_emitted": sum(call.get("tool_calls_emitted", 0) for call in calls),
        "prompt_tokens": sum(row.get("prompt_tokens", 0) for row in usage),
        "completion_tokens": sum(row.get("completion_tokens", 0) for row in usage),
        "request_bytes": sum(call.get("request_bytes", 0) for call in calls),
        "message_bytes": sum(call.get("message_bytes", 0) for call in calls),
        "system_message_bytes": sum(
            call.get("message_bytes_by_role", {}).get("system", 0) for call in calls
        ),
        "context_tokens_per_generation": [
            call.get("requested_num_ctx") for call in calls
        ],
        "runtime_observation_per_generation": [
            {
                "model_resident_at_response_boundary": (
                    call.get("runtime_probe_status", "unavailable")
                ),
                "loaded_context_tokens": call.get("loaded_context_tokens"),
            }
            for call in calls
        ],
    }


def require_measured_runtime_context(calls: list[dict[str, Any]],
                                    requested_context: int,
                                    allow_evicted_after_generation: bool = False) -> None:
    """Check requested context and any post-generation runtime observation."""
    if not calls or any(
        call.get("requested_num_ctx") != requested_context
        or (
            call.get("runtime_probe_status") == "resident"
            and call.get("loaded_context_tokens") != requested_context
        )
        or (
            call.get("runtime_probe_status") == "not_resident"
            and not allow_evicted_after_generation
        )
        or call.get("runtime_probe_status") not in {"resident", "not_resident"}
        for call in calls
    ):
        observed = [
            {
                "requested": call.get("requested_num_ctx"),
                "runtime_status": call.get("runtime_probe_status"),
                "loaded": call.get("loaded_context_tokens"),
            }
            for call in calls
        ]
        raise RuntimeError(
            "measured provider generation did not match the configured Ollama context; "
            f"observed={observed!r}"
        )


def measure_turn(gateway: dict[str, Any], proxy_module, turn: str, session: str,
                 messages: list[dict[str, str]], max_tokens: int = 512):
    proxy = gateway["proxy"]
    before = len(proxy.snapshot())
    try:
        row = proxy_module.chat(
            gateway["api_port"], gateway["stack"], session, messages, max_tokens
        )
        proxy.wait_idle()
        error = None
    except Exception as exc:
        row = {"status": None, "ttft_ms": None, "total_ms": None, "answer": ""}
        error = type(exc).__name__
    calls = proxy.snapshot()[before:]
    require_measured_runtime_context(
        calls, CONTEXT_LENGTH,
        allow_evicted_after_generation=(gateway["stack"] == "hades"),
    )
    answer = row.get("answer", "")
    if isinstance(answer, str) and answer.startswith("CSV finance read ("):
        answer = "[redacted: unrelated owner-finance response; routed from synthetic benchmark turn]"
    result = {
        "turn": turn,
        "status": row.get("status"),
        "ttft_ms": row.get("ttft_ms"),
        "total_ms": row.get("total_ms"),
        "answer": answer,
        "metrics": summarize_calls(calls),
        "provider_calls": calls,
    }
    if error:
        result["error_type"] = error
    return result


def median(rows: list[dict[str, Any]], key: str):
    values = [row.get(key) for row in rows if isinstance(row.get(key), (int, float))]
    return round(statistics.median(values), 1) if values else None


def write_incomplete_artifact(output: pathlib.Path, *, source_revision: str,
                              failure_stage: str, error_type: str,
                              repetitions: list[dict[str, Any]],
                              hindsight_calls: list[dict[str, Any]],
                              safe_failure_detail: str | None = None) -> pathlib.Path:
    """Persist partial safe metrics without arbitrary exception or conversation text."""
    partial_path = output.with_name(f"{output.stem}-incomplete{output.suffix}")
    artifact = {
        "schema_version": 1,
        "classification": "incomplete; no preference or stack comparison",
        "source_revision": source_revision,
        "failure": {
            "stage": failure_stage,
            "error_type": error_type if error_type.isidentifier() else "UnknownError",
        },
        "repetitions": safe_repetitions(repetitions),
        "hindsight_ollama_calls": hindsight_calls,
        "preference_bucket": "UNASSIGNED; no owner dogfood",
    }
    if (isinstance(safe_failure_detail, str)
            and re.fullmatch(
                r"Hindsight (?:pending|processing) operation status unavailable "
                r"\([A-Za-z_][A-Za-z0-9_]*(?:; status=[1-5][0-9]{2})?\)",
                safe_failure_detail)):
        artifact["failure"]["safe_detail"] = safe_failure_detail
    partial_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n")
    return partial_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument(
        "--automatic-only", action="store_true",
        help="run only the paired greeting and synthetic automatic retain/recall; still drain Hindsight after HADES",
    )
    parser.add_argument(
        "--first-stack", choices=("plain", "hades"),
        help="starting stack for this paired pass; each invocation creates a fresh disposable Hindsight volume",
    )
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11445")
    parser.add_argument("--hermes-root", type=pathlib.Path, default=DEFAULT_HERMES)
    parser.add_argument("--hindsight-plugin", type=pathlib.Path, default=DEFAULT_PLUGIN)
    parser.add_argument("--hindsight-image", default=DEFAULT_IMAGE)
    parser.add_argument("--hindsight-model", default=DEFAULT_HINDSIGHT_MODEL)
    parser.add_argument(
        "--hindsight-llm-max-concurrent", type=int, default=1,
        help="global LLM cap for disposable Hindsight; 1 follows Hindsight 0.10.2 guidance for shared local Ollama",
    )
    parser.add_argument(
        "--hindsight-retain-mode", choices=("concise", "chunks"), default="concise",
        help="disposable Hindsight retain mode; chunks stores source chunks without LLM fact extraction",
    )
    parser.add_argument(
        "--hindsight-disable-observations", action="store_true",
        help="disable derived observation consolidation for the disposable Hindsight service",
    )
    parser.add_argument(
        "--capture-recall-diagnostics", action="store_true",
        help="enable HADES INFO logs temporarily and retain only allowlisted recall ranks, types and scores",
    )
    parser.add_argument(
        "--hindsight-network", choices=("bridge", "host"), default="bridge",
        help="use loopback-only host networking only when rootless bridge cannot reach host services",
    )
    parser.add_argument(
        "--hades-scope", choices=("owner", "household"), default="owner",
        help="authenticated HADES scope for the synthetic subject (default: owner)",
    )
    parser.add_argument(
        "--hades-recall-types", choices=("observation", "all"), default="observation",
        help="synthetic HADES recall-type setting; all enables observation, world and experience",
    )
    parser.add_argument(
        "--hades-recall-budget", choices=("low", "mid"), default="mid",
        help="synthetic HADES recall budget; low tests the upstream fast-lookup profile",
    )
    parser.add_argument(
        "--hades-prefer-observations", action="store_true",
        help="enable Hindsight's prefer_observations option in the isolated synthetic HADES profile",
    )
    parser.add_argument(
        "--output", type=pathlib.Path,
        default=ROOT / "benchmarks/hades-core-memory-paired-v2.json",
    )
    args = parser.parse_args()
    if args.samples != 1:
        parser.error(
            "use exactly one paired pass per fresh Hindsight volume; run separate invocations for additional independent samples"
        )
    if args.hindsight_llm_max_concurrent < 1:
        parser.error("--hindsight-llm-max-concurrent must be at least 1")
    try:
        hermes_root = args.hermes_root.resolve(strict=True)
        executable = hermes_executable(hermes_root)
        hermes_version = subprocess.run(
            [str(executable), "--version"], check=True, text=True,
            capture_output=True, timeout=15,
        ).stdout.strip().splitlines()[0]
    except (OSError, subprocess.SubprocessError, ValueError, IndexError) as exc:
        parser.error(f"Could not verify staged Hermes root: {type(exc).__name__}")
    if not args.hindsight_plugin.is_dir():
        parser.error(f"Staged Hindsight plugin not found: {args.hindsight_plugin}")
    if "@sha256:" not in args.hindsight_image:
        parser.error("Hindsight image must use an immutable sha256 digest")
    parsed = urllib.parse.urlparse(args.ollama_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        parser.error("The inference endpoint must be local loopback Ollama")
    if not shutil.which("docker"):
        parser.error("docker is required to create a disposable Hindsight service")

    benchmark = load_owner_benchmark()
    memory_supplement = load_memory_supplement()
    memory_bank = synthetic_memory_bank(args.hades_scope)
    ollama = args.ollama_url.rstrip("/")
    try:
        version = benchmark.local_json(f"{ollama}/api/version").get("version")
        model_rows = benchmark.local_json(f"{ollama}/api/tags").get("models", [])
        model_row = next((row for row in model_rows if row.get("name") == MODEL), None)
    except Exception as exc:
        parser.error(f"Could not verify loopback Ollama: {type(exc).__name__}")
    if not model_row:
        parser.error(f"{MODEL} is absent from local Ollama /api/tags")
    hindsight_model_row = next(
        (row for row in model_rows if row.get("name") == args.hindsight_model), None
    )
    if not hindsight_model_row:
        parser.error(f"{args.hindsight_model} is absent from local Ollama /api/tags")
    try:
        context_probe = benchmark.local_json(
            f"{ollama}/v1/chat/completions",
            {
                "model": MODEL,
                "messages": [{"role": "user", "content": "context " * 7000}],
                "stream": False,
                "max_tokens": 1,
            },
            timeout=360,
        )
        context_probe_prompt_tokens = (context_probe.get("usage") or {}).get("prompt_tokens")
    except Exception as exc:
        parser.error(f"OpenAI-compatible Ollama context probe failed: {type(exc).__name__}")
    if not isinstance(context_probe_prompt_tokens, int) or context_probe_prompt_tokens < 5000:
        parser.error(
            "OpenAI-compatible Ollama chat path did not accept a >4k-context probe; "
            f"observed prompt_tokens={context_probe_prompt_tokens!r}"
        )
    try:
        context_probe_models = benchmark.local_json(f"{ollama}/api/ps").get("models", [])
        context_probe_loaded_model = benchmark.require_loaded_context(
            context_probe_models, MODEL, CONTEXT_LENGTH
        )
        context_probe_loaded_context = context_probe_loaded_model["context_length"]
    except Exception as exc:
        parser.error(
            "Ollama did not retain the required loaded context after the exact chat-path probe: "
            f"{type(exc).__name__}"
        )
    subprocess.run(["docker", "image", "inspect", args.hindsight_image], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    run_id = f"hades-memory-paired-{os.getpid()}"
    volume = f"{run_id}-data"
    temp = pathlib.Path(tempfile.mkdtemp(prefix="hades-memory-pair-"))
    container_started = False
    bridge = None
    bridge_thread = None
    gateways: dict[str, dict[str, Any]] = {}
    warmups: dict[str, Any] = {}
    repetitions: list[dict[str, Any]] = []
    failure_stage = "staging_setup"
    try:
        gateway_ip = "127.0.0.1" if args.hindsight_network == "host" else docker_bridge_gateway()
        bridge, bridge_thread, bridge_port = start_hindsight_ollama_proxy(
            gateway_ip, parsed.port or 80
        )
        hindsight_url = start_hindsight(
            args.hindsight_image,
            (
                f"http://127.0.0.1:{bridge_port}"
                if args.hindsight_network == "host"
                else f"http://host.docker.internal:{bridge_port}"
            ),
            run_id,
            volume,
            args.hindsight_model,
            args.hindsight_network,
            args.hindsight_llm_max_concurrent,
            args.hindsight_retain_mode,
            not args.hindsight_disable_observations,
        )
        container_started = True
        for stack in ("plain", "hades"):
            gateways[stack] = create_gateway(
                stack, ROOT, args.hindsight_plugin, benchmark, hindsight_url, temp,
                ollama, hermes_root, args.hades_scope, args.hades_recall_types,
                args.hades_recall_budget,
                args.hades_prefer_observations, args.capture_recall_diagnostics,
            )

        for stack in ("plain", "hades"):
            failure_stage = f"{stack}_warmup"
            gateway = gateways[stack]
            warmups[stack] = measure_turn(
                gateway, benchmark, "warmup", "memory-pair-warmup",
                [{"role": "user", "content": "Hi."}], 64,
            )
            if not warmups[stack]["answer"]:
                raise RuntimeError(f"{stack} warmup returned no assistant response")

        failure_stage = "hindsight_idle_after_warmups"
        warmup_idle = wait_hindsight_idle(
            hindsight_url, memory_bank, proxy=bridge
        )
        if not warmup_idle["idle"]:
            raise RuntimeError("Hindsight warmup work did not drain before measured arms")
        warmups["hindsight_idle"] = warmup_idle

        loaded = benchmark.local_json(f"{ollama}/api/ps").get("models", [])
        loaded_model = next((row for row in loaded if row.get("name") == MODEL), None)
        for sample in range(args.samples):
            first = args.first_stack or "plain"
            order = [first, "hades" if first == "plain" else "plain"]
            sample_result: dict[str, Any] = {
                "sample": sample + 1,
                "first_stack": first,
                "stacks": {},
            }
            repetitions.append(sample_result)
            for stack in order:
                failure_stage = f"sample_{sample + 1}_{stack}"
                sample_result.setdefault("runtime_normalization", {})[stack] = (
                    normalize_ollama_for_arm(
                        ollama, benchmark, MODEL, args.hindsight_model, CONTEXT_LENGTH
                    )
                )
                gateway = gateways[stack]
                round_id = f"{sample + 1:02d}"
                rows = []
                ordinary = measure_turn(
                    gateway, benchmark, "ordinary",
                    f"memory-pair-{stack}-{round_id}-ordinary",
                    [{"role": "user", "content": OWNER_CORE_01_GREETING}],
                )
                rows.append(ordinary)
                print(json.dumps({"sample": sample + 1, "stack": stack,
                                  "turn": "ordinary", "total_ms": ordinary["total_ms"],
                                  "provider_calls": ordinary["metrics"]["provider_generations"]}),
                      flush=True)

                automatic_fact = measure_turn(
                    gateway, benchmark, "automatic_retain",
                    f"memory-pair-{stack}-{round_id}-automatic-retain",
                    [{"role": "user", "content": "I moved to Denver in 2024."}],
                )
                rows.append(automatic_fact)
                automatic_retention_state = (
                    hindsight_bank_lifecycle(
                        hindsight_url, memory_bank
                    )
                    if stack == "hades" else None
                )
                sample_result.setdefault(
                    "runtime_after_automatic_retain", {}
                )[stack] = runtime_residency_snapshot(
                    ollama, benchmark, MODEL, args.hindsight_model
                )
                automatic_recall = measure_turn(
                    gateway, benchmark, "automatic_recall",
                    f"memory-pair-{stack}-{round_id}-automatic-recall",
                    [{"role": "user", "content": "Where did I say I moved?"}],
                )
                rows.append(automatic_recall)
                automatic_marker_present = (
                    "denver" in automatic_recall["answer"].casefold()
                )
                automatic_fact_visible = (
                    retained_fact_visible(
                        hindsight_url,
                        memory_bank,
                        "Denver",
                    )
                    if stack == "hades" else None
                )
                print(json.dumps({"sample": sample + 1, "stack": stack,
                                  "turn": "automatic_recall",
                                  "total_ms": automatic_recall["total_ms"],
                                  "provider_calls": automatic_recall["metrics"]["provider_generations"],
                                  "tool_calls": automatic_recall["metrics"]["tool_calls_emitted"],
                                  "expected_marker_present": automatic_marker_present,
                                  "retained_fact_visible": automatic_fact_visible}), flush=True)

                if args.automatic_only:
                    sample_result["stacks"][stack] = {
                        "turns": [safe_turn_record(row) for row in rows],
                        "automatic_recall_expected_fact": "Denver",
                        "automatic_recall_expected_marker_present": automatic_marker_present,
                        "automatic_retained_fact_visible": automatic_fact_visible,
                        "automatic_retention_state_before_recall": automatic_retention_state,
                    }
                    if stack == "hades":
                        failure_stage = f"hindsight_idle_after_focused_hades_{sample + 1}"
                        idle = wait_hindsight_idle(
                            hindsight_url, memory_bank, proxy=bridge
                        )
                        sample_result["hindsight_idle_after_hades"] = idle
                        if not idle["idle"]:
                            raise RuntimeError(
                                "Hindsight background operations did not drain after focused HADES arm"
                            )
                        sample_result["stacks"][stack][
                            "automatic_retained_fact_visible_after_drain"
                        ] = retained_fact_visible(
                            hindsight_url, memory_bank, "Denver"
                        )
                        after_idle_recall = measure_turn(
                            gateway,
                            benchmark,
                            "automatic_recall_after_idle",
                            f"memory-pair-{stack}-{round_id}-automatic-recall-after-idle",
                            [{"role": "user", "content": "Where did I say I moved?"}],
                        )
                        rows.append(after_idle_recall)
                        after_idle_marker = "denver" in after_idle_recall["answer"].casefold()
                        print(json.dumps({
                            "sample": sample + 1,
                            "stack": stack,
                            "turn": "automatic_recall_after_idle_review",
                            "expected_marker_present": after_idle_marker,
                            "total_ms": after_idle_recall["total_ms"],
                        }, ensure_ascii=False), flush=True)
                        sample_result["stacks"][stack]["turns"].append(
                            safe_turn_record(after_idle_recall)
                        )
                        sample_result["stacks"][stack][
                            "automatic_recall_after_idle_expected_marker_present"
                        ] = after_idle_marker
                        print(json.dumps({
                            "sample": sample + 1,
                            "hindsight_idle_after_hades": idle["elapsed_ms"],
                            "barrier": "focused_automatic_only",
                            "polls": idle["polls"],
                        }), flush=True)
                    continue

                core09_save = measure_turn(
                    gateway, benchmark, "core09_save",
                    f"memory-pair-{stack}-{round_id}-core09-save",
                    [{"role": "user", "content": "Remember that my savings target is $3,000."}],
                )
                rows.append(core09_save)
                core09_recall = measure_turn(
                    gateway, benchmark, "core09_recall",
                    f"memory-pair-{stack}-{round_id}-core09-recall",
                    [{"role": "user", "content": OWNER_CORE_09_RECALL}],
                )
                rows.append(core09_recall)
                core09_marker_present = core09_answer_matches_target(core09_recall["answer"])
                print(json.dumps({"sample": sample + 1, "stack": stack,
                                  "turn": "core09_recall",
                                  "total_ms": core09_recall["total_ms"],
                                  "provider_calls": core09_recall["metrics"]["provider_generations"],
                                  "tool_calls": core09_recall["metrics"]["tool_calls_emitted"],
                                  "expected_marker_present": core09_marker_present}), flush=True)

                sequence_id = f"memory-pair-{stack}-{round_id}-sequence"
                fact = "my favorite fruit is mango"
                save_prompt = f"Remember that {fact}."
                save = measure_turn(
                    gateway, benchmark, "save", sequence_id,
                    [{"role": "user", "content": save_prompt}],
                )
                rows.append(save)
                history = [
                    {"role": "user", "content": save_prompt},
                    {"role": "assistant", "content": save["answer"]},
                ]
                print(json.dumps({"sample": sample + 1, "stack": stack,
                                  "turn": "save", "total_ms": save["total_ms"],
                                  "provider_calls": save["metrics"]["provider_generations"],
                                  "tool_calls": save["metrics"]["tool_calls_emitted"]}),
                      flush=True)

                correction_prompt = "Correction: my favorite fruit is pear."
                correction = measure_turn(
                    gateway, benchmark, "correction", sequence_id,
                    history + [{"role": "user", "content": correction_prompt}],
                )
                rows.append(correction)
                history.extend(
                    [
                        {"role": "user", "content": correction_prompt},
                        {"role": "assistant", "content": correction["answer"]},
                    ]
                )
                print(json.dumps({"sample": sample + 1, "stack": stack,
                                  "turn": "correction", "total_ms": correction["total_ms"],
                                  "provider_calls": correction["metrics"]["provider_generations"],
                                  "tool_calls": correction["metrics"]["tool_calls_emitted"]}),
                      flush=True)

                implicit_recall = measure_turn(
                    gateway, benchmark, "implicit_recall",
                    f"memory-pair-{stack}-{round_id}-implicit-recall",
                    [{"role": "user", "content": "What kind of fruit do I like?"}],
                )
                rows.append(implicit_recall)
                implicit_marker_present = "pear" in implicit_recall["answer"].casefold() and "mango" not in implicit_recall["answer"].casefold()
                print(json.dumps({"sample": sample + 1, "stack": stack,
                                  "turn": "implicit_recall", "total_ms": implicit_recall["total_ms"],
                                  "provider_calls": implicit_recall["metrics"]["provider_generations"],
                                  "tool_calls": implicit_recall["metrics"]["tool_calls_emitted"],
                                  "expected_marker_present": implicit_marker_present}), flush=True)

                recall_prompt = "What is my favorite fruit?"
                recall = measure_turn(
                    gateway, benchmark, "fresh_recall",
                    f"memory-pair-{stack}-{round_id}-fresh-recall",
                    [{"role": "user", "content": recall_prompt}],
                )
                rows.append(recall)
                recall_marker_present = "pear" in recall["answer"].casefold() and "mango" not in recall["answer"].casefold()
                supplement_results = []
                for memory_case in memory_supplement:
                    result = measure_memory_supplement_case(
                        gateway, benchmark, memory_case, stack, round_id
                    )
                    rows.extend(result["turns"])
                    supplement_results.append({
                        key: value for key, value in result.items() if key != "turns"
                    })
                sample_result["stacks"][stack] = {
                    "turns": rows,
                    "memory_supplement": supplement_results,
                    "fresh_recall_expected_fact": "pear",
                    "fresh_recall_expected_marker_present": recall_marker_present,
                    "fresh_recall_stale_mango_present": "mango" in recall["answer"].casefold(),
                    "implicit_recall_expected_fact": "pear",
                    "implicit_recall_expected_marker_present": implicit_marker_present,
                    "implicit_recall_stale_mango_present": "mango" in implicit_recall["answer"].casefold(),
                    "automatic_recall_expected_fact": "Denver",
                    "automatic_recall_expected_marker_present": automatic_marker_present,
                    "automatic_retained_fact_visible": automatic_fact_visible,
                    "automatic_retention_state_before_recall": automatic_retention_state,
                    "core09_recall_expected_fact": "$3,000 synthetic savings target",
                    "core09_recall_expected_marker_present": core09_marker_present,
                }
                print(json.dumps({"sample": sample + 1, "stack": stack,
                                  "turn": "fresh_recall", "total_ms": recall["total_ms"],
                                  "provider_calls": recall["metrics"]["provider_generations"],
                                  "expected_marker_present": recall_marker_present}), flush=True)
                if stack == "hades":
                    barrier_label = (
                        f"before_plain_sample_{sample + 1}"
                        if order.index(stack) < len(order) - 1
                        else f"before_next_sample_{sample + 1}"
                    )
                    failure_stage = f"hindsight_idle_{barrier_label}"
                    idle = wait_hindsight_idle(
                        hindsight_url, memory_bank, proxy=bridge
                    )
                    sample_result["hindsight_idle_after_hades"] = idle
                    if not idle["idle"]:
                        raise RuntimeError(
                            "Hindsight background operations did not drain after HADES arm"
                        )
                    visibility = {}
                    for memory_case in memory_supplement:
                        review = memory_case["review_check"]
                        visibility[memory_case["id"]] = retained_fact_visible(
                            hindsight_url,
                            review["visibility_bank"],
                            review["visibility_needle"],
                        )
                    sample_result["stacks"]["hades"][
                        "memory_supplement_visibility_after_drain"
                    ] = visibility
                    sample_result["stacks"]["hades"][
                        "core09_fact_visibility_after_drain"
                    ] = {
                        "canonical_bank": retained_fact_visible(
                            hindsight_url, memory_bank, "$3,000"
                        ),
                        "explicit_bank": retained_fact_visible(
                            hindsight_url, memory_bank + "-explicit", "$3,000"
                        ),
                        "explicit_bank_tagged": retained_fact_visible(
                            hindsight_url, memory_bank + "-explicit", "$3,000",
                            required_tag="hades-explicit-memory",
                        ),
                    }
                    sample_result["stacks"]["hades"][
                        "synthetic_recall_candidate_diagnostic"
                    ] = hindsight_recall_candidate_diagnostic(
                        hindsight_url, memory_bank
                    )
                    print(json.dumps({"sample": sample + 1,
                                      "hindsight_idle_after_hades": idle["elapsed_ms"],
                                      "barrier": barrier_label,
                                      "polls": idle["polls"]}), flush=True)
            if not args.automatic_only:
                # Keep the immediate recall above as owner-visible readiness
                # evidence, then test the same exact fact after HADES reports
                # all memory work idle. Run both stacks after that barrier so
                # order and elapsed memory-settle work are visible in context.
                for stack in order:
                    failure_stage = (
                        f"sample_{sample + 1}_{stack}_core09_recall_after_idle"
                    )
                    settled_recall = measure_turn(
                        gateways[stack], benchmark, "core09_recall_after_idle",
                        f"memory-pair-{stack}-{sample + 1:02d}-core09-recall-after-idle",
                        [{"role": "user", "content": OWNER_CORE_09_RECALL}],
                    )
                    sample_result["stacks"][stack]["turns"].append(settled_recall)
                    settled_marker = core09_answer_matches_target(
                        settled_recall.get("answer", "")
                    )
                    sample_result["stacks"][stack][
                        "core09_recall_after_idle_expected_marker_present"
                    ] = settled_marker
                    print(json.dumps({
                        "sample": sample + 1, "stack": stack,
                        "turn": "core09_recall_after_idle",
                        "total_ms": settled_recall["total_ms"],
                        "provider_calls": settled_recall["metrics"]["provider_generations"],
                        "expected_marker_present": settled_marker,
                    }), flush=True)
        by_stack_turn: dict[str, Any] = {}
        supplement_turn_names = []
        for memory_case in (() if args.automatic_only else memory_supplement):
            if memory_case["id"] == "core-55":
                supplement_turn_names.extend(
                    f"supplement_core-55_turn_{index + 1}"
                    for index in range(len(memory_case["turns"]))
                )
            else:
                supplement_turn_names.extend((
                    f"supplement_{memory_case['id']}_seed",
                    f"supplement_{memory_case['id']}_probe",
                ))
        for stack in ("plain", "hades"):
            for turn in (
                "ordinary", "automatic_retain", "automatic_recall", "core09_save",
                "core09_recall", "core09_recall_after_idle", "save", "correction",
                "implicit_recall", "fresh_recall",
                *supplement_turn_names,
            ):
                rows = [
                    item
                    for sample in repetitions
                    for item in sample["stacks"][stack]["turns"]
                    if item["turn"] == turn
                ]
                by_stack_turn[f"{stack}.{turn}"] = {
                    "samples": len(rows),
                    "median_ttft_ms": median(rows, "ttft_ms"),
                    "median_total_ms": median(rows, "total_ms"),
                    "median_provider_generations": median(
                        [row["metrics"] for row in rows], "provider_generations"
                    ),
                    "median_tool_schema_exposures": median(
                        [row["metrics"] for row in rows], "tool_schema_exposures"
                    ),
                    "median_tool_schema_bytes_exposed": median(
                        [row["metrics"] for row in rows], "tool_schema_bytes_exposed"
                    ),
                    "median_tool_calls": median(
                        [row["metrics"] for row in rows], "tool_calls_emitted"
                    ),
                    "median_prompt_tokens": median(
                        [row["metrics"] for row in rows], "prompt_tokens"
                    ),
                    "median_request_bytes": median(
                        [row["metrics"] for row in rows], "request_bytes"
                    ),
                    "fresh_recalls_with_expected_marker": (
                        sum(s["stacks"][stack]["fresh_recall_expected_marker_present"] for s in repetitions)
                        if turn == "fresh_recall" and not args.automatic_only else None
                    ),
                    "fresh_recalls_with_stale_mango": (
                        sum(s["stacks"][stack]["fresh_recall_stale_mango_present"]
                            for s in repetitions)
                        if turn == "fresh_recall" and not args.automatic_only else None
                    ),
                    "implicit_recalls_with_expected_marker": (
                        sum(s["stacks"][stack]["implicit_recall_expected_marker_present"] for s in repetitions)
                        if turn == "implicit_recall" and not args.automatic_only else None
                    ),
                    "implicit_recalls_with_stale_mango": (
                        sum(s["stacks"][stack]["implicit_recall_stale_mango_present"]
                            for s in repetitions)
                        if turn == "implicit_recall" and not args.automatic_only else None
                    ),
                    "automatic_recalls_with_expected_marker": (
                        sum(s["stacks"][stack]["automatic_recall_expected_marker_present"] for s in repetitions)
                        if turn == "automatic_recall" else None
                    ),
                    "owner_corpus_recalls_with_expected_marker": (
                        sum(s["stacks"][stack][
                            "core09_recall_after_idle_expected_marker_present"
                            if turn == "core09_recall_after_idle"
                            else "core09_recall_expected_marker_present"
                        ] for s in repetitions)
                        if turn in {"core09_recall", "core09_recall_after_idle"}
                        and not args.automatic_only else None
                    ),
                }

        supplement_summary = {}
        for memory_case in (() if args.automatic_only else memory_supplement):
            case_id = memory_case["id"]
            supplement_summary[case_id] = {}
            for stack in ("plain", "hades"):
                case_results = [
                    result
                    for sample in repetitions
                    for result in sample["stacks"][stack].get("memory_supplement", [])
                    if result["case_id"] == case_id
                ]
                final_turn = (
                    f"supplement_core-55_turn_{len(memory_case['turns'])}"
                    if case_id == "core-55" else f"supplement_{case_id}_probe"
                )
                final_rows = [
                    row
                    for sample in repetitions
                    for row in sample["stacks"][stack]["turns"]
                    if row["turn"] == final_turn
                ]
                supplement_summary[case_id][stack] = {
                    "samples": len(case_results),
                    "answers_with_expected_marker": sum(
                        bool(result["answer_contains_expected_marker"])
                        for result in case_results
                    ),
                    "median_final_turn_ms": median(final_rows, "total_ms"),
                }
                if stack == "hades" and not args.automatic_only:
                    supplement_summary[case_id][stack]["fact_visible_after_drain"] = sum(
                        bool(sample["stacks"][stack][
                            "memory_supplement_visibility_after_drain"
                        ].get(case_id))
                        for sample in repetitions
                        if "memory_supplement_visibility_after_drain" in sample["stacks"][stack]
                    )

        artifact = {
            "schema_version": 1,
            "date": time.strftime("%Y-%m-%d"),
            "title": (
                "Focused ordinary chat and synthetic automatic-memory recall comparison"
                if args.automatic_only else
                "Counterbalanced owner-core-09 savings recall and synthetic memory correction comparison"
            ),
            "classification": "synthetic local comparative benchmark; no owner preference or release qualification",
            "source_revision": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                text=True, capture_output=True, timeout=10,
            ).stdout.strip(),
            "method": {
                "samples": args.samples,
                "hermes_version": hermes_version,
                "counterbalance": f"One paired pass; {args.first_stack or 'plain'} runs first. Repeated comparisons require separate invocations so each gets an empty disposable Hindsight volume.",
                "sequence": (
                    ["owner core-01 greeting", "synthetic automatic personal-fact retain/recall"]
                    if args.automatic_only else
                    ["owner core-01 greeting", "synthetic automatic personal-fact retain/recall", "owner core-09 explicit synthetic save and natural recall wording", "core-09 immediate and post-drain recall", "synthetic favorite-fruit save/correction", "fresh-session implicit recall", "fresh-session explicit recall"]
                ),
                "owner_corpus_case_map": {
                    "core-01": OWNER_CORE_01_GREETING,
                    **({} if args.automatic_only else {
                        "core-09": {"save": "Remember that my savings target is $3,000.", "recall": OWNER_CORE_09_RECALL},
                    }),
                },
                "owner_memory_supplement": {} if args.automatic_only else {
                    row["id"]: {
                        "turns": len(row["turns"]),
                        "review_check": row["review_check"],
                    }
                    for row in memory_supplement
                },
                "profile_continuity": (
                    "Persistent gateway/home and memory bank within each stack; recall uses a new Hermes session ID."
                    if args.automatic_only else
                    "Persistent gateway/home and memory bank within each stack; the same synthetic preference is re-saved and corrected every sample; recall uses a new Hermes session ID."
                ),
                "model": MODEL,
                "ollama_version": version,
                "openai_chat_context_probe_prompt_tokens": context_probe_prompt_tokens,
                "openai_chat_context_probe_minimum_tokens": 5000,
                "openai_chat_context_probe_loaded_context": context_probe_loaded_context,
                "model_digest": model_row.get("digest"),
                "model_quantization": model_row.get("details", {}).get("quantization_level"),
                "ollama_loaded_context_after_stack_warmups": loaded_model.get("context_length") if loaded_model else None,
                "hermes_ollama_context_configured": CONTEXT_LENGTH,
                "measured_context_verification": "The same Ollama OpenAI-compatible chat endpoint must accept a >5k-token probe without a per-request context override, and /api/ps must report the configured context immediately after that probe. Every Hermes provider generation must request the configured context. Runtime /api/ps is sampled at each provider response boundary and retained per generation; when HADES background inference has already evicted the interactive model, the boundary records non-residency. The measured HADES run is then interpreted with the exact-route startup probe and global OLLAMA_CONTEXT_LENGTH setting, while plain turns must remain resident at the target context.",
                "hindsight_image": args.hindsight_image,
                "hindsight_model": args.hindsight_model,
                "hindsight_model_digest": hindsight_model_row.get("digest"),
                "hindsight_model_quantization": hindsight_model_row.get("details", {}).get("quantization_level"),
                "hindsight_llm_max_concurrent": args.hindsight_llm_max_concurrent,
                "retain_mode": args.hindsight_retain_mode,
                "observations_enabled": not args.hindsight_disable_observations,
                "assistant_response_storage": (
                    "Assistant response text is evaluated only in memory and is never printed or persisted; aggregate marker metrics are retained."
                    if args.automatic_only else
                    "Assistant response text is evaluated only in memory and is never printed or persisted; aggregate marker metrics are retained."
                ),
                "reasoning": "disabled per request",
                "max_output_tokens": 512,
                "user_generation_overrides": {
                    "temperature": 0.1,
                    "top_p": 0.95,
                    "scope": "all Hermes provider generations in both benchmark arms",
                },
                "effective_sampler_capture": "Provider traces persist the actual temperature/top_p fields sent to the common local Ollama runtime; the artifact can be checked for equality.",
                "plain_toolset": ["memory"],
                "hades_toolset": [],
                "hades_scope": args.hades_scope,
                "hades_recall_types": args.hades_recall_types,
                "hades_recall_budget": args.hades_recall_budget,
                "hades_prefer_observations": args.hades_prefer_observations,
                "recall_diagnostics_captured": args.capture_recall_diagnostics,
                "recall_timing_diagnostics_captured": args.capture_recall_diagnostics,
                "post_idle_recall_type_diagnostic": (
                    "Not run in automatic-only mode."
                    if args.automatic_only else
                    "After HADES background work drains, make eight direct synthetic Hindsight recalls across observation-only, raw-only, all-types, and all-types with prefer_observations for Denver and place-preference queries. Store only result counts, type counts, expected-marker first rank, and elapsed time; never result text or IDs."
                ),
                "hades_memory_bank": memory_bank,
                "hades_memory_path": ("bundled Hermes Hindsight provider" if (hermes_root / "source/plugins/memory/hindsight").is_dir() else "separately installed upstream Hindsight provider") + "; local_external mode; loopback disposable service; authenticated subject bank selected by HADES; explicit facts use a chunks bank with local embeddings",
        "hindsight_network_mode": args.hindsight_network,
                "hindsight_inference_accounting": "The local proxy records Hindsight-to-Ollama API route, safe scalar controls, byte counts, response timing, and Ollama usage counters; request/response bodies, prompts, facts, and credentials are never persisted. These background calls are additional HADES inference and are reported separately from user-facing Hermes provider generations.",
            "memory_score_diagnostics": "For HADES only, opt-in diagnostic logs retain up to eight result ranks, canonical memory types, and numeric retrieval scores; query text, facts, IDs, tags, entities, and subjects are excluded.",
                "hindsight_residency_capture": "After forwarding each Hindsight request response, the proxy samples local Ollama /api/ps and records only the matching model's residency status, context length, total size, and VRAM size. A not_resident or unavailable observation is retained explicitly; the probe occurs after the measured response and is excluded from its elapsed time.",
                "interactive_residency_capture": "The runner samples /api/ps after each automatic retain and immediately before the next read, storing only role-based residency, context length, and VRAM bytes for the interactive and Hindsight models; no model names or response data are retained in this probe.",
                "arm_isolation": "Before measured arms, the runner drains Hindsight warmup work. Before each stack arm, it unloads the extractor, warms and verifies the interactive model at the configured context, and records normalization timings outside measured turns. After every HADES arm, it polls pending/processing operations across every bank in the disposable Hindsight database until two consecutive idle observations; unavailable status or timeout aborts the run. This prevents background work from carrying across counterbalanced arms.",
                "warmups": {
                    key: (
                        value if key == "hindsight_idle" else {
                            "status": value["status"],
                            "provider_generations": value["metrics"]["provider_generations"],
                        }
                    )
                    for key, value in warmups.items()
                },
                "data": "The owner core-09 recall wording uses only a synthetic savings target ($3,000). Automatic cross-session Denver fact and favorite-fruit save/correction remain synthetic controls. Temporary homes, container and database volume.",
        "privacy": (
            "Ollama endpoint restricted to loopback; Ollama server launched with OLLAMA_NO_CLOUD=1. "
            + ("Hindsight used rootless Docker host networking, with API/control-plane listeners and accounting proxy bound only to 127.0.0.1 on ephemeral ports; synthetic benchmark data only. "
               if args.hindsight_network == "host" else
               "Hindsight used rootless Docker bridge networking; accounting proxy bound only to the bridge gateway.")
        ),
            },
            "summary_by_stack_and_turn": by_stack_turn,
            "memory_supplement_summary": supplement_summary,
            "hades_recall_diagnostics": (
                read_safe_recall_diagnostics(gateways["hades"]["log_path"])[0]
                if args.capture_recall_diagnostics else []
            ),
            "hades_recall_timing_diagnostics": (
                read_safe_recall_timings(gateways["hades"]["log_path"])[0]
                if args.capture_recall_diagnostics else []
            ),
            "hindsight_ollama_calls": bridge.snapshot() if bridge is not None else [],
            "repetitions": safe_repetitions(repetitions),
            "preference_bucket": "UNASSIGNED; no owner dogfood",
            "semantic_correctness_review": "UNSCORED: expected-marker presence is descriptive only and is not semantic correctness; human review is required.",
            "limitations": [
                "The model digest is staged local Qwen; this does not prove equality with production model weights.",
                "Gateway stack order is balanced, but each task sequence is serialized and no human quality ratings were collected.",
                "The owner core-09 recall is measured once immediately after save and again for both stacks after HADES background memory work drains; readiness delay and settled recall are separate outcomes.",
                "A fresh recall is a new Hermes session in the same private profile/subject. This does not qualify Open WebUI authentication, household UI isolation, or populated production data migration.",
                "Provider metrics are aggregate structural/timing data. Naturalness and whether Scotty prefers either workflow require direct owner review.",
            ],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({"result": "written", "output": str(args.output),
                          "summary": by_stack_turn}, ensure_ascii=False), flush=True)
        return 0
    except Exception as exc:
        revision = "unknown"
        try:
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                text=True, capture_output=True, timeout=10,
            ).stdout.strip()
        except Exception:
            pass
        safe_failure_detail = None
        if isinstance(exc, RuntimeError):
            message = str(exc)
            if re.fullmatch(
                    r"Hindsight (?:pending|processing) operation status unavailable "
                    r"\([A-Za-z_][A-Za-z0-9_]*(?:; status=[1-5][0-9]{2})?\)",
                    message):
                safe_failure_detail = message
        partial = write_incomplete_artifact(
            args.output, source_revision=revision, failure_stage=failure_stage,
            error_type=type(exc).__name__, repetitions=repetitions,
            hindsight_calls=bridge.snapshot() if bridge is not None else [],
            safe_failure_detail=safe_failure_detail,
        )
        print(json.dumps({"result": "incomplete", "output": str(partial),
                          "failure_stage": failure_stage,
                          "error_type": type(exc).__name__}), flush=True)
        raise
    finally:
        for gateway in gateways.values():
            gateway["process"].terminate()
            try:
                gateway["process"].wait(timeout=10)
            except subprocess.TimeoutExpired:
                gateway["process"].kill()
                gateway["process"].wait()
            gateway["proxy"].shutdown()
            gateway["proxy"].server_close()
            gateway["proxy_thread"].join(timeout=2)
            gateway["log"].close()
        if bridge is not None:
            bridge.shutdown()
            bridge.server_close()
        if bridge_thread is not None:
            bridge_thread.join(timeout=2)
        subprocess.run(["docker", "rm", "-f", run_id],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["docker", "volume", "rm", volume],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.environ.get("HADES_BENCHMARK_KEEP_TEMP") == "1":
            print(json.dumps({"temporary_diagnostics_kept": str(temp)}), flush=True)
        else:
            shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
