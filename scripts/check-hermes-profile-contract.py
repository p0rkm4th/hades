#!/usr/bin/env python3
"""Check required Hermes MCP registrations against the reconstruction contract."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def profile_servers(text: str) -> dict[str, str]:
    match = re.search(r"(?m)^mcp_servers:\s*$", text)
    if not match:
        raise ValueError("profile has no top-level mcp_servers mapping")
    body = text[match.end():]
    starts = list(re.finditer(r"(?m)^  ([A-Za-z0-9_-]+):\s*$", body))
    if not starts:
        raise ValueError("profile has no MCP server entries")
    result: dict[str, str] = {}
    for index, start in enumerate(starts):
        name = start.group(1)
        if name in result:
            raise ValueError(f"duplicate MCP registration: {name}")
        end = starts[index + 1].start() if index + 1 < len(starts) else len(body)
        result[name] = body[start.end():end]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument(
        "--canonical-template", action="store_true",
        help="require every classified registration and disabled optional/staged defaults",
    )
    parser.add_argument(
        "--manifest", type=Path,
        default=Path(__file__).resolve().parents[1] / "config/reconstruction-manifest.json",
    )
    args = parser.parse_args()
    try:
        profile = args.profile.read_text(encoding="utf-8")
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        contract = manifest["hermes_profile_contract"]
        servers = profile_servers(profile)
        required = contract["v1_required_servers"]
        owner_gated = contract["owner_gated_servers"]
        staged = contract["optional_staged_servers"]
        categories = [set(required), set(owner_gated), set(staged)]
        if any(categories[i] & categories[j] for i in range(3) for j in range(i + 1, 3)):
            raise ValueError("a profile server appears in more than one activation class")
        classified = set.union(*categories)
        required_names = set(required)
        unclassified = sorted(set(servers) - classified)
        missing_required = sorted(required_names - set(servers))
        missing_canonical = sorted(classified - set(servers)) if args.canonical_template else []
        if unclassified or missing_required or missing_canonical:
            raise ValueError(
                "profile/manifest registration mismatch; "
                f"missing_required={missing_required}, missing_canonical={missing_canonical}, "
                f"unclassified={unclassified}"
            )
        for name, markers in required.items():
            block = servers[name]
            if re.search(r"(?m)^    enabled:\s*false\s*$", block):
                raise ValueError(f"required V1 `{name}` registration is explicitly disabled")
            missing_markers = [marker for marker in markers if marker not in block]
            if name == "homelab-readonly" and missing_markers == [
                "integrations/homelab-readonly/server.py"
            ]:
                generated_entrypoint = re.search(
                    r'(?m)^    command:\s*python(?:[0-9]+(?:\.[0-9]+)*)?\s*$'
                    r'.*?^    args:\s*\["\$\{HADES_INTEGRATIONS_ROOT\}/'
                    r'homelab-readonly-[A-Za-z0-9_-]{6,64}/server\.py"\]\s*$',
                    block,
                    re.DOTALL,
                )
                if generated_entrypoint:
                    missing_markers = []
            if missing_markers:
                raise ValueError(f"required `{name}` registration is incomplete: {missing_markers}")
            print(f"PASS V1-required Hermes MCP registration: {name}")
        for name in sorted(owner_gated):
            print(f"PASS classified owner-gated Hermes MCP registration: {name}")
            if name not in servers:
                continue
            disabled = bool(re.search(r"(?m)^    enabled:\s*false\s*$", servers[name]))
            if args.canonical_template and not disabled:
                raise ValueError(f"owner-gated `{name}` must be disabled in the canonical profile")
            if disabled:
                print(f"PASS disabled owner-gated Hermes MCP registration: {name}")
            else:
                print(f"WARN owner-gated Hermes MCP is enabled in operator profile: {name}; explicit owner activation must be verified")
        for name in sorted(staged):
            if name not in servers:
                continue
            disabled = bool(re.search(r"(?m)^    enabled:\s*false\s*$", servers[name]))
            if args.canonical_template and not disabled:
                raise ValueError(f"optional/staged `{name}` must be disabled in the canonical profile")
            if disabled:
                print(f"PASS disabled optional/staged Hermes MCP registration: {name}")
            else:
                print(f"WARN optional/staged Hermes MCP is enabled in operator profile: {name}")
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL Hermes profile contract: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
