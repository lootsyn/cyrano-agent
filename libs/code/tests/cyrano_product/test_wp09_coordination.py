"""WP09 coordination: leases, mailbox, budgets, worktree boundary."""

from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.planning.subject import (
    GovernedWorkPlan,
    WorkUnitSpec,
)
from deepagents_code.cyrano.sqlite.repository import ScopedRepository
from deepagents_code.cyrano.workflow.coordination import TeamCoordinator
from deepagents_code.cyrano.workflow.dispatch import (
    Dispatcher,
    ExecutionPermit,
)

ROOT = Path(__file__).resolve().parents[2]
TARGET_DDL = (ROOT / "cyrano/contracts/sql/target-schema.sql").read_text()


@pytest.fixture()
def ctx(tmp_path):
    repo = ScopedRepository.create(tmp_path / "db.sqlite3", TARGET_DDL)
    scope = repo.register_scope("t1", "u1", "w1")
    repo.create_stream(scope, "s1", "request")
    coord = TeamCoordinator(repo, scope)
    yield repo, scope, coord
    repo.close()


def _unit(uid, writes=("f.py",), deps=()):
    return WorkUnitSpec(
        unit_id=uid,
        requirement_ids=("R1",),
        acceptance_ids=("A1",),
        dependencies=tuple(deps),
        write_paths=tuple(writes),
        test_recipe="pytest-unit",
        test_oracle="o",
        cost_cap=10,
    )


def _permit(units):
    return ExecutionPermit(
        permit_id="p1",
        subject_digest="sd",
        source_snapshot_digest="snap",
        approved_units=tuple(u.unit_id for u in units),
        generation=0,
    )


def test_con_tem_01_single_lease_winner(ctx):
    _, _, coord = ctx
    coord.register_task("s1", "task-1", write_paths=("f.py",))
    lease = coord.claim_task("s1", "task-1", 0, "worker-a", now=1)
    with pytest.raises(CyranoError) as exc:
        coord.claim_task("s1", "task-1", 0, "worker-b", now=1)
    assert exc.value.code == "LEASE_LOST"
    assert lease.worker_id == "worker-a"


def test_con_tem_02_stale_result_after_expiry(ctx):
    _, _, coord = ctx
    coord.register_task("s1", "task-1", write_paths=("f.py",))
    lease1 = coord.claim_task("s1", "task-1", 0, "w-a", now=1, ttl=5)
    reclaimed = coord.reclaim_expired("s1", now=10)
    assert reclaimed == ("task-1",)
    with pytest.raises(CyranoError) as exc:
        coord.settle("s1", lease1, "rd", outcome="completed")
    assert exc.value.code == "RESULT_STALE"


def test_con_tem_03_heartbeat_without_progress_pauses(ctx):
    _, _, coord = ctx
    coord.register_task("s1", "task-1", write_paths=("f.py",))
    lease = coord.claim_task("s1", "task-1", 0, "w-a", now=0)
    coord.heartbeat("s1", lease, now=10)
    with pytest.raises(CyranoError) as exc:
        coord.heartbeat("s1", lease, now=100, progress_deadline=50)
    assert exc.value.code == "NO_PROGRESS"
    # A real progress mark keeps the lease alive.
    coord2 = coord
    coord2.register_task("s1", "task-2", write_paths=("g.py",))
    lease2 = coord2.claim_task("s1", "task-2", 0, "w-a", now=0)
    renewed = coord2.heartbeat(
        "s1", lease2, now=100, progress=True, progress_deadline=50
    )
    assert renewed.lease_until > 100


def test_con_tem_04_mailbox_dedup(ctx):
    _, _, coord = ctx
    coord.send("s1", "m1", "a", "b", "dig", generation=0, expires_at=100)
    with pytest.raises(CyranoError) as exc:
        coord.send("s1", "m1", "a", "b", "dig", generation=0, expires_at=100)
    assert exc.value.code == "IDEMPOTENCY_CONFLICT"
    assert coord.consume("s1", "b", now=1) is not None
    assert coord.consume("s1", "b", now=1) is None


def test_con_tem_05_cross_scope_message_denied(tmp_path):
    repo = ScopedRepository.create(tmp_path / "db.sqlite3", TARGET_DDL)
    scope_a = repo.register_scope("t1", "u1", "w1")
    scope_b = repo.register_scope("t2", "u2", "w2")
    repo.create_stream(scope_a, "s1", "request")
    coord_b = TeamCoordinator(repo, scope_b)
    coord_b.send("s1", "m1", "x", "y", "dig", generation=0, expires_at=100)
    coord_a = TeamCoordinator(repo, scope_a)
    with pytest.raises(CyranoError) as exc:
        coord_a.consume("s1", "y", now=1)
    assert exc.value.code == "ACL_DENIED"
    repo.close()


