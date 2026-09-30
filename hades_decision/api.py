"""Typed, backend-neutral semantic decisions for HADES.

This module deliberately contains no tools, policy decisions, model calls, or
domain mutations. A backend recommends semantic values; callers still apply
deterministic identity, authorization, confirmation, and reconciliation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence


DECISION_SCHEMA = "decision-api/v1"


def intersect_recommended_capabilities(
    authorized: Sequence[str], recommended: Sequence[str]
) -> tuple[str, ...]:
    """Return only recommendations already allowed by deterministic policy.

    This is intentionally an intersection, never a grant.  Authorization is
    resolved by the caller before this helper is invoked; the decision plane
    cannot add a capability merely by recommending it.
    """

    allowed = set(authorized)
    return tuple(item for item in recommended if item in allowed)


@dataclass(frozen=True)
class DecisionInput:
    """Minimum state needed for one semantic evaluation.

    ``actor_class`` is deliberately coarse. It is useful for evaluation and
    calibration but is not an identity or an authorization assertion.
    """

    request: str
    context: tuple[str, ...] = ()
    actor_class: str = "unknown"
    input_kind: str = "typed"
    allowed_capability_families: tuple[str, ...] = ()

    def bounded(self, *, max_request: int = 4000, max_context: int = 4) -> "DecisionInput":
        return DecisionInput(
            request=self.request[:max_request],
            context=tuple(self.context[-max_context:]),
            actor_class=self.actor_class[:64],
            input_kind=self.input_kind[:32],
            allowed_capability_families=tuple(self.allowed_capability_families),
        )


@dataclass(frozen=True)
class DecisionValue:
    value: str
    score: float
    score_kind: str = "uncalibrated_score"
    distribution: Mapping[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "score": self.score,
            "score_kind": self.score_kind,
            "distribution": dict(self.distribution),
        }


@dataclass(frozen=True)
class DecisionResult:
    schema: str
    backend: str
    decisions: Mapping[str, DecisionValue]
    abstained: bool = False
    fallback: str | None = None
    latency_ms: float | None = None
    error: str | None = None
    # Optional composite recommendations preserve multi-domain semantics
    # without changing scalar v1 decisions or granting authority.
    recommendations: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "backend": self.backend,
            "decisions": {key: value.as_dict() for key, value in self.decisions.items()},
            "abstained": self.abstained,
            "fallback": self.fallback,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "recommendations": {key: list(values) for key, values in self.recommendations.items()},
        }


class DecisionBackend(Protocol):
    name: str
    manifest: Mapping[str, Any]

    def evaluate(
        self, state: DecisionInput, decision_types: Sequence[str]
    ) -> DecisionResult: ...


class DecisionPlane:
    """Small HADES-owned façade with safe fallback semantics."""

    def __init__(self, backend: DecisionBackend, fallback: DecisionBackend):
        self.backend = backend
        self.fallback = fallback

    def evaluate(
        self, state: DecisionInput, decision_types: Sequence[str]
    ) -> DecisionResult:
        bounded = state.bounded()
        try:
            result = self.backend.evaluate(bounded, tuple(decision_types))
            if result.schema != DECISION_SCHEMA:
                raise ValueError("decision backend returned an unsupported schema")
            return result
        except Exception as exc:
            # A decision backend can never expand capabilities on failure.
            # Returning CURRENT is safer than manufacturing a permissive answer.
            fallback = self.fallback.evaluate(bounded, tuple(decision_types))
            return DecisionResult(
                schema=DECISION_SCHEMA,
                backend=fallback.backend,
                decisions=fallback.decisions,
                abstained=fallback.abstained,
                fallback="current",
                latency_ms=fallback.latency_ms,
                error=f"decision backend unavailable: {type(exc).__name__}",
                recommendations=fallback.recommendations,
            )
