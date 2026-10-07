#!/usr/bin/env python3
"""Exercise pinned Hindsight retain and fresh recall against a local mock model."""
from __future__ import annotations

import http.server
import json
import math
import os
import statistics
import subprocess
import threading
import time
import urllib.request
import uuid
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
MODEL = "synthetic-hindsight-route-model"
FACT = "The synthetic user prefers violet comet-42 markers."
FACT_RESPONSE = json.dumps({
    "facts": [{
        "what": FACT,
        "when": "N/A",
        "where": "N/A",
        "who": "user",
        "why": "Explicit synthetic acceptance fact.",
        "fact_type": "world",
        "entities": ["user", "violet comet-42 markers"],
    }],
})


def run(*args: str, capture: bool = False) -> str:
    result = subprocess.run(
        args,
        cwd=REPO,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
    )
    return result.stdout.strip() if capture else ""


def image_pin() -> str:
    for line in (REPO / "config/versions.env").read_text().splitlines():
        if line.startswith("HADES_HINDSIGHT_IMAGE="):
            return line.partition("=")[2].strip().strip("\"'")
    raise RuntimeError("HADES_HINDSIGHT_IMAGE is missing from config/versions.env")


requests_seen: list[dict[str, str]] = []


class MockModel(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
        requests_seen.append({"path": self.path, "model": str(body.get("model", ""))})
        if self.path.endswith("/api/chat"):
            response = {
                "model": MODEL,
                "message": {"role": "assistant", "content": FACT_RESPONSE},
                "done": True,
            }
        else:
            response = {
                "id": "synthetic-route-test",
                "object": "chat.completion",
                "created": 1,
                "model": MODEL,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": FACT_RESPONSE},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
        payload = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args: object) -> None:
        return


def wait_healthy(url: str, seconds: int = 90) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2).read()
            return True
        except Exception:
            time.sleep(1)
    return False


