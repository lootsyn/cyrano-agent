"""Human decision requests: a response is never a receipt by itself.

A ``DecisionRequest`` seals a purpose, subject digest, display digest,
nonce, revision, expiry, and the allowed response kinds. Purposes are
distinct: plan consent, execution permission, source apply, final
acceptance, and publish each need their own request and receipt.

Structured responses are ``approve / reject / defer / cancel /
request_changes / ask_question``. Free text is only a proposal — a
trusted parser may suggest ``request_changes`` but nothing is granted
until an explicit UI choice or trusted caller confirms. Silence,
window close, expiry, and replayed clicks create no authority.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError

PURPOSES = frozenset(
    {
        "design_choice",
        "plan_approval",
        "execution_permission",
        "source_apply",
        "acceptance",
        "publish",
    }
)
RESPONSES = frozenset(
    {
        "approve",
        "reject",
        "defer",
        "cancel",
        "request_changes",
        "ask_question",
    }
)


@dataclass(frozen=True, slots=True)
class DecisionRequest:
    """One pending decision bound to digests, nonce, and expiry."""

    decision_id: str
    scope: str
    purpose: str
    subject_digest: str
    display_digest: str
    request_revision: int
    nonce: str
    expires_at: int
    allowed_responses: tuple[str, ...]
    state: str = "pending"
    approved_units: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DecisionOutcome:
    """The adjudicated result; ``granted`` only on a valid approve."""

    granted: bool
    state: str
    decision_id: str
    purpose: str
    reason: str = ""


class DecisionDesk:
    """Present and adjudicate human decisions with CAS semantics."""

    def __init__(self, *, now: int = 0) -> None:
        """Decisions use a caller-supplied clock; never wall time."""
        self._now: int = now
        self._requests: dict[str, DecisionRequest] = {}

    def set_clock(self, now: int) -> None:
        """Advance the desk's monotonic decision clock."""
        self._now: int = now

    def present(
        self,
        decision_id: str,
        scope: str,
        purpose: str,
        subject_digest: str,
        display_digest: str,
        *,
        revision: int = 0,
        ttl: int = 600,
        allowed_responses: tuple[str, ...] | None = None,
    ) -> DecisionRequest:
        """Create a pending request; presenting grants no authority.

        Re-presenting the same ``decision_id`` returns the existing
        request — resume must not mint a second nonce for the same
        decision.
        """
        if purpose not in PURPOSES:
            raise CyranoError("INVALID_PURPOSE", purpose)
        existing = self._requests.get(decision_id)
        if existing is not None:
            if (
                existing.subject_digest != subject_digest
                or existing.purpose != purpose
            ):
                raise CyranoError(
                    "IDEMPOTENCY_CONFLICT",
                    "same decision_id, different subject",
                )
            return existing
        allowed = (
            tuple(sorted(RESPONSES))
            if allowed_responses is None
            else allowed_responses
        )
        unknown = set(allowed) - RESPONSES
        if unknown:
            raise CyranoError("INVALID_RESPONSE_KIND", f"{sorted(unknown)}")
        request = DecisionRequest(
            decision_id=decision_id,
            scope=scope,
            purpose=purpose,
            subject_digest=subject_digest,
            display_digest=display_digest,
            request_revision=revision,
            nonce=secrets.token_hex(8),
            expires_at=self._now + ttl,
            allowed_responses=allowed,
        )
        self._requests[decision_id] = request
        return request

    def load(self, decision_id: str) -> DecisionRequest | None:
        """Read a pending or settled request."""
        return self._requests.get(decision_id)

    def record_response(
        self,
        decision_id: str,
        response: str,
        *,
        nonce: str,
        subject_digest: str,
        display_digest: str,
        expected_revision: int,
        approved_units: tuple[str, ...] = (),
    ) -> DecisionOutcome:
        """Adjudicate a structured response; replay-safe.

        A response grants authority only when nonce, revision, and
        both digests match the live request and it is unexpired.
        Everything else leaves the request ``pending``/terminal with
        no grant.
        """
        request = self._requests.get(decision_id)
        if request is None:
            raise CyranoError("UNKNOWN_DECISION", decision_id)
        if request.state != "pending":
            return DecisionOutcome(
                granted=False,
                state=request.state,
                decision_id=decision_id,
                purpose=request.purpose,
                reason="already settled; replay has no effect",
            )
        if self._now > request.expires_at:
            request = self._replace(request, state="expired")
            self._requests[decision_id] = request
            return DecisionOutcome(
                granted=False,
                state="expired",
                decision_id=decision_id,
                purpose=request.purpose,
                reason="decision request expired",
            )
        if response not in request.allowed_responses:
            raise CyranoError("INVALID_RESPONSE_KIND", response)
        if (
            nonce != request.nonce
            or expected_revision != request.request_revision
            or subject_digest != request.subject_digest
            or display_digest != request.display_digest
        ):
            raise CyranoError(
                "PERMIT_STALE",
                "response does not match the displayed request",
            )
        state = {
            "approve": "approved",
            "reject": "rejected",
            "defer": "deferred",
            "cancel": "cancelled",
            "request_changes": "amend_requested",
            "ask_question": "deferred",
        }[response]
        request = self._replace(
            request, state=state, approved_units=approved_units
        )
        self._requests[decision_id] = request
        return DecisionOutcome(
            granted=response == "approve",
            state=state,
            decision_id=decision_id,
            purpose=request.purpose,
        )

    def expire_pending(self) -> tuple[str, ...]:
        """Expire unanswered requests; expiry grants nothing."""
        expired = []
        for key, request in self._requests.items():
            if request.state == "pending" and self._now > request.expires_at:
                self._requests[key] = self._replace(request, state="expired")
                expired.append(key)
        return tuple(expired)

    @staticmethod
    def _replace(
        request: DecisionRequest, **fields: object
    ) -> DecisionRequest:
        from dataclasses import replace

        updated = replace(request, **fields)
        return updated


def partial_approval_units(
    approved: tuple[str, ...],
    dependencies: dict[str, tuple[str, ...]],
) -> tuple[str, ...]:
    """Keep only approved units whose deps are all approved.

    Partial approval applies to dependency-closed subsets only: an
    approved unit that needs an unapproved dependency is held back,
    and "approve A" never becomes a whole-plan permit.
    """
    approved_set = set(approved)
    allowed = []
    changed = True
    # Fixed point: drop units until every kept unit's deps are kept.
    pending = set(approved_set)
    while changed:
        changed = False
        for unit in list(pending):
            if not set(dependencies.get(unit, ())) <= pending:
                pending.discard(unit)
                changed = True
    for unit in approved:
        if unit in pending:
            allowed.append(unit)
    return tuple(allowed)
