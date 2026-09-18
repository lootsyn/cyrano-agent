"""WP02 resume-lifecycle cases RESUME-001..012 at the ledger level."""

import sqlite3
from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

ROOT = Path(__file__).resolve().parents[2]
TARGET_DDL = (ROOT / "cyrano/contracts/sql/target-schema.sql").read_text()


@pytest.fixture()
def repo(tmp_path):
    store = ScopedRepository.create(tmp_path / "db.sqlite3", TARGET_DDL)
    sid = store.register_scope("t1", "u1", "w1")
    store.create_stream(sid, "s1", "session")
    yield store, sid
    store.close()


def test_resume_001_node_resume_reuses_decision(repo):
    store, sid = repo
    first = store.reserve_node(sid, "s1", "question-1")
    again = store.reserve_node(sid, "s1", "question-1")
    assert first == again
    rows = store._db.execute(
        "SELECT COUNT(*) FROM node_reservations"
    ).fetchone()[0]
    assert rows == 1


def test_resume_002_out_of_order_responses_map_by_id(repo):
    store, sid = repo
    store.record_response(sid, "s1", "r2", {"v": 2})
    store.record_response(sid, "s1", "r1", {"v": 1})
    assert store.response_for(sid, "s1", "r1") != (
        store.response_for(sid, "s1", "r2")
    )


def test_resume_003_self_approved_command_blocked(repo):
    store, sid = repo
    with pytest.raises(CyranoError) as exc:
        store.execute_command(
            sid,
            "a",
            "work.execute",
            "k1",
            {"approved": True},
            "s1",
            0,
        )
    assert exc.value.code == "WRONG_PURPOSE"


def test_resume_004_expired_permit_blocks_dispatch(repo):
    store, sid = repo
    store.record_approval(sid, "ap1", "sha256:" + "a" * 64, 100)
    assert store.approval_usable("ap1", 50) is True
    assert store.approval_usable("ap1", 150) is False


def test_resume_005_revoked_approval_blocks_dispatch(repo):
    store, sid = repo
    store.record_approval(sid, "ap1", "sha256:" + "a" * 64, 1000)
    store.revoke_approval("ap1", revision=3)
    assert store.approval_usable("ap1", 50) is False
    store.execute_command(
        sid,
        "a",
        "work.execute",
        "k1",
        {"x": 1},
        "s1",
        0,
        enqueue=True,
    )
    job = store._db.execute("SELECT job_id FROM outbox").fetchone()[0]
    store.cancel_job(sid, job)
    assert store.claim_outbox(sid, "w1", now=1, ttl_seconds=10) is None


def test_resume_006_dispatched_then_revoked_is_unknown(repo):
    store, sid = repo
    assert store.reserve_effect(sid, "s1", "e1", {"t": 1})
    store.dispatch_effect("e1")
    store.mark_effect_unknown("e1")
    row = store._db.execute(
        "SELECT status FROM effect_reservations WHERE effect_key='e1'"
    ).fetchone()
    assert row[0] == "unknown"


def test_resume_007_stale_result_bills_once(repo):
    store, sid = repo
    store.execute_command(
        sid,
        "a",
        "work.execute",
        "k1",
        {"x": 1},
        "s1",
        0,
        enqueue=True,
    )
    lease = store.claim_outbox(sid, "w1", now=1, ttl_seconds=10)
    second = store.claim_outbox(sid, "w2", now=100, ttl_seconds=10)
    assert store.submit_result(lease.job_id, "w1", lease.fence, 5) == "stale"
    units = store._db.execute(
        "SELECT units FROM usage_log WHERE job_id=?",
        (lease.job_id,),
    ).fetchone()[0]
    assert units == 5
    assert (
        store.submit_result(lease.job_id, "w2", second.fence, 9) == "applied"
    )
    units = store._db.execute(
        "SELECT units FROM usage_log WHERE job_id=?",
        (lease.job_id,),
    ).fetchone()[0]
    assert units == 5


def test_resume_008_uncommitted_reservation_never_sends(repo):
    store, sid = repo

    class Crash:
        def __init__(self, real):
            self._real = real

        def execute(self, sql, *a, **k):
            if "INSERT INTO effect_reservations" in str(sql):
                raise sqlite3.OperationalError("crash")
            return self._real.execute(sql, *a, **k)

    real = store._db
    store._db = Crash(real)
    try:
        with pytest.raises(sqlite3.OperationalError):
            store.reserve_effect(sid, "s1", "e1", {"t": 1})
    finally:
        store._db = real
    with pytest.raises(CyranoError) as exc:
        store.dispatch_effect("e1")
    assert exc.value.code == "EFFECT_NOT_RESERVED"


def test_resume_009_replayed_message_is_idempotent(repo):
    store, sid = repo
    req = {"msg": "send"}
    assert store.reserve_effect(sid, "s1", "e1", req) is True
    store.dispatch_effect("e1")
    assert store.reserve_effect(sid, "s1", "e1", req) is False


def test_resume_010_stale_token_result_rejected(repo):
    store, sid = repo
    store.execute_command(
        sid,
        "a",
        "work.execute",
        "k1",
        {"x": 1},
        "s1",
        0,
        enqueue=True,
    )
    old = store.claim_outbox(sid, "w1", now=1, ttl_seconds=5)
    new = store.claim_outbox(sid, "w2", now=100, ttl_seconds=5)
    assert store.submit_result(old.job_id, "w1", old.fence, 3) == "stale"
    assert store.submit_result(old.job_id, "w2", new.fence, 3) == "applied"


def test_resume_011_old_reader_refuses_new_checkpoint(repo):
    store, sid = repo
    store.write_checkpoint("s1", 2, {"s": "v2"})
    with pytest.raises(CyranoError) as exc:
        store.read_checkpoint("s1", reader_version=1)
    assert exc.value.code == "VERSION_CONFLICT"
    assert store.read_checkpoint("s1", reader_version=2)["s"] == "v2"


def test_resume_012_unreachable_sandbox_blocks_not_resets(repo):
    store, sid = repo
    store.execute_command(sid, "a", "work.execute", "k1", {"x": 1}, "s1", 0)
    store.mark_blocked("s1", "sandbox reconnect failed")
    assert store.read_scoped_entity(sid, "s1") == 1
    status = store._db.execute(
        "SELECT status FROM streams WHERE stream_id='s1'"
    ).fetchone()[0]
    assert status == "blocked"
