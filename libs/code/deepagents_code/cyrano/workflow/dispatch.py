"""Dispatch consumes a separate execution permit — approval is not it.

``reserve_ready_work`` re-checks, inside one transaction boundary, that
the subject digest is still current, an execution-permission decision
exists for it, the source snapshot has not drifted, and the unit's
write-set does not collide with a live lease. A plan approval alone
never permits a write; ``apply_candidate`` nodes need the separate
``source_apply`` purpose.
"""

from __future__ import annotations

from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.planning.decisions import DecisionDesk
from deepagents_code.cyrano.planning.subject import (
    GovernedWorkPlan,
)


@dataclass(frozen=True, slots=True)
class ExecutionPermit:
    """A consumed execution-permission decision bound to digests."""

    permit_id: str
    subject_digest: str
    source_snapshot_digest: str
    approved_units: tuple[str, ...]
    generation: int


@dataclass(slots=True)
class _Lease:
    unit_id: str
    worker_id: str
    fence: int
    write_paths: tuple[str, ...]


class Dispatcher:
    """Issue work leases against permits, digests, and conflicts."""

    def __init__(self) -> None:
        """Leases and fences live in memory for the owner service."""
        self._leases: dict[str, _Lease] = {}
        self._fence = 0

    def check_permit(
        self,
        permit: ExecutionPermit | None,
        subject_digest: str,
        current_snapshot_digest: str,
    ) -> ExecutionPermit:
        """Re-validate the permit right before any effect starts."""
        if permit is None:
            raise CyranoError(
                "APPROVAL_REQUIRED",
                "plan approval exists but no execution permission",
            )
        if permit.subject_digest != subject_digest:
            raise CyranoError(
                "PERMIT_STALE", "permit binds a different subject"
            )
        if permit.source_snapshot_digest != current_snapshot_digest:
            raise CyranoError(
                "PERMIT_STALE", "source changed since the permit"
            )
        return permit

    def reserve_ready_work(
        self,
        plan: GovernedWorkPlan,
        permit: ExecutionPermit,
        worker_id: str,
        *,
        completed: frozenset[str] | None = None,
        failed: frozenset[str] | None = None,
    ) -> tuple[str, int]:
        """Lease one ready unit; conflicting writers wait or fail.

        A unit is ready when every dependency completed. Units with a
        failed dependency are blocked, never silently skipped.
        """
        done = completed or frozenset()
        failed_set = failed or frozenset()
        for unit in plan.units:
            if unit.unit_id in done or unit.unit_id in self._leases:
                continue
            deps = set(unit.dependencies)
            if deps & failed_set:
                continue
            if not deps <= done:
                continue
            if unit.unit_id not in permit.approved_units:
                continue
            overlap = [
                lease.unit_id
                for lease in self._leases.values()
                if set(lease.write_paths) & set(unit.write_paths)
            ]
            if overlap:
                raise CyranoError(
                    "RESOURCE_CONFLICT",
                    f"{unit.unit_id} write-set overlaps {overlap}",
                )
            self._fence += 1
            self._leases[unit.unit_id] = _Lease(
                unit.unit_id, worker_id, self._fence, unit.write_paths
            )
            return unit.unit_id, self._fence
        raise CyranoError("NO_READY_WORK", "no unit is dispatchable")

    def release(self, unit_id: str, worker_id: str, fence: int) -> None:
        """Release a lease only for the fenced owner."""
        lease = self._leases.get(unit_id)
        if (
            lease is None
            or lease.worker_id != worker_id
            or (lease.fence != fence)
        ):
            raise CyranoError("LEASE_LOST", f"no live lease {unit_id}")
        del self._leases[unit_id]


def make_permit(
    desk: DecisionDesk,
    decision_id: str,
    *,
    subject_digest: str,
    source_snapshot_digest: str,
    generation: int,
    plan: GovernedWorkPlan,
) -> ExecutionPermit:
    """Turn a granted execution-permission decision into a permit.

    An approve with no unit selection covers the whole plan; a partial
    selection is reduced to its dependency-closed approved subset —
    an approved unit never pulls an unapproved dependency with it.
    """
    from deepagents_code.cyrano.planning.decisions import (
        partial_approval_units,
    )

    request = desk.load(decision_id)
    if request is None or request.state != "approved":
        raise CyranoError(
            "APPROVAL_REQUIRED", "no approved execution decision"
        )
    if request.purpose != "execution_permission":
        raise CyranoError(
            "APPROVAL_REQUIRED",
            f"purpose {request.purpose!r} is not execution permission",
        )
    if request.subject_digest != subject_digest:
        raise CyranoError("PERMIT_STALE", "decision binds a different subject")
    if request.approved_units:
        approved = partial_approval_units(
            request.approved_units,
            {u.unit_id: u.dependencies for u in plan.units},
        )
    else:
        approved = tuple(sorted(u.unit_id for u in plan.units))
    return ExecutionPermit(
        permit_id=f"permit-{decision_id}",
        subject_digest=subject_digest,
        source_snapshot_digest=source_snapshot_digest,
        approved_units=approved,
        generation=generation,
    )
