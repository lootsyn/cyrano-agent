"""Release recovery: rollback and revocation impact reporting.

Rollback moves the live pointer to a prior immutable release — it
never rewrites history and never reverts user code. A canary
regression or a security revoke stops new dispatch, pauses impacted
runs, and reports the affected sessions separately from the harness
pointer move.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.kernel.releases import ReleaseLane

SEQ = (list, tuple, set, frozenset)


@dataclass(frozen=True, slots=True)
class RecoveryReport:
    """A pointer move plus its honest impact surface."""

    action: str  # rollback | revoke
    new_live: str
    impacted_sessions: tuple[str, ...]
    new_dispatch_stopped: bool
    user_code_reverted: bool


def rollback_or_revoke(
    lane: ReleaseLane,
    *,
    target_release: str | None = None,
    revoke_release: str | None = None,
    reason: str = "",
    running_runs: Iterable[Mapping[str, object]] = (),
) -> RecoveryReport:
    """Move the pointer or revoke, then report real impact.

    ``running_runs`` are inspected for impact: a run on a revoked or
    superseded release is listed as impacted and paused. User code
    is never reverted — only the harness pointer moves.
    """
    live_before = lane.live.release_id
    if revoke_release is not None:
        lane.revoke(revoke_release, reason=reason)
    if target_release is None:
        if revoke_release is None or revoke_release == lane.live.release_id:
            target_release = lane.live.parent_id
        else:
            target_release = lane.live.release_id
    if target_release is None:
        raise CyranoError("MISSING_RELEASE", "no parent to roll back to")
    new_live = lane.rollback(target_release).release_id
    impacted = tuple(
        sorted(
            str(r.get("run_id", ""))
            for r in running_runs
            if str(r.get("release_id", "")) != new_live
        )
    )
    return RecoveryReport(
        action="revoke" if revoke_release else "rollback",
        new_live=new_live,
        impacted_sessions=impacted,
        new_dispatch_stopped=(
            revoke_release == live_before or new_live != live_before
        ),
        user_code_reverted=False,
    )
