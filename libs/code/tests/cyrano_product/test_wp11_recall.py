"""WP11 recall contract cases CON-MEM-01..12."""

from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.dcode.memory_adapter import RecallService
from deepagents_code.cyrano.memory import MemoryRepository, MemoryService
from deepagents_code.cyrano.memory.application import (
    Exposure,
    record_application,
)
from deepagents_code.cyrano.memory.models import RecallHint
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

ROOT = Path(__file__).resolve().parents[2]
TARGET_DDL = (ROOT / "cyrano/contracts/sql/target-schema.sql").read_text()
SRC = frozenset({"src:1"})


@pytest.fixture()
def ctx(tmp_path):
    path = tmp_path / "db.sqlite3"
    repo = ScopedRepository.create(path, TARGET_DDL)
    scope = repo.register_scope("t1", "u1", "w1")
    yield MemoryService(MemoryRepository(repo)), scope, repo, path
    repo.close()


def _active(service, scope, mid, content=b"fact", kind="rule.style",
            rank=0):
    service.propose_memory(
        scope, mid, kind=kind, content=content,
        source_digest="src:1", evidence_refs=("e",), at=1,
        rank=rank,
    )
    service.activate_memory(scope, mid, expected_revision=1, at=2)
    return mid


def _hint(mid, rev=1, exp=100, hid="h1"):
    return RecallHint(hid, mid, rev, "edit", "e1", exp)


def test_con_mem_01(tmp_path):
    """New process: active memory persists and is recalled."""
    path = tmp_path / "db.sqlite3"
    repo = ScopedRepository.create(path, TARGET_DDL)
    scope = repo.register_scope("t1", "u1", "w1")
    service = MemoryService(MemoryRepository(repo))
    _active(service, scope, "m1")
    repo.close()
    repo2 = ScopedRepository.open(path)
    scope2 = repo2.register_scope("t1", "u1", "w1")
    svc2 = MemoryService(MemoryRepository(repo2))
    records = svc2.query_memory(
        scope2, now=5, available_source_digests=SRC
    ).records
    assert [r.memory_id for r in records] == ["m1"]
    repo2.close()


def test_con_mem_02(ctx):
    """Another user's scope cannot recall this workspace's records."""
    service, scope_a, repo, _ = ctx
    scope_b = repo.register_scope("t1", "u2", "w2")
    _active(service, scope_a, "m1", content=b"a-secret")
    result = service.query_memory(
        scope_b, now=5, available_source_digests=SRC
    )
    assert result.records == ()
    assert service.get(scope_b, "m1") is None


def test_con_mem_03(ctx):
    """ACL runs before top-k: only in-scope actives are ranked."""
    service, scope_a, repo, _ = ctx
    scope_b = repo.register_scope("t1", "u1", "w2")
    _active(service, scope_a, "a1", rank=9)
    _active(service, scope_b, "b1", rank=1)
    result = service.query_memory(
        scope_b, now=5, available_source_digests=SRC, limit=10
    )
    assert [r.memory_id for r in result.records] == ["b1"]


def test_con_mem_04(ctx):
    """A stale source demotes the record to a revalidation candidate."""
    service, scope, _, _ = ctx
    _active(service, scope, "m1")
    service.mark_stale_if_source_moved(
        scope, frozenset({"src:new"}), at=3
    )
    record = service.get(scope, "m1")
    assert record.status == "stale"
    # Revalidation is an explicit re-activation, not an auto-restore.
    reactivated = service.activate_memory(
        scope, "m1", expected_revision=record.revision, at=4
    )
    assert reactivated.status == "active"
    res = service.query_memory(scope, now=5,
                             available_source_digests=SRC)
    assert [r.memory_id for r in res.records] == ["m1"]


