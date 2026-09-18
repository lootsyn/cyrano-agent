"""Legacy approval conversion guard.

Legacy signature bytes are preserved as evidence but never become
execution authority. A new TrustedApprovalReceipt with an exact
binding and a separate approval is required before any legacy
artifact may authorize work.
"""

from dataclasses import dataclass
from typing import Literal, Mapping

from deepagents_code.cyrano.contracts.canonical import raw_digest
from deepagents_code.cyrano.contracts.ingress import (
    JSON,
    parse_document,
)
from deepagents_code.cyrano.contracts.types import CyranoError


@dataclass(frozen=True, slots=True)
class LegacyApproval:
    """Preserved legacy approval bytes plus non-authoritative claims."""

    raw: bytes
    raw_digest: str
    format: str
    claims: Mapping[str, JSON]

    @property
    def executable(self) -> Literal[False]:
        """Legacy bytes can never authorize execution directly."""
        return False


def inspect_legacy_approval(raw: bytes) -> LegacyApproval:
    """Preserve and classify legacy approval bytes without authority."""
    claims: Mapping[str, JSON] = {}
    format_name = "unknown"
    try:
        document = parse_document(raw)
    except CyranoError:
        document = {}
    if document:
        kind = document.get("kind")
        if kind == "permit":
            format_name = "permit_v1"
        elif kind == "trusted_approval_receipt":
            format_name = "approval_v2"
        claims = document
    return LegacyApproval(
        raw=raw,
        raw_digest=raw_digest(raw),
        format=format_name,
        claims=claims,
    )


def derive_authority(legacy: LegacyApproval) -> None:
    """Renaming legacy signature fields is never authority."""
    raise CyranoError(
        "LEGACY_AUTHORITY",
        f"{legacy.format} bytes require a separately approved receipt",
    )


def require_receipt_binding(
    legacy: LegacyApproval, receipt: Mapping[str, JSON]
) -> str:
    """Bind preserved bytes to a new TrustedApprovalReceipt.

    Returns the receipt's recorded binding for the legacy artifact;
    the receipt still needs its own approval before it authorizes.
    """
    if receipt.get("kind") != "trusted_approval_receipt":
        raise CyranoError(
            "LEGACY_AUTHORITY",
            "only a trusted_approval_receipt may bind legacy bytes",
        )
    bindings = receipt.get("bindings")
    if not isinstance(bindings, dict):
        raise CyranoError("MISSING_RECEIPT_BINDING", "receipt has no bindings")
    bound = [
        value for value in bindings.values() if value == legacy.raw_digest
    ]
    if not bound:
        raise CyranoError(
            "MISSING_RECEIPT_BINDING",
            "receipt does not reference the preserved digest",
        )
    return str(bound[0])
