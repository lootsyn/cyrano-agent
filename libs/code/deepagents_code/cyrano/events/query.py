"""Scope-checked read service for the event ledger.

Reads go through the scope ACL before any payload is touched. A cursor
is a committed ``event_seq``; a cursor older than the retained window
reports ``stale`` so the client resyncs from a snapshot instead of
silently missing events. Queries never call a model.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.events.catalogue import is_failure_event
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

MAX_PAGE = 500


@dataclass(frozen=True, slots=True)
class EventRow:
    """One committed event with its decoded, already-stored payload."""

    event_seq: int
    event_id: str
    stream_id: str
    kind: str
    producer: str
    producer_seq: int
    observation_kind: str
    observed_at: str
    ingested_at: str
    payload: dict[str, Any]
    payload_digest: str


@dataclass(frozen=True, slots=True)
class Timeline:
    """A bounded, deduplicated slice plus cursor state."""

    events: tuple[EventRow, ...]
    cursor: int
    stale_cursor: bool
    complete: bool


@dataclass(frozen=True, slots=True)
class FailureReport:
    """The first observed failure with trusted and untrusted causes."""

    run_id: str
    failed_kind: str
    event_seq: int
    evidence: dict[str, Any]
    self_reports: tuple[dict[str, Any], ...]


class ObservationQuery:
    """Authorized reads over events and their stored payloads."""

    def __init__(self, repo: ScopedRepository) -> None:
        """Bind the query service to a scoped repository."""
        self._repo = repo

    def _check_scope(self, scope_id: str, stream_id: str) -> None:
        self._repo.read_scoped_entity(scope_id, stream_id)

    def _rows(
        self, scope_id: str, stream_id: str, *, after_seq: int = 0
    ) -> list[EventRow]:
        self._check_scope(scope_id, stream_id)
        rows = self._repo.connection.execute(
            "SELECT event_seq,event_id,stream_id,kind,producer,"
            "producer_seq,observation_kind,observed_at,ingested_at,"
            "payload_digest "
            "FROM events "
            "WHERE stream_id=? AND event_seq>? ORDER BY event_seq",
            (stream_id, after_seq),
        ).fetchall()
        out: list[EventRow] = []
        for (
            seq,
            eid,
            sid,
            kind,
            producer,
            pseq,
            obs_kind,
            observed_at,
            ingested_at,
            dig,
        ) in rows:
            body = self._repo.read_artifact(scope_id, str(dig))
            payload: dict[str, Any] = {}
            if body is not None:
                try:
                    payload = json.loads(body)
                except (ValueError, TypeError):
                    payload = {"unreadable": True}
            out.append(
                EventRow(
                    event_seq=int(seq),
                    event_id=str(eid),
                    stream_id=str(sid),
                    kind=str(kind),
                    producer=str(producer),
                    producer_seq=int(pseq),
                    observation_kind=str(obs_kind),
                    observed_at=str(observed_at),
                    ingested_at=str(ingested_at),
                    payload=payload,
                    payload_digest=str(dig),
                )
            )
        return out

    def _scope_of(self, stream_id: str) -> str | None:
        row = self._repo.connection.execute(
            "SELECT scope_id FROM streams WHERE stream_id=?", (stream_id,)
        ).fetchone()
        return str(row[0]) if row else None

    def _deny_unless_scope(self, scope_id: str, stream_id: str) -> None:
        """Uniform deny/not-found: never leak that a stream exists."""
        if self._scope_of(stream_id) != scope_id:
            raise CyranoError("SCOPE_DENIED", "unknown request")

    def get_timeline(
        self,
        scope_id: str,
        stream_id: str,
        *,
        after_seq: int = 0,
        limit: int = MAX_PAGE,
    ) -> Timeline:
        """Events after ``after_seq``; a stale cursor is flagged."""
        if not 1 <= limit <= MAX_PAGE:
            raise CyranoError("INVALID_PAGE_LIMIT", "limit out of range")
        self._deny_unless_scope(scope_id, stream_id)
        rows = self._rows(scope_id, stream_id, after_seq=after_seq)
        seen: set[str] = set()
        deduped = []
        for row in rows:
            if row.event_id in seen:
                continue
            seen.add(row.event_id)
            deduped.append(row)
        stale = False
        if after_seq > 0 and deduped:
            first = self._repo.connection.execute(
                "SELECT MIN(event_seq) FROM events WHERE stream_id=?",
                (stream_id,),
            ).fetchone()
            if (
                first
                and first[0] is not None
                and int(first[0]) > (after_seq + 1)
            ):
                stale = True
        cursor = deduped[-1].event_seq if deduped else after_seq
        return Timeline(
            events=tuple(deduped[:limit]),
            cursor=cursor,
            stale_cursor=stale,
            complete=len(deduped) <= limit,
        )

    def get_failure(
        self, scope_id: str, stream_id: str
    ) -> FailureReport | None:
        """First trusted failure plus distinct self-report claims."""
        self._deny_unless_scope(scope_id, stream_id)
        rows = self._rows(scope_id, stream_id)
        trusted = [
            r
            for r in rows
            if r.observation_kind == "trusted"
            and is_failure_event(r.kind, r.payload)
        ]
        if not trusted:
            return None
        first = min(trusted, key=lambda r: r.event_seq)
        reports = tuple(
            dict(r.payload)
            for r in rows
            if r.observation_kind == "self_report"
        )
        return FailureReport(
            run_id=str(first.payload.get("run_id", stream_id)),
            failed_kind=first.kind,
            event_seq=first.event_seq,
            evidence=dict(first.payload),
            self_reports=reports,
        )

    def get_trace(self, scope_id: str, stream_id: str) -> dict[str, Any]:
        """Span tree for one stream; orphans are marked, not hidden."""
        self._deny_unless_scope(scope_id, stream_id)
        rows = self._rows(scope_id, stream_id)
        spans: dict[str, dict[str, Any]] = {}
        for row in rows:
            span_id = row.payload.get("span_id")
            if not span_id:
                continue
            spans[str(span_id)] = {
                "span_id": span_id,
                "parent_span_id": row.payload.get("parent_span_id"),
                "kind": row.kind,
                "event_seq": row.event_seq,
                "observation_kind": row.observation_kind,
            }
        orphans = [
            s["span_id"]
            for s in spans.values()
            if s["parent_span_id"] and str(s["parent_span_id"]) not in spans
        ]
        return {
            "stream_id": stream_id,
            "spans": sorted(spans.values(), key=lambda s: s["event_seq"]),
            "orphans": sorted(orphans),
            "total_events": len(rows),
        }

    def list_requests(
        self, scope_id: str, *, cursor: str = "", limit: int = 50
    ) -> dict[str, Any]:
        """Recent request streams plus the true total count."""
        if not 1 <= limit <= MAX_PAGE:
            raise CyranoError("INVALID_PAGE_LIMIT", "limit out of range")
        rows = self._repo.connection.execute(
            "SELECT stream_id,entity_type,status,revision FROM streams "
            "WHERE scope_id=? AND stream_id>? ORDER BY stream_id",
            (scope_id, cursor),
        ).fetchall()
        total = len(rows)
        page = rows[:limit]
        return {
            "requests": [
                {
                    "stream_id": r[0],
                    "entity_type": r[1],
                    "status": r[2],
                    "revision": r[3],
                }
                for r in page
            ],
            "total": total,
            "listed": len(page),
            "cursor": str(page[-1][0]) if page else cursor,
        }

    def resume_stream(
        self, scope_id: str, stream_id: str, cursor: int
    ) -> Timeline:
        """Reconnect after ``cursor``; duplicates are safe to replay."""
        return self.get_timeline(scope_id, stream_id, after_seq=cursor)

    def iter_events(
        self, scope_id: str, stream_id: str, *, page_size: int = 500
    ) -> Iterator[EventRow]:
        """Yield every event in commit order; pages never truncate."""
        after = 0
        while True:
            page = self.get_timeline(
                scope_id, stream_id, after_seq=after, limit=page_size
            )
            yield from page.events
            if page.complete:
                return
            if page.cursor <= after:
                raise CyranoError(
                    "CURSOR_STALLED", "timeline cursor did not advance"
                )
            after = page.cursor