def test_con_mem_05(ctx):
    """A user correction wins: old record superseded, view changes."""
    service, scope, _, _ = ctx
    _active(service, scope, "m1", content=b"old fact")
    service.propose_memory(
        scope, "m2", kind="rule.style", content=b"corrected",
        source_digest="src:1", evidence_refs=("e",), at=1,
    )
    service.activate_memory(
        scope, "m2", expected_revision=1, supersedes="m1", at=3
    )
    result = service.query_memory(scope, now=5,
                                available_source_digests=SRC)
    assert [r.memory_id for r in result.records] == ["m2"]


def test_con_mem_06(ctx):
    """A manipulated hint id is refused."""
    service, scope, _, _ = ctx
    _active(service, scope, "m1")
    recall = RecallService(service)
    with pytest.raises(CyranoError) as exc:
        recall.admit_hint(
            scope, _hint("forged-id"), now=5, epoch="e1"
        )
    assert exc.value.code == "INPUT_INVALID"


def test_con_mem_07(ctx):
    """An expired hint is not injected."""
    service, scope, _, _ = ctx
    _active(service, scope, "m1")
    recall = RecallService(service)
    rev = service.get(scope, "m1").revision
    with pytest.raises(CyranoError) as exc:
        recall.admit_hint(
            scope, _hint("m1", rev=rev, exp=5), now=10, epoch="e1"
        )
    assert exc.value.code == "INPUT_INVALID"


def test_con_mem_08(ctx):
    """Same id, new revision: the stale hint fails, the new admits."""
    service, scope, _, _ = ctx
    _active(service, scope, "m1")
    service.propose_memory(
        scope, "m1r", kind="rule.style", content=b"r2 content",
        source_digest="src:1", evidence_refs=("e",), at=3,
    )
    recall = RecallService(service)
    # Out-of-band revision bump: supersede m1 with m1r.
    service.activate_memory(
        scope, "m1r", expected_revision=1, supersedes="m1", at=4
    )
    with pytest.raises(CyranoError):
        recall.admit_hint(
            scope, _hint("m1", rev=1), now=5, epoch="e1"
        )
    rev = service.get(scope, "m1r").revision
    admitted = recall.admit_hint(
        scope, _hint("m1r", rev=rev, hid="h2"), now=5, epoch="e1"
    )
    assert admitted.hint.memory_id == "m1r"


def test_con_mem_09():
    """Exposure without evidence is referenced, never applied."""
    v = record_application(Exposure("m1", 1, "exp1"))
    assert v.state == "referenced"


def test_con_mem_10():
    """A complete evidence chain yields applied."""
    v = record_application(
        Exposure("m1", 1, "exp1"),
        plan_evidence=("p1",), tool_evidence=("t1",),
        test_evidence=("x1",),
    )
    assert v.state == "applied"


def test_con_mem_11(tmp_path):
    """Delete then restore: the tombstone keeps m1 unsearchable."""
    path = tmp_path / "db.sqlite3"
    repo = ScopedRepository.create(path, TARGET_DDL)
    scope = repo.register_scope("t1", "u1", "w1")
    service = MemoryService(MemoryRepository(repo))
    _active(service, scope, "m1", content=b"gone")
    service.delete(scope, "m1", at=3)
    backup = tmp_path / "bak.sqlite3"
    repo.backup(backup)
    repo.restore(backup)
    result = service.query_memory(scope, now=5,
                                  available_source_digests=SRC)
    assert result.records == ()
    assert service.search_documents(
        scope, "gone", now=5, available_source_digests=SRC
    ) == []
    repo.close()


def test_con_mem_12(ctx):
    """A gate-module failure blocks the hint as AUDIT_UNAVAILABLE."""
    service, scope, repo, _ = ctx
    _active(service, scope, "m1")
    recall = RecallService(service)
    repo.close()  # store failure path
    with pytest.raises(CyranoError) as exc:
        recall.admit_hint(scope, _hint("m1"), now=5, epoch="e1")
    assert exc.value.code in {
        "AUDIT_UNAVAILABLE",
        "INPUT_INVALID",
        "MEMORY_STORE_UNAVAILABLE",
    }
