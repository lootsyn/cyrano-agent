"""WP09 plan lifecycle: static validation, subject digests, scope."""

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.planning.changes import (
    PlanRevisions,
    classify_change,
)
from deepagents_code.cyrano.planning.subject import (
    GovernedWorkPlan,
    WorkUnitSpec,
    build_subject,
    subject_digest,
)
from deepagents_code.cyrano.planning.validation import (
    require_ready,
    validate_plan,
)


def _unit(uid, reqs=("R1",), accs=("A1",), deps=(), writes=("f.py",), **kw):
    kw.setdefault("test_recipe", "pytest-unit")
    kw.setdefault("test_oracle", "exit_code==0")
    kw.setdefault("cost_cap", 10)
    return WorkUnitSpec(
        unit_id=uid,
        requirement_ids=tuple(reqs),
        acceptance_ids=tuple(accs),
        dependencies=tuple(deps),
        write_paths=tuple(writes),
        **kw,
    )


def _plan(units, **kw):
    kw.setdefault("plan_id", "p1")
    kw.setdefault("revision", 0)
    kw.setdefault("requirements", ("R1",))
    kw.setdefault("budget_cap", 1000)
    return GovernedWorkPlan(units=tuple(units), **kw)


def test_plan_001_valid_plan_ready_for_review():
    units = (
        _unit("A"),
        _unit("B", deps=("A",), writes=("b.py",)),
        _unit("C", deps=("A",), writes=("c.py",)),
        _unit("D", deps=("B", "C"), writes=("d.py",)),
    )
    report = validate_plan(
        _plan(units),
        active_requirements=("R1",),
        known_recipes=frozenset({"pytest-unit"}),
    )
    assert report.ready_for_review
    assert report.violations == ()


def test_plan_002_uncovered_requirement():
    report = validate_plan(
        _plan((_unit("A"),)),
        active_requirements=("R1", "R2"),
        known_recipes=frozenset({"pytest-unit"}),
    )
    assert "UNBOUND_REQUIREMENT" in report.violations
    assert not report.ready_for_review


def test_plan_003_out_of_scope_write():
    # A path escaping the workspace root is an unbounded write set.
    report = validate_plan(
        _plan((_unit("A", writes=("../outside/db.py",)),)),
        known_recipes=frozenset({"pytest-unit"}),
    )
    assert "UNBOUNDED_WRITE_SET" in report.violations
    abs_report = validate_plan(
        _plan((_unit("B", writes=("/etc/x",)),)),
        known_recipes=frozenset({"pytest-unit"}),
    )
    assert "UNBOUNDED_WRITE_SET" in abs_report.violations


def test_uh_plan_04_unbounded_write_set():
    unit = _unit("A", writes=("**/*",))
    report = validate_plan(
        _plan((unit,)), known_recipes=frozenset({"pytest-unit"})
    )
    assert "UNBOUNDED_WRITE_SET" in report.violations


def test_plan_004_acceptance_without_oracle():
    unit = _unit("A", test_oracle=None)
    report = validate_plan(
        _plan((unit,)), known_recipes=frozenset({"pytest-unit"})
    )
    assert "TEST_RECIPE_MISSING" in report.violations


def test_plan_005_interface_mismatch():
    a = _unit("A", produces=("foo",))
    b = _unit("B", deps=("A",), consumes=("foo",), writes=("b.py",))
    interfaces = {"A.foo": "(x)->str", "B.foo": "(x,y)->int"}
    report = validate_plan(
        _plan((a, b)),
        known_interfaces=interfaces,
        known_recipes=frozenset({"pytest-unit"}),
    )
    assert "INTERFACE_MISMATCH" in report.violations


def test_plan_006_cycle_detected_with_path():
    a = _unit("A", deps=("D",))
    b = _unit("B", deps=("A",), writes=("b.py",))
    c = _unit("C", deps=("A",), writes=("c.py",))
    d = _unit("D", deps=("B", "C"), writes=("d.py",))
    report = validate_plan(
        _plan((a, b, c, d)),
        known_recipes=frozenset({"pytest-unit"}),
    )
    assert "DAG_CYCLE" in report.violations
    assert report.cycle_path