def test_con_tem_06_expired_message_recorded(ctx):
    _, _, coord = ctx
    coord.send("s1", "m1", "a", "b", "dig", generation=0, expires_at=10)
    with pytest.raises(CyranoError) as exc:
        coord.consume("s1", "b", now=20)
    assert exc.value.code == "MESSAGE_EXPIRED"
    assert coord.consume("s1", "b", now=30) is None


def test_con_tem_07_children_share_parent_budget(ctx):
    _, _, coord = ctx
    coord.set_budget(100)
    coord.reserve_budget(60)
    coord.reserve_budget(40)
    with pytest.raises(CyranoError) as exc:
        coord.reserve_budget(1)
    assert exc.value.code == "BUDGET_UNBOUND"


def test_con_tem_08_same_file_writers_serialized(ctx):
    _, _, coord = ctx
    coord.register_task("s1", "a", write_paths=("same.py",))
    coord.register_task("s1", "b", write_paths=("same.py",))
    coord.claim_task("s1", "a", 0, "w1", now=1)
    with pytest.raises(CyranoError) as exc:
        coord.claim_task("s1", "b", 0, "w2", now=1)
    assert exc.value.code == "RESOURCE_CONFLICT"


def test_uh_run_06_dispatcher_write_conflict():
    units = (
        _unit("a", writes=("same.py",)),
        _unit("b", writes=("same.py",)),
    )
    plan = GovernedWorkPlan(
        plan_id="p",
        revision=0,
        requirements=("R1",),
        units=units,
        budget_cap=100,
    )
    dispatcher = Dispatcher()
    permit = _permit(units)
    uid, _ = dispatcher.reserve_ready_work(plan, permit, "w1")
    assert uid == "a"
    with pytest.raises(CyranoError) as exc:
        dispatcher.reserve_ready_work(plan, permit, "w2")
    assert exc.value.code == "RESOURCE_CONFLICT"


def test_uh_run_07_atomic_budget_reservation(ctx):
    _, _, coord = ctx
    coord.set_budget(1)
    coord.reserve_budget(1)
    with pytest.raises(CyranoError) as exc:
        coord.reserve_budget(1)
    assert exc.value.code == "BUDGET_UNBOUND"


def test_uh_run_10_lease_reclaim_needs_verification(ctx):
    _, _, coord = ctx
    coord.register_task("s1", "t", write_paths=("f.py",))
    coord.claim_task("s1", "t", 0, "w", now=0, ttl=5)
    reclaimed = coord.reclaim_expired("s1", now=10)
    assert reclaimed == ("t",)
    # Reclaimed tasks land in recovery_check, not blindly re-leased.
    with pytest.raises(CyranoError) as exc:
        coord.claim_task("s1", "t", 0, "w2", now=11)
    assert exc.value.code == "LEASE_LOST"


def test_integ_cost_reserve_unknown_liability(ctx):
    _, _, coord = ctx
    coord.set_budget(100)
    coord.reserve_budget(30)
    # The billable call returned no usage: keep the liability.
    coord.settle_budget(30, usage_observed=None)
    with pytest.raises(CyranoError) as exc:
        coord.reserve_budget(1)
    assert exc.value.code == "BUDGET_BLOCKED"


def test_con_wfl_06_apply_without_permit():
    dispatcher = Dispatcher()
    plan = GovernedWorkPlan(
        plan_id="p",
        revision=0,
        requirements=("R1",),
        units=(_unit("a"),),
        budget_cap=100,
    )
    with pytest.raises(CyranoError) as exc:
        dispatcher.reserve_ready_work(
            plan,
            ExecutionPermit(
                permit_id="p",
                subject_digest="sd",
                source_snapshot_digest="s",
                approved_units=(),
                generation=0,
            ),
            "w",
        )
    # Unapproved unit never leases; nothing is dispatchable.
    assert exc.value.code == "NO_READY_WORK"


