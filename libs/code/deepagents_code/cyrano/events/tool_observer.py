"""Observer for tool-call lifecycle events.

``requested``, ``denied``, ``started``, ``finished``, ``failed`` and
``unknown`` are distinct states — a denial is neither a success nor an
execution failure, and an unknown outcome is never promoted to either.
Tool output is redacted by the sink before it is stored.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.events.domain_sink import DomainSink


class ToolObserver:
    """Commit trusted tool lifecycle events to the domain sink."""

    def __init__(self, sink: DomainSink) -> None:
        """Bind the observer to a domain sink."""
        self._sink = sink

    def _emit(
        self,
        scope_id: str,
        stream_id: str,
        event_type: str,
        payload: Mapping[str, Any],
    ) -> int:
        return self._sink.record_event(
            scope_id,
            stream_id,
            "tool_observer",
            self._sink.next_producer_seq("tool_observer"),
            event_type,
            {**payload, "schema_family": "tool"},
        )

    def requested(
        self, scope_id: str, stream_id: str, tool_call_id: str, **kw: Any
    ) -> int:
        """A tool call was requested by the model."""
        return self._emit(
            scope_id,
            stream_id,
            "tool.requested",
            {"tool_call_id": tool_call_id, **kw},
        )

    def denied(
        self,
        scope_id: str,
        stream_id: str,
        tool_call_id: str,
        decision_id: str,
        **kw: Any,
    ) -> int:
        """A policy denial; distinct from execution failure."""
        return self._emit(
            scope_id,
            stream_id,
            "tool.denied",
            {
                "tool_call_id": tool_call_id,
                "decision_id": decision_id,
                **kw,
            },
        )

    def started(
        self, scope_id: str, stream_id: str, tool_call_id: str, **kw: Any
    ) -> int:
        """A permitted tool call began executing."""
        return self._emit(
            scope_id,
            stream_id,
            "tool.started",
            {"tool_call_id": tool_call_id, **kw},
        )

    def finished(
        self, scope_id: str, stream_id: str, tool_call_id: str, **kw: Any
    ) -> int:
        """A tool call returned a result."""
        return self._emit(
            scope_id,
            stream_id,
            "tool.finished",
            {"tool_call_id": tool_call_id, **kw},
        )

    def failed(
        self,
        scope_id: str,
        stream_id: str,
        tool_call_id: str,
        error_class: str,
        **kw: Any,
    ) -> int:
        """A tool call failed with a classified error."""
        return self._emit(
            scope_id,
            stream_id,
            "tool.failed",
            {
                "tool_call_id": tool_call_id,
                "error_class": error_class,
                **kw,
            },
        )

    def unknown(
        self, scope_id: str, stream_id: str, tool_call_id: str, **kw: Any
    ) -> int:
        """A tool call's outcome is not established."""
        return self._emit(
            scope_id,
            stream_id,
            "tool.unknown",
            {"tool_call_id": tool_call_id, **kw},
        )

    def emit(
        self, scope_id: str, stream_id: str, event_type: str, **kw: Any
    ) -> int:
        """Refuse kinds outside the tool lifecycle surface."""
        if not event_type.startswith("tool."):
            raise CyranoError(
                "EVENT_PRODUCER_DENIED",
                "tool observer may only emit tool.* events",
            )
        return self._emit(scope_id, stream_id, event_type, kw)
