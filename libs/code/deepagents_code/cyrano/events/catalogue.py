"""Event type catalogue, producer authority, and payload hygiene.

Every durable event type declares a schema family, the producers
allowed to commit it, and the payload fields it requires. A model's
own sentences are never a trusted producer: self-reports are stored
only through the untrusted path and cannot mint domain truth.

Payloads are redacted before they reach durable storage; content that
cannot be classified is quarantined, never written raw.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from deepagents_code.cyrano.contracts.types import CyranoError


@dataclass(frozen=True, slots=True)
class EventTypeSpec:
    """One registered event type and its commit authority."""

    family: str
    trusted_producers: frozenset[str]
    required_fields: frozenset[str]
    sensitivity: str = "internal"


#: Registered event types. Unknown types are refused at ingest.
EVENT_CATALOGUE: dict[str, EventTypeSpec] = {
    "model.attempt_started": EventTypeSpec(
        "model",
        frozenset({"native_observer"}),
        frozenset({"attempt_id", "logical_request_id", "is_retry"}),
    ),
    "model.finished": EventTypeSpec(
        "model",
        frozenset({"native_observer"}),
        frozenset({"attempt_id", "logical_request_id"}),
    ),
    "model.failed": EventTypeSpec(
        "model",
        frozenset({"native_observer"}),
        frozenset({"attempt_id", "logical_request_id", "error_class"}),
    ),
    "model.self_report": EventTypeSpec(
        "report", frozenset(), frozenset(), sensitivity="untrusted"
    ),
    "tool.requested": EventTypeSpec(
        "tool", frozenset({"tool_observer"}), frozenset({"tool_call_id"})
    ),
    "tool.denied": EventTypeSpec(
        "tool",
        frozenset({"tool_observer"}),
        frozenset({"tool_call_id", "decision_id"}),
    ),
    "tool.started": EventTypeSpec(
        "tool", frozenset({"tool_observer"}), frozenset({"tool_call_id"})
    ),
    "tool.finished": EventTypeSpec(
        "tool", frozenset({"tool_observer"}), frozenset({"tool_call_id"})
    ),
    "tool.failed": EventTypeSpec(
        "tool",
        frozenset({"tool_observer"}),
        frozenset({"tool_call_id", "error_class"}),
    ),
    "tool.unknown": EventTypeSpec(
        "tool", frozenset({"tool_observer"}), frozenset({"tool_call_id"})
    ),
    "approval.granted": EventTypeSpec(
        "approval",
        frozenset({"approval_broker"}),
        frozenset({"approval_id"}),
    ),
    "approval.revoked": EventTypeSpec(
        "approval",
        frozenset({"approval_broker"}),
        frozenset({"approval_id"}),
    ),
    "file.changed": EventTypeSpec(
        "change",
        frozenset({"action_broker"}),
        frozenset({"path", "post_digest"}),
    ),
    "test.finished": EventTypeSpec(
        "verify",
        frozenset({"runner"}),
        frozenset({"run_id", "outcome"}),
    ),
    "memory.queried": EventTypeSpec(
        "memory",
        frozenset({"memory_service"}),
        frozenset({"query_id"}),
    ),
    "memory.selected": EventTypeSpec(
        "memory",
        frozenset({"memory_service", "context_binder"}),
        frozenset({"memory_id"}),
    ),
    "memory.injected": EventTypeSpec(
        "memory",
        frozenset({"context_binder"}),
        frozenset({"memory_id"}),
    ),
    "memory.referenced": EventTypeSpec(
        "memory",
        frozenset({"application_checker"}),
        frozenset({"memory_id"}),
    ),
    "memory.applied": EventTypeSpec(
        "memory",
        frozenset({"application_checker"}),
        frozenset({"memory_id", "application_id"}),
    ),
    "memory.error": EventTypeSpec(
        "memory",
        frozenset({"memory_service", "context_binder"}),
        frozenset({"error_code"}),
    ),
    "learning.proposed": EventTypeSpec(
        "learning",
        frozenset({"learning_worker"}),
        frozenset({"candidate_id"}),
    ),
    "learning.evaluated": EventTypeSpec(
        "learning",
        frozenset({"learning_worker"}),
        frozenset({"candidate_id"}),
    ),
    "release.promoted": EventTypeSpec(
        "release",
        frozenset({"release_service"}),
        frozenset({"release_digest"}),
    ),
    "release.rolled_back": EventTypeSpec(
        "release",
        frozenset({"release_service"}),
        frozenset({"release_digest"}),
    ),
    "work.started": EventTypeSpec(
        "work", frozenset({"domain_service"}), frozenset({"run_id"})
    ),
    "work.completed": EventTypeSpec(
        "work", frozenset({"domain_service"}), frozenset({"run_id"})
    ),
    "work.failed": EventTypeSpec(
        "work", frozenset({"domain_service"}), frozenset({"run_id"})
    ),
    "work.cancelled": EventTypeSpec(
        "work", frozenset({"domain_service"}), frozenset({"run_id"})
    ),
    "telemetry.gap": EventTypeSpec(
        "telemetry",
        frozenset({"native_observer", "tool_observer", "domain_sink"}),
        frozenset({"reason"}),
    ),
}

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{8,}"),
    re.compile(r"AKIA[0-9A-Z]{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password)"
        r"[\s'\"]*[:=][\s'\"]*[A-Za-z0-9_\-]{8,}"
    ),
)


def spec_for(event_type: str) -> EventTypeSpec:
    """Return the registered spec or refuse an unknown type."""
    spec = EVENT_CATALOGUE.get(event_type)
    if spec is None:
        raise CyranoError(
            "UNKNOWN_EVENT_TYPE", f"unregistered event {event_type!r}"
        )
    return spec


def authorize_event(event_type: str, producer: str) -> EventTypeSpec:
    """Refuse when ``producer`` may not commit ``event_type``."""
    spec = spec_for(event_type)
    if producer not in spec.trusted_producers:
        raise CyranoError(
            "EVENT_PRODUCER_DENIED",
            f"{producer!r} may not commit {event_type!r}",
        )
    return spec


def payload_family(payload: Mapping[str, Any]) -> str | None:
    """Return the payload's declared schema family, if any."""
    family = payload.get("schema_family")
    return family if isinstance(family, str) else None


