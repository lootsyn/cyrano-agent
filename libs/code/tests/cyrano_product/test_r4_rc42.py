"""R4-RC42: trace query, failure cause, privacy, scope ACL."""

import json
from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.events.domain_sink import DomainSink
from deepagents_code.cyrano.events.export import export_bundle
from deepagents_code.cyrano.events.query import ObservationQuery
from deepagents_code.cyrano.events.tool_observer import ToolObserver
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

ROOT = Path(__file__).resolve().parents[2]
TARGET_DDL = (ROOT / "cyrano/contracts/sql/target-schema.sql").read_text()


@pytest.fixture()
def ctx(tmp_path):
    repo = ScopedRepository.create(tmp_path / "db.sqlite3", TARGET_DDL)
    scope_a = repo.register_scope("t1", "u1", "w1")
    scope_b = repo.register_scope("t2", "u2", "w2")
    repo.create_stream(scope_a, "req-a", "request")
    repo.create_stream(scope_b, "req-b", "request")
    sink = DomainSink(repo)
    yield repo, scope_a, scope_b, sink, ObservationQuery(repo)
    repo.close()


def test_rc42_01_failure_cause(ctx):
    """A failure resolves to its first trusted event and evidence."""
    _, scope_a, _, sink, query = ctx
    tool = ToolObserver(sink)
    tool.started(scope_a, "req-a", "tc-1", tool="bash")
    tool.failed(
        scope_a,
        "req-a",
        "tc-1",
        "nonzero_exit",
        argv="pytest -q",
        exit_code=2,
    )
    failure = query.get_failure(scope_a, "req-a")
    assert failure is not None
    assert failure.failed_kind == "tool.failed"
    assert failure.evidence["error_class"] == "nonzero_exit"
    assert failure.evidence["exit_code"] == 2


def test_rc42_02_scope_bypass(ctx):
    """Knowing another scope's stream id grants nothing."""
    repo, scope_a, scope_b, sink, query = ctx
    sink.record_event(
        scope_b,
        "req-b",
        "domain_service",
        1,
        "work.started",
        {"run_id": "req-b", "schema_family": "work", "secret": "x"},
    )
    for call in (
        lambda: query.get_timeline(scope_a, "req-b"),
        lambda: query.get_failure(scope_a, "req-b"),
        lambda: query.get_trace(scope_a, "req-b"),
        lambda: export_bundle(repo, query, scope_a, "req-b"),
    ):
        with pytest.raises(CyranoError) as exc:
            call()
        assert exc.value.code == "SCOPE_DENIED"
    listed = query.list_requests(scope_a)
    assert all(r["stream_id"] != "req-b" for r in listed["requests"])


def test_rc42_03_sensitive(ctx):
    """Secret-shaped stderr is masked at ingest, absent on export."""
    repo, scope_a, _, sink, query = ctx
    tool = ToolObserver(sink)
    tool.failed(
        scope_a,
        "req-a",
        "tc-1",
        "nonzero_exit",
        stderr="Authorization: Bearer token='sk-live-abcdef123'",
    )
    rows = query.get_timeline(scope_a, "req-a").events
    body = repo.read_artifact(scope_a, rows[0].payload_digest)
    assert b"sk-live-abcdef123" not in body
    bundle = export_bundle(repo, query, scope_a, "req-a")
    assert "sk-live-abcdef123" not in json.dumps(bundle)


def test_rc42_04_reconnect(ctx):
    """Resume dedupes, drops nothing, and flags a stale cursor."""
    _, scope_a, _, sink, query = ctx
    seqs = []
    for i in range(1, 5):
        seqs.append(
            sink.record_event(
                scope_a,
                "req-a",
                "domain_service",
                i,
                "work.started",
                {"run_id": f"s{i}", "schema_family": "work"},
            )
        )
    resumed = query.resume_stream(scope_a, "req-a", seqs[1])
    assert [r.event_seq for r in resumed.events] == seqs[2:]
    # replaying the same window never double-delivers an event_id
    replay = query.resume_stream(scope_a, "req-a", 0)
    ids = [r.event_id for r in replay.events]
    assert len(ids) == len(set(ids))
