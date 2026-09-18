"""Signed permits and the human approval desk.

A permit is Ed25519-signed over its canonical subject fields: the
shown display digest, the authenticated user event, scope, purpose,
nonce, and expiry. A model boolean or a renamed field is not a
permit; verification order is signature, revocation, expiry,
purpose, then subject.
"""

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, replace

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from deepagents_code.cyrano.contracts.canonical import (
    canonical_bytes,
    digest,
)
from deepagents_code.cyrano.contracts.types import CyranoError

PURPOSES = frozenset({"plan_approval", "execute", "spec", "release"})


@dataclass(frozen=True, slots=True)
class SignedPermit:
    """An Ed25519-signed authorization bound to a subject digest."""

    permit_id: str
    subject_digest: str
    shown_digest: str
    user_event_id: str
    scope_id: str
    purpose: str
    audience: str
    nonce: str
    issued_at: int
    expires_at: int
    signature: str


def _permit_body(permit: SignedPermit) -> bytes:
    """Canonical signing preimage; the signature is never signed."""
    fields = {k: v for k, v in asdict(permit).items() if k != "signature"}
    return canonical_bytes(fields)


def issue_permit(
    key: Ed25519PrivateKey,
    *,
    permit_id: str,
    subject_digest: str,
    shown_digest: str,
    user_event_id: str,
    scope_id: str,
    purpose: str,
    audience: str,
    nonce: str,
    issued_at: int,
    expires_at: int,
) -> SignedPermit:
    """Sign a permit; every authorization field is in the preimage."""
    if purpose not in PURPOSES:
        raise CyranoError("WRONG_APPROVAL_ACTION", purpose)
    unsigned = SignedPermit(
        permit_id=permit_id,
        subject_digest=subject_digest,
        shown_digest=shown_digest,
        user_event_id=user_event_id,
        scope_id=scope_id,
        purpose=purpose,
        audience=audience,
        nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
        signature="",
    )
    signature = key.sign(_permit_body(unsigned)).hex()
    return replace(unsigned, signature=signature)


def verify_permit(
    permit: SignedPermit,
    trust_root: Ed25519PublicKey,
    *,
    purpose: str,
    subject_digest: str,
    now: int,
    is_revoked: Callable[[str], bool],
) -> None:
    """Verify a permit; every failure is a typed refusal."""
    body = _permit_body(permit)
    try:
        trust_root.verify(bytes.fromhex(permit.signature), body)
    except (InvalidSignature, ValueError) as exc:
        raise CyranoError("INVALID_SIGNATURE", permit.permit_id) from exc
    if is_revoked(permit.permit_id):
        raise CyranoError("PERMIT_REVOKED", permit.permit_id)
    if now >= permit.expires_at:
        raise CyranoError("PERMIT_EXPIRED", permit.permit_id)
    if permit.purpose != purpose:
        raise CyranoError(
            "WRONG_APPROVAL_ACTION",
            f"{permit.purpose} used as {purpose}",
        )
    if permit.subject_digest != subject_digest:
        raise CyranoError("SUBJECT_MISMATCH", permit.subject_digest)


@dataclass(frozen=True, slots=True)
class DisplayRecord:
    """What the user actually saw; receipts bind to its digest."""

    request_id: str
    display_revision: int
    display_digest: str
    subject_digest: str
    audience: str
    nonce: str
    expires_at: int
    purpose: str
    dependencies: Mapping[str, tuple[str, ...]]


@dataclass(slots=True)
class DecisionResult:
    """A human decision outcome; receipt is absent unless approved."""

    status: str
    decision_kind: str = ""
    receipt_digest: str | None = None
    permitted: tuple[str, ...] = ()


