"""Pure transition validation; prerequisites are broker-verified."""

from deepagents_code.cyrano.contracts.types import CyranoError

TRANSITIONS: dict[str, frozenset[str]] = {
    "proposed": frozenset({"static_validated", "rejected", "revoked"}),
    "static_validated": frozenset({"evaluating", "rejected", "revoked"}),
    "evaluating": frozenset(
        {"evaluated", "inconclusive", "rejected", "revoked"}
    ),
    "inconclusive": frozenset({"evaluating", "rejected", "revoked"}),
    "evaluated": frozenset({"reviewed", "rejected", "revoked"}),
    "reviewed": frozenset({"await_approval", "rejected", "revoked"}),
    "await_approval": frozenset({"promoted", "rejected", "revoked"}),
    "promoted": frozenset({"revoked"}),
    "rejected": frozenset(),
    "revoked": frozenset(),
}


PLAN_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"static_validated", "rejected"}),
    "static_validated": frozenset({"in_review", "rejected"}),
    "in_review": frozenset(
        {"amendment_requested", "human_review", "rejected"}
    ),
    "amendment_requested": frozenset({"draft", "rejected"}),
    "human_review": frozenset(
        {"approved", "rejected", "deferred", "cancelled"}
    ),
    "deferred": frozenset({"human_review", "cancelled"}),
    "approved": frozenset({"executable", "amendment_requested", "cancelled"}),
    "executable": frozenset({"executing", "amendment_requested", "cancelled"}),
    "executing": frozenset({"completed", "failed", "cancelled"}),
    "completed": frozenset(),
    "failed": frozenset({"draft", "cancelled"}),
    "rejected": frozenset(),
    "cancelled": frozenset(),
}


def transition(
    current: str, target: str, *, evidence_ready: bool = False
) -> str:
    """Validate candidate lifecycle; never generates approval."""
    if target not in TRANSITIONS.get(current, frozenset()):
        raise CyranoError("INVALID_TRANSITION", f"{current} -> {target}")
    if target == "promoted" and not evidence_ready:
        raise CyranoError(
            "PROMOTION_NOT_AUTHORIZED",
            "verified receipts are required",
        )
    return target


def plan_transition(
    current: str,
    target: str,
    *,
    reviewed: bool = False,
    decision_ready: bool = False,
    permit_ready: bool = False,
) -> str:
    """Validate the governed plan lifecycle.

    Three separate gates, none implied by the others: review evidence
    before human review, a resolved human decision before approval,
    and an execution permission before ``executable``. A plan that was
    approved can still return to ``amendment_requested`` when the
    subject digest changes.
    """
    if target not in PLAN_TRANSITIONS.get(current, frozenset()):
        raise CyranoError("INVALID_TRANSITION", f"{current} -> {target}")
    if current == "in_review" and target == "human_review" and (not reviewed):
        raise CyranoError(
            "REVIEW_REQUIRED", "independent review must finish first"
        )
    if target == "approved" and not decision_ready:
        raise CyranoError(
            "APPROVAL_REQUIRED", "no approved plan decision exists"
        )
    if target == "executable" and not permit_ready:
        raise CyranoError(
            "APPROVAL_REQUIRED",
            "plan approval is not execution permission",
        )
    return target