def test_plan_007_write_conflict_requires_ordering():
    b = _unit("B", writes=("shared.py",))
    c = _unit("C", writes=("shared.py",))
    report = validate_plan(
        _plan((b, c)), known_recipes=frozenset({"pytest-unit"})
    )
    assert "RESOURCE_CONFLICT" in report.violations
    # An explicit dependency serializes the writers.
    c2 = _unit("C", deps=("B",), writes=("shared.py",))
    ok = validate_plan(
        _plan((b, c2)), known_recipes=frozenset({"pytest-unit"})
    )
    assert "RESOURCE_CONFLICT" not in ok.violations


def test_plan_008_undeclared_effect():
    a = _unit("A", effects=("external.install",))
    report = validate_plan(
        _plan((a,)), known_recipes=frozenset({"pytest-unit"})
    )
    assert "UNDECLARED_EFFECT" in report.violations


def test_plan_009_self_referential_subject_rejected():
    plan = _plan((_unit("A"),))
    with pytest.raises(CyranoError) as exc:
        build_subject(
            plan,
            {"subject_digest": "self"},
            {"files": {}},
            {"scope_id": "s1"},
        )
    assert exc.value.code == "INVALID_SUBJECT_PROJECTION"


def test_plan_010_presentation_only_keeps_digest():
    plan = _plan((_unit("A"),))
    scope = {"scope_id": "s1"}
    s1 = build_subject(plan, {"r": 1}, {"files": {}}, scope)
    s2 = build_subject(
        plan,
        {"r": 1, "title": "renamed", "progress": 20},
        {"files": {}},
        scope,
    )
    assert subject_digest(s1) == subject_digest(s2)


def test_plan_012_stale_source_blocks_apply():
    # Authorize binds the snapshot digest; a drifted tree fails.
    from deepagents_code.cyrano.workflow.dispatch import (
        Dispatcher,
        ExecutionPermit,
    )

    permit = ExecutionPermit(
        permit_id="p",
        subject_digest="sd",
        source_snapshot_digest="snap-1",
        approved_units=("A",),
        generation=0,
    )
    with pytest.raises(CyranoError) as exc:
        Dispatcher().check_permit(permit, "sd", "snap-2")
    assert exc.value.code == "PERMIT_STALE"


def test_plan_change_expanded_write_set_needs_reapproval():
    old = _plan((_unit("A"),))
    new = _plan((_unit("A", writes=("f.py", "auth.py")),), revision=1)
    impact = classify_change(old, new)
    assert impact.classification == "execution_meaning_change"
    assert impact.requires_new_approval
    assert "auth.py" in impact.changed_paths


def test_plan_conflict_serialized_or_rejected():
    report = validate_plan(
        _plan((_unit("B", writes=("s.py",)), _unit("C", writes=("s.py",)))),
        known_recipes=frozenset({"pytest-unit"}),
    )
    assert "RESOURCE_CONFLICT" in report.violations


def test_integ_delivery_bind_mode_change_needs_new_subject():
    old = _plan((_unit("A"),), delivery_mode="patch_only")
    new = _plan((_unit("A"),), revision=1, delivery_mode="apply_to_source")
    revisions = PlanRevisions()
    assert revisions.delivery_mode_changed(old, new)
    impact = classify_change(old, new)
    assert impact.requires_new_approval


def test_uh_plan_01_empty_units_rejected():
    report = validate_plan(_plan(()), known_recipes=frozenset({"pytest-unit"}))
    assert "INVALID_PLAN" in report.violations
    with pytest.raises(CyranoError):
        require_ready(report)


def test_uh_plan_02_cycle_reported():
    a = _unit("A", deps=("B",))
    b = _unit("B", deps=("A",), writes=("b.py",))
    report = validate_plan(
        _plan((a, b)), known_recipes=frozenset({"pytest-unit"})
    )
    assert "DAG_CYCLE" in report.violations


def test_uh_plan_03_uncovered_blocks_readiness():
    report = validate_plan(
        _plan((_unit("A"),)),
        active_requirements=("R1", "REQ-2"),
        known_recipes=frozenset({"pytest-unit"}),
    )
    assert not report.ready_for_review
    assert "UNBOUND_REQUIREMENT" in report.violations


def test_uh_plan_10_scope_widening_is_change():
    old = _plan((_unit("A"),))
    new = _plan((_unit("A"), _unit("B", writes=("api.py",))), revision=1)
    impact = classify_change(old, new)
    assert impact.classification == "execution_meaning_change"
    assert impact.requires_new_review
