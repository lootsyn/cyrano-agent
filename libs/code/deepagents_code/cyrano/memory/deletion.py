"""Deletion: tombstones with pending purge ranges.

Deleting a record removes it from active search, FTS projections and
exports immediately; the tombstone preserves only the minimal
identity needed for audit. A purge receipt names the projections
still pending so lag never looks like resurrection.
"""

import hashlib
import json

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.memory.models import DeletionReceipt
from deepagents_code.cyrano.memory.repository import MemoryRepository


def delete_memory(
    repository: MemoryRepository,
    scope_id: str,
    memory_id: str,
    *,
    at: int,
    pending_projections: tuple[str, ...] = (),
) -> DeletionReceipt:
    """Tombstone a record; the body leaves every live view."""
    record = repository.get(scope_id, memory_id)
    if record is None:
        raise CyranoError("SCOPE_DENIED", "memory not readable in this scope")
    repository.transition(
        scope_id,
        memory_id,
        "deleted",
        expected_revision=record.revision,
        at=at,
    )
    tombstone = json.dumps(
        {"memory_id": memory_id, "at": at, "scope": scope_id},
        sort_keys=True,
    )
    return DeletionReceipt(
        memory_id=memory_id,
        tombstone_id="sha256:"
        + hashlib.sha256(tombstone.encode()).hexdigest(),
        pending_purge=pending_projections,
    )
