"""WP09 contract scenarios: R3-22 planning and R3-23 review cases."""

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.planning.review import (
    ReviewBoard,
    ReviewerBinding,
    ReviewFinding,
)
from deepagents_code.cyrano.planning.subject import (
    GovernedWorkPlan,
    WorkUnitSpec,
)
from deepagents_code.cyrano.planning.validation import validate_plan


def _unit(uid, **kw):
    kw.setdefault("requirement_ids", ("R1",))
    kw.setdefault("acceptance_ids", ("A1",))
    kw.setdefault("write_paths", ("src/f.py",))
    kw.setdefault("test_recipe", "pytest-unit")
    kw.setdefault("test_oracle", "exit_code==0")
    kw.setdefault("cost_cap", 10)
    return WorkUnitSpec(unit_id=uid, **kw)


def _plan(units, **kw):
    kw.setdefault("plan_id", "fx")
    kw.setdefault("revision", 0)
    kw.setdefault("requirements", ("R1",))
    kw.setdefault("budget_cap", 100000)
    return GovernedWorkPlan(units=tuple(units), **kw)


def _board_and_record(digest="sd"):
    board = ReviewBoard()
    record = board.request_review(
        digest,
        ReviewerBinding(
            reviewer_run_id="rev-1",
            author_run_id="auth-1",
            model_id="m1",
            author_model_id="m1",
            read_only=True,
            blind=True,
        ),
        reviewer_input={"subject_digest": digest},
    )
    return board, record


def test_r3_22_01_full_plan_binds_units_and_recipes():
    units = (
        _unit("A", write_paths=("src/service.py",)),
        _unit("B", dependencies=("A",), write_paths=("src/api.py",)),
        _unit("C", dependencies=("A",), write_paths=("src/cli.py",)),
        _unit("D", dependencies=("B", "C"), write_paths=("src/x.py",)),
    )
    plan = _plan(units)
    report = validate_plan(
        plan,
        active_requirements=("R1",),
        known_recipes=frozenset({"pytest-unit"}),
    )
    assert report.ready_for_review
    # Permission intersection: writes stay inside declared paths.
    allowed = {"src/service.py", "src/api.py", "src/cli.py", "src/x.py"}
    for unit in plan.units:
        assert set(unit.write_paths) <= allowed
        assert unit.test_recipe == "pytest-unit"


def test_r3_22_02_vague_plan_incomplete():
    plan = _plan((_unit("A", write_paths=()),))
    report = validate_plan(plan)
    assert "PLAN_INCOMPLETE" in report.violations
    assert not report.ready_for_review


def test_r3_22_03_cycle_or_write_conflict():
    a = _unit("A", dependencies=("B",))
    b = _unit("B", dependencies=("A",), write_paths=("b.py",))
    report = validate_plan(_plan((a, b)))
    assert "DAG_CYCLE" in report.violations
    w1 = _unit("W1", write_paths=("same.py",))
    w2 = _unit("W2", write_paths=("same.py",))
    report2 = validate_plan(_plan((w1, w2)))
    assert "RESOURCE_CONFLICT" in report2.violations


def test_r3_22_04_test_string_only_is_missing_recipe():
    plan = _plan((_unit("A", test_recipe=None, test_oracle=None),))
    report = validate_plan(plan, known_recipes=frozenset({"pytest-unit"}))
    assert "TEST_RECIPE_MISSING" in report.violations


def test_r3_22_05_name_only_binding_is_review_finding():
    # Unit claims R1 but its test only exercises an unrelated path;
    # a name-only trace must surface as a review finding, not pass.
    plan = _plan(
        (
            _unit(
                "A",
                requirement_ids=("R1",),
            ),
        ),
        requirements=("R1", "R2"),
    )
    report = validate_plan(
        plan,
        active_requirements=("R1", "R2"),
        known_recipes=frozenset({"pytest-unit"}),
    )
    assert "UNBOUND_REQUIREMENT" in report.violations
    board, record = _board_and_record()
    finding = board.submit_finding(
        record,
        ReviewFinding(
            finding_id="trace-1",
            subject_digest="sd",
            reviewer_run_id="rev-1",
            severity="high",
            summary="test recipe does not exercise R1",
            evidence_ids=("ev-1",),
            requirement_refs=("R1",),
        ),
    )
    assert finding.requirement_refs == ("R1",)
    assert board.finish_review(record) == "changes_required"


