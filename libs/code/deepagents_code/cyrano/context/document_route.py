"""Deterministic, scoped document selection for Cyrano work items.

The product-side router receives its inputs explicitly — a parsed
document catalog, a parsed routing table, and a byte reader — so it
never assumes the development checkout layout at
``Path(__file__).parents[...]``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

from deepagents_code.cyrano.contracts.types import CyranoError

FORBIDDEN = frozenset({"generated", "historical", "evidence"})
STAGES = frozenset({"plan", "implement", "test"})


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    """One verified source bound to its digest and authority label."""

    path: str
    category: str
    sha256: str
    size: int


@dataclass(frozen=True, slots=True)
class Readset:
    """A verified manifest plus the exact bodies it describes."""

    manifest: dict[str, object]
    documents: tuple[tuple[str, str], ...]


def _mapping(value: object) -> Mapping[str, object]:
    """Require a string-keyed mapping at a JSON parsing boundary.

    Returns:
        The mapping with string keys.

    Raises:
        CyranoError: ``INVALID_ROUTE_DOCUMENT`` for non-mapping input.
    """
    if not isinstance(value, dict):
        raise CyranoError("INVALID_ROUTE_DOCUMENT", "expected an object")
    return {str(key): item for key, item in value.items()}


def _as_items(value: object) -> list[object]:
    """Require a list without silently coercing a missing field.

    Returns:
        The list unchanged.

    Raises:
        CyranoError: ``INVALID_ROUTE_DOCUMENT`` for non-list input.
    """
    if not isinstance(value, list):
        raise CyranoError("INVALID_ROUTE_DOCUMENT", "expected an array")
    result: list[object] = list(value)
    return result


def _strings(value: object) -> list[str]:
    """Require a list of non-empty strings; coercion is not allowed.

    Returns:
        The validated string list.

    Raises:
        CyranoError: ``INVALID_ROUTE_DOCUMENT`` for malformed input.
    """
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise CyranoError(
            "INVALID_ROUTE_DOCUMENT",
            "expected an array of strings",
        )
    return [str(item) for item in value]


def _entry_paths(
    routing: Mapping[str, object],
    task: str,
    stage: str,
) -> list[str]:
    tasks = _mapping(routing.get("tasks", {}))
    if task not in tasks:
        raise CyranoError("UNKNOWN_TASK", task)
    stages = _mapping(_mapping(routing.get("stages", {})).get(task, {}))
    selected = _strings(stages.get(stage, tasks[task]))
    always = _strings(routing.get("always", []))
    return list(dict.fromkeys(always + selected))


def select_readset(
    *,
    task: str,
    catalog: Mapping[str, object],
    routing: Mapping[str, object],
    read_bytes: Callable[[str], bytes],
    stage: str = "implement",
    max_bytes: int = 98304,
    allow_reference: bool = False,
) -> Readset:
    """Select the same documents for the same inputs, every time.

    Args:
        task: Registered work-item identifier.
        catalog: Parsed ``document-catalog.json`` with ``documents``
            entries.
        routing: Parsed ``document-routing.json`` with ``tasks`` and
            ``always`` plus optional per-``stage`` overrides.
        read_bytes: Injected reader; the router performs no implicit
            I/O.
        stage: One of ``plan``, ``implement``, ``test``.
        max_bytes: Total UTF-8 source budget; excess is an error,
            never a silent truncation.
        allow_reference: Permit ``reference``-category sources. Their
            label is preserved; they are never promoted to policy.

    Returns:
        A manifest with per-document digests plus ordered path and
        content pairs.

    Raises:
        CyranoError: On unknown tasks, unsafe budgets, unregistered
            documents, forbidden categories, missing reference consent,
            or stale digests.
    """
    if stage not in STAGES:
        raise CyranoError("UNKNOWN_STAGE", stage)
    if not isinstance(max_bytes, int) or max_bytes < 1:
        raise CyranoError("INVALID_READSET_BUDGET", str(max_bytes))
    documents = _as_items(catalog.get("documents", []))
    entries = {
        str(item["path"]): item
        for item in [_mapping(raw) for raw in documents]
        if isinstance(item.get("path"), str)
    }
    records: list[DocumentRecord] = []
    bodies: list[tuple[str, str]] = []
    for path in _entry_paths(routing, task, stage):
        entry = entries.get(path)
        if entry is None:
            raise CyranoError("UNREGISTERED_DOCUMENT", path)
        category = entry.get("category")
        if not isinstance(category, str):
            raise CyranoError(
                "INVALID_ROUTE_DOCUMENT",
                f"{path}: missing category",
            )
        if category in FORBIDDEN:
            raise CyranoError("NONCANONICAL_DEFAULT_DOCUMENT", path)
        if category == "reference" and not allow_reference:
            raise CyranoError("EXPLICIT_REFERENCE_CONSENT_REQUIRED", path)
        raw = read_bytes(path)
        actual = hashlib.sha256(raw).hexdigest()
        if actual != entry.get("sha256"):
            raise CyranoError("STALE_DOCUMENT_CATALOG", path)
        records.append(DocumentRecord(path, category, actual, len(raw)))
        bodies.append((path, raw.decode("utf-8")))
    size = sum(record.size for record in records)
    if size > max_bytes:
        raise CyranoError("READSET_TOO_LARGE", f"{size}>{max_bytes}")
    record_dicts = [
        {
            "path": record.path,
            "category": record.category,
            "sha256": record.sha256,
            "bytes": record.size,
        }
        for record in records
    ]
    canonical = json.dumps(
        record_dicts,
        sort_keys=True,
        separators=(",", ":"),
    )
    manifest: dict[str, object] = {
        "task": task,
        "stage": stage,
        "documents": record_dicts,
        "source_bytes": size,
        "readset_digest": hashlib.sha256(canonical.encode()).hexdigest(),
        "owner_wp": _mapping(routing.get("owner_wp", {})).get(task),
        "resource_paths_not_loaded": _mapping(
            routing.get("resources", {}),
        ).get(task, []),
    }
    return Readset(manifest, tuple(bodies))
