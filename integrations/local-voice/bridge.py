"""Wyoming-to-STT bridge primitives for the local voice staging path."""

from __future__ import annotations

import io
import wave
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from contract import classify_transcript, validate_wav

MAX_PCM_BYTES = 10 * 1024 * 1024


def collect_audio(events: Iterable[Mapping[str, Any]]) -> bytes:
    """Assemble one complete audio-start/chunk/stop sequence into WAV bytes."""
    iterator = iter(events)
    start = next(iterator, None)
    if not start or start.get("type") != "audio-start":
        raise ValueError("voice stream must begin with audio-start")
    data = start.get("data") or {}
    rate, width, channels = data.get("rate"), data.get("width"), data.get("channels")
    if not isinstance(rate, int) or not isinstance(width, int) or not isinstance(channels, int):
        raise ValueError("audio-start is missing format")
    chunks: list[bytes] = []
    stopped = False
    for event in iterator:
        event_type = event.get("type")
        if event_type == "audio-stop":
            stopped = True
            break
        if event_type != "audio-chunk":
            raise ValueError("unexpected event in voice audio stream")
        chunk_data = event.get("data") or {}
        if (chunk_data.get("rate"), chunk_data.get("width"), chunk_data.get("channels")) != (rate, width, channels):
            raise ValueError("audio chunk format changed during voice stream")
        payload = event.get("payload", b"")
        if not isinstance(payload, bytes) or not payload:
            raise ValueError("audio chunk has no payload")
        chunks.append(payload)
        if sum(len(chunk) for chunk in chunks) > MAX_PCM_BYTES:
            raise ValueError("voice PCM exceeds bounded size")
    if not stopped or not chunks:
        raise ValueError("voice stream must contain audio and audio-stop")
    pcm = b"".join(chunks)
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    result = output.getvalue()
    validate_wav(result)
    return result


def transcribe(
    wav_bytes: bytes,
    provider: Callable[[bytes], Mapping[str, Any]],
) -> dict[str, Any]:
    """Pass validated audio to a provider and preserve absent confidence."""
    validate_wav(wav_bytes)
    result = provider(wav_bytes)
    if not isinstance(result, Mapping):
        raise ValueError("STT provider returned an invalid result")
    return classify_transcript(result.get("text"), result.get("confidence"))
