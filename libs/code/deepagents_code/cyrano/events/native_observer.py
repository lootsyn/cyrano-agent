"""Observer for native model/child-graph callbacks.

Each expected call path is registered once and reports
``observed_verified``, ``unsupported``, ``failed``, or ``not_tested``.
A path that exists but has no working hook is a coverage gap — never a
zero — and an exporter outage must not stall the durable local write.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.events.domain_sink import DomainSink

EXPECTED_SOURCES = (
    "main_model",
    "child_graph",
    "summarizer",
    "grader",
    "classifier",
    "tool_offload",
    "internal_retry",
)

_SOURCE_STATES = {
    "observed_verified",
    "unsupported",
    "failed",
    "not_tested",
}


@dataclass(frozen=True, slots=True)
class AttemptSpan:
    """One physical provider attempt as seen by the native callback."""

    attempt_id: str
    logical_request_id: str
    is_retry: bool
    operation_kind: str
    provider_request_id: str | None
    started_monotonic_ms: int | None


class NativeObserver:
    """Record native callback evidence and per-source coverage."""

    def __init__(self, sink: DomainSink) -> None:
        """Bind the observer to a domain sink; nothing assumed seen."""
        self._sink = sink
        self._status: dict[str, str] = {
            source: "not_tested" for source in EXPECTED_SOURCES
        }

    def note_source(self, source: str, status: str) -> None:
        """Record a probe result; unsupported stays a visible gap."""
        if source not in self._status:
            raise CyranoError(
                "UNKNOWN_SOURCE", f"unregistered source {source!r}"
            )
        if status not in _SOURCE_STATES:
            raise CyranoError("INVALID_PROBE", f"bad probe status {status!r}")
        self._status[source] = status

    def coverage_report(self) -> dict[str, Any]:
        """Expected vs actually verified sources; gaps are explicit."""
        gaps = sorted(
            s for s, v in self._status.items() if v != "observed_verified"
        )
        return {
            "sources": dict(self._status),
            "gaps": gaps,
            "complete": not gaps,
        }

    def observe_provider_attempt(
        self,
        scope_id: str,
        stream_id: str,
        span: Mapping[str, Any],
        *,
        finished: bool,
        usage: Mapping[str, Any] | None = None,
        error_class: str | None = None,
    ) -> int:
        """Commit one attempt span from the trusted native callback."""
        attempt_id = span.get("attempt_id")
        logical = span.get("logical_request_id")
        if not attempt_id or not logical:
            raise CyranoError(
                "EVENT_PAYLOAD_INVALID", "span needs attempt+logical ids"
            )
        seq = self._sink.next_producer_seq("native_observer")
        event_type = (
            "model.attempt_started"
            if not finished
            else ("model.failed" if error_class else "model.finished")
        )
        payload: dict[str, Any] = {
            "attempt_id": str(attempt_id),
            "logical_request_id": str(logical),
            "is_retry": bool(span.get("is_retry")),
            "operation_kind": str(span.get("operation_kind", "main")),
            "schema_family": "model",
        }
        for key in (
            "provider_request_id",
            "attempt_no",
            "parent_span_id",
            "span_id",
            "started_monotonic_ms",
            "finished_monotonic_ms",
        ):
            if span.get(key) is not None:
                payload[key] = span[key]
        if span.get("aggregate_only"):
            payload["aggregate_only"] = True
        if usage is not None:
            payload["usage"] = dict(usage)
        if error_class:
            payload["error_class"] = error_class
        return self._sink.record_event(
            scope_id,
            stream_id,
            "native_observer",
            seq,
            event_type,
            payload,
        )

    def note_internal_gap(
        self,
        scope_id: str,
        stream_id: str,
        reason: str,
    ) -> int:
        """Record that an internal path was not observable."""
        return self._sink.record_event(
            scope_id,
            stream_id,
            "native_observer",
            self._sink.next_producer_seq("native_observer"),
            "telemetry.gap",
            {"reason": reason, "schema_family": "telemetry"},
        )
