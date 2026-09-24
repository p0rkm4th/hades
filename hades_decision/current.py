"""CURRENT decision backend built from the routing signals serving HADES now.

This is a control, not a new production router. It reuses the maintained
HADES overlay's semantic regexes and exposes their result through the Alpha
contract so candidate backends can be compared against real current behavior.
Scores are explicitly ``heuristic_score``; they are not probabilities.
"""

from __future__ import annotations

import re
import time
import logging
from typing import Any, Mapping, Sequence

from .api import DECISION_SCHEMA, DecisionInput, DecisionResult, DecisionValue

try:
    logging.getLogger("hades.overlay").setLevel(logging.CRITICAL)
    from hermes import sitecustomize as current
except Exception:  # pragma: no cover - deployment-only import failure path
    current = None


MANIFEST: Mapping[str, Any] = {
    "backend": "CURRENT",
    "revision": "production-routing-signals",
    "supported_decisions": [
        "Intent",
        "CapabilityFamily",
        "NeedsClarification",
        "ReasoningTier",
        "RetrievalNeeded",
        "ToolRequired",
        "ToolFamily",
    ],
    "score_semantics": "heuristic_score",
    "privacy_class": "local_current_rules",
}


def _search(pattern: Any, text: str) -> bool:
    return bool(pattern and pattern.search(text))


def _fallback_patterns() -> dict[str, re.Pattern[str]]:
    return {
        "web": re.compile(r"\b(?:search|look(?:\s+\w+){0,2}\s+up|latest|news|web|current|today|weather|internet)\b|https?://", re.I),
        "page": re.compile(r"\b(?:read|article|page|website|what does it say|open the link)\b", re.I),
        "ordinary": re.compile(r"\b(?:hello|hey|hi|explain|tell me|write|joke|never mind)\b", re.I),
        "memory": re.compile(r"\b(?:remember|recall|forget|what\b.{0,40}\bdid\s+i\s+tell)\b", re.I),
        "grocy": re.compile(r"\b(?:grocy|grocery|groceries|pantry|food|recipe|cook|snacks?|missing|eggs?|milks?|bread|shopping list)\b", re.I),
        "grocy_write": re.compile(r"\b(?:add|remove|buy|bought|consume|used|put|throw|toss|mark|take)\b", re.I),
        "finance": re.compile(r"\b(?:finance|money|bank|budget|spend|spent|checking|savings|credit card)\b", re.I),
        "homelab": re.compile(r"\b(?:server|tartarus|hypnos|erebus|proxmox|netbox|kuma|is anything down)\b", re.I),
        "agent_zero": re.compile(r"\b(?:agent\s*(?:zero|0)|operator|inspect the server|ask the operator)\b", re.I),
        "ha": re.compile(r"\b(?:home assistant|temperature inside|living room|air quality|lights? on|front door|garage door|alarm)\b", re.I),
        "ambiguous": re.compile(r"\b(?:that|it|the other one|bags|thing|do it again|same thing again|restart it|share it|remove that|what about)\b", re.I),
        "deep": re.compile(r"\b(?:deeply|in detail|long analysis|compare architectures|large context|reason through)\b", re.I),
    }


def _patterns() -> dict[str, Any]:
    if current is None:
        return _fallback_patterns()
    return {
        "web": getattr(current, "_HADES_LIVE_WEB_INTENT", None),
        "page": re.compile(
            r"\b(?:read|article|page|website|what\s+does\s+it\s+say|open\s+(?:the\s+)?(?:page|article|link|first\s+result))\b",
            re.I,
        ),
        "ordinary": getattr(current, "_HADES_ORDINARY_CHAT_INTENT", None),
        "memory": re.compile(r"\b(?:remember|recall|forget|what\b.{0,40}\bdid\s+i\s+tell|do\s+you\s+remember|memory)\b", re.I),
        "grocy": re.compile(
            r"\b(?:grocy|grocery|groceries|grocry|shopping\s+list|pantry|inventory|stock|recipe|cook|snacks?|missing|food|"
            r"what(?:'s|\s+is)\s+in\s+stock|do\s+we\s+have)\b",
            re.I,
        ),
        "grocy_write": re.compile(r"\b(?:add|remove|buy|bought|consume|used|put|throw|toss|mark|take)\b", re.I),
        "finance": re.compile(r"\b(?:finance|money|bank|budget|spend|spent|checking|savings|credit\s+card)\b", re.I),
        "homelab": getattr(current, "_HADES_HOMELAB_INTENT", None),
        "agent_zero": re.compile(r"\b(?:agent\s*(?:zero|0)|operator|inspect the server|ask the operator)\b", re.I),
        "ha": re.compile(r"\b(?:home assistant|temperature inside|living room|air quality|lights? on|front door|garage door|alarm)\b", re.I),
        "ambiguous": re.compile(r"\b(?:that|it|the other one|bags|thing|do it again|same thing again|restart it|share it|remove that|the second one|the old one|what about)\b", re.I),
        "deep": re.compile(r"\b(?:deeply|in detail|long analysis|compare architectures|large context|reason through)\b", re.I),
    }


