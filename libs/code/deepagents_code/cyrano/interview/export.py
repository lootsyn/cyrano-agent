"""Contract compile and approved-bundle export.

A bundle is digest-bound to its statements, decisions, obligations,
and snapshot. Exporting an *approved* bundle requires an approval
whose subject and snapshot digests match exactly — another item's
approval or a changed snapshot refuses. An unapproved compile is a
draft artifact only; it never carries execution authority.
"""

import hashlib
import json
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.interview.service import InterviewService
from deepagents_code.cyrano.interview.workers import ReviewLedger

MANDATORY_REVIEW = frozenset(
    {
        "spec_critic",
        "blind_handoff",
        "plan_review",
        "final_code_review",
    }
)


@dataclass(frozen=True, slots=True)
class Approval:
    """An approval bound to one subject digest and snapshot."""

    approval_id: str
    subject_digest: str
    snapshot_digest: str


@dataclass(frozen=True, slots=True)
class TaskProfile:
    """A resolved review profile; mandatory duties cannot shrink."""

    risk: str
    reviews: frozenset[str]


@dataclass(frozen=True, slots=True)
class ContractBundle:
    """Digest-bound contract; ``draft_unapproved`` grants nothing."""

    status: str  # "draft_unapproved" | "approved"
    subject_digest: str
    snapshot_digest: str
    statement_count: int
    decision_count: int


def _digest(payload: object) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()


def resolve_task_profile(
    risk: str, requested_removals: frozenset[str]
) -> TaskProfile:
    """Refuse to drop mandatory reviews regardless of risk."""
    blocked = set(requested_removals) & MANDATORY_REVIEW
    if blocked:
        raise CyranoError(
            "REVIEW_DUTY_REQUIRED",
            f"mandatory reviews cannot be removed: {sorted(blocked)}",
        )
    return TaskProfile(risk=risk, reviews=MANDATORY_REVIEW)


def compile_contract(
    service: InterviewService,
    *,
    snapshot_digest: str,
) -> ContractBundle:
    """Compile the current interview state into a digest bundle."""
    statements = {
        sid: (s.kind, s.text) for sid, s in service.statements.items()
    }
    decisions = {
        d.decision_id: (d.status, d.revision)
        for d in service.decisions.all_current()
    }
    subject = _digest(
        {
            "statements": statements,
            "decisions": decisions,
            "obligations": list(service.obligations),
        }
    )
    status = "approved" if service.approved else "draft_unapproved"
    return ContractBundle(
        status=status,
        subject_digest=subject,
        snapshot_digest=snapshot_digest,
        statement_count=len(statements),
        decision_count=len(decisions),
    )


def export_draft(bundle: ContractBundle) -> dict[str, object]:
    """Draft artifact for an unapproved bundle; no authority claim."""
    return {
        "status": "draft_unapproved",
        "subject_digest": bundle.subject_digest,
        "execution_authorized": False,
    }


def export_approved_bundle(
    bundle: ContractBundle,
    approval: Approval,
    *,
    ledger: ReviewLedger,
    current_snapshot: str,
) -> dict[str, object]:
    """Export artifacts only under a matching approval + snapshot.

    Refusals: unapproved draft, approval for a different subject,
    a snapshot change since approval (re-review required), and any
    missing required review.
    """
    if bundle.status != "approved":
        raise CyranoError(
            "UNAPPROVED_EXPORT", "bundle is a draft, not a contract"
        )
    if approval.subject_digest != bundle.subject_digest:
        raise CyranoError(
            "APPROVAL_MISMATCH", "approval binds a different subject"
        )
    if (
        approval.snapshot_digest != bundle.snapshot_digest
        or bundle.snapshot_digest != current_snapshot
    ):
        raise CyranoError(
            "STALE_SNAPSHOT",
            "snapshot changed since approval; re-review required",
        )
    missing = ledger.missing_required()
    if missing:
        raise CyranoError(
            "REVIEW_INCOMPLETE",
            f"required reviews missing: {sorted(missing)}",
        )
    return {
        "status": "approved",
        "subject_digest": bundle.subject_digest,
        "snapshot_digest": bundle.snapshot_digest,
        "approval_id": approval.approval_id,
        "execution_authorized": True,
    }
