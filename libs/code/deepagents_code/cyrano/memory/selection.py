"""Exact-scope, time-bounded selection; relevance is not authority."""

from dataclasses import dataclass
from datetime import datetime

from deepagents_code.cyrano.contracts.types import CyranoError, Scope


@dataclass(frozen=True, slots=True)
class Memory:
    """Verified memory metadata; bodies stay access-controlled."""

    memory_id: str
    scope: Scope
    status: str
    valid_until: datetime
    required_digests: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    content_ref: str
    rank: int = 0


def select_memories(
    records: list[Memory],
    scope: Scope,
    now: datetime,
    available_digests: frozenset[str],
    *,
    limit: int = 10,
) -> list[Memory]:
    """Filter scope and freshness before ranking; no fallback."""
    if now.tzinfo is None or any(
        r.valid_until.tzinfo is None for r in records
    ):
        raise CyranoError(
            "NAIVE_TIME", "timestamps need an explicit UTC offset"
        )
    if limit < 0:
        raise CyranoError("INVALID_LIMIT", "limit must be nonnegative")
    allowed = [
        record
        for record in records
        if record.scope == scope
        and record.status == "active"
        and record.valid_until > now
        and record.evidence_refs
        and set(record.required_digests).issubset(available_digests)
    ]
    return sorted(
        allowed, key=lambda record: (-record.rank, record.memory_id)
    )[:limit]
