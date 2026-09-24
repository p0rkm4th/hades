"""Privacy gate for external Decision Plane research backends."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Sequence

from .api import DecisionInput


_SECRET_MARKERS = re.compile(
    r"\b(?:password|passphrase|api[_ -]?key|access[_ -]?token|bearer|private[_ -]?key|secret)\b",
    re.I,
)


@dataclass(frozen=True)
class ExternalDecisionPayload:
    schema: str
    privacy_class: str
    request: str
    context: tuple[str, ...]
    decision_types: tuple[str, ...]
    request_hash: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "privacy_class": self.privacy_class,
            "request": self.request,
            "context": list(self.context),
            "decision_types": list(self.decision_types),
            "request_hash": self.request_hash,
        }


def build_external_payload(
    state: DecisionInput,
    decision_types: Sequence[str],
    *,
    privacy_class: str,
) -> ExternalDecisionPayload:
    """Build the only payload shape permitted for hosted research calls.

    The caller must label the fixture as synthetic/public/redacted. Identity,
    authority context, credentials, and filesystem/authentication state are not
    represented in this payload at all.
    """

    allowed = (
        privacy_class in {"public_synthetic", "redacted_synthetic"}
        or privacy_class.startswith("synthetic_")
        or privacy_class.endswith("_synthetic")
    )
    if not allowed:
        raise ValueError("external decision backends accept only synthetic/public/redacted data")
    bounded = state.bounded()
    material = "\n".join((*bounded.context, bounded.request))
    if _SECRET_MARKERS.search(material):
        raise ValueError("external decision payload contains a prohibited secret marker")
    canonical = {
        "request": bounded.request,
        "context": bounded.context,
        "decision_types": tuple(decision_types),
        "privacy_class": privacy_class,
    }
    request_hash = hashlib.sha256(
        json.dumps(canonical, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return ExternalDecisionPayload(
        schema="decision-api/v1/external",
        privacy_class=privacy_class,
        request=bounded.request,
        context=bounded.context,
        decision_types=tuple(decision_types),
        request_hash=request_hash,
    )
