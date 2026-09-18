"""Context epochs: identity changes force a new, unmixed context.

An epoch binds the stable inputs that make a prefix reusable: tool
inventory, model/provider identity, release, profile, and the pinned
memory view. Any change advances the epoch; contexts from different
epochs are never merged. TTL validity is judged from request start,
and a restarted monotonic clock reports uncertainty instead of a
guarantee.
"""

from dataclasses import dataclass

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError


@dataclass(frozen=True, slots=True)
class ContextEpoch:
    """One stable-context identity; reuse is only valid inside it."""

    epoch_id: str
    tool_inventory_digest: str
    model_identity: str
    route: str | None
    release_digest: str
    profile_digest: str
    memory_view_digest: str
    generation: int


def epoch_for(
    *,
    tool_inventory_digest: str,
    model_identity: str,
    route: str | None,
    release_digest: str,
    profile_digest: str,
    memory_view_digest: str,
    generation: int = 0,
) -> ContextEpoch:
    """Derive the epoch id from every stable input."""
    epoch_id = digest(
        {
            "tools": tool_inventory_digest,
            "model": model_identity,
            "route": route,
            "release": release_digest,
            "profile": profile_digest,
            "memory": memory_view_digest,
        }
    )
    return ContextEpoch(
        epoch_id=epoch_id,
        tool_inventory_digest=tool_inventory_digest,
        model_identity=model_identity,
        route=route,
        release_digest=release_digest,
        profile_digest=profile_digest,
        memory_view_digest=memory_view_digest,
        generation=generation,
    )


class EpochManager:
    """Advance the epoch when any stable input changes."""

    def __init__(self, current: ContextEpoch) -> None:
        """Hold the active epoch and never serve a stale one."""
        self._current = current

    @property
    def current(self) -> ContextEpoch:
        """The active epoch."""
        return self._current

    def update(
        self,
        *,
        tool_inventory_digest: str | None = None,
        model_identity: str | None = None,
        route: str | None = None,
        release_digest: str | None = None,
        profile_digest: str | None = None,
        memory_view_digest: str | None = None,
    ) -> ContextEpoch:
        """Recompute the epoch; changed input bumps generation."""
        current = self._current
        candidate = epoch_for(
            tool_inventory_digest=(
                tool_inventory_digest or current.tool_inventory_digest
            ),
            model_identity=(model_identity or current.model_identity),
            route=route if route is not None else current.route,
            release_digest=(release_digest or current.release_digest),
            profile_digest=(profile_digest or current.profile_digest),
            memory_view_digest=(
                memory_view_digest or current.memory_view_digest
            ),
            generation=current.generation,
        )
        if candidate.epoch_id != current.epoch_id:
            candidate = epoch_for(
                tool_inventory_digest=candidate.tool_inventory_digest,
                model_identity=candidate.model_identity,
                route=candidate.route,
                release_digest=candidate.release_digest,
                profile_digest=candidate.profile_digest,
                memory_view_digest=candidate.memory_view_digest,
                generation=current.generation + 1,
            )
            self._current = candidate
        return self._current

    def require_current(self, epoch_id: str) -> None:
        """A stale epoch cannot bind new work."""
        if epoch_id != self._current.epoch_id:
            raise CyranoError("STALE_EPOCH", epoch_id)


def ttl_status(
    *,
    request_start: float,
    ttl_seconds: float,
    now: float,
    clock_kind: str,
) -> str:
    """TTL is measured from request start, never from write time.

    ``monotonic`` values are only valid inside one process lifetime;
    after a restart the caller must pass ``wall``/``provider`` and the
    result is ``unknown`` rather than a fabricated guarantee.
    """
    if clock_kind == "monotonic_restarted":
        return "unknown"
    if now - request_start > ttl_seconds:
        return "expired"
    return "valid"
