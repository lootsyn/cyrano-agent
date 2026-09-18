"""Read-only dashboard views over the event ledger.

``render_dashboard`` escapes everything through ``terminal_text`` — a
log line can never inject terminal controls or markup. The headless
path returns a JSON-serializable dict with no ANSI and no prompt, and
no code path here invokes a model.

Self-reported claims render under an explicit ``self_reported``
section and never satisfy the trusted completion status.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from deepagents_code.cyrano.events.catalogue import is_failure_event
from deepagents_code.cyrano.events.metrics import reduce_events
from deepagents_code.cyrano.events.query import ObservationQuery
from deepagents_code.cyrano.monitor.projection import terminal_text


@dataclass(frozen=True, slots=True)
class DashboardReport:
    """What the dashboard may claim about one request."""

    request_id: str
    status: str
    coverage_complete: bool
    coverage_gaps: tuple[str, ...] = ()
    trusted_failures: tuple[dict[str, Any], ...] = ()
    self_reports: tuple[dict[str, Any], ...] = ()
    logical_llm_requests: int | None = None
    physical_llm_attempts: int | None = None
    llm_retry_count: int | None = None
    cost_actual: float | None = None
    cost_estimated: float | None = None
    cost_unknown: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


def render_dashboard(report: DashboardReport) -> str:
    """Render an escaped, terminal-safe text view of one report."""
    lines = [f"request: {report.request_id}"]
    lines.append(f"status: {report.status}")
    if report.coverage_complete:
        lines.append("coverage: complete")
    else:
        lines.append("coverage: unknown")
        for gap in report.coverage_gaps:
            lines.append(f"  gap: {gap}")
    for key in (
        "logical_llm_requests",
        "physical_llm_attempts",
        "llm_retry_count",
        "cost_actual",
        "cost_estimated",
        "cost_unknown",
    ):
        value = getattr(report, key)
        rendered = "unknown" if value is None else str(value)
        lines.append(f"{key}: {rendered}")
    for failure in report.trusted_failures:
        lines.append(
            "failure: "
            + json.dumps(failure, ensure_ascii=False, sort_keys=True)
        )
    for report_item in report.self_reports:
        lines.append(
            "self_reported (unverified): "
            + json.dumps(report_item, ensure_ascii=False, sort_keys=True)
        )
    for key, value in sorted(report.extra.items()):
        lines.append(f"{key}: {value}")
    return terminal_text("\n".join(lines), limit=16000)


_EXPECTED_STAGES = (
    "work.started",
    "model.attempt_started",
    "tool.requested",
    "file.changed",
    "test.finished",
    "work.completed",
)


def build_report(
    query: ObservationQuery,
    scope_id: str,
    stream_id: str,
    *,
    coverage_complete: bool,
    coverage_gaps: tuple[str, ...] = (),
) -> DashboardReport:
    """Derive a report from trusted events; self-reports stay separate.

    A stage with no trusted event is ``not_observed`` — the report
    never fabricates success. A model's "done" claim cannot raise the
    status to ``completed`` while a trusted failure exists.
    """
    rows = list(query.iter_events(scope_id, stream_id))
    trusted = [r for r in rows if r.observation_kind == "trusted"]
    reports = [
        dict(r.payload) for r in rows if r.observation_kind == "self_report"
    ]
    kinds = {r.kind for r in trusted}
    failures = tuple(
        dict(r.payload) for r in trusted if is_failure_event(r.kind, r.payload)
    )
    stages = {
        stage: ("observed" if stage in kinds else "not_observed")
        for stage in _EXPECTED_STAGES
    }
    if "work.cancelled" in kinds:
        status = "cancelled"
    elif failures:
        status = "failed"
    elif "work.completed" in kinds:
        status = "completed"
    elif "work.started" in kinds:
        status = "in_progress"
    else:
        status = "unknown"
    metrics = reduce_events(
        [
            {
                "event_id": r.event_id,
                "kind": r.kind,
                "payload": r.payload,
            }
            for r in trusted
        ]
    )
    return DashboardReport(
        request_id=stream_id,
        status=status,
        coverage_complete=coverage_complete,
        coverage_gaps=coverage_gaps,
        trusted_failures=failures,
        self_reports=tuple(reports),
        logical_llm_requests=metrics.logical_llm_requests,
        physical_llm_attempts=metrics.physical_llm_attempts,
        llm_retry_count=metrics.llm_retry_count,
        cost_actual=metrics.cost_actual,
        cost_estimated=metrics.cost_estimated,
        cost_unknown=metrics.cost_unknown,
        extra={"stages": json.dumps(stages, sort_keys=True)},
    )


def monitor_capability(dispatcher: object) -> dict[str, Any]:
    """Report whether the host can expose a native ``/cyrano`` entry.

    The extension API today registers tools only; without a slash
    registration hook the monitor entry is honestly ``unavailable``
    rather than faked as registered.
    """
    has_slash = callable(getattr(dispatcher, "register_command", None))
    has_tool = callable(getattr(dispatcher, "register_tool", None))
    return {
        "slash_entry": "available" if has_slash else "unavailable",
        "tool_registration": "available" if has_tool else "unavailable",
        "reason": (
            None if has_slash else "extension API exposes register_tool only"
        ),
    }


def headless_view(report: DashboardReport) -> dict[str, Any]:
    """JSON view for non-TTY callers; no ANSI, no prompt, no model."""
    return {
        "schema_version": 1,
        "kind": "cyrano_monitor_view",
        "request_id": report.request_id,
        "status": report.status,
        "coverage": ("complete" if report.coverage_complete else "unknown"),
        "coverage_gaps": list(report.coverage_gaps),
        "trusted_failures": list(report.trusted_failures),
        "self_reports": list(report.self_reports),
        "metrics": {
            "logical_llm_requests": report.logical_llm_requests,
            "physical_llm_attempts": report.physical_llm_attempts,
            "llm_retry_count": report.llm_retry_count,
            "cost_actual": report.cost_actual,
            "cost_estimated": report.cost_estimated,
            "cost_unknown": report.cost_unknown,
        },
    }
