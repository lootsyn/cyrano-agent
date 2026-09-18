"""Durable event sink over the scoped ledger.

Trusted domain events are committed only by authorized producers, with
payloads redacted before they reach durable storage. State changes and
their events share one transaction: when the event/audit write fails,
the mutation rolls back with it — an effect is never recorded without
its observation.

Self-reported claims are kept, but under ``observation_kind``
``self_report``; they never satisfy coverage or completion checks.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping
from typing import Any

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.events.catalogue import (
    authorize_event,
    check_typed_payload,
    redact_payload,
    spec_for,
)
from deepagents_code.cyrano.sqlite.repository import ScopedRepository


class DomainSink:
    """Commit authorized, redacted events to the scoped ledger."""

    def __init__(self, repo: ScopedRepository) -> None:
        """Bind the sink to a scoped repository."""
        self._repo = repo

    def next_producer_seq(self, producer: str) -> int:
        """Return the next free sequence for ``producer``.

        Producer sequences are unique ledger-wide, not per stream,
        so the floor must span every stream.
        """
        row = self._repo.connection.execute(
            "SELECT MAX(producer_seq) FROM events WHERE producer=?",
            (producer,),
        ).fetchone()
        return int(row[0]) + 1 if row and row[0] is not None else 1

    def _write(
        self,
        db,
        scope_id: str,
        stream_id: str,
        producer: str,
        producer_seq: int,
        event_type: str,
        payload: Mapping[str, Any],
        *,
        observation_kind: str,
    ) -> int:
        try:
            return self._repo.record_observation_in(
                db,
                scope_id,
                stream_id,
                producer,
                producer_seq,
                {**payload, "event_type": event_type},
                kind=event_type,
                observation_kind=observation_kind,
            )
        except sqlite3.Error as error:
            raise CyranoError("EVENT_STORE_UNAVAILABLE", str(error)) from error

    def record_event(
        self,
        scope_id: str,
        stream_id: str,
        producer: str,
        producer_seq: int,
        event_type: str,
        payload: Mapping[str, Any],
    ) -> int:
        """Commit one trusted event; unauthorized producers refuse.

        The payload is family-checked and redacted before the durable
        write. A storage failure is explicit — the caller's mutation
        must not proceed on an unrecorded effect.
        """
        authorize_event(event_type, producer)
        check_typed_payload(event_type, payload)
        clean, redacted = redact_payload(dict(payload))
        if redacted:
            clean = {**clean, "redaction": "applied"}
        with self._repo.transaction() as db:
            return self._write(
                db,
                scope_id,
                stream_id,
                producer,
                producer_seq,
                event_type,
                clean,
                observation_kind="trusted",
            )

    def record_untrusted(
        self,
        scope_id: str,
        stream_id: str,
        producer: str,
        producer_seq: int,
        event_type: str,
        payload: Mapping[str, Any],
    ) -> int:
        """Store a self-report verbatim-but-redacted as untrusted.

        No producer authority is required because the record can never
        satisfy coverage, approval, or completion checks.
        """
        spec_for(event_type)  # unknown types are still refused
        clean, _ = redact_payload(dict(payload))
        with self._repo.transaction() as db:
            return self._write(
                db,
                scope_id,
                stream_id,
                producer,
                producer_seq,
                event_type,
                clean,
                observation_kind="self_report",
            )

    def commit_transition(
        self,
        scope_id: str,
        stream_id: str,
        producer: str,
        producer_seq: int,
        event_type: str,
        payload: Mapping[str, Any],
        mutate: Callable[[sqlite3.Connection], None],
    ) -> int:
        """Apply ``mutate`` and commit ``event_type`` atomically.

        When the event write fails, the mutation rolls back with it —
        an unrecorded effect is an error, not a partial success.
        """
        authorize_event(event_type, producer)
        check_typed_payload(event_type, payload)
        clean, redacted = redact_payload(dict(payload))
        if redacted:
            clean = {**clean, "redaction": "applied"}
        with self._repo.transaction() as db:
            mutate(db)
            return self._write(
                db,
                scope_id,
                stream_id,
                producer,
                producer_seq,
                event_type,
                clean,
                observation_kind="trusted",
            )

    def record_quarantined(
        self,
        scope_id: str,
        stream_id: str,
        producer: str,
        event_type: str,
        *,
        reason: str,
    ) -> int:
        """Record that a payload was refused; the body is never kept.

        The sink authors this record itself — the original producer
        keeps no authority to commit a ``telemetry.gap`` event.
        """
        with self._repo.transaction() as db:
            return self._write(
                db,
                scope_id,
                stream_id,
                "domain_sink",
                self.next_producer_seq("domain_sink"),
                "telemetry.gap",
                {
                    "reason": "payload_quarantined",
                    "quarantined_type": event_type,
                    "quarantined_producer": producer,
                    "detail": reason[:200],
                },
                observation_kind="trusted",
            )