def exercise_hades_route(api: str, bank: str, subject: str) -> None:
    """Run the actual HADES route in an explicitly supplied Hermes runtime."""
    hermes_python = os.environ.get("HADES_HERMES_PYTHON", "").strip()
    if not hermes_python:
        print("SKIP actual HADES route integration: set HADES_HERMES_PYTHON to Hermes 0.21.2 Python")
        return
    if not Path(hermes_python).is_file():
        raise RuntimeError("HADES_HERMES_PYTHON does not name a file")

    route_env = os.environ.copy()
    route_env["HADES_HINDSIGHT_URL"] = api
    overlay_override = route_env.get("HADES_HINDSIGHT_OVERLAY_SOURCE", "").strip()
    overlay_dir = REPO / "hermes"
    if overlay_override:
        overlay_path = Path(overlay_override).resolve()
        if overlay_path.name != "sitecustomize.py" or not overlay_path.is_file():
            raise RuntimeError("HADES_HINDSIGHT_OVERLAY_SOURCE must name a sitecustomize.py file")
        overlay_dir = overlay_path.parent
    route_env["PYTHONPATH"] = os.pathsep.join(filter(None, [
        str(overlay_dir),
        str(REPO),
        route_env.get("PYTHONPATH", ""),
    ]))
    code = (
        "import sitecustomize as hades; import sys, json; calls=[]; "
        "original=hades._HindsightClient.recall; "
        "exec('def observed_recall(self, *args, **kwargs):\\n "
        "calls.append(kwargs)\\n return original(self, *args, **kwargs)'); "
        "hades._HindsightClient.recall=observed_recall; "
        "answer=hades._hades_direct_memory_response(sys.argv[1], sys.argv[2], 'household'); "
        "print(json.dumps({'answer': answer, 'semantic_calls': len(calls)}))"
    )
    route_times_ms: dict[str, float] = {}
    semantic_calls_by_prompt: dict[str, int] = {}

    def call(prompt: str, actor: str = subject) -> str:
        started = time.monotonic()
        result = subprocess.run(
            [hermes_python, "-c", code, prompt, actor],
            cwd=REPO,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=route_env,
            timeout=90,
        )
        route_times_ms[prompt] = (time.monotonic() - started) * 1000
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        semantic_calls_by_prompt[prompt] = int(payload["semantic_calls"])
        return str(payload["answer"])

    first = call("Remember that I like violet comet-42 markers.")
    if "I'll remember that privately" not in first:
        raise RuntimeError("actual HADES retain route did not confirm the synthetic private retain")
    second = call("What do you remember about violet comet-42?")
    if "I remember:" not in second or "violet comet-42" not in second.casefold():
        raise RuntimeError("actual HADES recall route did not return the synthetic fact in a fresh process")

    for fact in ("My favorite fruit is mango.", "My favorite fruit is pear."):
        retained = call(f"Remember that {fact}")
        if "I'll remember that privately" not in retained:
            raise RuntimeError("actual HADES correction fixture was not retained")
    fixture_rows = json.load(urllib.request.urlopen(
        f"{api}/v1/default/banks/{bank}/memories/list"
        "?tags=hades-explicit-memory&tags_match=any&state=valid&limit=100",
        timeout=15,
    )).get("items", [])
    corrected = call("What is my favrite frut?")
    if "pear" not in corrected.casefold() or "mango" in corrected.casefold():
        evidence = [
            {key: row.get(key) for key in ("text", "entities", "updated_at", "mentioned_at", "created_at", "state")}
            for row in fixture_rows if isinstance(row, dict)
        ]
        raise RuntimeError(
            f"typo-tolerant fresh correction recall returned unexpected text: {corrected!r}; "
            f"synthetic list evidence={evidence!r}"
        )

    # This is intentionally a paraphrase without a lexical anchor in the
    # retained fact. Prove it reaches Hindsight semantic recall instead of
    # passing only because the direct recent-memory matcher found "fruit".
    paraphrase_prompt = "What do you remember about the thing I was drawn to?"
    paraphrase = call(paraphrase_prompt)
    if "violet comet-42" not in paraphrase.casefold():
        raise RuntimeError(f"paraphrased recall returned unexpected text: {paraphrase!r}")
    if semantic_calls_by_prompt[paraphrase_prompt] == 0:
        raise RuntimeError("lexically unmatched paraphrase did not reach the Hindsight recall fallback")

    beta_bank = f"hades-user-synthetic-beta"
    create_beta_bank = urllib.request.Request(
        f"{api}/v1/default/banks/{beta_bank}",
        data=json.dumps({"name": "Synthetic HADES route isolation test"}).encode(),
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    urllib.request.urlopen(create_beta_bank, timeout=10).read()
    isolated = call("What is my favrite frut?", "synthetic-beta")
    if "pear" in isolated.casefold() or "mango" in isolated.casefold():
        raise RuntimeError("synthetic Beta received Alpha's private memory")
    print(
        "PASS actual HADES explicit retain, newest correction after a two-word typo, "
        f"paraphrase recall, and Alpha/Beta isolation on {bank}"
    )
    print(
        "Observed synthetic local explicit-memory route latency (includes fresh Python startup): "
        f"direct match {route_times_ms['What do you remember about violet comet-42?']:.1f} ms; "
        f"typo correction {route_times_ms['What is my favrite frut?']:.1f} ms; "
        f"semantic paraphrase fallback {route_times_ms[paraphrase_prompt]:.1f} ms"
    )
    sample_count = int(os.environ.get("HADES_HINDSIGHT_BENCHMARK_SAMPLES", "0") or "0")
    if sample_count:
        if sample_count < 5 or sample_count > 100:
            raise RuntimeError("HADES_HINDSIGHT_BENCHMARK_SAMPLES must be between 5 and 100")
        benchmark_code = r'''
import json, sys, time
import sitecustomize as hades
subject, prompt, count, expected, must_recall = sys.argv[1:]
count = int(count)
calls = []
original = hades._HindsightClient.recall
def observed_recall(self, *args, **kwargs):
    calls.append(True)
    return original(self, *args, **kwargs)
hades._HindsightClient.recall = observed_recall
def invoke():
    start = time.perf_counter_ns()
    answer = hades._hades_direct_memory_response(prompt, subject, "household")
    elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
    return elapsed_ms, str(answer or "")
warmup = [invoke()[1] for _ in range(2)]
warmup_calls = len(calls)
samples = []
answers = []
recall_counts = []
for _ in range(count):
    before = len(calls)
    elapsed, answer = invoke()
    samples.append(elapsed)
    answers.append(answer)
    recall_counts.append(len(calls) - before)
print(json.dumps({
    "warmup_answers": warmup,
    "warmup_semantic_calls": warmup_calls,
    "samples_ms": samples,
    "answers": answers,
    "semantic_calls_per_sample": recall_counts,
    "must_recall": must_recall == "true",
    "expected": expected,
}))
'''

        def measure(prompt: str, expected: str, must_recall: bool) -> dict[str, object]:
            process_started = time.monotonic()
            result = subprocess.run(
                [
                    hermes_python, "-c", benchmark_code,
                    subject, prompt, str(sample_count), expected,
                    "true" if must_recall else "false",
                ],
                cwd=REPO,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=route_env,
                timeout=180,
            )
            process_startup_inclusive_ms = (time.monotonic() - process_started) * 1000
            output = json.loads(result.stdout.strip().splitlines()[-1])
            samples = [float(value) for value in output["samples_ms"]]
            if len(samples) != sample_count:
                raise RuntimeError("Hindsight benchmark returned an incomplete sample set")
            answers = [str(value).casefold() for value in output["answers"]]
            if any(expected.casefold() not in answer for answer in answers):
                raise RuntimeError("Hindsight benchmark returned an unexpected synthetic answer")
            recall_counts = [int(value) for value in output["semantic_calls_per_sample"]]
            if must_recall and any(value == 0 for value in recall_counts):
                raise RuntimeError("Hindsight semantic-fallback benchmark skipped recall on a sample")
            if not must_recall and any(value != 0 for value in recall_counts):
                raise RuntimeError("direct-memory benchmark unexpectedly used semantic recall")
            ordered = sorted(samples)
            p95 = ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]
            return {
                "sample_count": len(samples),
                "warmup_count": len(output["warmup_answers"]),
                "route_p50_ms": statistics.median(samples),
                "route_p95_ms_nearest_rank": p95,
                "route_max_ms": max(samples),
                "process_wall_ms_including_startup_and_samples": process_startup_inclusive_ms,
                "semantic_recall_calls_per_sample": sorted(set(recall_counts)),
                "scope": "synthetic local Hindsight only; route time excludes Python startup",
            }

        benchmark = {
            "fresh_retain_to_new_process_recall": {
                "retain_route_ms_including_python_startup": route_times_ms[
                    "Remember that I like violet comet-42 markers."
                ],
                "new_process_natural_recall_ms_including_python_startup": route_times_ms[
                    "What do you remember about violet comet-42?"
                ],
                "combined_ms": (
                    route_times_ms["Remember that I like violet comet-42 markers."]
                    + route_times_ms["What do you remember about violet comet-42?"]
                ),
                "scope": "one synthetic retain followed by natural recall in a new Hermes Python process",
            },
            "direct_matching_recall": measure(
                "What is my favorite fruit?", "pear", False,
            ),
            "Hindsight_recall_fallback": measure(
                paraphrase_prompt, "violet comet-42", True,
            ),
        }
        candidate_budgets = {
            "direct_route_p95_ms": 100,
            "hindsight_fallback_p95_ms": 1000,
            "retain_to_fresh_process_recall_ms": 4000,
        }
        benchmark["candidate_budgets_ms"] = candidate_budgets
        if benchmark["direct_matching_recall"]["route_p95_ms_nearest_rank"] > candidate_budgets["direct_route_p95_ms"]:
            raise RuntimeError("synthetic direct-memory route exceeded its 100 ms p95 candidate budget")
        if benchmark["Hindsight_recall_fallback"]["route_p95_ms_nearest_rank"] > candidate_budgets["hindsight_fallback_p95_ms"]:
            raise RuntimeError("synthetic Hindsight fallback exceeded its 1,000 ms p95 candidate budget")
        if benchmark["fresh_retain_to_new_process_recall"]["combined_ms"] > candidate_budgets["retain_to_fresh_process_recall_ms"]:
            raise RuntimeError("synthetic retain-to-fresh-process recall exceeded its 4,000 ms candidate budget")
        report_path = os.environ.get("HADES_HINDSIGHT_BENCHMARK_REPORT", "").strip()
        if report_path:
            output_path = Path(report_path)
            output_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            output_path.write_text(json.dumps(benchmark, indent=2) + "\n", encoding="utf-8")
            output_path.chmod(0o600)
        print("Repeated synthetic Hindsight route benchmark: " + json.dumps(benchmark, sort_keys=True))