class ApprovalDesk:
    """Approval request lifecycle: display, decide, receipt.

    Only an explicit structured approve over a currently shown
    display produces a receipt. Defer, close, request_changes, and
    key events before display-open produce no approval.
    """

    def __init__(self) -> None:
        """Start an empty desk; nothing is pre-approved."""
        self._requests: dict[str, DisplayRecord] = {}
        self._opened: set[str] = set()
        self._decisions: dict[str, DecisionResult] = {}
        self._seq: int = 0

    def present(
        self,
        *,
        subject_digest: str,
        shown_text: str,
        audience: str,
        nonce: str,
        expires_at: int,
        purpose: str = "plan_approval",
        dependencies: Mapping[str, tuple[str, ...]] | None = None,
    ) -> DisplayRecord:
        """Open a pending request bound to the shown bytes' digest."""
        self._seq += 1
        record = DisplayRecord(
            request_id=f"req{self._seq}",
            display_revision=1,
            display_digest=digest(
                {"text": shown_text, "subject": subject_digest}
            ),
            subject_digest=subject_digest,
            audience=audience,
            nonce=nonce,
            expires_at=expires_at,
            purpose=purpose,
            dependencies=dict(dependencies or {}),
        )
        self._requests[record.request_id] = record
        return record

    def open_display(self, request_id: str) -> None:
        """Mark the display as actually opened for explicit choice."""
        if request_id in self._requests:
            self._opened.add(request_id)

    def revise_display(self, request_id: str, shown_text: str) -> None:
        """Bump the display revision; older client views go stale."""
        record = self._requests[request_id]
        self._requests[request_id] = replace(
            record,
            display_revision=record.display_revision + 1,
            display_digest=digest(
                {
                    "text": shown_text,
                    "subject": record.subject_digest,
                }
            ),
        )

    def submit(
        self,
        request_id: str,
        *,
        actor: str,
        nonce: str,
        decision: str,
        shown_text: str,
        display_revision: int,
        client_event_id: str,
        now: int,
        choices: tuple[str, ...] = (),
        amendment_artifact_id: str | None = None,
    ) -> DecisionResult:
        """Record a decision; only explicit approve yields a receipt."""
        record = self._requests.get(request_id)
        if record is None:
            raise CyranoError("UNKNOWN_REQUEST", request_id)
        if actor != record.audience:
            raise CyranoError("ACL_DENIED", actor)
        if nonce != record.nonce:
            raise CyranoError("NONCE_MISMATCH", nonce)
        existing = self._decisions.get(client_event_id)
        if existing is not None:
            marker = digest(
                {
                    "request": request_id,
                    "decision": decision,
                    "actor": actor,
                }
            )
            prior = digest(
                {
                    "request": request_id,
                    "decision": existing.decision_kind,
                    "actor": actor,
                }
            )
            if marker == prior:
                return existing
            raise CyranoError("IDEMPOTENCY_CONFLICT", client_event_id)
        if now >= record.expires_at:
            raise CyranoError("DECISION_EXPIRED", request_id)
        if (
            digest({"text": shown_text, "subject": record.subject_digest})
            != record.display_digest
        ):
            raise CyranoError("DISPLAY_INTEGRITY_FAILURE", request_id)
        if display_revision != record.display_revision:
            raise CyranoError("STALE_DISPLAY", request_id)
        if decision == "approve" and amendment_artifact_id:
            raise CyranoError(
                "INPUT_INVALID",
                "structured approve carries no amendment",
            )
        if decision != "approve" or request_id not in self._opened:
            result = DecisionResult(status="deferred", decision_kind=decision)
            self._decisions[client_event_id] = result
            return result
        permitted = tuple(choices) if choices else ("*",)
        if choices:
            for choice in choices:
                required = set(record.dependencies.get(choice, ()))
                missing = required - set(choices)
                if missing:
                    raise CyranoError(
                        "DEPENDENCY_NOT_AUTHORIZED",
                        f"{choice} requires {sorted(missing)}",
                    )
        receipt = digest(
            {
                "subject": record.subject_digest,
                "nonce": nonce,
                "actor": actor,
                "client_event": client_event_id,
                "purpose": record.purpose,
            }
        )
        result = DecisionResult(
            status="approved",
            decision_kind=decision,
            receipt_digest=receipt,
            permitted=permitted,
        )
        self._decisions[client_event_id] = result
        return result

    def settle(self, request_id: str, now: int) -> str:
        """A request with no user event expires; it never approves."""
        record = self._requests[request_id]
        if now >= record.expires_at:
            return "expired"
        return "pending"
