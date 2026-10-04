#!/usr/bin/env python3
"""Guard owner-only routing for configured inference/GPU read tools."""

from pathlib import Path

source = Path("hermes/sitecustomize.py").read_text(encoding="utf-8")
required = (
    'self._hades_session_scope == "owner"\n            and _hades_is_homelab_intent',
    '"mcp_homelab_readonly_homelab_inference_inventory"',
    '"mcp_homelab_readonly_homelab_gpu_telemetry"',
    '"call": lambda _args: module.homelab_inference_inventory()',
    '"call": lambda _args: module.homelab_gpu_telemetry()',
    '"call": lambda _args: module.homelab_inference_capacity()',
    '"call": lambda _args: module.homelab_backup_status()',
    '"call": lambda args: module.homelab_recent_activity((args or {}).get("window_hours", 24))',
    '"homelab_inference_capacity"',
    '"tool_choice": "required" if capacity_intent or backup_intent or activity_intent else',
    '"homelab_backup_status"',
    '"homelab_recent_activity"',
    '_hades_direct_proxmox_backup_status',
    'Provider catalogs do not prove',
    'point-in-time observation, not a',
)
for marker in required:
    if marker not in source:
        raise SystemExit(f"FAIL owner inference/GPU route missing contract: {marker}")

intent_start = source.index("_HADES_HOMELAB_INTENT = re.compile(")
intent_end = source.index("\n\n\ndef _hades_is_homelab_intent", intent_start)
intent = source[intent_start:intent_end]
for phrase in ("inference", "ollama", "models?", "where\\s+should\\s+i"):
    if phrase not in intent:
        raise SystemExit(f"FAIL natural inference intent missing {phrase}")

print("PASS owner inference/GPU, backup, and recent-activity reads are explicitly routed with scope/freshness caveats")
