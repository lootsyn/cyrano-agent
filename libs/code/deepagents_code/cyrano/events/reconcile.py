"""Reconcile attempts that started but never reached a terminal event.

A start with no finish is ``unknown`` — it is never counted as success
or failure. A finish that arrived before its start is bound by identity
and flagged ``ordering_uncertain``; the pair is not discarded and its
duration is not trusted.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ReconcileReport:
    """Orphaned attempts and out-of-order pairs found in one stream."""

    orphan_attempt_ids: tuple[str, ...]
    ordering_uncertain: tuple[str, ...]
    resolved: tuple[str, ...]


def reconcile_attempts(
    events: Sequence[Mapping[str, Any]],
) -> ReconcileReport:
    """Pair started/finished by attempt_id over exported event rows."""
    started: dict[str, int] = {}
    finished: dict[str, int] = {}
    order: list[str] = []
    for event in events:
        kind = str(event.get("kind") or "")
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            continue
        attempt_id = payload.get("attempt_id")
        if not attempt_id:
            continue
        key = str(attempt_id)
        if key not in order:
            order.append(key)
        seq = int(event.get("event_seq", 0))
        if kind == "model.attempt_started":
            started[key] = seq
        elif kind in {"model.finished", "model.failed"}:
            finished[key] = seq
    orphans = tuple(k for k in order if k in started and k not in finished)
    uncertain = tuple(
        k
        for k in order
        if k in finished and (k not in started or finished[k] < started[k])
    )
    resolved = tuple(
        k
        for k in order
        if k in started and k in finished and finished[k] >= started[k]
    )
    return ReconcileReport(
        orphan_attempt_ids=orphans,
        ordering_uncertain=uncertain,
        resolved=resolved,
    )