def test_r3_22_06_structured_plan_binds_to_execution():
    units = (
        _unit("A", write_paths=("src/service.py",)),
        _unit("V", dependencies=("A",), write_paths=("tests/t.py",)),
    )
    plan = _plan(units)
    report = validate_plan(
        plan,
        active_requirements=("R1",),
        known_recipes=frozenset({"pytest-unit"}),
    )
    assert report.ready_for_review
    from deepagents_code.cyrano.workflow.compiler import (
        compile_workflow,
        units_to_nodes,
    )

    compiled = compile_workflow(
        units_to_nodes(plan.units),
        known_recipes=frozenset({"pytest-unit"}),
        known_requirements=frozenset(plan.requirements),
    )
    assert compiled.order.index("A") < compiled.order.index("V")


def test_r3_23_01_review_produces_real_artifact():
    board, record = _board_and_record()
    board.submit_finding(
        record,
        ReviewFinding(
            finding_id="f-1",
            subject_digest="sd",
            reviewer_run_id="rev-1",
            severity="info",
            summary="note",
            evidence_ids=("ev-1",),
        ),
    )
    assert board.finish_review(record) == "reviewed"
    # The artifact is a record with verdict and findings, not a
    # bare "review complete" string.
    assert record.verdict == "approve"
    assert record.findings


def test_r3_23_02_seeded_defects_detected():
    board, record = _board_and_record()
    for fid, summary in (
        ("f-rb", "missing rollback"),
        ("f-ts", "missing test"),
    ):
        board.submit_finding(
            record,
            ReviewFinding(
                finding_id=fid,
                subject_digest="sd",
                reviewer_run_id="rev-1",
                severity="critical",
                summary=summary,
                evidence_ids=("ev-1",),
            ),
        )
    assert board.finish_review(record) == "changes_required"
    # Resolving binds the finding id to the fixed revision.
    resolved = board.resolve_finding(
        "f-rb",
        "rev-1",
        "fixed_verified",
        new_subject_digest="sd-v2",
        evidence_ids=("ev-2",),
    )
    assert resolved.finding_id == "f-rb"
    assert resolved.subject_digest == "sd-v2"


def test_r3_23_03_reviewer_timeout_unverifiable():
    board, record = _board_and_record()
    assert board.finish_review(record, reviewer_ok=False) == ("unverifiable")
    assert not board.is_reviewed("sd")
    with pytest.raises(CyranoError):
        board.require_reviewed("sd")


def test_r3_23_04_open_blocking_finding_blocks():
    board, record = _board_and_record()
    board.submit_finding(
        record,
        ReviewFinding(
            finding_id="f-1",
            subject_digest="sd",
            reviewer_run_id="rev-1",
            severity="critical",
            summary="unsafe write",
            evidence_ids=("ev-1",),
        ),
    )
    board.finish_review(record)
    with pytest.raises(CyranoError) as exc:
        board.require_reviewed("sd")
    assert exc.value.code == "REVIEW_FINDINGS_OPEN"


def test_r3_23_05_v1_review_cannot_approve_v2():
    board, record = _board_and_record(digest="sd-v1")
    assert board.finish_review(record) == "reviewed"
    assert board.is_reviewed("sd-v1")
    assert not board.is_reviewed("sd-v2")
    with pytest.raises(CyranoError) as exc:
        board.require_reviewed("sd-v2")
    assert exc.value.code == "STALE_REVIEW"


def test_r3_23_06_leaked_verdict_invalidates_review():
    board = ReviewBoard()
    with pytest.raises(CyranoError) as exc:
        board.request_review(
            "sd",
            ReviewerBinding(
                reviewer_run_id="rev-1",
                author_run_id="auth-1",
                model_id="m1",
                author_model_id="m1",
                read_only=True,
                blind=True,
            ),
            reviewer_input={
                "subject_digest": "sd",
                "author_verdict": "lgtm",
            },
        )
    assert exc.value.code == "INPUT_INVALID"
