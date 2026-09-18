"""WP13 product tests: event sink, metrics, query, dashboard honesty."""

import json
from pathlib import Path

import pytest

from deepagents_code.cyrano.cli.dashboard import (
    DashboardReport,
    build_report,
    render_dashboard,
)
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.events.coverage import (
    Coverage,
    record_keepalive,
)
from deepagents_code.cyrano.events.domain_sink import DomainSink
from deepagents_code.cyrano.events.export import export_bundle
from deepagents_code.cyrano.events.metrics import reduce_events
from deepagents_code.cyrano.events.native_observer import (
    EXPECTED_SOURCES,
    NativeObserver,
)
from deepagents_code.cyrano.events.query import ObservationQuery
from deepagents_code.cyrano.events.tool_observer import ToolObserver
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

ROOT = Path(__file__).resolve().parents[2]
TARGET_DDL = (ROOT / "cyrano/contracts/sql/target-schema.sql").read_text()


@pytest.fixture()
def ctx(tmp_path):
    repo = ScopedRepository.create(tmp_path / "db.sqlite3", TARGET_DDL)
    scope = repo.register_scope("t1", "u1", "w1")
    repo.create_stream(scope, "req-1", "request")
    sink = DomainSink(repo)
    yield repo, scope, sink, ObservationQuery(repo)
    repo.close()


def _attempt(
    sink,
    scope,
    seq,
    attempt,
    logical,
    *,
    retry=False,
    finish=True,
    usage=None,
    monotonic=(100, 200),
    **kw,
):
    sink.record_event(
        scope,
        "req-1",
        "native_observer",
        seq,
        "model.attempt_started",
        {
            "attempt_id": attempt,
            "logical_request_id": logical,
            "is_retry": retry,
            "started_monotonic_ms": monotonic[0],
            **kw,
        },
    )
    if finish:
        sink.record_event(
            scope,
            "req-1",
            "native_observer",
            seq + 1000,
            "model.finished",
            {
                "attempt_id": attempt,
                "logical_request_id": logical,
                "finished_monotonic_ms": monotonic[1],
                **({"usage": usage} if usage else {}),
                **kw,
            },
        )


def _events(query, scope):
    return query.get_timeline(scope, "req-1").events


def test_obs_empty(ctx):
    """Empty coverage never reports as complete."""
    _, scope, sink, query = ctx
    report = build_report(
        query,
        scope,
        "req-1",
        coverage_complete=Coverage(frozenset(), frozenset()).complete,
    )
    assert report.status == "unknown"
    assert report.coverage_complete is False
    text = render_dashboard(report)
    assert "coverage: unknown" in text
    assert "complete" not in text.split("coverage:")[1].split("\n")[0]


def test_obs_report(ctx):
    """Trusted failure and self-report render as separate sections."""
    repo, scope, sink, query = ctx
    sink.record_event(
        scope,
        "req-1",
        "runner",
        1,
        "test.finished",
        {"run_id": "req-1", "outcome": "failed", "schema_family": "verify"},
    )
    sink.record_event(
        scope,
        "req-1",
        "runner",
        2,
        "test.finished",
        {
            "run_id": "req-1",
            "outcome": "failed",
            "error_class": "assertion",
            "schema_family": "verify",
        },
    )
    sink.record_untrusted(
        scope,
        "req-1",
        "model",
        1,
        "model.self_report",
        {"claim": "everything passed"},
    )
    report = build_report(query, scope, "req-1", coverage_complete=True)
    text = render_dashboard(report)
    assert "self_reported (unverified)" in text
    failure = query.get_failure(scope, "req-1")
    assert failure is not None
    assert failure.failed_kind == "test.finished"
    assert failure.self_reports[0]["claim"] == "everything passed"


def test_obs_xss(ctx):
    """Rendered views strip terminal controls and markup payloads."""
    report = DashboardReport(
        request_id="r1",
        status="failed",
        coverage_complete=False,
        coverage_gaps=("\x1b[31mgap\x1b]8;;http://x\x07",),
        trusted_failures=({"error": "\x1b]52;;AAAA\x07[bold]"},),
    )
    text = render_dashboard(report)
    assert "\x1b" not in text
    assert "\x07" not in text
    assert "[bold]" in text  # markup stays literal text


def test_obs_secret(ctx):
    """Secret-shaped tool output is masked before durable storage."""
    repo, scope, sink, query = ctx
    tool = ToolObserver(sink)
    tool.failed(
        scope,
        "req-1",
        "tc-1",
        "nonzero_exit",
        stderr="api_key = 'sk-abcdef1234567890'",
    )
    rows = _events(query, scope)
    blob = repo.read_artifact(scope, rows[0].payload_digest)
    assert b"sk-abcdef1234567890" not in blob
    assert "[redacted]" in rows[0].payload["stderr"]
    bundle = export_bundle(repo, query, scope, "req-1")
    assert "sk-abcdef1234567890" not in json.dumps(bundle)


