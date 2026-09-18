"""Read-only bounded monitoring views built from trusted events."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass, field
from typing import Any


class ProjectionError(ValueError):
    """Reject malformed or conflicting cross-session monitoring data."""


def terminal_text(value: str, limit: int = 2000) -> str:
    """Replace terminal and bidi controls; preserve Korean text.

    Render the returned value with markup disabled. Escaping does not
    grant permission to export content: redaction must have happened.
    """
    if not isinstance(value, str) or type(limit) is not int or limit < 1:
        raise ProjectionError("INVALID_TEXT_LIMIT")
    clean = "".join(
        ch
        if ch == "\n" or unicodedata.category(ch) not in {"Cc", "Cf", "Cs"}
        else "\ufffd"
        for ch in value
    )
    return clean[:limit]


@dataclass
class MonitorProjection:
    """Track one scope/generation with idempotent physical-call counts.

    The record cap requires a new authoritative snapshot, rather
    than silently dropping entries while presenting incomplete
    totals as exact.
    """

    workspace_id: str
    request_id: str
    generation: str
    max_events: int = 10000
    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    hashes: dict[str, str] = field(default_factory=dict)
    cursor: int = 0
    connected: bool = False
    complete: bool = False

    def ingest(self, event: dict[str, Any]) -> bool:
        """Validate and add one event; false on an exact duplicate.

        Gaps in global sequence numbers are allowed because views are
        scoped. Late events are accepted if their identities and
        sequence ownership do not conflict. Authentication is the
        supplying service's job, not the projection's.
        """
        required = {
            "event_id",
            "commit_seq",
            "workspace_id",
            "request_id",
            "generation",
            "event_type",
            "payload",
        }
        if not required <= set(event):
            raise ProjectionError("MISSING_EVENT_FIELD")
        if (
            event["workspace_id"] != self.workspace_id
            or event["request_id"] != self.request_id
            or event["generation"] != self.generation
        ):
            raise ProjectionError("SCOPE_OR_GENERATION_MISMATCH")
        seq = event["commit_seq"]
        if type(seq) is not int or seq < 1:
            raise ProjectionError("INVALID_SEQUENCE")
        event_id = event["event_id"]
        if not isinstance(event_id, str) or not event_id:
            raise ProjectionError("INVALID_EVENT_ID")
        if not isinstance(event["event_type"], str) or not event["event_type"]:
            raise ProjectionError("INVALID_EVENT_TYPE")
        if not isinstance(event["payload"], dict):
            raise ProjectionError("INVALID_PAYLOAD")
        try:
            encoded = json.dumps(
                event,
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            )
        except (ValueError, TypeError) as error:
            raise ProjectionError("INVALID_JSON_EVENT") from error
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        if event_id in self.hashes:
            if self.hashes[event_id] != digest:
                raise ProjectionError("EVENT_IDEMPOTENCY_CONFLICT")
            return False
        if any(row["commit_seq"] == seq for row in self.records.values()):
            raise ProjectionError("SEQUENCE_OWNERSHIP_CONFLICT")
        if len(self.records) >= self.max_events:
            raise ProjectionError("SNAPSHOT_REQUIRED")
        # Deep-copy so callers cannot mutate accepted records.
        self.records[event_id] = json.loads(encoded)
        self.hashes[event_id] = digest
        self.cursor = max(self.cursor, seq)
        return True

    def summary(self) -> dict[str, Any]:
        """Observed counts plus connection/completeness flags."""
        calls: dict[str, dict[str, Any]] = {}
        logical: set[str] = set()
        failures = []
        memory_applied: set[str] = set()
        candidates: set[str] = set()
        promoted: set[str] = set()
        for row in self.records.values():
            kind, payload = row["event_type"], row["payload"]
            if kind == "model.attempt_started":
                ident = payload.get("attempt_id")
                logical_id = payload.get("logical_request_id")
                retry = payload.get("is_retry")
                if not ident or not logical_id or type(retry) is not bool:
                    raise ProjectionError("INVALID_ATTEMPT")
                if ident in calls and calls[ident] != payload:
                    raise ProjectionError("ATTEMPT_BINDING_CONFLICT")
                calls[ident] = payload
                logical.add(logical_id)
            if kind.endswith(".failed") or payload.get("outcome") in {
                "failed",
                "error",
            }:
                failures.append(row)
            if kind == "memory.applied":
                if not payload.get("application_id"):
                    raise ProjectionError("MISSING_APPLICATION_ID")
                memory_applied.add(payload["application_id"])
            if kind == "learning.proposed":
                candidates.add(payload["candidate_id"])
            if kind == "release.promoted":
                promoted.add(payload["release_digest"])
        first = min(failures, key=lambda x: x["commit_seq"], default=None)
        return {
            "total_events": len(self.records),
            "logical_requests_observed": len(logical),
            "physical_attempts_observed": len(calls),
            "retries_observed": sum(p["is_retry"] for p in calls.values()),
            "memory_applications_observed": len(memory_applied),
            "candidates_observed": len(candidates),
            "promotions_observed": len(promoted),
            "first_observed_failure": (
                json.loads(json.dumps(first)) if first else None
            ),
            "cursor": self.cursor,
            "connected": self.connected,
            "coverage": "complete" if self.complete else "partial_or_unknown",
        }

    def timeline(self, limit: int = 200) -> list[dict[str, Any]]:
        """Newest bounded records in commit order, not causal order."""
        if not 1 <= limit <= 1000:
            raise ProjectionError("INVALID_PAGE_LIMIT")
        rows = sorted(self.records.values(), key=lambda x: x["commit_seq"])
        return json.loads(json.dumps(rows[-limit:]))
