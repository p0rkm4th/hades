#!/usr/bin/env bash
set -euo pipefail

runtime="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/integrations/local-voice/runtime.py"

grep -q 'f"{whisper_device}-pending"' "$runtime" \
  || { echo 'FAIL voice health does not distinguish unexercised device'; exit 1; }
grep -q 'self._whisper_device_state = self.whisper_device' "$runtime" \
  || { echo 'FAIL voice health does not record successful effective device'; exit 1; }
grep -q 'self._whisper_device_state = "cpu"' "$runtime" \
  || { echo 'FAIL voice health does not record CPU fallback'; exit 1; }
grep -q '"stt_device": self._whisper_device_state' "$runtime" \
  || { echo 'FAIL health endpoint exposes stale configured device'; exit 1; }

echo 'PASS voice health reports pending versus effective inference device'