def test_uh_cache_02(ctx):
    """No cache usage field means null, never an estimated hit."""
    _, scope, sink, query = ctx
    _attempt(sink, scope, 1, "a1", "l1", usage={"input_tokens": 10})
    snap = reduce_events(
        [
            {"kind": r.kind, "payload": r.payload, "event_id": r.event_id}
            for r in _events(query, scope)
        ]
    )
    assert snap.cache_read_tokens is None
    assert snap.input_tokens == 10


def test_uh_cache_03():
    """A faster second call is never reported as a cache hit."""
    obs = record_keepalive(observed_ping=True)
    assert obs.network_reachable is True
    assert obs.cache_read is None  # latency alone proves nothing


def test_uh_obs_01_leaf_only(ctx):
    """Parent aggregates never double a child's own attempt."""
    _, scope, sink, query = ctx
    _attempt(sink, scope, 1, "a1", "l1")
    sink.record_event(
        scope,
        "req-1",
        "native_observer",
        5,
        "model.attempt_started",
        {
            "attempt_id": "parent-agg",
            "logical_request_id": "l1",
            "is_retry": False,
            "aggregate_only": True,
            "started_monotonic_ms": 0,
        },
    )
    snap = reduce_events(
        [
            {"kind": r.kind, "payload": r.payload, "event_id": r.event_id}
            for r in _events(query, scope)
        ]
    )
    assert snap.logical_llm_requests == 1
    assert snap.physical_llm_attempts == 1


def test_uh_obs_02(ctx):
    """One logical call with three attempts: logical 1, retries 2."""
    _, scope, sink, query = ctx
    for i in range(3):
        _attempt(sink, scope, i * 2 + 1, f"a{i}", "l1", retry=i > 0)
    snap = reduce_events(
        [
            {"kind": r.kind, "payload": r.payload, "event_id": r.event_id}
            for r in _events(query, scope)
        ]
    )
    assert snap.logical_llm_requests == 1
    assert snap.physical_llm_attempts == 3
    assert snap.llm_retry_count == 2


def test_uh_obs_03(ctx):
    """An unobservable internal retry is a gap, not a zero."""
    _, scope, sink, _ = ctx
    obs = NativeObserver(sink)
    obs.note_source("main_model", "observed_verified")
    obs.note_source("internal_retry", "unsupported")
    obs.note_internal_gap(scope, "req-1", "transport cannot see retry")
    report = obs.coverage_report()
    assert report["complete"] is False
    assert "internal_retry" in report["gaps"]


def test_uh_obs_04(ctx):
    """Exporter outage keeps the durable local event and the outbox."""
    repo, scope, sink, query = ctx
    sink.record_event(
        scope,
        "req-1",
        "domain_service",
        1,
        "work.started",
        {"run_id": "req-1", "schema_family": "work"},
    )

    def enqueue(db):
        row = db.execute(
            "SELECT event_id,payload_digest FROM events "
            "WHERE stream_id=? ORDER BY event_seq LIMIT 1",
            ("req-1",),
        ).fetchone()
        db.execute(
            "INSERT INTO outbox(job_id,event_id,scope_id,"
            "payload_digest,state,deadline,meta_depth) "
            "VALUES ('job-1',?,?,?,'pending','9999',0)",
            (row[0], scope, row[1]),
        )

    sink.commit_transition(
        scope,
        "req-1",
        "domain_service",
        2,
        "work.completed",
        {"run_id": "req-1", "schema_family": "work"},
        enqueue,
    )
    # The "exporter" never claims the job; the event stays durable and
    # the lag is visible rather than silently dropped.
    assert repo.export_lag(scope) >= 1
    rows = _events(query, scope)
    assert [r.kind for r in rows] == ["work.started", "work.completed"]


def test_uh_obs_05(ctx):
    """A canary in stdout is masked at store and absent from export."""
    repo, scope, sink, query = ctx
    tool = ToolObserver(sink)
    tool.finished(
        scope,
        "req-1",
        "tc-9",
        stdout="token=AKIAIOSFODNN7EXAMPLE done",
    )
    rows = _events(query, scope)
    assert "AKIAIOSFODNN7EXAMPLE" not in json.dumps(rows[0].payload)
    bundle = export_bundle(repo, query, scope, "req-1")
    assert "AKIAIOSFODNN7EXAMPLE" not in json.dumps(bundle)


