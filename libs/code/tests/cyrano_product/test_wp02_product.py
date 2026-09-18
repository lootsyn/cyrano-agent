"""WP02 product tests: scoped ledger, migration, fencing.

Each STORE/UH/INTEG acceptance case runs against a real SQLite
database in a temp directory — no fixture doubles stand in for the
transaction layer.
"""

import sqlite3
from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.sqlite.migrations import (
    apply_migration,
    inspect_database,
    plan_migration,
)
from deepagents_code.cyrano.sqlite.repository import ScopedRepository
from deepagents_code.cyrano.sqlite.store import DDL as FOUNDATION_DDL

ROOT = Path(__file__).resolve().parents[2]
TARGET_DDL = (ROOT / "cyrano/contracts/sql/target-schema.sql").read_text()


@pytest.fixture()
def repo(tmp_path):
    store = ScopedRepository.create(tmp_path / "db.sqlite3", TARGET_DDL)
    yield store
    store.close()


@pytest.fixture()
def scoped(repo):
    sid = repo.register_scope("t1", "u1", "w1")
    repo.create_stream(sid, "stream-1", "plan")
    return sid


class TestScopeIsolation:
    """STORE-SCOPE: data outside the caller scope is never returned."""

    def test_cross_scope_read_denied(self, repo, scoped):
        other = repo.register_scope("t2", "u2", "w2")
        with pytest.raises(CyranoError) as exc:
            repo.read_scoped_entity(other, "stream-1")
        assert exc.value.code == "SCOPE_DENIED"

    def test_unknown_stream_same_denial(self, repo, scoped):
        with pytest.raises(CyranoError) as exc:
            repo.read_scoped_entity(scoped, "no-such-stream")
        assert exc.value.code == "SCOPE_DENIED"

    def test_scoped_read_returns_revision(self, repo, scoped):
        assert repo.read_scoped_entity(scoped, "stream-1") == 0


class TestCommandTransactions:
    """STORE-CRASH, UH-RUN-01/02/03/05 transactional semantics."""

    def test_stale_revision_rejected(self, repo, scoped):
        repo.execute_command(
            scoped,
            "a",
            "plan.propose",
            "k1",
            {"x": 1},
            "stream-1",
            0,
        )
        with pytest.raises(CyranoError) as exc:
            repo.execute_command(
                scoped,
                "b",
                "plan.propose",
                "k2",
                {"x": 2},
                "stream-1",
                0,
            )
        assert exc.value.code == "STALE_REVISION"
        assert repo.read_scoped_entity(scoped, "stream-1") == 1

    def test_telemetry_does_not_bump_control_revision(self, repo, scoped):
        repo.execute_command(
            scoped,
            "a",
            "plan.propose",
            "k1",
            {"x": 1},
            "stream-1",
            0,
        )
        repo.record_observation(scoped, "stream-1", "metrics", 1, {"cpu": 1})
        assert repo.read_scoped_entity(scoped, "stream-1") == 1

    def test_duplicate_producer_seq_deduped(self, repo, scoped):
        first = repo.record_observation(scoped, "stream-1", "w1", 7, {"v": 1})
        again = repo.record_observation(scoped, "stream-1", "w1", 7, {"v": 1})
        assert first == again
        with pytest.raises(CyranoError) as exc:
            repo.record_observation(scoped, "stream-1", "w1", 7, {"v": 2})
        assert exc.value.code == "IDEMPOTENCY_CONFLICT"

    def test_idempotent_command_replay(self, repo, scoped):
        repo.execute_command(
            scoped,
            "a",
            "plan.propose",
            "k1",
            {"x": 1},
            "stream-1",
            0,
        )
        r2 = repo.execute_command(
            scoped,
            "a",
            "plan.propose",
            "k1",
            {"x": 1},
            "stream-1",
            0,
        )
        assert r2.idempotent_replay is True
        assert repo.read_scoped_entity(scoped, "stream-1") == 1

    def test_forced_error_rolls_back_all(self, repo, scoped):
        real = repo._db

        class Boom:
            def execute(self, *a, **k):
                if "INSERT INTO events" in str(a[0]):
                    raise sqlite3.OperationalError("forced")
                return real.execute(*a, **k)

        repo._db = Boom()
        try:
            with pytest.raises(sqlite3.OperationalError):
                repo.execute_command(
                    scoped,
                    "a",
                    "plan.propose",
                    "k9",
                    {"x": 1},
                    "stream-1",
                    0,
                )
        finally:
            repo._db = real
        assert repo.read_scoped_entity(scoped, "stream-1") == 0
        row = repo._db.execute("SELECT COUNT(*) FROM requests").fetchone()
        assert row[0] == 0
        row = repo._db.execute("SELECT COUNT(*) FROM events").fetchone()
        assert row[0] == 0

    def test_self_approved_payload_rejected(self, repo, scoped):
        with pytest.raises(CyranoError) as exc:
            repo.execute_command(
                scoped,
                "a",
                "work.execute",
                "k1",
                {"approved": True},
                "stream-1",
                0,
            )
        assert exc.value.code == "WRONG_PURPOSE"


