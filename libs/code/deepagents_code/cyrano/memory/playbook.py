"""Pure playbook-delta validation; publication remains broker-owned."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal


class DeltaError(ValueError):
    """Reject a stale, unauthorized, or ungrounded playbook change."""


@dataclass(frozen=True)
class PlaybookEntry:
    """Hold a bounded, revisioned note with evidence references."""

    entry_id: str
    revision: int
    scope: str
    text: str
    evidence: tuple[str, ...]
    protected: bool = False
    deprecated: bool = False


@dataclass(frozen=True)
class EntryDelta:
    """Propose one explicit operation against an entry revision."""

    operation: Literal["add", "refine", "deprecate"]
    entry_id: str
    expected_revision: int
    scope: str
    text: str
    evidence: tuple[str, ...]


def apply_delta(
    entries: tuple[PlaybookEntry, ...],
    delta: EntryDelta,
    *,
    expected_release: str,
    actual_release: str,
    permitted_scope: str,
    known_evidence: frozenset[str],
    max_chars: int,
) -> tuple[PlaybookEntry, ...]:
    """Validate a candidate revision without touching the release.

    Args:
        entries: Current candidates; each identity must be unique.
        delta: Proposed edit; deprecated entries cannot be refined.
        expected_release: Release identity used at proposal time.
        actual_release: Trusted release identity at validation time.
        permitted_scope: Scope resolved by the broker, not the proposal.
        known_evidence: Readable evidence IDs after scope/freshness.
        max_chars: Approved aggregate budget; not a token estimate.

    Returns:
        A new candidate tuple. Independent review, evaluation and
        approval are still required before its publication.

    Raises:
        DeltaError: Any precondition, evidence or capacity check fails.
    """
    if not actual_release or expected_release != actual_release:
        raise DeltaError("STALE_RELEASE")
    if (
        type(max_chars) is not int
        or max_chars < 1
        or delta.scope != permitted_scope
    ):
        raise DeltaError("SCOPE_OR_BUDGET")
    if type(delta.expected_revision) is not int:
        raise DeltaError("INVALID_REVISION")
    if any(entry.scope != permitted_scope for entry in entries):
        raise DeltaError("FOREIGN_BASE_ENTRY")
    if not delta.entry_id or not delta.evidence:
        raise DeltaError("UNGROUNDED_DELTA")
    if not set(delta.evidence) <= known_evidence:
        raise DeltaError("UNKNOWN_EVIDENCE")
    current = {entry.entry_id: entry for entry in entries}
    if len(current) != len(entries):
        raise DeltaError("DUPLICATE_ENTRY")
    old = current.get(delta.entry_id)
    if delta.operation == "add":
        if old is not None or delta.expected_revision != 0:
            raise DeltaError("ENTRY_EXISTS")
        if not delta.text.strip():
            raise DeltaError("EMPTY_ENTRY")
        new = PlaybookEntry(
            delta.entry_id,
            1,
            delta.scope,
            delta.text,
            delta.evidence,
        )
    elif delta.operation in {"refine", "deprecate"}:
        if old is None or old.revision != delta.expected_revision:
            raise DeltaError("STALE_ENTRY")
        if old.scope != permitted_scope or old.protected:
            raise DeltaError("PROTECTED_OR_FOREIGN_ENTRY")
        if old.deprecated:
            raise DeltaError("DEPRECATED_ENTRY")
        if delta.operation == "refine" and not delta.text.strip():
            raise DeltaError("EMPTY_ENTRY")
        new = replace(
            old,
            revision=old.revision + 1,
            text=delta.text if delta.operation == "refine" else old.text,
            evidence=tuple(dict.fromkeys(old.evidence + delta.evidence)),
            deprecated=delta.operation == "deprecate",
        )
    else:
        raise DeltaError("UNKNOWN_DELTA")
    current[delta.entry_id] = new
    result = tuple(current[key] for key in sorted(current))
    visible = [entry.text.strip() for entry in result if not entry.deprecated]
    if len(set(visible)) != len(visible):
        raise DeltaError("DUPLICATE_CONTENT")
    if sum(len(e.text) for e in result if not e.deprecated) > max_chars:
        raise DeltaError("CAPACITY_EXCEEDED")
    return result