def test_con_wfl_12_journal_binds_snapshot(ctx):
    _, _, coord = ctx
    coord.journal_store(
        "s1",
        "n1",
        snapshot_digest="snap-1",
        input_digest="in-1",
        result_digest="res-1",
        status="ok",
        now=1,
    )
    hit = coord.journal_lookup(
        "s1", "n1", snapshot_digest="snap-1", input_digest="in-1"
    )
    assert hit == "res-1"
    # Same prompt/model but a changed workspace snapshot misses.
    miss = coord.journal_lookup(
        "s1", "n1", snapshot_digest="snap-2", input_digest="in-1"
    )
    assert miss is None


def test_con_tem_09_interface_merge_revalidates():
    from deepagents_code.cyrano.planning.changes import compute_impact

    a = WorkUnitSpec(
        unit_id="A",
        requirement_ids=("R1",),
        acceptance_ids=("A1",),
        write_paths=("a.py",),
        produces=("sig",),
        test_recipe="r",
        test_oracle="o",
        cost_cap=1,
    )
    b = WorkUnitSpec(
        unit_id="B",
        requirement_ids=("R1",),
        acceptance_ids=("A1",),
        write_paths=("b.py",),
        consumes=("sig",),
        dependencies=("A",),
        test_recipe="r",
        test_oracle="o",
        cost_cap=1,
    )
    plan = GovernedWorkPlan(
        plan_id="p",
        revision=0,
        requirements=("R1",),
        units=(a, b),
        budget_cap=10,
    )
    # A changed producer signature forces the consumer to revalidate.
    assert compute_impact(plan, frozenset({"A"})) == ("A", "B")


def test_con_tem_10_worktree_boundary(ctx):
    _, _, coord = ctx
    coord.claim_worktree(
        "s1",
        "t1",
        "lease-1",
        "/repo/tree-a",
        "digest-1",
        generation=0,
    )
    coord.check_worktree_access("lease-1", "/repo/tree-a/src/x.py")
    with pytest.raises(CyranoError) as exc:
        coord.check_worktree_access("lease-1", "/repo/tree-b/x.py")
    assert exc.value.code == "ACL_DENIED"
    with pytest.raises(CyranoError) as exc2:
        coord.check_worktree_access("lease-1", "/repo/tree-a/.git/config")
    assert exc2.value.code == "ACL_DENIED"


def test_con_tem_11_user_modified_cleanup_preserved(ctx):
    _, _, coord = ctx
    coord.claim_worktree(
        "s1",
        "t1",
        "lease-1",
        "/repo/tree-a",
        "baseline-1",
        generation=0,
    )
    assert coord.cleanup_worktree("lease-1", "baseline-1") == "cleaned"
    coord.claim_worktree(
        "s1",
        "t2",
        "lease-2",
        "/repo/tree-b",
        "baseline-2",
        generation=0,
    )
    assert (
        coord.cleanup_worktree("lease-2", "user-edited")
        == "conflict_preserved"
    )


def test_con_tem_12_parent_cancel_child_result_audit_only(ctx):
    _, _, coord = ctx
    coord.register_task("s1", "parent", write_paths=("p.py",))
    coord.register_task(
        "s1", "child", write_paths=("c.py",), parent_task="parent"
    )
    lease = coord.claim_task("s1", "child", 0, "w", now=1)
    coord.cancel_task("s1", "parent")
    with pytest.raises(CyranoError) as exc:
        coord.settle("s1", lease, "rd", outcome="completed")
    assert exc.value.code == "RESULT_STALE"


def test_con_hil_08_partial_approval_dispatches_only_approved():
    units = (_unit("a"), _unit("b", writes=("b.py",)))
    plan = GovernedWorkPlan(
        plan_id="p",
        revision=0,
        requirements=("R1",),
        units=units,
        budget_cap=100,
    )
    dispatcher = Dispatcher()
    permit = ExecutionPermit(
        permit_id="p",
        subject_digest="sd",
        source_snapshot_digest="s",
        approved_units=("a",),
        generation=0,
    )
    uid, _ = dispatcher.reserve_ready_work(plan, permit, "w1")
    assert uid == "a"
    with pytest.raises(CyranoError) as exc:
        dispatcher.reserve_ready_work(plan, permit, "w2")
    assert exc.value.code == "NO_READY_WORK"


def test_con_hil_10_source_change_before_permit():
    dispatcher = Dispatcher()
    permit = ExecutionPermit(
        permit_id="p",
        subject_digest="sd",
        source_snapshot_digest="snap-old",
        approved_units=("a",),
        generation=0,
    )
    with pytest.raises(CyranoError) as exc:
        dispatcher.check_permit(permit, "sd", "snap-new")
    assert exc.value.code == "PERMIT_STALE"
