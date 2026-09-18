"""WP02 contract scenarios CON-REC-01..12 on the real ledger."""

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
    store.create_stream(sid, "s1", "run")
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
    yield store, sid
    store.close()


class _FailOn:
    """Connection proxy that raises inside a transaction."""

    def __init__(self, real, needle: str):
        self._real = real
        self._needle = needle

    def execute(self, sql, *args, **kwargs):
        if self._needle in str(sql):
            raise sqlite3.OperationalError("injected crash")
        return self._real.execute(sql, *args, **kwargs)

    def executescript(self, sql):
        return self._real.executescript(sql)


class TestCrashRecovery:
    def test_con_rec_01_claim_crash_keeps_pending(self, repo):
        store, sid = repo
        store._db = _FailOn(store._db, "UPDATE outbox")
        try:
            with pytest.raises(sqlite3.OperationalError):
                store.claim_outbox(sid, "w1", now=100, ttl_seconds=10)
        finally:
            store._db = store._db._real
        assert (
            store.job_state(
                store._db.execute("SELECT job_id FROM outbox").fetchone()[0]
            )
            == "pending"
        )

    def test_con_rec_02_committed_claim_survives(self, repo, tmp_path):
        store, sid = repo
        lease = store.claim_outbox(sid, "w1", now=100, ttl_seconds=10)
        store.close()
        reopened = ScopedRepository.open(tmp_path / "db.sqlite3")
        assert reopened.job_state(lease.job_id) == "leased"
        again = reopened.claim_outbox(sid, "w2", now=200, ttl_seconds=10)
        assert again is not None
        reopened.close()

    def test_con_rec_03_unsettled_write_is_unknown(self, repo):
        store, sid = repo
        lease = store.claim_outbox(sid, "w1", now=100, ttl_seconds=10)
        store.mark_job_unknown(lease.job_id)
        assert store.job_state(lease.job_id) == "unknown"

    def test_con_rec_04_old_process_loses_lease(self, repo):
        store, sid = repo
        first = store.claim_outbox(sid, "w1", now=100, ttl_seconds=10)
        second = store.claim_outbox(sid, "w2", now=200, ttl_seconds=10)
        with pytest.raises(CyranoError) as exc:
            store.finish_outbox(first.job_id, "w1", first.fence, 201)
        assert exc.value.code == "STALE_LEASE"
        store.finish_outbox(second.job_id, "w2", second.fence, 201)

    def test_con_rec_05_corrupt_checkpoint_blocked(self, repo):
        store, sid = repo
        store.write_checkpoint("s1", 1, {"state": "ok"})
        store._db.execute(
            "UPDATE checkpoints SET body='{}' WHERE stream_id='s1'"
        )
        with pytest.raises(CyranoError) as exc:
            store.read_checkpoint("s1", reader_version=2)
        assert exc.value.code == "CORRUPT_CHECKPOINT"

    def test_con_rec_06_export_lag_reported(self, repo):
        store, sid = repo
        assert store.export_lag(sid) == 1
        lease = store.claim_outbox(sid, "w1", now=1, ttl_seconds=10)
        store.finish_outbox(lease.job_id, "w1", lease.fence, 2)
        assert store.export_lag(sid) == 0

    def test_con_rec_07_audit_write_failure_is_typed(self, repo):
        store, sid = repo
        store._db = _FailOn(store._db, "INSERT INTO audit_log")
        try:
            with pytest.raises(sqlite3.OperationalError):
                store.audit("s1", "detail")
        finally:
            store._db = store._db._real

        class FullDisk:
            def execute(self, *a, **k):
                raise sqlite3.OperationalError("database or disk is full")

        real = store._db
        store._db = FullDisk()
        try:
            with pytest.raises(CyranoError) as exc:
                store.audit("s1", "x")
            assert exc.value.code == "AUDIT_UNAVAILABLE"
        finally:
            store._db = real

    def test_con_rec_08_cancel_blocks_dispatch(self, repo):
        store, sid = repo
        job = store._db.execute("SELECT job_id FROM outbox").fetchone()[0]
        store.cancel_job(sid, job)
        assert store.claim_outbox(sid, "w1", now=1, ttl_seconds=10) is None
        assert store.job_state(job) == "cancelled"

    def test_con_rec_09_effect_reservation_dedupes(self, repo):
        store, sid = repo
        req = {"tool": "write", "path": "x"}
        assert store.reserve_effect(sid, "s1", "e1", req) is True
        store.dispatch_effect("e1")
        assert store.reserve_effect(sid, "s1", "e1", req) is False
        with pytest.raises(CyranoError) as exc:
            store.reserve_effect(sid, "s1", "e1", {"tool": "rm"})
        assert exc.value.code == "IDEMPOTENCY_CONFLICT"

    def test_con_rec_10_monotonic_lease_floor(self, repo):
        store, sid = repo
        first = store.claim_outbox(sid, "w1", now=100, ttl_seconds=10)
        store.cancel_job(sid, first.job_id)
        store.execute_command(
            sid,
            "a",
            "work.execute",
            "k2",
            {"x": 2},
            "s1",
            1,
            enqueue=True,
        )
        second = store.claim_outbox(sid, "w2", now=50, ttl_seconds=10)
        assert int(second.lease_until) >= 110 + 10 - 10
        assert int(second.lease_until) == 110 + 10

    def test_con_rec_11_tombstone_wins_over_backup(self, repo, tmp_path):
        store, sid = repo
        backup = tmp_path / "b.sqlite3"
        store.backup(backup)
        store.delete_stream("s1", "t")
        store.restore(backup)
        with pytest.raises(CyranoError) as exc:
            store.read_scoped_entity(sid, "s1")
        assert exc.value.code == "SCOPE_DENIED"

    def test_con_rec_12_blocked_preserves_state(self, repo):
        store, sid = repo
        store.mark_blocked("s1", "sandbox unreachable")
        status = store._db.execute(
            "SELECT status FROM streams WHERE stream_id='s1'"
        ).fetchone()[0]
        assert status == "blocked"
        assert store.read_scoped_entity(sid, "s1") == 1
