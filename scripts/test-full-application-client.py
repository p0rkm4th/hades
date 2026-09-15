#!/usr/bin/env python3
"""Exercise the isolated Open WebUI application path over its private network."""

import json
import sys
import time
import uuid
import urllib.request
from urllib.error import HTTPError


base = sys.argv[1].rstrip("/")
model_base = sys.argv[2].rstrip("/")


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


alpha = request(
    "/api/v1/auths/signup",
    "POST",
    {"name": "Alpha", "email": "alpha@reconstruction.invalid", "password": "Synthetic-Only-123!"},
)
token = alpha["token"]
beta = request(
    "/api/v1/auths/add",
    "POST",
    {"name": "Beta", "email": "beta@reconstruction.invalid", "password": "Synthetic-Only-123!", "role": "user"},
    token,
)
beta_token = beta["token"]
request(
    "/openai/config/update",
    "POST",
    {
        "ENABLE_OPENAI_API": True,
        "OPENAI_API_BASE_URLS": [model_base],
        "OPENAI_API_KEYS": ["synthetic"],
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
        "model": "synthetic-reconstruction-model",
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
try:
    request(f"/api/v1/chats/{chat_id}", token=beta_token)
except HTTPError as exc:
    if exc.code not in {401, 403}:
        raise SystemExit(f"Beta received unexpected private-chat status: {exc.code}")
else:
    raise SystemExit("Beta accessed Alpha's private chat")
print(f"PASS isolated Open WebUI model route and persisted Alpha chat {chat_id}")
print("PASS Beta cannot retrieve Alpha's private chat")
