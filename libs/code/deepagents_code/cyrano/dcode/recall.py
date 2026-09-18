"""Task-triggered recall for the governed runtime.

The governed path must not depend on a harness staging memory records
by hand. When a run is recall-backed, ``run_governed_work`` derives a
``RecallContext`` from the real task inputs — task identity, authorized
scope, plan path hints, time and epoch — and resolves records, rule
bodies and a freshly pinned ``MemoryView`` from the live store before
the work plan is sealed.

Recall relevance is not authority: this stage returns candidates and
exclusion reasons; only ``project_obligations`` decides which recalled
``scope_rule`` records become obligations. A store failure surfaces as
``MEMORY_STORE_UNAVAILABLE`` — an empty or partial answer is never
fabricated.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.context.binding import MemoryView
from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.memory.models import MemoryRecord
from deepagents_code.cyrano.memory.obligations import is_scope_rule
from deepagents_code.cyrano.memory.recall import RecallResult
from deepagents_code.cyrano.memory.repository import MemoryRepository
from deepagents_code.cyrano.memory.service import MemoryService


@dataclass(frozen=True, slots=True)
class RecallContext:
    """The authorized query context derived from real task inputs.

    Every field is defined by the runtime — never by fixture ids:
    ``task_id`` is the run identity, ``scope_id`` the authorized
    memory namespace, ``path_hints`` the plan's declared write paths,
    ``limit`` the recall budget, ``now``/``epoch`` the current
    time/epoch binding.
    """

    task_id: str
    scope_id: str
    path_hints: tuple[str, ...]
    query_terms: frozenset[str] | None
    limit: int
    now: int
    epoch: str | None
    source_digests: frozenset[str]

    @property
    def query_digest(self) -> str:
        """Canonical digest of the query shape — no raw task text."""
        return digest(
            {
                "task_id": self.task_id,
                "scope_id": self.scope_id,
                "path_hints": list(self.path_hints),
                "query_terms": sorted(self.query_terms or ()),
                "limit": self.limit,
                "epoch": self.epoch,
            }
        )


@dataclass(frozen=True, slots=True)
class RecallEvidence:
    """Digest-only recall record for durable run evidence.

    Carries ids, revisions, digests and exclusion reasons — never
    memory bodies, task text, or model content.
    """

    query_digest: str
    view_digest: str
    returned: tuple[tuple[str, int], ...]
    excluded: tuple[tuple[str, str], ...]
    reason: str


@dataclass(frozen=True, slots=True)
class RecallOutcome:
    """Internal carrier: records and bodies feed projection.

    ``rule_bodies`` are access-controlled store content — present for
    ``project_obligations`` and never persisted in run evidence.
    """

    context: RecallContext
    records: tuple[MemoryRecord, ...]
    rule_bodies: Mapping[str, bytes]
    memory_view: MemoryView
    evidence: RecallEvidence


def classify_excluded(record: MemoryRecord, context: RecallContext) -> str:
    """Report why one record was ineligible at recall time."""
    if record.status != "active":
        return f"inactive:{record.status}"
    if record.expires_at is not None and context.now >= record.expires_at:
        return "expired"
    if record.source_digest not in context.source_digests:
        return "stale_source"
    if not record.evidence_refs:
        return "no_evidence"
    return "excluded"


def task_recall(
    *,
    service: MemoryService,
    repository: MemoryRepository,
    context: RecallContext,
) -> RecallOutcome:
    """Resolve one task's recall from the live store, pinned fresh.

    A fresh ``MemoryView`` is pinned from the store at recall time —
    a cached view can never smuggle a revoked or superseded record
    past the projection gates.
    """
    result: RecallResult = service.query_memory(
        context.scope_id,
        context.now,
        context.source_digests,
        query_terms=context.query_terms,
        limit=context.limit,
    )
    records = tuple(result.records)
    bodies: dict[str, bytes] = {}
    for record in records:
        if not is_scope_rule(record):
            continue
        body = repository.get_content(context.scope_id, record.content_digest)
        if body is not None:
            bodies[record.memory_id] = body
    all_records = repository.list_scope(context.scope_id)
    revoked = frozenset(
        r.memory_id for r in all_records if r.status != "active"
    )
    view = MemoryView(digest(sorted(revoked)), "task-recall", revoked)
    excluded = tuple(
        sorted(
            (
                mid,
                classify_excluded(
                    next(r for r in all_records if r.memory_id == mid),
                    context,
                ),
            )
            for mid in result.excluded
        )
    )
    evidence = RecallEvidence(
        query_digest=context.query_digest,
        view_digest=view.view_digest,
        returned=tuple(sorted((r.memory_id, r.revision) for r in records)),
        excluded=excluded,
        reason=result.reason,
    )
    return RecallOutcome(
        context=context,
        records=records,
        rule_bodies=bodies,
        memory_view=view,
        evidence=evidence,
    )


__all__ = (
    "RecallContext",
    "RecallEvidence",
    "RecallOutcome",
    "task_recall",
)
