"""Non-steering comparison mode for Decision Plane candidates."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import time
from typing import Any, Sequence

from .api import DecisionBackend, DecisionInput, DecisionResult


@dataclass(frozen=True)
class ShadowObservation:
    request_hash: str
    current_backend: str
    candidate_backend: str
    compared_decisions: tuple[str, ...]
    agreements: int
    disagreements: int
    candidate_error: str | None
    candidate_latency_ms: float | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "hades-decision-shadow/v1",
            "request_hash": self.request_hash,
            "current_backend": self.current_backend,
            "candidate_backend": self.candidate_backend,
            "compared_decisions": list(self.compared_decisions),
            "agreements": self.agreements,
            "disagreements": self.disagreements,
            "candidate_error": self.candidate_error,
            "candidate_latency_ms": self.candidate_latency_ms,
        }


class ShadowDecisionPlane:
    """Evaluate a candidate without allowing it to steer production behavior."""

    def __init__(self, current: DecisionBackend, candidate: DecisionBackend):
        self.current = current
        self.candidate = candidate

    def evaluate(
        self, state: DecisionInput, decision_types: Sequence[str]
    ) -> tuple[DecisionResult, ShadowObservation]:
        bounded = state.bounded()
        current_result = self.current.evaluate(bounded, tuple(decision_types))
        request_hash = hashlib.sha256(
            json.dumps(
                {
                    "request": bounded.request,
                    "context": bounded.context,
                    "input_kind": bounded.input_kind,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        started = time.perf_counter()
        candidate_error: str | None = None
        candidate_latency_ms: float | None = None
        try:
            candidate_result = self.candidate.evaluate(bounded, tuple(decision_types))
            candidate_latency_ms = candidate_result.latency_ms
            if candidate_latency_ms is None:
                candidate_latency_ms = (time.perf_counter() - started) * 1000
        except Exception as exc:  # shadow failure cannot affect CURRENT
            candidate_result = None
            candidate_error = type(exc).__name__

        compared = tuple(
            key for key in decision_types
            if key.lower() in current_result.decisions
            and candidate_result is not None
            and key.lower() in candidate_result.decisions
        )
        agreements = sum(
            current_result.decisions[key.lower()].value
            == candidate_result.decisions[key.lower()].value
            for key in compared
        ) if candidate_result is not None else 0
        return current_result, ShadowObservation(
            request_hash=request_hash,
            current_backend=current_result.backend,
            candidate_backend=getattr(self.candidate, "name", "unknown"),
            compared_decisions=compared,
            agreements=agreements,
            disagreements=len(compared) - agreements,
            candidate_error=candidate_error,
            candidate_latency_ms=candidate_latency_ms,
        )
