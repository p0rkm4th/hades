"""Small localhost HTTP STT service boundary for staged local voice."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from bridge import transcribe
from contract import MAX_AUDIO_BYTES


def process_audio(
    audio: bytes,
    provider: Callable[[bytes], Mapping[str, Any]],
) -> tuple[int, dict[str, Any]]:
    try:
        return 200, transcribe(audio, provider)
    except ValueError as exc:
        return 400, {"status": "FAILED", "error": str(exc), "voice_authenticated": False}
    except Exception:
        return 503, {"status": "FAILED", "error": "STT provider unavailable", "voice_authenticated": False}


def _faster_whisper_provider(model_name: str, compute_type: str) -> Callable[[bytes], Mapping[str, Any]]:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cpu", compute_type=compute_type)

    def provider(audio: bytes) -> Mapping[str, Any]:
        with tempfile.NamedTemporaryFile(suffix=".wav") as handle:
            handle.write(audio)
            handle.flush()
            segments, _info = model.transcribe(handle.name, beam_size=1, vad_filter=True)
            text = " ".join(segment.text.strip() for segment in segments).strip()
        # faster-whisper exposes segment log probabilities, not a calibrated
        # confidence score. Do not turn that into authority; force CLARIFY
        # until a reviewed confidence policy exists.
        return {"text": text, "confidence": None, "confidence_source": "unavailable"}

    return provider


def create_server(
    host: str,
    port: int,
    provider: Callable[[bytes], Mapping[str, Any]],
) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/health":
                self.send_error(404)
                return
            body = json.dumps({"status": "OK", "service": "local-voice-stt"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path != "/inference":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self.send_error(400, "Content-Length is required")
                return
            if length <= 0 or length > MAX_AUDIO_BYTES:
                self.send_error(400, "audio body is outside the bounded size")
                return
            audio = self.rfile.read(length)
            if len(audio) != length:
                self.send_error(400, "audio body is truncated")
                return
            status, result = process_audio(audio, provider)
            body = json.dumps(result, sort_keys=True).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    return ThreadingHTTPServer((host, port), Handler)


def main() -> None:
    host = os.environ.get("HADES_STT_HOST", "127.0.0.1")
    port = int(os.environ.get("HADES_STT_PORT", "8766"))
    model = os.environ.get("HADES_STT_MODEL", "tiny.en")
    compute_type = os.environ.get("HADES_STT_COMPUTE_TYPE", "int8")
    server = create_server(host, port, _faster_whisper_provider(model, compute_type))
    server.serve_forever()


if __name__ == "__main__":
    main()
