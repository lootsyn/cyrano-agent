"""Resume-safe decision handling after interrupt or restart.

A resumed node re-presents the same pending decision instead of
minting a second request, nonce, reservation, or tool effect. The
same ``decision_id`` returns the same request; a different payload
under the same id is an idempotency conflict, never a second grant.
"""

from __future__ import annotations

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.planning.decisions import (
    DecisionDesk,
    DecisionRequest,
)


def resume_pending(
    desk: DecisionDesk,
    decision_id: str,
    scope: str,
    purpose: str,
    subject_digest: str,
    display_digest: str,
    *,
    revision: int = 0,
    ttl: int = 600,
) -> DecisionRequest:
    """Re-present an interrupted decision without duplicating it.

    A pending request returns as-is so a re-executed node cannot
    double-book a nonce, budget reservation, or outbox row.
    """
    existing = desk.load(decision_id)
    if existing is not None:
        if existing.state != "pending":
            raise CyranoError(
                "DECISION_SETTLED",
                f"{decision_id} is {existing.state}; cannot resume",
            )
        if (
            existing.subject_digest != subject_digest
            or existing.display_digest != display_digest
            or existing.purpose != purpose
        ):
            raise CyranoError(
                "IDEMPOTENCY_CONFLICT",
                "same decision_id, different sealed content",
            )
        return existing
    return desk.present(
        decision_id,
        scope,
        purpose,
        subject_digest,
        display_digest,
        revision=revision,
        ttl=ttl,
    )
