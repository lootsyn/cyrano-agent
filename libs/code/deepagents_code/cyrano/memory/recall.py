"""Recall selection: ACL, freshness, and status before ranking.

Only ``active`` records inside the caller's scope are eligible; a
candidate is never injected. When nothing has enough grounding the
result is empty with an explicit reason — abstaining beats inventing.
"""

from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.memory.models import MemoryRecord


@dataclass(frozen=True, slots=True)
class RecallResult:
    """A recall view with the exclusion reason when empty."""

    records: tuple[MemoryRecord, ...]
    reason: str  # "ok" | "no_recall" | "abstain"
    excluded: tuple[str, ...]


def select_recall(
    records: list[MemoryRecord],
    scope_id: str,
    now: int,
    available_source_digests: frozenset[str],
    *,
    query_terms: frozenset[str] | None = None,
    limit: int = 10,
) -> RecallResult:
    """Filter scope/status/freshness, then rank — never leak.

    Order of operations is contractual: ACL first, then status and
    expiry, then digest freshness, then rank. An excluded record's
    body, hit count and diagnostics never surface.
    """
    if limit < 0:
        raise CyranoError("INVALID_LIMIT", "limit must be nonnegative")
    excluded: list[str] = []
    eligible: list[MemoryRecord] = []
    for record in records:
        if record.scope_id != scope_id:
            # Cross-scope records leave no trace — not even an id in
            # the exclusion list.
            continue
        if record.status != "active":
            excluded.append(record.memory_id)
            continue
        if record.expires_at is not None and now >= record.expires_at:
            excluded.append(record.memory_id)
            continue
        if record.source_digest not in available_source_digests:
            excluded.append(record.memory_id)
            continue
        if not record.evidence_refs:
            excluded.append(record.memory_id)
            continue
        eligible.append(record)
    if query_terms is not None:
        eligible = [
            r for r in eligible if any(term in r.kind for term in query_terms)
        ]
    eligible.sort(key=lambda r: (-r.rank, r.memory_id))
    chosen = tuple(eligible[:limit])
    reason = "ok" if chosen else "no_recall"
    return RecallResult(chosen, reason, tuple(sorted(excluded)))
