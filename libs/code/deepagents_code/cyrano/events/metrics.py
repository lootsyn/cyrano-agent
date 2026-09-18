"""Pure metric reducer over exported event rows.

Only leaf physical attempts are summed; a parent-reported aggregate and
its child's own attempt share a billing identity and count once. Missing
usage stays ``None`` — it is never coerced to zero — and reversed clocks
are flagged rather than clamped. Duplicate ``event_id`` deliveries do
not change any count.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

_ATTEMPT_START = "model.attempt_started"
_ATTEMPT_END = {"model.finished", "model.failed"}
_TOOL_KINDS = (
    "requested",
    "started",
    "finished",
    "denied",
    "failed",
    "unknown",
)
_MEMORY_STAGES = (
    "queried",
    "selected",
    "injected",
    "referenced",
    "applied",
    "error",
)
_LEARNING_KINDS = ("proposed", "evaluated")


@dataclass(frozen=True, slots=True)
class MetricSnapshot:
    """Reduced counters; absent usage fields stay ``None``."""

    logical_llm_requests: int
    physical_llm_attempts: int
    llm_retry_count: int
    attempts_unknown_outcome: int
    tool_counts: dict[str, int]
    memory_counts: dict[str, int]
    learning_counts: dict[str, int]
    input_tokens: int | None
    output_tokens: int | None
    cache_read_tokens: int | None
    cache_write_tokens: int | None
    cost_actual: float | None
    cost_estimated: float | None
    cost_unknown: int
    durations_ms: list[int]
    clock_anomalies: int
    terminal_states: dict[str, int]
    coverage_gaps: tuple[str, ...]
    total_events: int
    duplicate_events: int


@dataclass(slots=True)
class _Attempt:
    attempt_id: str
    logical_id: str
    is_retry: bool
    billing_key: str
    leaf: bool
    started_ms: int | None = None
    finished_ms: int | None = None
    terminal: str | None = None
    error_class: str | None = None
    ordering_uncertain: bool = False
    usage: dict[str, Any] = field(default_factory=dict)


def _sum_optional(values: Iterable[int | None]) -> int | None:
    """Sum reported values; ``None`` when nothing was reported."""
    known = [v for v in values if v is not None]
    return sum(known) if known else None


def _billing_key(payload: Mapping[str, Any]) -> str:
    """One physical call counts once across parent/child reports."""
    provider_id = payload.get("provider_request_id")
    if isinstance(provider_id, str) and provider_id:
        attempt_no = payload.get("attempt_no", 0)
        return f"provider:{provider_id}:{attempt_no}"
    return f"attempt:{payload.get('attempt_id')}"


def _monotonic_ms(value: object) -> int | None:
    """Coerce a canonical monotonic-ms field; ``None`` on bad shape."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.lstrip("-").isdigit():
        return int(value)
    return None


