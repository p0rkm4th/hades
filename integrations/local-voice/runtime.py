"""Bounded node-local STT/TTS runtime for the Delta voice staging path.

This service intentionally exposes only transcription and speech synthesis. It
does not authenticate speakers, select HADES tools, or authorize actions. The
authenticated HADES gateway remains the only place that may submit a voice
transcript as a user turn.
"""

from __future__ import annotations

import base64
import io
import json
import os
import tempfile
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from faster_whisper import WhisperModel
from piper import PiperVoice

MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 12_000


class VoiceRuntime:
    def __init__(self) -> None:
        root = Path(os.environ.get("HADES_VOICE_DATA", "."))
        whisper_root = Path(os.environ.get("HADES_VOICE_WHISPER_CACHE", root / "whisper"))
        whisper_model = os.environ.get("HADES_VOICE_WHISPER_MODEL", "tiny.en")
        whisper_device = os.environ.get("HADES_VOICE_WHISPER_DEVICE", "cuda")
        whisper_type = os.environ.get("HADES_VOICE_WHISPER_COMPUTE", "float16")
        self.voice_path = Path(
            os.environ.get(
                "HADES_VOICE_PIPER_MODEL",
                root / "piper" / "en_US-lessac-medium.onnx",
            )
        )
        self._whisper_error = ""
        self.whisper_device = whisper_device
        # Model construction can succeed before CTranslate2 actually loads
        # CUDA user-space libraries. Keep health honest until the first real
        # inference proves the effective device.
        self._whisper_device_state = f"{whisper_device}-pending"
        self._whisper_model_name = whisper_model
        self._whisper_root = whisper_root
        self._piper_error = ""
        try:
            self.whisper = WhisperModel(
                whisper_model,
                device=whisper_device,
                compute_type=whisper_type,
                download_root=str(whisper_root),
            )
        except Exception as exc:  # startup health reports the bounded failure
            # Some inference nodes have the NVIDIA kernel driver but do not
            # carry the CUDA user-space libraries needed by CTranslate2.
            # Keep processing on the node and use a bounded CPU fallback
            # instead of silently moving audio processing to a client laptop.
            try:
                self.whisper_device = "cpu"
                self._whisper_device_state = "cpu"
                self.whisper = WhisperModel(
                    whisper_model,
                    device="cpu",
                    compute_type="int8",
                    download_root=str(whisper_root),
                )
                self._whisper_error = f"{type(exc).__name__}: CPU fallback"
            except Exception as fallback_exc:
                self.whisper = None
                self._whisper_error = type(fallback_exc).__name__
        try:
            self.piper = PiperVoice.load(self.voice_path)
        except Exception as exc:
            self.piper = None
            self._piper_error = type(exc).__name__

    def health(self) -> dict[str, object]:
        return {
            "status": "OK" if self.whisper and self.piper else "DEGRADED",
            "service": "hades-node-local-voice",
            "stt": "ready" if self.whisper else "unavailable",
            "stt_device": self._whisper_device_state if self.whisper else "none",
            "tts": "ready" if self.piper else "unavailable",
            "voice_authenticated": False,
            "action_authorized": False,
            "stt_error": self._whisper_error,
            "tts_error": self._piper_error,
        }

    def transcribe(self, audio: bytes) -> dict[str, object]:
        if not self.whisper:
            return {"status": "FAILED", "error": "STT provider unavailable"}
        if not audio or len(audio) > MAX_AUDIO_BYTES:
            return {"status": "FAILED", "error": "audio is outside the bounded size"}
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav") as handle:
                handle.write(audio)
                handle.flush()
                try:
                    segments, info = self.whisper.transcribe(
                        handle.name, beam_size=1, vad_filter=True
                    )
                    self._whisper_device_state = self.whisper_device
                    text = " ".join(segment.text.strip() for segment in segments).strip()
                except Exception as exc:
                    # CTranslate2 may defer loading CUDA libraries until the
                    # first encoder call. Retry once on this same node with
                    # bounded CPU/int8 processing and expose the downgrade.
                    if self.whisper_device != "cuda":
                        raise
                    self.whisper = WhisperModel(
                        self._whisper_model_name,
                        device="cpu",
                        compute_type="int8",
                        download_root=str(self._whisper_root),
                    )
                    self.whisper_device = "cpu"
                    self._whisper_device_state = "cpu"
                    self._whisper_error = f"{type(exc).__name__}: CPU fallback"
                    segments, info = self.whisper.transcribe(
                        handle.name, beam_size=1, vad_filter=True
                    )
                    text = " ".join(segment.text.strip() for segment in segments).strip()
            return {
                "status": "SUCCEEDED" if text else "SILENCE",
                "text": text,
                "language": getattr(info, "language", None),
                "confidence": None,
                "voice_authenticated": False,
                "action_authorized": False,
            }
        except Exception:
            return {"status": "FAILED", "error": "STT transcription failed"}

    def synthesize(self, text: str) -> bytes | None:
        if not self.piper or not text or len(text) > MAX_TEXT_CHARS:
            return None
        output = io.BytesIO()
        try:
            with wave.open(output, "wb") as wav:
                self.piper.synthesize_wav(text, wav)
            return output.getvalue()
        except Exception:
            return None


def create_server(runtime: VoiceRuntime) -> ThreadingHTTPServer:
    token = os.environ.get("HADES_VOICE_TOKEN", "")

    class Handler(BaseHTTPRequestHandler):
        def _authorized(self) -> bool:
            return bool(token) and self.headers.get("Authorization") == f"Bearer {token}"

        def _json(self, status: int, value: dict[str, object]) -> None:
            body = json.dumps(value, sort_keys=True).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path != "/health":
                self.send_error(404)
                return
            self._json(200, runtime.health())

        def do_POST(self) -> None:
            if not self._authorized():
                self.send_error(401)
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_AUDIO_BYTES:
                self.send_error(413)
                return
            body = self.rfile.read(length)
            if self.path in {"/stt", "/v1/audio/transcriptions", "/audio/transcriptions"}:
                if self.path.endswith("/transcriptions"):
                    try:
                        payload = json.loads(body.decode())
                        encoded = payload.get("input_audio", {}).get("data", "")
                        body = base64.b64decode(encoded, validate=True)
                    except (ValueError, TypeError, UnicodeDecodeError):
                        self.send_error(400)
                        return
                self._json(200, runtime.transcribe(body))
                return
            if self.path in {"/tts", "/v1/audio/speech", "/audio/speech"}:
                try:
                    payload = json.loads(body.decode())
                    text = payload.get("text", payload.get("input", ""))
                except (ValueError, UnicodeDecodeError, AttributeError):
                    self.send_error(400)
                    return
                if not isinstance(text, str) or len(text) > MAX_TEXT_CHARS:
                    self.send_error(400)
                    return
                audio = runtime.synthesize(text)
                if not audio:
                    self._json(503, {"status": "FAILED", "error": "TTS provider unavailable"})
                    return
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(audio)))
                self.end_headers()
                self.wfile.write(audio)
                return
            self.send_error(404)

        def log_message(self, *_args: object) -> None:
            return

    return ThreadingHTTPServer(
        (os.environ.get("HADES_VOICE_HOST", "127.0.0.1"), int(os.environ.get("HADES_VOICE_PORT", "8766"))),
        Handler,
    )


def main() -> None:
    runtime = VoiceRuntime()
    create_server(runtime).serve_forever()


if __name__ == "__main__":
    main()