def _value(value: str, score: float, distribution: Mapping[str, float]) -> DecisionValue:
    return DecisionValue(value=value, score=score, score_kind="heuristic_score", distribution=distribution)


def _normalize_request(text: str) -> str:
    """Apply small, domain-generic normalizations before current signals.

    These are intentionally transcription/shorthand aliases, not sentence
    or-user-specific rules.  The original request remains available for
    ambiguity decisions and telemetry at the caller boundary.
    """
    normalized = text
    replacements = (
        (r"\bgrocry\b", "grocery"),
        (r"\bgrossy\b", "grocery"),
        (r"\bservr\b", "server"),
        (r"\bmc\b", "minecraft"),
        (r"\bpls\b", "please"),
        (r"\btht\b", "that"),
        (r"\bmlk\b", "milk"),
    )
    for pattern, replacement in replacements:
        normalized = re.sub(pattern, replacement, normalized, flags=re.I)
    return normalized


class CurrentRulesBackend:
    name = "CURRENT"
    manifest = MANIFEST

    def evaluate(self, state: DecisionInput, decision_types: Sequence[str]) -> DecisionResult:
        started = time.perf_counter()
        request_text = _normalize_request(state.request)
        text = "\n".join((*state.context[-4:], request_text))
        p = _patterns()
        fallback = _fallback_patterns()
        hits = {
            "web": _search(p["web"], text) or _search(fallback["web"], text),
            "page": _search(p["page"], text) or _search(fallback["page"], text),
            "memory": _search(p["memory"], text),
            # Keep production signals primary, but retain the adapter's
            # maintained local vocabulary for ordinary aliases they omit.
            "grocy": _search(p["grocy"], text) or _search(fallback["grocy"], text),
            "grocy_write": (_search(p["grocy_write"], text) or _search(fallback["grocy_write"], text)) and (_search(p["grocy"], text) or _search(fallback["grocy"], text)),
            "finance": _search(p["finance"], text),
            "homelab": _search(p["homelab"], text) or _search(fallback["homelab"], text),
            "agent_zero": _search(p["agent_zero"], text),
            "ha": _search(p["ha"], text),
            "ambiguous": _search(p["ambiguous"], request_text),
            "deep": _search(p["deep"], text),
            "ordinary": _search(p["ordinary"], state.request) or _search(fallback["ordinary"], state.request),
        }

        intent = "general_chat"
        family = "GENERAL"
        tool = "NONE"
        server_create = bool(re.search(r"\b(?:make|create|spin\s+up|host|give\s+me|start)\b.{0,40}\b(?:server|minecraft|linux|sandbox|website|site)\b|\b(?:minecraft|mc)\s+server\b", request_text, re.I))
        server_delete = bool(re.search(r"\b(?:delete|remove|trash|wipe|destroy)\b.{0,40}\b(?:server|sandbox|minecraft|test\s+one|thing)\b", request_text, re.I))
        server_status = bool(re.search(r"\b(?:is|did|what(?:'s|\s+is)|show)\b.{0,40}\b(?:server|minecraft|running|created|up)\b|\b(?:server|minecraft)\s+(?:up|down|running|working)\b", request_text, re.I))
        correction = bool(re.search(r"\b(?:actually|rather|instead|not\s+that|no,?)\b", request_text, re.I))
        low_information = bool(re.fullmatch(r"\s*[\d?!.]+\s*", request_text))
        voice_normalization = state.input_kind == "voice_transcript" and request_text.casefold() != state.request.casefold()
        if re.search(r"\b(?:the\s+)?(?:test|other|old|second)\s+(?:one|\w+)\b", request_text, re.I):
            hits["ambiguous"] = True
        if hits["agent_zero"]:
            intent, family, tool = "agent_zero", "AGENT_ZERO", "AGENT_ZERO"
        elif hits["finance"]:
            intent, family, tool = "finance", "FINANCE", "FINANCE"
        elif server_create:
            intent, family, tool = "server_provision", "SELF_SERVICE", "SELF_SERVICE"
        elif server_delete:
            intent, family, tool = "server_delete", "SELF_SERVICE", "SELF_SERVICE"
        elif server_status:
            intent, family, tool = "server_status", "SELF_SERVICE", "SELF_SERVICE"
        elif hits["homelab"]:
            intent, family, tool = "homelab", "HOMELAB", "HOMELAB_READ"
        elif hits["ha"]:
            intent, family, tool = "home_assistant", "HOME_ASSISTANT", "HOME_ASSISTANT_READ"
        elif hits["page"]:
            intent, family, tool = "page_read", "WEB", "PAGE_READ"
        elif hits["web"]:
            intent, family, tool = "web_search", "WEB", "WEB_SEARCH"
        elif hits["grocy_write"]:
            intent, family, tool = "grocery_mutation", "GROCY", "GROCY_MUTATION"
        elif hits["grocy"]:
            intent, family, tool = "pantry_read", "GROCY", "GROCY_READ"
        elif hits["memory"]:
            intent, family, tool = "memory", "MEMORY", "MEMORY"

        decisions: dict[str, DecisionValue] = {}
        supported = set(decision_types)
        if "Intent" in supported:
            decisions["intent"] = _value(intent, 0.82 if family != "GENERAL" else 0.62, {intent: 1.0})
        if "CapabilityFamily" in supported:
            decisions["capability_family"] = _value(family, 0.82 if family != "GENERAL" else 0.62, {family: 1.0})
        if "ToolRequired" in supported:
            decisions["tool_required"] = _value("true" if tool != "NONE" else "false", 0.84, {"true": 0.84, "false": 0.16})
        if "ToolFamily" in supported:
            decisions["tool_family"] = _value(tool, 0.82 if tool != "NONE" else 0.90, {tool: 1.0})
        if "NeedsClarification" in supported:
            needs = (
                low_information
                or (hits["ambiguous"] and (family in {"HOMELAB", "FINANCE", "AGENT_ZERO", "SELF_SERVICE"} or hits["grocy_write"] or family == "GENERAL"))
                or (correction and hits["grocy_write"])
                or voice_normalization
                or (re.search(r"\b(?:yesterday|today|last\s+(?:week|month|time))\b", request_text, re.I) is not None and bool(state.context))
            )
            decisions["needs_clarification"] = _value("true" if needs else "false", 0.78, {"true": 0.78 if needs else 0.22, "false": 0.22 if needs else 0.78})
        if "ReasoningTier" in supported:
            tier = "deep" if hits["deep"] else "fast"
            decisions["reasoning_tier"] = _value(tier, 0.80, {tier: 0.80, "fast" if tier == "deep" else "deep": 0.20})
        if "RetrievalNeeded" in supported:
            retrieval = hits["web"] or hits["page"] or hits["memory"] or hits["grocy"] or hits["homelab"] or hits["ha"]
            decisions["retrieval_needed"] = _value("true" if retrieval else "false", 0.80, {"true": 0.80 if retrieval else 0.20, "false": 0.20 if retrieval else 0.80})

        # Keep scalar decisions backward-compatible, but expose an ordered
        # decomposition when one request clearly spans multiple domains.
        # This is recommendation metadata only; callers still intersect each
        # family with deterministic authorization before exposing tools.
        domain_candidates: list[tuple[int, str, str]] = []

        def add_domain(pattern: str, capability: str, tool_family: str) -> None:
            match = re.search(pattern, request_text, re.I)
            if match:
                domain_candidates.append((match.start(), capability, tool_family))

        add_domain(
            r"\b(?:grocy|grocery|groceries|grocry|pantry|food|recipe|cook|snacks?|eggs?|milk|bread|shopping)\b",
            "GROCY",
            "GROCY_MUTATION" if hits["grocy_write"] else "GROCY_READ",
        )
        add_domain(
            r"\b(?:finance|money|bank|budget|spend|spent|checking|savings|credit\s+card)\b",
            "FINANCE",
            "FINANCE",
        )
        add_domain(
            r"\b(?:search|look(?:\s+\w+){0,2}\s+up|latest|news|web|weather|internet)\b",
            "WEB",
            "PAGE_READ" if hits["page"] else "WEB_SEARCH",
        )
        add_domain(
            r"\b(?:server|minecraft|proxmox|tartarus|hypnos|erebus|homelab)\b",
            "SELF_SERVICE" if (server_create or server_delete) else "HOMELAB" if not server_status else "SELF_SERVICE",
            "SELF_SERVICE" if (server_create or server_delete) else "HOMELAB_READ" if server_status else "HOMELAB_READ",
        )
        add_domain(r"\b(?:remember|recall|forget|memory)\b", "MEMORY", "MEMORY")
        domain_candidates.sort(key=lambda item: item[0])
        distinct_domains: list[tuple[str, str]] = []
        for _, capability, tool_family in domain_candidates:
            if (capability, tool_family) not in distinct_domains:
                distinct_domains.append((capability, tool_family))
        recommendations = {}
        if len(distinct_domains) > 1:
            recommendations = {
                "capability_family": tuple(item[0] for item in distinct_domains),
                "tool_family": tuple(item[1] for item in distinct_domains),
            }

        abstained = not decisions or (hits["ambiguous"] and family == "GENERAL")
        return DecisionResult(
            schema=DECISION_SCHEMA,
            backend=self.name,
            decisions=decisions,
            abstained=abstained,
            latency_ms=(time.perf_counter() - started) * 1000,
            recommendations=recommendations,
        )