def reduce_events(events: Iterable[Mapping[str, Any]]) -> MetricSnapshot:
    """Fold ordered event dicts into one honest snapshot."""
    seen_ids: set[str] = set()
    duplicates = 0
    attempts: dict[str, _Attempt] = {}
    billing_seen: set[str] = set()
    tool_counts = {kind: 0 for kind in _TOOL_KINDS}
    memory_counts = {stage: 0 for stage in _MEMORY_STAGES}
    learning_counts = {kind: 0 for kind in _LEARNING_KINDS}
    learning_counts["promoted"] = 0
    learning_counts["revoked"] = 0
    terminal: dict[str, int] = {}
    gaps: list[str] = []
    durations: list[int] = []
    anomalies = 0
    total = 0

    for event in events:
        event_id = event.get("event_id")
        if event_id in seen_ids:
            duplicates += 1
            continue
        if event_id:
            seen_ids.add(str(event_id))
        total += 1
        kind = str(event.get("kind") or event.get("event_type") or "")
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            payload = {}

        if kind == _ATTEMPT_START:
            attempt_id = str(payload.get("attempt_id", ""))
            if not attempt_id:
                gaps.append("model.attempt_started:missing_id")
                continue
            key = _billing_key(payload)
            attempt = attempts.get(attempt_id)
            if attempt is None:
                attempt = _Attempt(
                    attempt_id=attempt_id,
                    logical_id=str(payload.get("logical_request_id", "")),
                    is_retry=bool(payload.get("is_retry")),
                    billing_key=key,
                    leaf=not bool(payload.get("aggregate_only")),
                )
                attempts[attempt_id] = attempt
            raw_started = payload.get("started_monotonic_ms")
            if raw_started is not None:
                started_ms = _monotonic_ms(raw_started)
                if started_ms is None:
                    gaps.append("model.attempt_started:bad_monotonic_ms")
                else:
                    attempt.started_ms = started_ms
        elif kind in _ATTEMPT_END:
            attempt_id = str(payload.get("attempt_id", ""))
            attempt = attempts.get(attempt_id)
            if attempt is None:
                # Finish-before-start: bind by identity, flag ordering.
                attempt = _Attempt(
                    attempt_id=attempt_id,
                    logical_id=str(payload.get("logical_request_id", "")),
                    is_retry=bool(payload.get("is_retry")),
                    billing_key=_billing_key(payload),
                    leaf=not bool(payload.get("aggregate_only")),
                )
                attempts[attempt_id] = attempt
                # Finish-before-start: bind by identity, flag ordering.
                attempt.ordering_uncertain = True
            attempt.terminal = (
                "failed" if kind.endswith("failed") else "finished"
            )
            if payload.get("error_class") is not None:
                attempt.error_class = str(payload["error_class"])
            raw_finished = payload.get("finished_monotonic_ms")
            if raw_finished is not None:
                finished_ms = _monotonic_ms(raw_finished)
                if finished_ms is None:
                    gaps.append("model.attempt_finished:bad_monotonic_ms")
                else:
                    attempt.finished_ms = finished_ms
            usage = payload.get("usage")
            if isinstance(usage, Mapping):
                attempt.usage = dict(usage)
        elif kind.startswith("tool."):
            state = kind.split(".", 1)[1]
            if state in tool_counts:
                tool_counts[state] += 1
        elif kind.startswith("memory."):
            stage = kind.split(".", 1)[1]
            if stage in memory_counts:
                memory_counts[stage] += 1
        elif kind.startswith("learning."):
            stage = kind.split(".", 1)[1]
            learning_counts[stage] = learning_counts.get(stage, 0) + 1
        elif kind in {"release.promoted", "release.rolled_back"}:
            stage = kind.split(".", 1)[1]
            learning_counts[stage] = learning_counts.get(stage, 0) + 1
        elif kind == "telemetry.gap":
            reason = payload.get("reason", "unknown")
            gaps.append(f"telemetry.gap:{reason}")
        elif kind.startswith("work."):
            state = kind.split(".", 1)[1]
            terminal[state] = terminal.get(state, 0) + 1

    logical_ids: set[str] = set()
    physical = 0
    retries = 0
    unknown_outcome = 0
    inputs: list[int | None] = []
    outputs: list[int | None] = []
    cache_r: list[int | None] = []
    cache_w: list[int | None] = []
    actual: list[float] = []
    estimated: list[float] = []
    cost_unknown = 0

    for attempt in attempts.values():
        if not attempt.leaf:
            continue
        if attempt.billing_key in billing_seen:
            continue
        billing_seen.add(attempt.billing_key)
        physical += 1
        if attempt.logical_id:
            logical_ids.add(attempt.logical_id)
        if attempt.is_retry:
            retries += 1
        if (
            attempt.terminal is None
            or attempt.error_class == "unknown_outcome"
        ):
            unknown_outcome += 1
        usage = attempt.usage
        inputs.append(
            usage.get("input_tokens") if "input_tokens" in usage else None
        )
        outputs.append(
            usage.get("output_tokens") if "output_tokens" in usage else None
        )
        cache_r.append(
            usage.get("cache_read") if "cache_read" in usage else None
        )
        cache_w.append(
            usage.get("cache_write") if "cache_write" in usage else None
        )
        cost = usage.get("cost_actual")
        if isinstance(cost, (int, str)) and str(cost).strip():
            actual.append(float(cost))
        elif usage.get("cost_estimated") is not None:
            estimated.append(float(str(usage["cost_estimated"])))
        else:
            cost_unknown += 1
        if attempt.ordering_uncertain:
            anomalies += 1  # time cannot be trusted for this pair
            continue
        if attempt.started_ms is not None and attempt.finished_ms is not None:
            delta = attempt.finished_ms - attempt.started_ms
            if delta < 0:
                anomalies += 1  # reversed clock: flag, never clamp
            else:
                durations.append(delta)

    return MetricSnapshot(
        logical_llm_requests=len(logical_ids),
        physical_llm_attempts=physical,
        llm_retry_count=retries,
        attempts_unknown_outcome=unknown_outcome,
        tool_counts=tool_counts,
        memory_counts=memory_counts,
        learning_counts=learning_counts,
        input_tokens=_sum_optional(inputs),
        output_tokens=_sum_optional(outputs),
        cache_read_tokens=_sum_optional(cache_r),
        cache_write_tokens=_sum_optional(cache_w),
        cost_actual=sum(actual) if actual else None,
        cost_estimated=sum(estimated) if estimated else None,
        cost_unknown=cost_unknown,
        durations_ms=durations,
        clock_anomalies=anomalies,
        terminal_states=terminal,
        coverage_gaps=tuple(sorted(set(gaps))),
        total_events=total,
        duplicate_events=duplicates,
    )
