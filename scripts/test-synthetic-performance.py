#!/usr/bin/env python3
"""Measure bounded daily-driver workflows without real integrations."""

import json
import os
import time
import urllib.request
import urllib.error

BASE_URL = os.environ.get("HADES_OLLAMA_URL", "http://127.0.0.1:11434/v1").rstrip("/")
MODEL = os.environ.get("HADES_OLLAMA_MODEL", "qwen3:8b")
MAX_TOKENS = int(os.environ.get("HADES_PERF_MAX_TOKENS", "400"))
TOOLS = [
    {"type": "function", "function": {"name": "web_search", "description": "Search current external information.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "hindsight_recall", "description": "Recall private personal context for the current user only; never use it as live system state or authority.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "mcp_grocy_stock_overview_tool", "description": "Read canonical shared household pantry stock. This is read-only.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "recipe_set_servings", "description": "Preview a recipe serving change; never apply without confirmation.", "parameters": {"type": "object", "properties": {"recipe": {"type": "string"}, "servings": {"type": "integer"}}, "required": ["recipe", "servings"]}}},
    {"type": "function", "function": {"name": "agent_zero_delegate", "description": "Delegate a bounded synthetic read-only operator task; never execute or authorize a real action.", "parameters": {"type": "object", "properties": {"task": {"type": "string"}}, "required": ["task"]}}},
]


def model_call(messages):
    payload = {"model": MODEL, "messages": messages, "tools": TOOLS, "tool_choice": "auto", "stream": False, "max_tokens": MAX_TOKENS, "temperature": 0}
    request = urllib.request.Request(f"{BASE_URL}/chat/completions", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            choice = json.load(response)["choices"][0]
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(
            "HOST-SENSITIVE: synthetic performance capture needs an Ollama-compatible "
            f"model endpoint at {BASE_URL}; set HADES_OLLAMA_URL to an approved "
            "reachable gateway (or start the disposable model lane)"
        ) from exc
    return choice, (time.perf_counter() - started) * 1000


def synthetic_tool(name, arguments):
    started = time.perf_counter()
    if name == "web_search":
        result = {"title": "Synthetic mushroom-free pasta", "snippet": "A pasta recipe using tomatoes and basil."}
    elif name == "recipe_set_servings":
        result = {"outcome": "PREVIEW", "recipe": arguments.get("recipe"), "servings": arguments.get("servings")}
    elif name == "hindsight_recall":
        result = {"memory_scope": "private", "fact": "Beta dislikes mushrooms (synthetic)"}
    elif name == "mcp_grocy_stock_overview_tool":
        result = {"authority": "grocy", "stock": [{"item": "tomatoes", "quantity": 2}, {"item": "basil", "quantity": 1}]}
    elif name == "agent_zero_delegate":
        result = {"outcome": "SYNTHETIC_READ_ONLY", "task": arguments.get("task"), "authorized": False}
    else:
        raise AssertionError(f"unexpected tool: {name}")
    return result, (time.perf_counter() - started) * 1000


def run(label, prompt, expected=None):
    messages = [{"role": "system", "content": "Use only the named tools when appropriate. Hindsight is private personal context; Grocy is canonical shared pantry state; web is current external truth. All tools are synthetic. Never make a real write or claim one. Recipe changes are preview-only and require confirmation."}, {"role": "user", "content": prompt}]
    total_started = time.perf_counter()
    first, model_ms = model_call(messages)
    message = first.get("message", {})
    calls = message.get("tool_calls", [])
    names = [call.get("function", {}).get("name") for call in calls]
    if expected is not None and names != expected:
        raise SystemExit(f"{label}: expected {expected}, got {names}")
    messages.append(message)
    tool_started = time.perf_counter()
    tool_timings = []
    for call in calls:
        args = json.loads(call.get("function", {}).get("arguments", "{}"))
        result, elapsed = synthetic_tool(call["function"]["name"], args)
        tool_timings.append({"tool": call["function"]["name"], "tool_ms": round(elapsed, 1)})
        messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})
    tool_ms = (time.perf_counter() - tool_started) * 1000
    continuation, continuation_ms = model_call(messages)
    continuation_calls = continuation.get("message", {}).get("tool_calls", [])
    if continuation_calls:
        loop_names = [call.get("function", {}).get("name") for call in continuation_calls]
        raise SystemExit(f"{label}: unnecessary continuation tool loop: {loop_names}")
    total_ms = (time.perf_counter() - total_started) * 1000
    return {
        "workflow": label,
        "tool_calls": names,
        # This is complete non-streaming model response latency, not true
        # time-to-first-token; keep the distinction explicit in the output.
        "model_ms": round(model_ms, 1),
        "time_to_tool_ms": round(model_ms, 1) if calls else None,
        "tool_ms": round(tool_ms, 1),
        "tool_timings": tool_timings,
        "continuation_ms": round(continuation_ms, 1),
        "total_ms": round(total_ms, 1),
    }


def main():
    results = [
        run("normal_chat", "Say hello and tell me one short cooking tip.", []),
        run("memory_recall", "MUST use private memory: what does Beta dislike?", ["hindsight_recall"]),
        run("grocy_read", "What is currently in the shared pantry?", ["mcp_grocy_stock_overview_tool"]),
        run("grocy_mutation_confirmation", "I want to add milk to the shopping list, but do not change anything yet.", []),
        run("recipe", "Preview changing the mushroom-free pasta recipe to 4 servings.", ["recipe_set_servings"]),
        run("web", "Find a recipe online using tomatoes and basil.", ["web_search"]),
        run("multi_domain", "Find a recipe online using what is currently in our pantry and remember that Beta dislikes mushrooms.", None),
        run("agent_zero_synthetic", "Delegate a bounded read-only synthetic check of service status; do not execute anything.", ["agent_zero_delegate"]),
    ]
    print(json.dumps({"model": MODEL, "results": results}, sort_keys=True))
    print("PASS synthetic performance capture")


if __name__ == "__main__":
    main()
