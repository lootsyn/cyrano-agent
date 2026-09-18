"""Rollout: canary cohorts, run pinning, dispatch gating.

A promoted release binds only new runs — a run in progress keeps
the release it pinned at start, and revocation outranks pinning: a
run on a revoked release pauses rather than continuing. Canary
cohorts are pinned slices of new dispatch; a canary regression
stops new dispatch and reports impacted sessions without touching
user code.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.kernel.releases import ReleaseLane

SEQ = (list, tuple, set, frozenset)


@dataclass(frozen=True, slots=True)
class CanaryCohort:
    """A pinned slice of new dispatch bound to one release."""

    cohort_id: str
    release_id: str
    member_ids: tuple[str, ...]


def assign_canary(
    lane: ReleaseLane,
    member_ids: Iterable[str],
    *,
    cohort_id: str,
) -> CanaryCohort:
    """Pin a cohort of new runs to the live release.

    Members are explicit; a canary never captures runs that started
    before the promotion.
    """
    members = tuple(sorted({str(m) for m in member_ids}))
    if not members:
        raise CyranoError("INPUT_INVALID", "a cohort needs members")
    return CanaryCohort(
        cohort_id=cohort_id,
        release_id=lane.live.release_id,
        member_ids=members,
    )


@dataclass(frozen=True, slots=True)
class DispatchBinding:
    """Which release a run may use; pause is a state, not a guess."""

    run_id: str
    release_id: str
    state: str  # bound | paused
    reason: str


def bind_dispatch(
    lane: ReleaseLane,
    run: Mapping[str, object],
) -> DispatchBinding:
    """Bind a run; revocation outranks pins, promotion only new runs.

    A run on a revoked release pauses and needs a new binding. A run
    started before a promotion stays on its pinned release; a new
    run binds the live one. An unknown pin is paused, not trusted.
    """
    run_id = str(run.get("run_id", ""))
    used = str(run.get("release_id", ""))
    if lane.is_revoked(used):
        return DispatchBinding(run_id, used, "paused", "REVOKED_RELEASE")
    known = {r.release_id for r in lane.history()}
    started_after = bool(run.get("started_after_promotion", False))
    if started_after:
        if lane.is_revoked(lane.live.release_id):
            return DispatchBinding(
                run_id, lane.live.release_id, "paused", "REVOKED_RELEASE"
            )
        return DispatchBinding(
            run_id, lane.live.release_id, "bound", "live_release"
        )
    pinned = run.get("pinned_release_id")
    if str(pinned) not in known:
        return DispatchBinding(
            run_id, used, "paused", "UNKNOWN_PINNED_RELEASE"
        )
    if lane.is_revoked(str(pinned)):
        return DispatchBinding(
            run_id, str(pinned), "paused", "REVOKED_RELEASE"
        )
    return DispatchBinding(run_id, str(pinned), "bound", "pinned_release")


def stop_dispatch(lane: ReleaseLane) -> Mapping[str, object]:
    """Report a stopped-dispatch state for a revoked live release."""
    return {
        "new_dispatch": "stopped",
        "live_release": lane.live.release_id,
        "revoked": lane.is_revoked(lane.live.release_id),
    }