def main() -> None:
    image = image_pin()
    run("docker", "image", "inspect", image)
    name = "hades-hindsight-route-" + uuid.uuid4().hex[:8]
    volume = "hades-hindsight-route-" + uuid.uuid4().hex[:8]
    mock = http.server.ThreadingHTTPServer(("0.0.0.0", 0), MockModel)
    mock_port = mock.server_address[1]
    threading.Thread(target=mock.serve_forever, daemon=True).start()
    try:
        run("docker", "volume", "create", volume)
        run(
            "docker", "run", "-d", "--name", name,
            "--add-host=host.docker.internal:host-gateway",
            "-p", "127.0.0.1::8888",
            "-v", f"{volume}:/home/hindsight/.pg0",
            "-e", "HINDSIGHT_API_HOST=0.0.0.0",
            "-e", "HINDSIGHT_API_PORT=8888",
            "-e", "HINDSIGHT_API_ENABLE_OBSERVATIONS=true",
            "-e", f"HINDSIGHT_API_WORKER_ID={name}",
            "-e", "HINDSIGHT_API_LLM_PROVIDER=ollama",
            "-e", f"HINDSIGHT_API_LLM_MODEL={MODEL}",
            "-e", f"HINDSIGHT_API_LLM_BASE_URL=http://host.docker.internal:{mock_port}/v1",
            "-e", "HINDSIGHT_API_LLM_API_KEY=synthetic",
            image,
        )
        inspection = json.loads(run("docker", "inspect", name, capture=True))[0]
        api_port = inspection["NetworkSettings"]["Ports"]["8888/tcp"][0]["HostPort"]
        api = f"http://127.0.0.1:{api_port}"
        if not wait_healthy(api + "/health"):
            raise RuntimeError("disposable pinned Hindsight API did not become healthy")

        bank = "route-test-" + uuid.uuid4().hex[:8]
        create = urllib.request.Request(
            f"{api}/v1/default/banks/{bank}",
            data=json.dumps({"name": "Synthetic fresh recall test"}).encode(),
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        urllib.request.urlopen(create, timeout=10).read()
        retain = urllib.request.Request(
            f"{api}/v1/default/banks/{bank}/memories",
            data=json.dumps({
                "items": [{
                    "content": FACT,
                    "context": "synthetic fresh recall diagnostic",
                    "tags": ["hades-explicit-memory"],
                    "entities": [
                        {"text": "user", "type": "person"},
                        {"text": "violet comet-42 markers", "type": "concept"},
                    ],
                }],
                "async": False,
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(retain, timeout=60).read()

        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not requests_seen:
            time.sleep(0.2)
        if not requests_seen:
            raise RuntimeError("synthetic retain did not reach the configured mock extraction route")
        if any(item["model"] != MODEL for item in requests_seen):
            raise RuntimeError("Hindsight did not send the configured extraction model")
        if any(not item["path"].endswith(("/api/chat", "/v1/chat/completions")) for item in requests_seen):
            raise RuntimeError("Hindsight sent an unexpected path to the configured extraction route")
        listed_url = (
            f"{api}/v1/default/banks/{bank}/memories/list"
            "?tags=hades-explicit-memory&tags_match=any&state=valid&limit=100"
        )
        listed = json.load(urllib.request.urlopen(listed_url, timeout=15))
        rows = listed.get("items", [])
        if not any(
            isinstance(item, dict)
            and "violet comet-42" in str(item.get("text", "")).casefold()
            and "hades-explicit-memory" in item.get("tags", [])
            for item in rows
        ):
            raise RuntimeError("synchronous synthetic retain did not create a valid tagged canonical memory")

        recall = urllib.request.Request(
            f"{api}/v1/default/banks/{bank}/memories/recall",
            data=json.dumps({
                "query": "What markers does the synthetic user prefer? violet comet-42",
                "budget": "low",
                "max_tokens": 1200,
                "tags": ["hades-explicit-memory"],
                "tags_match": "any",
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        recalled = json.load(urllib.request.urlopen(recall, timeout=60))
        results = recalled.get("results", [])
        if not any(
            isinstance(item, dict)
            and "violet comet-42" in str(item.get("text", "")).casefold()
            for item in results
        ):
            raise RuntimeError("fresh synthetic recall did not return the newly retained fact")

        hermes_python = os.environ.get("HADES_HERMES_PYTHON", "").strip()
        if hermes_python:
            route_bank = "hades-user-synthetic-alpha"
            create_route_bank = urllib.request.Request(
                f"{api}/v1/default/banks/{route_bank}",
                data=json.dumps({"name": "Synthetic HADES route test"}).encode(),
                headers={"Content-Type": "application/json"},
                method="PUT",
            )
            urllib.request.urlopen(create_route_bank, timeout=10).read()
            exercise_hades_route(api, route_bank, "synthetic-alpha")
        else:
            exercise_hades_route(api, "hades-user-synthetic-alpha", "synthetic-alpha")

        print("PASS pinned Hindsight extracted one synthetic tagged fact through the configured local endpoint/model")
        print("PASS pinned Hindsight valid-memory listing contains the settled synthetic fact")
        print("PASS a fresh recall request returns the newly retained synthetic fact")
        print("Observed request paths: " + ", ".join(sorted({item["path"] for item in requests_seen})))
    finally:
        mock.shutdown()
        mock.server_close()
        subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["docker", "volume", "rm", volume], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
