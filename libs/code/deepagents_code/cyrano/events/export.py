"""Scope-bound export of the event ledger.

Export re-applies redaction at the boundary even though storage was
already masked, verifies each payload against its committed digest
after re-encoding, and refuses to proceed when any payload is missing
or cross-scope. An export never grants new authority.
"""

from __future__ import annotations

import json
from typing import Any

from deepagents_code.cyrano.contracts.canonical import canonical_bytes
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.events.catalogue import redact_payload
from deepagents_code.cyrano.events.query import ObservationQuery
from deepagents_code.cyrano.sqlite.repository import ScopedRepository


def export_bundle(
    repo: ScopedRepository,
    query: ObservationQuery,
    scope_id: str,
    stream_id: str,
) -> dict[str, Any]:
    """Export one stream's events with digests and redaction proof.

    Returns a manifest mapping each ``event_id`` to its stored digest
    plus the redacted payloads. A payload whose bytes are missing or
    whose re-encoded digest mismatches aborts the whole export. The
    export pages through the full timeline; it never truncates.
    """
    events: list[dict[str, Any]] = []
    manifest: dict[str, str] = {}
    seen: set[str] = set()
    for row in query.iter_events(scope_id, stream_id):
        if row.event_id in seen:
            continue
        seen.add(row.event_id)
        clean, redacted = redact_payload(dict(row.payload))
        encoded = canonical_bytes(clean)
        body = repo.read_artifact(scope_id, row.payload_digest)
        if body is None:
            raise CyranoError(
                "EVENT_PAYLOAD_MISSING",
                f"no stored body for {row.event_id}",
            )
        stored = json.loads(body)
        stored_clean, _ = redact_payload(dict(stored))
        if canonical_bytes(stored_clean) != encoded:
            raise CyranoError(
                "EVENT_DIGEST_MISMATCH",
                f"payload drift on {row.event_id}",
            )
        events.append(
            {
                "event_id": row.event_id,
                "event_seq": row.event_seq,
                "kind": row.kind,
                "producer": row.producer,
                "observation_kind": row.observation_kind,
                "payload": clean,
                "redacted": bool(redacted),
            }
        )
        manifest[row.event_id] = row.payload_digest
    return {
        "stream_id": stream_id,
        "scope_id": scope_id,
        "event_count": len(events),
        "events": events,
        "manifest": manifest,
    }
