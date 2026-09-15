"""Minimal bounded Wyoming event framing for local voice staging.

The protocol is transport only. Authentication/encryption belongs to the
trusted private network boundary; this module never grants user authority.
"""

from __future__ import annotations

import io
import json
from typing import Any, BinaryIO

MAX_HEADER_BYTES = 64 * 1024
MAX_EVENT_BYTES = 10 * 1024 * 1024


def encode_event(
    event_type: str,
    data: dict[str, Any] | None = None,
    *,
    additional: bytes = b"",
    payload: bytes = b"",
) -> bytes:
    if not event_type or "\n" in event_type:
        raise ValueError("Wyoming event type is invalid")
    if len(additional) + len(payload) > MAX_EVENT_BYTES:
        raise ValueError("Wyoming event exceeds bounded size")
    header = {
        "type": event_type,
        "data": data or {},
        "data_length": len(additional),
        "payload_length": len(payload),
    }
    encoded = json.dumps(header, separators=(",", ":")).encode("utf-8") + b"\n"
    if len(encoded) > MAX_HEADER_BYTES:
        raise ValueError("Wyoming header exceeds bounded size")
    return encoded + additional + payload


def read_event(stream: BinaryIO) -> dict[str, Any] | None:
    header_line = stream.readline(MAX_HEADER_BYTES + 1)
    if not header_line:
        return None
    if len(header_line) > MAX_HEADER_BYTES or not header_line.endswith(b"\n"):
        raise ValueError("Wyoming header is missing or too large")
    try:
        header = json.loads(header_line)
    except json.JSONDecodeError as exc:
        raise ValueError("Wyoming header is not valid JSON") from exc
    if not isinstance(header, dict) or not isinstance(header.get("type"), str):
        raise ValueError("Wyoming header has no valid event type")
    data_length = header.get("data_length", 0)
    payload_length = header.get("payload_length", 0)
    if not isinstance(data_length, int) or not isinstance(payload_length, int) or data_length < 0 or payload_length < 0:
        raise ValueError("Wyoming event lengths are invalid")
    if data_length + payload_length > MAX_EVENT_BYTES:
        raise ValueError("Wyoming event exceeds bounded size")
    additional = stream.read(data_length)
    payload = stream.read(payload_length)
    if len(additional) != data_length or len(payload) != payload_length:
        raise ValueError("Wyoming event is truncated")
    return {
        "type": header["type"],
        "data": header.get("data", {}),
        "additional": additional,
        "payload": payload,
    }


def round_trip(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stream = io.BytesIO(b"".join(
        encode_event(
            event["type"],
            event.get("data"),
            additional=event.get("additional", b""),
            payload=event.get("payload", b""),
        )
        for event in events
    ))
    result: list[dict[str, Any]] = []
    while True:
        event = read_event(stream)
        if event is None:
            return result
        result.append(event)
