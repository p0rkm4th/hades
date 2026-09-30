"""Feature-flagged runtime hook for non-steering Decision Plane shadowing."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Callable, Sequence

from .api import DecisionBackend, DecisionInput, DecisionResult
from .shadow import ShadowDecisionPlane, ShadowObservation


@dataclass(frozen=True)
class ShadowRuntimeConfig:
    enabled: bool = False
    sample_rate: float = 0.0
    production_steering: bool = False

    def validate(self) -> None:
        if not 0.0 <= self.sample_rate <= 1.0:
            raise ValueError("shadow sample rate must be between zero and one")
        if self.production_steering:
            raise ValueError("shadow runtime cannot steer production")


class RuntimeShadow:
    """A caller-owned hook that never changes the returned production result."""

    def __init__(
        self,
        current: DecisionBackend,
        candidate: DecisionBackend | None,
        config: ShadowRuntimeConfig,
        emit: Callable[[ShadowObservation], None] | None = None,
    ):
        config.validate()
        self._current = current
        self._candidate = candidate
        self._config = config
        self._emit = emit

    def evaluate(
        self, state: DecisionInput, decision_types: Sequence[str]
    ) -> DecisionResult:
        if not self._config.enabled or self._candidate is None or not self._sample(state):
            return self._current.evaluate(state.bounded(), tuple(decision_types))
        result, observation = ShadowDecisionPlane(self._current, self._candidate).evaluate(
            state, decision_types
        )
        if self._emit is not None:
            self._emit(observation)
        return result

    def _sample(self, state: DecisionInput) -> bool:
        digest = hashlib.sha256(state.bounded().request.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:8], "big") / 2**64
        return bucket < self._config.sample_rate
