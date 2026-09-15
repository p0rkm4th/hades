#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHONPATH="$repo_dir/integrations/local-voice" python3 - <<'PY'
import io
import json
import threading
import urllib.error
import urllib.request
import wave

from service import create_server

audio = io.BytesIO()
with wave.open(audio, "wb") as output:
    output.setnchannels(1)
    output.setsampwidth(2)
    output.setframerate(16000)
    output.writeframes(bytes([0, 0]) * 1600)

server = create_server("127.0.0.1", 0, lambda _: {"text": "check the pantry", "confidence": 0.91})
threading.Thread(target=server.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{server.server_port}/inference"
request = urllib.request.Request(url, data=audio.getvalue(), method="POST", headers={"Content-Type": "audio/wav"})
with urllib.request.urlopen(request) as response:
    result = json.load(response)
assert result["status"] == "ACCEPTED"
assert result["transcript_ready"] is True
assert result["action_authorized"] is False
assert result["voice_authenticated"] is False
bad = urllib.request.Request(url, data=b"not wav", method="POST")
try:
    urllib.request.urlopen(bad)
except urllib.error.HTTPError as error:
    assert error.code == 400
else:
    raise AssertionError("invalid audio accepted by STT service")
server.shutdown()
print("PASS local STT HTTP service accepts validated WAV")
print("PASS malformed audio returns FAILED without provider success")
print("PASS service response never authenticates speaker")
PY
