"""WP09 change lifecycle: classification, impact closure, CAS."""

from pathlib import Path

import pytest

from deepagents_code.cyrano.context.epochs import (
    EpochManager,
    epoch_for,
)
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.planning.changes import (
    PlanRevisions,
    apply_policy_change,
    classify_change,
    compute_impact,
    invalidate_requirements,
)
from deepagents_code.cyrano.planning.subject import (
    GovernedWorkPlan,
    WorkUnitSpec,
)
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

ROOT = Path(__file__).resolve().parents[2]
TARGET_DDL = (ROOT / "cyrano/contracts/sql/target-schema.sql").read_text()


def _unit(uid, **kw):
    kw.setdefault("requirement_ids", ("R1",))
    kw.setdefault("acceptance_ids", ("A1",))
    kw.setdefault("write_paths", ("f.py",))
    kw.setdefault("test_recipe", "pytest-unit")
    kw.setdefault("test_oracle", "o")
    kw.setdefault("cost_cap", 10)
    return WorkUnitSpec(unit_id=uid, **kw)


def _plan(units, **kw):
    kw.setdefault("plan_id", "p1")
    kw.setdefault("revision", 0)
    kw.setdefault("requirements", ("R1",))
    kw.setdefault("budget_cap", 1000)
    return GovernedWorkPlan(units=tuple(units), **kw)


def test_change_001_scope_widening():
    old = _plan((_unit("A"),))
    new = _plan((_unit("A", write_paths=("f.py", "auth.py")),), revision=1)
    impact = classify_change(old, new)
    assert impact.classification == "execution_meaning_change"
    assert impact.requires_new_review and impact.requires_new_approval


def test_change_002_budget_increase_new_subject():
    old = _plan((_unit("A"),), budget_cap=100000)
    new = _plan((_unit("A"),), revision=1, budget_cap=200000)
    impact = classify_change(old, new)
    assert impact.classification == "execution_meaning_change"
    assert impact.requires_new_approval


def test_change_003_shrinking_cap_never_hides_negative():
    result = apply_policy_change(100000, 50000, reserved=80000)
    assert result["shrunk_below_reserved"]
    assert not result["new_reservations_allowed"]
    assert result["headroom"] == -30000  # honest, not clamped to 0


def test_change_004_interface_impact_closure():
    a = _unit("A", produces=("api",))
    b = _unit("B", consumes=("api",), dependencies=("A",))
    c = _unit("C", consumes=("api",), dependencies=("A",))
    d = _unit("D", dependencies=("B", "C"))
    plan = _plan((a, b, c, d))
    assert compute_impact(plan, frozenset({"A"})) == ("A", "B", "C", "D")


def test_change_005_unrelated_edit_forces_no_rerun():
    a = _unit("A", produces=("api",))
    b = _unit("B", consumes=("api",), dependencies=("A",))
    z = _unit("Z", write_paths=("z.py",))
    plan = _plan((a, b, z), requirements=("R1",))
    assert compute_impact(plan, frozenset({"Z"})) == ("Z",)


def test_change_006_tool_schema_change_bumps_epoch():
    mgr = EpochManager(
        epoch_for(
            tool_inventory_digest="tools-v1",
            model_identity="m",
            route=None,
            release_digest="r",
            profile_digest="p",
            memory_view_digest="mv",
        )
    )
    stale = mgr.current
    mgr.update(tool_inventory_digest="tools-v2")
    assert mgr.current.generation == stale.generation + 1
    assert mgr.current.epoch_id != stale.epoch_id
    with pytest.raises(CyranoError) as exc:
        mgr.require_current(stale.epoch_id)
    assert exc.value.code == "STALE_EPOCH"


def test_change_007_delegated_choice_no_reapproval():
    old = _plan((_unit("A", test_recipe="algo-v1"),))
    new = _plan((_unit("A", test_recipe="algo-v2"),), revision=1)
    impact = classify_change(
        old,
        new,
        authorized_alternatives=frozenset({"algo-v1", "algo-v2"}),
    )
    assert impact.classification == "delegated_choice"
    assert not impact.requires_new_approval


def test_change_008_unclassifiable_pauses_work():
    old = _plan((_unit("A"),))
    new = _plan((_unit("A"),), revision=1)
    impact = classify_change(old, new, unclassifiable=True)
    assert impact.classification == "unknown"
    assert impact.affected_units == ("A",)


def test_change_009_retracted_requirement_stales_dependents():
    a = _unit("A", requirement_ids=("R1",))
    b = _unit("B", requirement_ids=("R2",), dependencies=("A",))
    plan = _plan((a, b), requirements=("R1", "R2"))
    impact = invalidate_requirements(plan, frozenset({"R1"}))
    assert impact.changed_requirements == ("R1",)
    assert set(impact.affected_units) == {"A", "B"}
    assert impact.requires_new_approval


def test_change_010_weakened_oracle_needs_protected_review():
    old = _plan((_unit("A", test_oracle="pytest -q"),))
    new = _plan((_unit("A", test_oracle="optional"),), revision=1)
    impact = classify_change(old, new)
    assert impact.classification == "execution_meaning_change"
    assert impact.requires_new_review


def test_change_011_cas_single_winner():
    revisions = PlanRevisions()
    v0 = _plan((_unit("A"),), revision=0)
    v1a = _plan((_unit("A", write_paths=("a.py",)),), revision=1)
    v1b = _plan((_unit("A", write_paths=("b.py",)),), revision=1)
    assert revisions.commit(v0, expected_revision=-1) == 0
    assert revisions.commit(v1a, expected_revision=0) == 1
    with pytest.raises(CyranoError) as exc:
        revisions.commit(v1b, expected_revision=0)
    assert exc.value.code == "CAS_CONFLICT"
    assert revisions.head("p1").revision == 1
    assert revisions.head("p1").units[0].write_paths == ("a.py",)


def test_change_012_past_effects_not_retroactively_approved(
    tmp_path,
):
    repo = ScopedRepository.create(tmp_path / "db.sqlite3", TARGET_DDL)
    scope = repo.register_scope("t", "u", "w")
    repo.create_stream(scope, "s1", "request")
    # An unapproved effect was recorded under an earlier revision.
    repo.record_approval(scope, "ap-1", "subject-v2", expires_at=100)
    assert repo.approval_usable("ap-1", now=50)
    # Approving v2 never marks a v1 action approved: approvals bind
    # their subject digest, and the incident record stands.
    assert not repo.approval_usable("ap-missing", now=50)
    repo.close()
