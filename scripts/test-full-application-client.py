#!/usr/bin/env python3
"""Exercise the isolated Open WebUI application path over its private network."""

import json
import os
import sys
import time
import uuid
import urllib.request
from urllib.error import HTTPError


base = sys.argv[1].rstrip("/")
model_base = sys.argv[2].rstrip("/")
mode = sys.argv[3] if len(sys.argv) > 3 else "create"
state_path = sys.argv[4] if len(sys.argv) > 4 else ""
model_key = os.environ.get("HADES_TEST_MODEL_KEY", "synthetic")
model_name = os.environ.get("HADES_TEST_MODEL_NAME", "synthetic-reconstruction-model")
run_id = os.environ.get("HADES_TEST_RUN_ID", "reconstruction")
alpha_email = f"alpha-{run_id}@reconstruction.invalid"
beta_email = f"beta-{run_id}@reconstruction.invalid"


def request(path, method="GET", body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    encoded = None if body is None else json.dumps(body).encode()
    with urllib.request.urlopen(
        urllib.request.Request(f"{base}{path}", data=encoded, headers=headers, method=method),
        timeout=20,
    ) as response:
        return json.load(response)


if mode == "verify-restart":
    if not state_path:
        raise SystemExit("restart verification requires a state file")
    with open(state_path, encoding="utf-8") as handle:
        chat_id = handle.read().strip()
    alpha = request(
        "/api/v1/auths/signin",
        "POST",
        {"email": alpha_email, "password": "Synthetic-Only-123!"},
    )
    saved = request(f"/api/v1/chats/{chat_id}", token=alpha["token"])
    if "Synthetic application response" not in json.dumps(saved):
        raise SystemExit(f"persisted application response missing after restart: {saved}")
    print(f"PASS Alpha chat {chat_id} survives Open WebUI restart")
    beta = request(
        "/api/v1/auths/signin",
        "POST",
        {"email": beta_email, "password": "Synthetic-Only-123!"},
    )
    try:
        request(f"/api/v1/chats/{chat_id}", token=beta["token"])
    except HTTPError as exc:
        if exc.code not in {401, 403}:
            raise SystemExit(f"Beta received unexpected post-restart status: {exc.code}")
    else:
        raise SystemExit("Beta accessed Alpha's chat after restart")
    print("PASS Beta remains isolated after Open WebUI restart")
    raise SystemExit(0)

alpha = request(
    "/api/v1/auths/signup",
    "POST",
    {"name": "Alpha", "email": alpha_email, "password": "Synthetic-Only-123!"},
)
token = alpha["token"]
beta = request(
    "/api/v1/auths/add",
    "POST",
    {"name": "Beta", "email": beta_email, "password": "Synthetic-Only-123!", "role": "user"},
    token,
)
beta_token = beta["token"]
request(
    "/openai/config/update",
    "POST",
    {
        "ENABLE_OPENAI_API": True,
        "OPENAI_API_BASE_URLS": [model_base],
        "OPENAI_API_KEYS": [model_key],
        "OPENAI_API_CONFIGS": {},
    },
    token,
)
message_id = str(uuid.uuid4())
assistant_id = str(uuid.uuid4())
session_id = str(uuid.uuid4())
chat = request(
    "/api/chat/completions",
    "POST",
    {
        "model": model_name,
        "messages": [{"id": message_id, "role": "user", "content": "reconstruction marker"}],
        "stream": False,
        "parent_id": None,
        "id": assistant_id,
        "session_id": session_id,
        "user_message": {"id": message_id, "role": "user", "content": "reconstruction marker"},
    },
    token,
)
chat_id = chat.get("chat_id")
if not chat_id:
    raise SystemExit(f"missing chat ID: {chat}")
saved = None
for _ in range(60):
    saved = request(f"/api/v1/chats/{chat_id}", token=token)
    if "Synthetic application response" in json.dumps(saved):
        break
    time.sleep(1)
if not saved or "Synthetic application response" not in json.dumps(saved):
    raise SystemExit(f"application response was not persisted: {saved}")
if state_path:
    with open(state_path, "w", encoding="utf-8") as handle:
        handle.write(chat_id)
try:
    request(f"/api/v1/chats/{chat_id}", token=beta_token)
except HTTPError as exc:
    if exc.code not in {401, 403}:
        raise SystemExit(f"Beta received unexpected private-chat status: {exc.code}")
else:
    raise SystemExit("Beta accessed Alpha's private chat")
print(f"PASS isolated Open WebUI model route and persisted Alpha chat {chat_id}")
print("PASS Beta cannot retrieve Alpha's private chat")
