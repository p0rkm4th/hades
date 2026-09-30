#!/usr/bin/env python3
"""Contract test for text and function-call SSE from the synthetic model."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


repo = Path(__file__).resolve().parents[1]
backend = repo / "scripts/synthetic-openai-backend.py"
with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]

process = subprocess.Popen(
    [sys.executable, str(backend), "127.0.0.1", str(port)],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
base = f"http://127.0.0.1:{port}/v1"
root = f"http://127.0.0.1:{port}"


def request(path: str, payload: dict | None = None) -> tuple[int, bytes]:
    headers = {"Content-Type": "application/json"}
    encoded = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"{base}{path}", data=encoded, headers=headers)
    with urllib.request.urlopen(req, timeout=8) as response:
        return response.status, response.read()


def completion_messages(messages: list[dict], tools: list[dict] | None = None) -> list[dict]:
    payload = {
        "model": "synthetic-reconstruction-model",
        "messages": messages,
        "tools": tools or [],
        "stream": True,
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    chunks = []
    with urllib.request.urlopen(req, timeout=8) as response:
        assert response.status == 200
        saw_done = False
        while line := response.readline():
            line = line.decode().strip()
            if line == "data: [DONE]":
                saw_done = True
                break
            if line.startswith("data: "):
                chunks.append(json.loads(line[6:]))
    assert saw_done
    return chunks


def completion(prompt: str, tools: list[dict] | None = None) -> list[dict]:
    return completion_messages([{"role": "user", "content": prompt}], tools)


def function_tool(name: str) -> dict:
    return {"type": "function", "function": {
        "name": name, "parameters": {"type": "object", "properties": {}},
    }}


try:
    for _ in range(50):
        if process.poll() is not None:
            raise AssertionError("synthetic model exited before becoming ready")
        try:
            status, _ = request("/models")
            if status == 200:
                break
        except OSError:
            time.sleep(0.1)
    else:
        raise AssertionError("synthetic model did not become ready")

    text_chunks = completion("Say hello")
    text_deltas = [row["choices"][0]["delta"] for row in text_chunks]
    assert any("Synthetic application response: Say hello" in row.get("content", "") for row in text_deltas)
    assert text_chunks[-1]["choices"][0]["finish_reason"] == "stop"

    grocy_read_tool = function_tool("mcp__grocy__stock_overview_tool")
    tool_chunks = completion("What is in our shared pantry?", [grocy_read_tool])
    tool_calls = [
        call
        for row in tool_chunks
        for call in row["choices"][0]["delta"].get("tool_calls", [])
    ]
    assert len(tool_calls) == 1
    assert tool_calls[0]["function"]["name"] == "mcp__grocy__stock_overview_tool"
    assert json.loads(tool_calls[0]["function"]["arguments"]) == {}
    assert tool_chunks[-1]["choices"][0]["finish_reason"] == "tool_calls"

    pantry_result = completion_messages([
        {"role": "user", "content": "What is in the pantry right now?"},
        {"role": "assistant", "tool_calls": [
            {"id": "stock-1", "type": "function", "function": {
                "name": "mcp__grocy__stock_overview_tool", "arguments": "{}",
            }},
        ]},
        {"role": "tool", "tool_call_id": "stock-1", "content": "No stock found."},
    ], [grocy_read_tool])
    pantry_text = "".join(
        row["choices"][0]["delta"].get("content", "") for row in pantry_result
    )
    assert "Grocy's current stock check found no items in the pantry" in pantry_text
    assert "didn't change anything" in pantry_text

    add_tool = function_tool("mcp__grocy__shopping_list_add_tool")
    add_chunks = completion("Add one HADES Synthetic Milk to the shared shopping list.", [add_tool])
    add_calls = [
        call for row in add_chunks
        for call in row["choices"][0]["delta"].get("tool_calls", [])
    ]
    assert len(add_calls) == 1
    assert add_calls[0]["function"]["name"] == "mcp__grocy__shopping_list_add_tool"
    assert json.loads(add_calls[0]["function"]["arguments"]) == {
        "product": "HADES Synthetic Milk", "amount": 1,
    }
    canonical_add_result = completion_messages([
        {"role": "user", "content": "Add one HADES Synthetic Milk to the shared shopping list."},
        {"role": "assistant", "tool_calls": add_calls},
        {"role": "tool", "tool_call_id": "add-1", "content": "canonical record: HADES Synthetic Milk x 1"},
    ], [add_tool])
    add_text = "".join(
        row["choices"][0]["delta"].get("content", "") for row in canonical_add_result
    )
    assert "Grocy returned this result" in add_text
    assert "canonical record: HADES Synthetic Milk x 1" in add_text

    ollama_request = urllib.request.Request(
        f"{root}/api/chat",
        data=json.dumps({
            "model": "synthetic-reconstruction-model",
            "messages": [{"role": "user", "content": "Synthetic extraction request"}],
            "stream": False,
        }).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(ollama_request, timeout=8) as response:
        extraction = json.load(response)
    facts = json.loads(extraction["message"]["content"])["facts"]
    assert facts and "violet comet-42" in facts[0]["what"]
    print("PASS synthetic OpenAI SSE text/tool streams and Hindsight Ollama extraction route")
finally:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