def check_typed_payload(event_type: str, payload: Mapping[str, Any]) -> None:
    """Refuse when the payload's declared family mismatches the type."""
    spec = spec_for(event_type)
    family = payload_family(payload)
    if family is not None and family != spec.family:
        raise CyranoError(
            "EVENT_PAYLOAD_FAMILY_MISMATCH",
            f"{event_type!r} payload declares {family!r}",
        )
    missing = spec.required_fields - set(payload)
    if missing:
        raise CyranoError(
            "EVENT_PAYLOAD_INVALID",
            f"{event_type!r} missing {sorted(missing)}",
        )


def is_failure_event(kind: str, payload: Mapping[str, Any]) -> bool:
    """True when a trusted row records a real failure outcome.

    ``*.failed`` kinds qualify, and so does a terminal record whose
    payload reports ``outcome`` ``failed`` or ``error`` — a
    ``test.finished`` row is a failure when its outcome says so.
    """
    if kind.endswith(".failed"):
        return True
    return payload.get("outcome") in {"failed", "error"}


def redact_text(text: str) -> tuple[str, bool]:
    """Mask secret-shaped spans; report whether anything was masked."""
    found = False
    out = text
    for pattern in _SECRET_PATTERNS:
        if pattern.search(out):
            found = True
            out = pattern.sub("[redacted]", out)
    return out, found


def redact_payload(value: Any, *, _depth: int = 0) -> tuple[Any, bool]:
    """Recursively mask secret-shaped strings in a JSON value."""
    if _depth > 16:
        raise CyranoError("PAYLOAD_QUARANTINED", "payload too deep")
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        found = False
        out: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CyranoError(
                    "PAYLOAD_QUARANTINED", "non-string payload key"
                )
            cleaned, hit = redact_payload(item, _depth=_depth + 1)
            found = found or hit
            out[key] = cleaned
        return out, found
    if isinstance(value, (list, tuple)):
        found = False
        items = []
        for item in value:
            cleaned, hit = redact_payload(item, _depth=_depth + 1)
            found = found or hit
            items.append(cleaned)
        return items, found
    if isinstance(value, (int, float, bool)) or value is None:
        return value, False
    raise CyranoError(
        "PAYLOAD_QUARANTINED", f"unclassifiable {type(value).__name__}"
    )
