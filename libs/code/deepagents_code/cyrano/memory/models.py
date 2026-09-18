"""Memory record value types.

Candidates and actives are separate states; a proposal never becomes
active without an explicit release decision. Status is a closed set —
``stale`` and ``deleted`` records still exist for audit but are never
returned by recall.
"""

from dataclasses import dataclass
from typing import Literal

MemoryStatus = Literal[
    "candidate", "active", "stale", "quarantined", "deleted"
]


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """One durable memory bound to an exact scope and digests."""

    memory_id: str
    revision: int
    scope_id: str
    kind: str
    status: MemoryStatus
    content_digest: str
    source_digest: str
    evidence_refs: tuple[str, ...]
    created_at: int
    expires_at: int | None
    supersedes: str | None
    rank: int = 0


@dataclass(frozen=True, slots=True)
class RecallHint:
    """An event-triggered recall candidate bound to identity."""

    hint_id: str
    memory_id: str
    revision: int
    trigger: str
    epoch: str
    expires_at: int


@dataclass(frozen=True, slots=True)
class ApplicationVerdict:
    """How far a memory's use is proven — never inflated."""

    state: str  # referenced | applied | unknown
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DeletionReceipt:
    """A tombstone plus the recorded pending purge range."""

    memory_id: str
    tombstone_id: str
    pending_purge: tuple[str, ...]
