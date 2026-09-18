"""WP09 product flow: submit → review → decide → permit → dispatch."""

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.planning.review import ReviewerBinding
from deepagents_code.cyrano.planning.subject import (
    GovernedWorkPlan,
    WorkUnitSpec,
    subject_digest,
)
from deepagents_code.cyrano.workflow.service import PlanService

REQS = {"R1": "add normalize"}
SNAP = {"files": {"src/service.py": "sha256:x"}}
SCOPE = {"scope_id": "sc-1"}
SNAP_DIGEST = "snap-1"


def _unit(uid, deps=(), writes=("f.py",)):
    return WorkUnitSpec(
        unit_id=uid,
        requirement_ids=("R1",),
        acceptance_ids=("A1",),
        dependencies=tuple(deps),
        write_paths=tuple(writes),
        test_recipe="pytest-unit",
        test_oracle="exit_code==0",
        cost_cap=10,
    )


def _plan(units=(_unit("A"),), revision=0, **kw):
    kw.setdefault("plan_id", "p1")
    kw.setdefault("requirements", ("R1",))
    kw.setdefault("budget_cap", 100)
    return GovernedWorkPlan(revision=revision, units=tuple(units), **kw)


def _service():
    return PlanService(known_recipes=frozenset({"pytest-unit"}))


def _submit(service, plan=None):
    plan = plan or _plan()
    subject, report = service.submit_plan(
        plan,
        requirements_doc=REQS,
        source_snapshot=SNAP,
        scope=SCOPE,
    )
    assert report.ready_for_review
    return subject


def _review(service, subject):
    record = service.request_review(
        subject,
        ReviewerBinding(
            reviewer_run_id="rev-1",
            author_run_id="auth-1",
            model_id="m1",
            author_model_id="m1",
            read_only=True,
            blind=True,
        ),
    )
    assert service.finish_review(record, subject.plan_id) == "reviewed"
    return record


def _approve(service, subject, purpose="plan_approval"):
    request = service.present_decision(
        subject, purpose=purpose, display_digest="display-1"
    )
    return service.record_decision(
        subject.plan_id,
        request.decision_id,
        "approve",
        nonce=request.nonce,
        subject_digest_value=subject_digest(subject),
        display_digest="display-1",
        expected_revision=subject.revision,
    )


def test_con_wfl_01_governed_flow_end_to_end():
    service = _service()
    subject = _submit(service)
    _review(service, subject)
    outcome = _approve(service, subject)
    assert outcome.granted
    exec_outcome = _approve(service, subject, purpose="execution_permission")
    assert exec_outcome.granted
    permit = service.issue_permit(
        subject,
        exec_outcome.decision_id,
        source_snapshot_digest=SNAP_DIGEST,
        generation=0,
    )
    uid, fence = service.reserve_ready_work(
        _plan(),
        permit,
        "worker-1",
        source_snapshot_digest=SNAP_DIGEST,
    )
    assert uid == "A" and fence == 1
    compiled = service.compile(_plan())
    assert compiled.order == ("A",)


def test_con_hil_02_skipping_gates_blocks_execution():
    service = _service()
    subject, _ = service.submit_plan(
        _plan(),
        requirements_doc=REQS,
        source_snapshot=SNAP,
        scope=SCOPE,
    )
    with pytest.raises(CyranoError) as exc:
        service.present_decision(
            subject, purpose="plan_approval", display_digest="d"
        )
    assert exc.value.code == "STALE_REVIEW"


def test_con_hil_03_reviewless_permit_blocked():
    service = _service()
    subject = _submit(service)
    with pytest.raises(CyranoError) as exc:
        service.issue_permit(
            subject,
            "missing-decision",
            source_snapshot_digest=SNAP_DIGEST,
            generation=0,
        )
    assert exc.value.code == "APPROVAL_REQUIRED"


def test_uh_plan_06_review_digest_mismatch_blocks():
    service = _service()
    subject = _submit(service)
    _review(service, subject)
    # A new plan revision seals a different digest; the review bound
    # to the old digest does not transfer.
    other = _plan(units=(_unit("A", writes=("other.py",)),), revision=1)
    subject2, report2 = service.submit_plan(
        other,
        requirements_doc=REQS,
        source_snapshot=SNAP,
        scope=SCOPE,
    )
    assert report2.ready_for_review
    with pytest.raises(CyranoError) as exc:
        service.present_decision(
            subject2, purpose="plan_approval", display_digest="d"
        )
    assert exc.value.code == "STALE_REVIEW"