class TestMigrationGuards:
    """STORE-FUTURE, UH-OPS-05, INTEG-MIGRATION."""

    def test_future_schema_refused(self, tmp_path):
        path = tmp_path / "db.sqlite3"
        ScopedRepository.create(path, TARGET_DDL).close()
        db = sqlite3.connect(str(path))
        db.execute("PRAGMA user_version=99")
        db.commit()
        db.close()
        with pytest.raises(CyranoError) as exc:
            ScopedRepository.open(path)
        assert exc.value.code == "FUTURE_SCHEMA"

    def test_foundation_db_needs_explicit_migration(self, tmp_path):
        path = tmp_path / "db.sqlite3"
        db = sqlite3.connect(str(path))
        db.executescript(FOUNDATION_DDL)
        db.close()
        with pytest.raises(CyranoError) as exc:
            ScopedRepository.open(path)
        assert exc.value.code == "UNVERSIONED_DATABASE"

    def test_plan_requires_backup_and_mapping(self, tmp_path):
        path = tmp_path / "db.sqlite3"
        db = sqlite3.connect(str(path))
        db.executescript(FOUNDATION_DDL)
        plan = plan_migration(db, TARGET_DDL)
        db.close()
        assert plan.requires_backup is True
        assert plan.field_mapping["streams.stream"] == ("streams.stream_id")

    def test_foundation_migration_applies_rows(self, tmp_path):
        path = tmp_path / "db.sqlite3"
        db = sqlite3.connect(str(path))
        db.executescript(FOUNDATION_DDL)
        db.execute("INSERT INTO streams VALUES ('s',0)")
        db.execute("INSERT INTO events VALUES ('s',1,'{}','d1')")
        db.commit()
        plan = plan_migration(db, TARGET_DDL)
        db.close()
        apply_migration(
            path,
            plan,
            tmp_path / "b.sqlite3",
            default_scope=("t", "u", "w"),
        )
        repo = ScopedRepository.open(path)
        sid = repo.register_scope("t", "u", "w")
        assert repo.read_scoped_entity(sid, "s") == 0
        repo.close()

    def test_failed_migration_restores_backup(self, tmp_path):
        path = tmp_path / "db.sqlite3"
        backup = tmp_path / "backup.sqlite3"
        repo = ScopedRepository.create(path, TARGET_DDL)
        repo.register_scope("t", "u", "w")
        repo.close()
        conn = sqlite3.connect(str(path))
        plan = plan_migration(conn, "CREATE TABLE broken (")
        conn.close()
        with pytest.raises(Exception):
            apply_migration(path, plan, backup)
        conn = sqlite3.connect(str(path))
        info = inspect_database(conn)
        assert info.integrity_ok is True
        assert conn.execute("SELECT COUNT(*) FROM scopes").fetchone()[0] == 1
        conn.close()

    def test_open_never_merges_ddl(self, tmp_path):
        path = tmp_path / "db.sqlite3"
        ScopedRepository.create(path, TARGET_DDL).close()
        repo = ScopedRepository.open(path)
        assert repo.verify_integrity() is True
        repo.close()


class TestFencing:
    """STORE-FENCE: stale fences are rejected."""

    def test_stale_fence_finish_rejected(self, repo, scoped):
        repo.execute_command(
            scoped,
            "a",
            "work.execute",
            "k1",
            {"x": 1},
            "stream-1",
            0,
            enqueue=True,
        )
        lease = repo.claim_outbox(scoped, "w1", now=100, ttl_seconds=10)
        assert lease is not None
        expired = repo.claim_outbox(scoped, "w2", now=200, ttl_seconds=10)
        assert expired is not None and expired.fence > lease.fence
        with pytest.raises(CyranoError) as exc:
            repo.finish_outbox(lease.job_id, "w1", lease.fence, 201)
        assert exc.value.code == "STALE_LEASE"

    def test_unknown_reconcile_requeue(self, repo, scoped):
        repo.execute_command(
            scoped,
            "a",
            "work.execute",
            "k1",
            {"x": 1},
            "stream-1",
            0,
            enqueue=True,
        )
        lease = repo.claim_outbox(scoped, "w1", now=100, ttl_seconds=10)
        repo.mark_job_unknown(lease.job_id)
        assert repo.job_state(lease.job_id) == "unknown"
        repo.reconcile_unknown(lease.job_id, "requeue")
        assert repo.job_state(lease.job_id) == "pending"
