"""Invalidation and dependency closure.

Correcting or deleting a memory invalidates everything derived from
it — superseded records, cached hints, projections, exports. The
closure is computed explicitly; nothing downstream may keep serving
stale facts for cache warmth.
"""

from deepagents_code.cyrano.memory.repository import MemoryRepository


def dependency_closure(
    repository: MemoryRepository,
    scope_id: str,
    root_id: str,
) -> list[str]:
    """All records derived from ``root_id`` via supersedes links."""
    records = {r.memory_id: r for r in repository.list_scope(scope_id)}
    closure: list[str] = []
    frontier = [root_id]
    while frontier:
        current = frontier.pop()
        for record in records.values():
            if record.supersedes == current and (
                record.memory_id not in closure
            ):
                closure.append(record.memory_id)
                frontier.append(record.memory_id)
    return closure


def invalidate_memory(
    repository: MemoryRepository,
    scope_id: str,
    memory_id: str,
    *,
    at: int,
) -> list[str]:
    """Stale a record and every dependent; returns the closure."""
    record = repository.get(scope_id, memory_id)
    if record is None:
        return []
    affected = [
        memory_id,
        *dependency_closure(repository, scope_id, memory_id),
    ]
    for mid in affected:
        current = repository.get(scope_id, mid)
        if current is not None and current.status == "active":
            repository.transition(
                scope_id,
                mid,
                "stale",
                expected_revision=current.revision,
                at=at,
            )
    return affected
