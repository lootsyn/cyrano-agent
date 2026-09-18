"""Context binding: pin the memory view and re-check permits at commit.

A binding pins the memory release digest so a query-view change and a
release change are distinguished. Revocation between compile and bind
produces a pause, not a stale authorized context, and a revoked memory
entry can never be served from cache.
"""

from collections.abc import Callable
from dataclasses import dataclass

from deepagents_code.cyrano.context.compiler import CompiledContext
from deepagents_code.cyrano.context.epochs import ContextEpoch
from deepagents_code.cyrano.contracts.types import CyranoError


@dataclass(frozen=True, slots=True)
class MemoryView:
    """The pinned set of memory entries a context may serve."""

    view_digest: str
    release_digest: str
    revoked_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class BindingReceipt:
    """Proof a context was bound to a live permit and epoch."""

    epoch_id: str
    stable_digest: str
    permit_id: str
    memory_view_digest: str


def bind_context(
    compiled: CompiledContext,
    epoch: ContextEpoch,
    *,
    permit_id: str,
    is_revoked: Callable[[str], bool],
    memory_view: MemoryView,
) -> BindingReceipt:
    """Re-verify the permit at commit; revocation pauses binding."""
    if is_revoked(permit_id):
        raise CyranoError("PERMIT_REVOKED", "rebind after re-approval")
    if epoch.memory_view_digest != memory_view.view_digest:
        raise CyranoError("STALE_EPOCH", "memory view changed")
    return BindingReceipt(
        epoch_id=epoch.epoch_id,
        stable_digest=compiled.stable_digest,
        permit_id=permit_id,
        memory_view_digest=memory_view.view_digest,
    )


def memory_entry_usable(entry_id: str, view: MemoryView) -> bool:
    """A revoked memory entry is never servable, cache be damned."""
    return entry_id not in view.revoked_ids
