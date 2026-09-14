#!/usr/bin/env python3
"""Run credential-free long-context tool-selection dogfood against Ollama."""

import json
import os
import sys
import urllib.request


BASE_URL = os.environ.get("HADES_OLLAMA_URL", "http://127.0.0.1:11434/v1").rstrip("/")
MODEL = os.environ.get("HADES_OLLAMA_MODEL", "qwen3:8b")
MAX_TOKENS = int(os.environ.get("HADES_OLLAMA_MAX_TOKENS", "400"))

TOOLS = [
    {"type": "function", "function": {
        "name": "hindsight_recall",
        "description": "Recall only the current user's private preferences. Never another user.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "hindsight_retain",
        "description": "Remember an explicit personal preference for the current user only.",
        "parameters": {"type": "object", "properties": {"fact": {"type": "string"}}, "required": ["fact"]},
    }},
    {"type": "function", "function": {
        "name": "mcp_grocy_stock_overview_tool",
        "description": "Read the canonical shared household pantry; read-only.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    }},
    {"type": "function", "function": {
        "name": "mcp_grocy_shopping_list_remove_tool",
        "description": "Remove a named shared shopping item; mutation requires a clear confirmed target.",
        "parameters": {"type": "object", "properties": {"item": {"type": "string"}}, "required": ["item"]},
    }},
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Search current external information.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    }},
]

TURNS = [
    ("preference", "I hate mushrooms. Please remember that.", {"hindsight_retain"}),
    ("pantry", "What do we have in the pantry?", {"mcp_grocy_stock_overview_tool"}),
    ("correction", "Correction: I actually like mushrooms now. Remember the correction.", {"hindsight_retain"}),
    ("web", "Search the current weather in Chicago.", {"web_search"}),
    ("abandoned", "Maybe we should add milk later, but do not do anything yet.", set()),
    # A stable fact may be answered directly or checked once on the web; both
    # are acceptable, unlike an abandoned or ambiguous mutation.
    ("switch", "What is the capital of France?", (set(), {"web_search"})),
    ("pronoun", "Remove it.", set()),
    ("recall", "What food preference did I tell you about?", {"hindsight_recall"}),
]


def call(messages):
    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "stream": False,
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
    }
    request = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)["choices"][0]


def main():
    users = os.environ.get("HADES_DOGFOOD_USERS", "alpha,beta,gamma").split(",")
    all_results = []
    for user in users:
        messages = [{
            "role": "system",
            "content": (
                f"You are in a synthetic household as user {user}. Private preferences are per-user. "
                "For any question about what the user said or prefers, MUST call "
                "hindsight_recall instead of answering from conversation text. "
                "Grocy is shared canonical pantry. Use web_search for current facts. "
                "Mutations require an explicit confirmed target; never infer a pronoun into a write."
            ),
        }]
        for label, prompt, expected in TURNS:
            messages.append({"role": "user", "content": prompt})
            choice = call(messages)
            message = choice.get("message", {})
            calls = {
                call.get("function", {}).get("name")
                for call in message.get("tool_calls", [])
            }
            accepted = expected if isinstance(expected, tuple) else (expected,)
            if calls not in accepted:
                raise SystemExit(
                    f"{user}/{label}: expected {sorted(expected)}, got {sorted(calls)} "
                    f"(finish={choice.get('finish_reason')})"
                )
            messages.append(message)
            for tool_call in message.get("tool_calls", []):
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": '{"synthetic":"read-only result"}',
                })
            all_results.append({"user": user, "turn": label, "calls": sorted(calls)})
    print(json.dumps({"model": MODEL, "turns": all_results}, sort_keys=True))
    print("PASS Ollama long synthetic dogfood")


if __name__ == "__main__":
    main()
