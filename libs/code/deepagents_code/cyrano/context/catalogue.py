"""Fixed skill/tool catalogue: metadata is stable, bodies load lazily.

The catalogue resolves only declared metadata; a body is read through
an injected loader only when the current task selects it. Selection
never loads every body into the stable prefix.
"""

from collections.abc import Callable
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.canonical import raw_digest
from deepagents_code.cyrano.contracts.types import CyranoError


@dataclass(frozen=True, slots=True)
class CatalogueEntry:
    """Declared metadata for one skill or tool; body stays off-heap."""

    entry_id: str
    kind: str
    metadata_digest: str
    body_digest: str


def resolve_catalogue(
    entries: list[CatalogueEntry],
) -> tuple[CatalogueEntry, ...]:
    """Return the fixed metadata set; duplicate ids are invalid."""
    ids = [e.entry_id for e in entries]
    if len(ids) != len(set(ids)):
        raise CyranoError("INPUT_INVALID", "duplicate catalogue id")
    return tuple(sorted(entries, key=lambda e: e.entry_id))


def select_bodies(
    catalogue: tuple[CatalogueEntry, ...],
    needed_ids: frozenset[str],
    loader: Callable[[CatalogueEntry], bytes],
) -> dict[str, bytes]:
    """Load bodies only for selected entries; verify each digest."""
    known = {e.entry_id: e for e in catalogue}
    missing = needed_ids - known.keys()
    if missing:
        raise CyranoError("UNKNOWN_CATALOGUE_ENTRY", ",".join(sorted(missing)))
    bodies: dict[str, bytes] = {}
    for entry_id in sorted(needed_ids):
        data = loader(known[entry_id])
        if raw_digest(data) != known[entry_id].body_digest:
            raise CyranoError("BODY_DIGEST_MISMATCH", entry_id)
        bodies[entry_id] = data
    return bodies
