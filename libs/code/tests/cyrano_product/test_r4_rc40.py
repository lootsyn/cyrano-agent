"""R4-RC40: request timeline and transactional event/outbox writes."""

from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.events.domain_sink import DomainSink
from deepagents_code.cyrano.events.query import ObservationQuery
from deepagents_code.cyrano.events.reconcile import reconcile_attempts
from deepagents_code.cyrano.events.recovery import recover_orphans
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

ROOT = Path(__file__).resolve().parents[2]
TARGET_DDL = (ROOT / "cyrano/contracts/sql/target-schema.sql").read_text()


@pytest.fixture()
def ctx(tmp_path):
    repo = ScopedRepository.create(tmp_path / "db.sqlite3", TARGET_DDL)
    scope = repo.register_scope("t1", "u1", "w1")
    repo.create_stream(scope, "req-1", "request")
    yield repo, scope, DomainSink(repo), ObservationQuery(repo)
    repo.close()


def _rows(query, scope):
    return query.get_timeline(scope, "req-1").events


def test_rc40_01_full_flow(ctx):
    """A mutation and its events commit atomically with the outbox."""
    repo, scope, sink, query = ctx

    # outbox.event_id references events(event_id); link to the row
    # committed just before inside the same transaction.
    def enqueue(db):
        db.execute(
            "INSERT INTO outbox(job_id,event_id,scope_id,"
            "payload_digest,state,deadline,meta_depth) "
            "SELECT 'job-x', event_id, ?, payload_digest,"
            "'pending','9999',0 FROM events WHERE stream_id=? "
            "ORDER BY event_seq LIMIT 1",
            (scope, "req-1"),
        )

    sink.record_event(
        scope,
        "req-1",
        "domain_service",
        1,
        "work.started",
        {"run_id": "req-1", "schema_family": "work"},
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
    rows = _rows(query, scope)
    assert [r.kind for r in rows] == ["work.started", "work.completed"]
    job = repo.claim_outbox(scope, "w", 1, 60)
    assert job is not None and job.job_id == "job-x"


def test_rc40_02_audit_failure(ctx):
    """A failed event write rolls the mutation back with it."""
    repo, scope, sink, query = ctx
    marker = []

    def mutate(db):
        marker.append("applied")
        db.execute(
            "UPDATE streams SET status='running' WHERE stream_id=?",
            ("req-1",),
        )

    with pytest.raises(CyranoError) as exc:
        sink.commit_transition(
            scope,
            "req-1",
            "model",
            1,
            "work.completed",
            {"run_id": "req-1", "schema_family": "work"},
            mutate,
        )
    assert exc.value.code == "EVENT_PRODUCER_DENIED"
    assert marker == []  # authorize fails before mutate even runs

    def mutate2(db):
        db.execute(
            "UPDATE streams SET status='running' WHERE stream_id=?",
            ("req-1",),
        )
        raise ValueError("simulated mutation fault")

    with pytest.raises(ValueError):
        sink.commit_transition(
            scope,
            "req-1",
            "domain_service",
            1,
            "work.completed",
            {"run_id": "req-1", "schema_family": "work"},
            mutate2,
        )
    status = repo.connection.execute(
        "SELECT status FROM streams WHERE stream_id='req-1'"
    ).fetchone()[0]
    assert status == "open"  # rolled back, not left half-applied
    assert _rows(query, scope) == ()


def test_rc40_03_dup_and_order(ctx):
    """Same producer_seq+payload dedupes; changed payload conflicts."""
    repo, scope, sink, query = ctx
    payload = {
        "attempt_id": "a1",
        "logical_request_id": "l1",
        "is_retry": False,
        "schema_family": "model",
    }
    first = sink.record_event(
        scope,
        "req-1",
        "native_observer",
        1,
        "model.attempt_started",
        payload,
    )
    again = sink.record_event(
        scope,
        "req-1",
        "native_observer",
        1,
        "model.attempt_started",
        payload,
    )
    assert again == first
    assert len(_rows(query, scope)) == 1
    with pytest.raises(CyranoError) as exc:
        sink.record_event(
            scope,
            "req-1",
            "native_observer",
            1,
            "model.attempt_started",
            {**payload, "is_retry": True},
        )
    assert exc.value.code == "IDEMPOTENCY_CONFLICT"


def test_rc40_04_crash(ctx):
    """A crashed writer's orphan attempt reconciles, never re-runs."""
    repo, scope, sink, query = ctx
    sink.record_event(
        scope,
        "req-1",
        "native_observer",
        1,
        "model.attempt_started",
        {
            "attempt_id": "a-orphan",
            "logical_request_id": "l1",
            "is_retry": False,
            "schema_family": "model",
        },
    )
    rows = [
        {"event_seq": r.event_seq, "kind": r.kind, "payload": r.payload}
        for r in _rows(query, scope)
    ]
    report = reconcile_attempts(rows)
    assert report.orphan_attempt_ids == ("a-orphan",)

    # remote says nothing came back -> marked unknown, not re-executed
    recovery = recover_orphans(
        sink, query, scope, "req-1", lambda attempt_id: None
    )
    assert recovery.marked_unknown == ("a-orphan",)
    rows2 = _rows(query, scope)
    assert rows2[-1].kind == "model.failed"
    assert rows2[-1].payload["error_class"] == "unknown_outcome"
