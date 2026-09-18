"""Interview decision log: authority, delegation, and rescission.

A model proposal is never a decision. High-impact choices need an
explicit user authorization; delegated domains cover only low-risk
internal choices. Rescinding a decision preserves the original record
and returns the invalidated dependents so scenarios, reviews, and
bundle approvals are recomputed rather than silently kept.
"""

from dataclasses import dataclass, replace
from typing import Mapping

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.interview.readiness import affected_closure

DELEGATED_DOMAINS = frozenset({"internal_structure", "internal_choice"})

DECISION_STATUS = frozenset({"proposed", "decided", "superseded", "revoked"})


@dataclass(frozen=True, slots=True)
class Decision:
    """One decision record; the original text is never rewritten."""

    decision_id: str
    text: str
    authority: str
    domain: str
    impact: str
    revision: int
    status: str = "proposed"


class DecisionLog:
    """Append-style decision store; history is preserved."""

    def __init__(self, delegated: frozenset[str] = DELEGATED_DOMAINS):
        """Bind the delegation scope; outside it needs a user."""
        self._delegated = delegated
        self._decisions: dict[str, Decision] = {}
        self._history: list[Decision] = []

    def propose(
        self,
        decision_id: str,
        text: str,
        *,
        proposer: str,
        domain: str,
        impact: str,
        revision: int,
        user_authorized: bool = False,
    ) -> Decision:
        """Record a decision; unauthorized promotion is refused."""
        if proposer == "model":
            if impact == "high" and not user_authorized:
                raise CyranoError("UNAUTHORIZED_DECISION", decision_id)
            if domain not in self._delegated and not user_authorized:
                raise CyranoError("UNAUTHORIZED_DECISION", decision_id)
        status = (
            "decided"
            if (proposer == "user" or user_authorized)
            else ("proposed")
        )
        if domain in self._delegated and impact == "low":
            status = "decided"
        decision = Decision(
            decision_id=decision_id,
            text=text,
            authority=(
                "user"
                if user_authorized or proposer == "user"
                else "delegated"
                if status == "decided"
                else proposer
            ),
            domain=domain,
            impact=impact,
            revision=revision,
            status=status,
        )
        if (
            decision_id in self._decisions
            and self._decisions[decision_id].status == "decided"
            and self._decisions[decision_id].text != text
        ):
            raise CyranoError("DECISION_CONFLICT", decision_id)
        self._decisions[decision_id] = decision
        self._history.append(decision)
        return decision

    def get(self, decision_id: str) -> Decision:
        """Return the current record or raise."""
        try:
            return self._decisions[decision_id]
        except KeyError:
            raise CyranoError("UNKNOWN_DECISION", decision_id) from None

    def rescind(
        self,
        decision_id: str,
        *,
        dependents: Mapping[str, set[str]],
    ) -> frozenset[str]:
        """Supersede a decision and return the invalidation closure.

        The original record stays in history; dependents (scenarios,
        reviews, bundle approvals) come back as review work.
        """
        current = self.get(decision_id)
        if current.status == "revoked":
            raise CyranoError("DECISION_CONFLICT", decision_id)
        self._decisions[decision_id] = replace(current, status="revoked")
        self._history.append(self._decisions[decision_id])
        return frozenset(affected_closure({decision_id}, dict(dependents)))

    def history(self, decision_id: str) -> tuple[Decision, ...]:
        """All versions of a decision, oldest first."""
        return tuple(d for d in self._history if d.decision_id == decision_id)

    def all_current(self) -> tuple[Decision, ...]:
        """Current record for every known decision id."""
        return tuple(self._decisions.values())