def test_uh_plan_07_approval_is_not_execution_permission():
    service = _service()
    subject = _submit(service)
    _review(service, subject)
    _approve(service, subject)
    # plan_approval granted; no execution_permission decision exists.
    with pytest.raises(CyranoError) as exc:
        service.issue_permit(
            subject,
            f"plan_approval-{subject.plan_id}-r0",
            source_snapshot_digest=SNAP_DIGEST,
            generation=0,
        )
    assert exc.value.code == "APPROVAL_REQUIRED"


def test_plan_011_authorized_lineage_progress():
    # B consumes what A produces: B may lease only after A completes.
    service = _service()
    units = (
        _unit("A"),
        _unit("B", deps=("A",), writes=("b.py",)),
    )
    plan = _plan(units=units)
    subject, report = service.submit_plan(
        plan,
        requirements_doc=REQS,
        source_snapshot=SNAP,
        scope=SCOPE,
    )
    assert report.ready_for_review
    _review(service, subject)
    _approve(service, subject)
    outcome = _approve(service, subject, purpose="execution_permission")
    permit = service.issue_permit(
        subject,
        outcome.decision_id,
        source_snapshot_digest=SNAP_DIGEST,
        generation=0,
    )
    uid, _ = service.reserve_ready_work(
        plan, permit, "w1", source_snapshot_digest=SNAP_DIGEST
    )
    assert uid == "A"
    # B is still blocked until A's result is recorded.
    uid2, _ = service.reserve_ready_work(
        plan,
        permit,
        "w2",
        completed=frozenset({"A"}),
        source_snapshot_digest=SNAP_DIGEST,
    )
    assert uid2 == "B"


def test_con_hil_10_permit_stale_after_source_change():
    service = _service()
    subject = _submit(service)
    _review(service, subject)
    _approve(service, subject)
    outcome = _approve(service, subject, purpose="execution_permission")
    permit = service.issue_permit(
        subject,
        outcome.decision_id,
        source_snapshot_digest="snap-old",
        generation=0,
    )
    with pytest.raises(CyranoError) as exc:
        service.reserve_ready_work(
            _plan(),
            permit,
            "w1",
            source_snapshot_digest="snap-new",
        )
    assert exc.value.code == "PERMIT_STALE"


def test_con_wfl_08_failed_join_marks_completion_failed():
    service = _service()
    subject = _submit(service)
    _review(service, subject)
    decision = service.assess_completion(
        outcome="failed",
        acceptance_results={"A1": False},
        subject_digest_value=subject_digest(subject),
    )
    assert not decision.acceptance_met
    assert not decision.may_apply
    assert decision.unmet == ("A1",)


def test_con_hil_11_acceptance_is_not_publish_permission():
    service = _service()
    subject = _submit(service)
    _review(service, subject)
    decision = service.assess_completion(
        outcome="changed",
        acceptance_results={"A1": True},
        subject_digest_value=subject_digest(subject),
        apply_permit=True,
        publish_permit=False,
    )
    assert decision.may_apply
    assert not decision.may_publish


def test_con_hil_12_verified_no_change():
    service = _service()
    subject = _submit(service)
    _review(service, subject)
    decision = service.assess_completion(
        outcome="verified_no_change",
        acceptance_results={"A1": True},
        subject_digest_value=subject_digest(subject),
        source_changed=False,
    )
    assert decision.outcome == "verified_no_change"
    assert not decision.may_apply  # nothing to apply


def test_con_hil_12b_verified_no_change_on_changed_tree_refused():
    service = _service()
    subject = _submit(service)
    _review(service, subject)
    with pytest.raises(CyranoError) as exc:
        service.assess_completion(
            outcome="verified_no_change",
            acceptance_results={"A1": True},
            subject_digest_value=subject_digest(subject),
            source_changed=True,
        )
    assert exc.value.code == "STALE_SOURCE"
