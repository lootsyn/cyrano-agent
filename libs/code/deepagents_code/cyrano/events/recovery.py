"""Crash recovery for orphaned attempts and leased effects.

After a writer crash an attempt with no terminal event is reconciled,
never blindly re-run: a remote receipt decides between ``finished`` and
``unknown``. A leased outbox job resumes only after its fence is
re-verified; a stale worker's terminal claim stays fenced out.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from deepagents_code.cyrano.events.domain_sink import DomainSink
from deepagents_code.cyrano.events.query import ObservationQuery
from deepagents_code.cyrano.events.reconcile import reconcile_attempts


@dataclass(frozen=True, slots=True)
class RecoveryReport:
    """What recovery established for each orphaned attempt."""

    recovered_finished: tuple[str, ...]
    marked_unknown: tuple[str, ...]


def _rows_as_mappings(
    query: ObservationQuery, scope_id: str, stream_id: str
) -> list[dict[str, Any]]:
    """Page the full timeline; recovery never scans a truncated view."""
    return [
        {
            "event_seq": r.event_seq,
            "kind": r.kind,
            "payload": r.payload,
            "observation_kind": r.observation_kind,
        }
        for r in query.iter_events(scope_id, stream_id)
    ]


def recover_orphans(
    sink: DomainSink,
    query: ObservationQuery,
    scope_id: str,
    stream_id: str,
    remote_check: Callable[[str], Mapping[str, Any] | None],
) -> RecoveryReport:
    """Resolve started-not-finished attempts via remote receipts.

    ``remote_check`` returns the provider's own receipt for an attempt
    or ``None``. A confirmed receipt records ``model.finished`` with
    ``recovered``; anything else records ``model.failed`` with
    ``error_class`` ``unknown_outcome`` so it is never a success.
    """
    rows = _rows_as_mappings(query, scope_id, stream_id)
    report = reconcile_attempts(rows)
    finished: list[str] = []
    unknown: list[str] = []
    next_seq = sink.next_producer_seq("native_observer")
    for index, attempt_id in enumerate(report.orphan_attempt_ids):
        seq = next_seq + index
        receipt = remote_check(attempt_id)
        if receipt is not None and receipt.get("status") == "completed":
            sink.record_event(
                scope_id,
                stream_id,
                "native_observer",
                seq,
                "model.finished",
                {
                    "attempt_id": attempt_id,
                    "logical_request_id": str(
                        receipt.get("logical_request_id", "")
                    ),
                    "recovered": True,
                    "schema_family": "model",
                },
            )
            finished.append(attempt_id)
        else:
            sink.record_event(
                scope_id,
                stream_id,
                "native_observer",
                seq,
                "model.failed",
                {
                    "attempt_id": attempt_id,
                    "logical_request_id": "",
                    "error_class": "unknown_outcome",
                    "recovered": True,
                    "schema_family": "model",
                },
            )
            unknown.append(attempt_id)
    return RecoveryReport(
        recovered_finished=tuple(finished), marked_unknown=tuple(unknown)
    )
