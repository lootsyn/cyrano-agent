"""Cache-observation and warming policy; observability stays honest.

A keepalive ping only proves network connectivity. Warming is off by
default, yields to pending user input, reserves budget
transactionally, and never shares cache identity across providers or
unobserved routes.
"""

from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError


@dataclass(frozen=True, slots=True)
class Coverage:
    """Declared observable activity and the missing evidence paths."""

    required: frozenset[str]
    observed: frozenset[str]

    @property
    def gaps(self) -> frozenset[str]:
        """Missing evidence types; absence is not zero activity."""
        return self.required - self.observed

    @property
    def complete(self) -> bool:
        """An empty requirement set cannot establish coverage."""
        return bool(self.required) and not self.gaps


@dataclass(frozen=True, slots=True)
class CacheObservation:
    """What the wire actually showed; hits come only from usage."""

    wire_observed: bool
    cache_read: int | None = None
    cache_write: int | None = None
    network_reachable: bool = False


def record_keepalive(observed_ping: bool) -> CacheObservation:
    """A ping updates reachability only; it says nothing about cache."""
    return CacheObservation(
        wire_observed=observed_ping,
        network_reachable=observed_ping,
    )


@dataclass(frozen=True, slots=True)
class WarmingPolicy:
    """Idle warming defaults off; caps and priority are explicit."""

    enabled: bool = False
    cost_cap: int = 0


class WarmScheduler:
    """Decide whether an idle warm may run; never silently calls."""

    def __init__(self, policy: WarmingPolicy) -> None:
        """Bind the policy; disabled means zero physical calls."""
        self._policy = policy
        self._reserved: int = 0
        self.calls_made: int = 0

    def maybe_warm(
        self,
        *,
        pending_input: bool,
        route_known: bool,
        model_changed: bool = False,
        stale_result: bool = False,
    ) -> str:
        """Return the warm decision without performing any call."""
        if not self._policy.enabled:
            return "disabled"
        if pending_input:
            return "deferred_user_input"
        if not route_known:
            raise CyranoError(
                "CAPABILITY_UNAVAILABLE", "upstream route unobserved"
            )
        if stale_result:
            return "stale_result"
        if model_changed:
            return "stale_generation"
        return "warm"

    def reserve_budget(self, units: int) -> bool:
        """First reserve wins; contention denies the loser."""
        if self._reserved + units > self._policy.cost_cap:
            return False
        self._reserved += units
        return True

    def complete_warm(self, *, generation_current: bool) -> str:
        """A late response is billed but marked stale if superseded."""
        self.calls_made += 1
        return "billed" if generation_current else "billed_stale"
