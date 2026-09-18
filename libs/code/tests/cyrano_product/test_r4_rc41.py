"""R4-RC41: native call coverage and metric correctness."""

from pathlib import Path

import pytest

from deepagents_code.cyrano.events.domain_sink import DomainSink
from deepagents_code.cyrano.events.metrics import reduce_events
from deepagents_code.cyrano.events.native_observer import NativeObserver
from deepagents_code.cyrano.events.query import ObservationQuery
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

ROOT = Path(__file__).resolve().parents[2]
TARGET_DDL = (ROOT / "cyrano/contracts/sql/target-schema.sql").read_text()


@pytest.fixture()
def ctx(tmp_path):
    repo = ScopedRepository.create(tmp_path / "db.sqlite3", TARGET_DDL)
    scope = repo.register_scope("t1", "u1", "w1")
    repo.create_stream(scope, "req-1", "request")
    sink = DomainSink(repo)
    yield repo, scope, sink, ObservationQuery(repo), NativeObserver(sink)
    repo.close()


def _snap(ctx):
    _, scope, _, query, _ = ctx
    rows = query.get_timeline(scope, "req-1").events
    return reduce_events(
        [
            {"kind": r.kind, "payload": r.payload, "event_id": r.event_id}
            for r in rows
        ]
    )


def test_rc41_01_retry_and_child(ctx):
    """Retries and child-graph calls classify as separate operations."""
    _, scope, _, _, obs = ctx
    obs.observe_provider_attempt(
        scope,
        "req-1",
        {
            "attempt_id": "a1",
            "logical_request_id": "l1",
            "is_retry": False,
            "operation_kind": "main",
        },
        finished=False,
    )
    obs.observe_provider_attempt(
        scope,
        "req-1",
        {
            "attempt_id": "a2",
            "logical_request_id": "l1",
            "is_retry": True,
            "operation_kind": "main",
        },
        finished=True,
    )
    obs.observe_provider_attempt(
        scope,
        "req-1",
        {
            "attempt_id": "c1",
            "logical_request_id": "l2",
            "is_retry": False,
            "operation_kind": "child_graph",
        },
        finished=True,
    )
    snap = _snap(ctx)
    assert snap.physical_llm_attempts == 3
    assert snap.llm_retry_count == 1
    assert snap.logical_llm_requests == 2


def test_rc41_02_negative_time(ctx):
    """A reversed clock flags an anomaly; duration is never clamped."""
    _, scope, _, _, obs = ctx
    obs.observe_provider_attempt(
        scope,
        "req-1",
        {
            "attempt_id": "a1",
            "logical_request_id": "l1",
            "is_retry": False,
            "started_monotonic_ms": 1250,
        },
        finished=False,
    )
    obs.observe_provider_attempt(
        scope,
        "req-1",
        {
            "attempt_id": "a1",
            "logical_request_id": "l1",
            "is_retry": False,
            "finished_monotonic_ms": 1000,
        },
        finished=True,
    )
    snap = _snap(ctx)
    assert snap.clock_anomalies == 1
    assert snap.durations_ms == []  # not silently reported as 0


def test_rc41_03_cache_usage_missing(ctx):
    """Missing cache fields stay null — never coerced to zero."""
    _, scope, _, _, obs = ctx
    obs.observe_provider_attempt(
        scope,
        "req-1",
        {"attempt_id": "a1", "logical_request_id": "l1", "is_retry": False},
        finished=True,
        usage={"input_tokens": 42},
    )
    snap = _snap(ctx)
    assert snap.input_tokens == 42
    assert snap.cache_read_tokens is None
    assert snap.cache_write_tokens is None


def test_rc41_04_hidden_call_path(ctx):
    """An offload the hook cannot see stays a declared coverage gap."""
    _, scope, sink, _, obs = ctx
    obs.note_source("main_model", "observed_verified")
    obs.note_source("tool_offload", "unsupported")
    obs.note_internal_gap(scope, "req-1", "offload path unobserved")
    report = obs.coverage_report()
    assert report["complete"] is False
    assert "tool_offload" in report["gaps"]
    snap = _snap(ctx)
    assert "telemetry.gap:offload path unobserved" in snap.coverage_gaps