def test_uh_obs_06(ctx):
    """A missing child-graph probe blocks full-coverage claims."""
    _, scope, sink, _ = ctx
    obs = NativeObserver(sink)
    for source in EXPECTED_SOURCES:
        obs.note_source(source, "observed_verified")
    obs.note_source("child_graph", "not_tested")
    report = obs.coverage_report()
    assert report["complete"] is False
    assert "child_graph" in report["gaps"]


def test_uh_obs_07(ctx):
    """Commit order and source time are preserved separately."""
    _, scope, sink, query = ctx
    sink.record_event(
        scope,
        "req-1",
        "domain_service",
        1,
        "work.started",
        {"run_id": "req-1", "occurred_at": "T+9", "schema_family": "work"},
    )
    sink.record_event(
        scope,
        "req-1",
        "domain_service",
        2,
        "work.failed",
        {"run_id": "req-1", "occurred_at": "T+1", "schema_family": "work"},
    )
    rows = _events(query, scope)
    assert rows[0].event_seq < rows[1].event_seq
    assert rows[0].payload["occurred_at"] == "T+9"
    assert rows[1].payload["occurred_at"] == "T+1"  # late source kept


def test_uh_obs_08(ctx):
    """Reconnect after seq N replays N+1 onward, dedupe-safe."""
    _, scope, sink, query = ctx
    for i in range(1, 6):
        sink.record_event(
            scope,
            "req-1",
            "domain_service",
            i,
            "work.started",
            {"run_id": f"step-{i}", "schema_family": "work"},
        )
    rows = _events(query, scope)
    mid = rows[2].event_seq
    resumed = query.resume_stream(scope, "req-1", mid)
    assert [r.event_seq for r in resumed.events] == [
        r.event_seq for r in rows[3:]
    ]
    assert resumed.stale_cursor is False


def test_uh_obs_09(ctx):
    """A session-A token cannot read session-B's request."""
    repo, scope, sink, query = ctx
    other = repo.register_scope("t1", "u1", "w2")
    repo.create_stream(other, "req-b", "request")
    with pytest.raises(CyranoError) as exc:
        query.get_timeline(scope, "req-b")
    assert exc.value.code == "SCOPE_DENIED"
    with pytest.raises(CyranoError):
        query.get_failure(scope, "req-b")


def test_uh_obs_10(ctx):
    """A 'done' claim cannot outrank a trusted failed check."""
    _, scope, sink, query = ctx
    sink.record_event(
        scope,
        "req-1",
        "domain_service",
        1,
        "work.started",
        {"run_id": "req-1", "schema_family": "work"},
    )
    sink.record_event(
        scope,
        "req-1",
        "runner",
        2,
        "test.finished",
        {"run_id": "req-1", "outcome": "failed", "schema_family": "verify"},
    )
    sink.record_untrusted(
        scope,
        "req-1",
        "model",
        3,
        "model.self_report",
        {"claim": "task completed"},
    )
    report = build_report(query, scope, "req-1", coverage_complete=True)
    assert report.status == "failed"
    assert report.self_reports[0]["claim"] == "task completed"


def test_uh_obs_11(ctx):
    """Coverage only ever claims the registered own sources."""
    _, scope, sink, _ = ctx
    obs = NativeObserver(sink)
    with pytest.raises(CyranoError) as exc:
        obs.note_source("other_ide_assistant", "observed_verified")
    assert exc.value.code == "UNKNOWN_SOURCE"
    assert set(obs.coverage_report()["sources"]) <= set(EXPECTED_SOURCES)


def test_uh_obs_12(ctx):
    """Missing pricing splits cost_unknown from reported tokens."""
    _, scope, sink, query = ctx
    _attempt(sink, scope, 1, "a1", "l1", usage={"input_tokens": 100})
    _attempt(
        sink,
        scope,
        5,
        "a2",
        "l2",
        usage={"input_tokens": 50, "cost_actual": "0.01"},
    )
    snap = reduce_events(
        [
            {"kind": r.kind, "payload": r.payload, "event_id": r.event_id}
            for r in _events(query, scope)
        ]
    )
    assert snap.cost_actual == pytest.approx(0.01)
    assert snap.cost_unknown == 1
    assert snap.input_tokens == 150


def test_integ_typed_payload(ctx):
    """A mismatched payload family refuses the event commit."""
    repo, scope, sink, query = ctx
    with pytest.raises(CyranoError) as exc:
        sink.record_event(
            scope,
            "req-1",
            "native_observer",
            1,
            "model.finished",
            {
                "attempt_id": "a1",
                "logical_request_id": "l1",
                "schema_family": "approval",
                "approval_id": "x",
            },
        )
    assert exc.value.code == "EVENT_PAYLOAD_FAMILY_MISMATCH"
    assert _events(query, scope) == ()
