"""Worker task lifecycle: required reviews are never optional.

A blind review task carries a field whitelist; naming an origin,
author, rationale, or prior review is refused before dispatch.
Accepted results are recorded per role so a missing required review
is a blocker, while optional advice that fails stays optional.
"""

from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.interview.service import InterviewService
from deepagents_code.cyrano.interview.worker_adapter import (
    WorkerBinding,
)

REQUIRED_ROLES = frozenset({"critic", "blind-handoff-reviewer"})

BLIND_FORBIDDEN_FIELDS = frozenset(
    {
        "author",
        "origin",
        "rationale",
        "prior_review",
        "facilitator_notes",
        "acceptance_hint",
    }
)


@dataclass(frozen=True, slots=True)
class WorkerResult:
    """How a returned worker result was classified."""

    task_id: str
    role: str
    status: str  # "accepted" | "stale_requeued"


class ReviewLedger:
    """Accepted worker results by role; required reviews gate pass."""

    def __init__(self) -> None:
        """Start empty; nothing is credited until a result lands."""
        self._accepted: dict[str, str] = {}
        self._requeued: list[str] = []

    def record(self, binding: WorkerBinding, status: str) -> None:
        """Record an accepted result; stale ones queue re-review."""
        if status == "accepted":
            self._accepted[binding.role] = binding.task_id
        else:
            self._requeued.append(binding.task_id)

    def missing_required(self) -> frozenset[str]:
        """Required roles with no accepted result yet."""
        return frozenset(REQUIRED_ROLES - set(self._accepted))

    @property
    def requeued(self) -> tuple[str, ...]:
        """Tasks awaiting re-review after a stale result."""
        return tuple(self._requeued)


def request_blind_review(
    task_id: str,
    revision: int,
    input_digest: str,
    *,
    visible_fields: frozenset[str],
) -> WorkerBinding:
    """Build a blind-review binding; forbidden fields refuse.

    A blind reviewer must not see who proposed the change or why —
    anything that could bias the verdict is a scope violation, not a
    hint to be dropped silently.
    """
    leaked = set(visible_fields) & BLIND_FORBIDDEN_FIELDS
    if leaked:
        raise CyranoError(
            "BLIND_SCOPE_VIOLATION",
            f"blind review may not see {sorted(leaked)}",
        )
    return WorkerBinding(
        task_id=task_id,
        role="blind-handoff-reviewer",
        revision=revision,
        input_digest=input_digest,
    )


def apply_worker_result(
    service: InterviewService,
    payload: dict[str, object],
    binding: WorkerBinding,
    ledger: ReviewLedger,
) -> WorkerResult:
    """Apply a result; stale-but-material evidence requeues.

    A cancelled session still refuses outright; a stale revision is
    preserved as re-review work rather than dropped.
    """
    try:
        status = service.ingest_worker_result(payload, binding)
    except CyranoError as exc:
        if exc.code == "STALE_REVISION":
            ledger.record(binding, "stale_requeued")
        raise
    ledger.record(binding, status)
    return WorkerResult(binding.task_id, binding.role, status)
