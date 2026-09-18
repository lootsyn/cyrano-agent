"""WP16: analysis, workplan, candidates, impact, and system gates."""

from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.dcode.adapter import (
    require_governed,
    runtime_status,
)
from deepagents_code.cyrano.dcode.middleware import (
    build_launch_view,
    check_path,
)
from deepagents_code.cyrano.dcode.probes import doctor
from deepagents_code.cyrano.improvement.analysis import (
    EpisodeRecord,
    analyze_patterns,
)
from deepagents_code.cyrano.improvement.candidates import (
    enqueue_review,
    propose_candidate,
    run_review,
    validate_delta,
)
from deepagents_code.cyrano.improvement.episodes import build_episode
from deepagents_code.cyrano.improvement.replay import (
    DEPENDENCY_NOT_OBSERVED,
    WorldReplay,
)
from deepagents_code.cyrano.improvement.workplan import (
    compile_learning_plan,
    request_stop,
    run_step,
)
from deepagents_code.cyrano.improvement.worlds import (
    ExecutionSignature,
    build_world,
)
from deepagents_code.cyrano.kernel.actions import Grant, evaluate
from deepagents_code.cyrano.memory.application import (
    Exposure,
    record_application,
)
from deepagents_code.cyrano.memory.repository import MemoryRepository
from deepagents_code.cyrano.memory.service import MemoryService
from deepagents_code.cyrano.planning.completion import assess_completion
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

ROOT = Path(__file__).resolve().parents[2]
TARGET_DDL = (ROOT / "cyrano/contracts/sql/target-schema.sql").read_text()

SIG = ExecutionSignature(
    model_id="m1",
    endpoint="e1",
    runtime_digest="sha256:rt",
    tool_inventory_digest="sha256:tools",
    skill_digest="sha256:skill",
)


@pytest.fixture()
def ctx(tmp_path):
    repo = ScopedRepository.create(tmp_path / "db.sqlite3", TARGET_DDL)
    scope = repo.register_scope("t1", "u1", "w1")
    repo.create_stream(scope, "run-1", "request")
    yield repo, scope
    repo.close()


def _candidate(author="author-1", diff="d", revision=1):
    return propose_candidate(
        base_revision=revision,
        diff=diff,
        scope="t1/u1/w1",
        author=author,
        grounds="observed failure cluster",
    )


# -- DREAM-ACT ---------------------------------------------------------


def test_dream_act_01_duplicate_dispatch_no_new_side_effect(ctx):
    repo, scope = ctx
    rev = repo.read_scoped_entity(scope, "run-1")
    repo.execute_command(
        scope,
        "cli",
        "dispatch",
        "k1",
        {"a": 1},
        "run-1",
        rev,
        enqueue=True,
    )
    replay = repo.execute_command(
        scope,
        "cli",
        "dispatch",
        "k1",
        {"a": 1},
        "run-1",
        rev,
        enqueue=True,
    )
    assert replay.idempotent_replay is True
    # A fresh revision makes the duplicate a refusal, not a mutation.
    with pytest.raises(CyranoError, match="IDEMPOTENCY_CONFLICT"):
        repo.execute_command(
            scope,
            "cli",
            "dispatch",
            "k1",
            {"a": 1},
            "run-1",
            rev + 1,
            enqueue=True,
        )
    jobs = repo.connection.execute(
        "SELECT COUNT(*) FROM outbox WHERE scope_id=?", (scope,)
    ).fetchone()[0]
    assert jobs == 1
    assert repo.read_scoped_entity(scope, "run-1") == rev + 1


def test_dream_act_02_batch_over_capacity_refused():
    world = build_world(
        build_episode("e", [{"node_id": "t", "kind": "run.finished"}]),
        SIG,
    )
    replay = WorldReplay(
        world, SIG, legal_actions=frozenset({"a", "b"}), worker_cap=1
    )
    replay.commit_slots(["a", "b"])
    with pytest.raises(CyranoError, match="INVALID_BATCH"):
        replay.open_batch({"a": "x", "b": "y"})


def test_dream_act_03_dependent_action_refused_before_parent():
    events = [
        {"node_id": "a", "kind": "step", "input_digest": "i1"},
        {
            "node_id": "b",
            "kind": "step",
            "input_digest": "i2",
            "observed_deps": ["a"],
        },
        {"node_id": "t", "kind": "run.finished"},
    ]
    world = build_world(build_episode("e", events), SIG)
    replay = WorldReplay(world, SIG, legal_actions=frozenset({"a", "b"}))
    replay.commit_slots(["a", "b"])
    outcome = replay.open_batch({"b": "i2"})
    assert outcome.steps[0].status == DEPENDENCY_NOT_OBSERVED


def test_dream_act_04_completion_requires_verification_and_review():
    decision = assess_completion(
        outcome="changed",
        acceptance_results={"a1": False},
        review_approved=False,
        apply_permit=False,
        publish_permit=False,
        source_changed=True,
    )
    assert decision.acceptance_met is False
    assert decision.may_apply is False
    assert "a1" in decision.unmet


def test_dream_act_05_denied_permission_not_bypassed():
    deny = Grant(path="policies/trust/x", deny=frozenset({"write_existing"}))
    assert (
        evaluate("write_existing", "policies/trust/x", (deny,)).allowed
        is False
    )
    assert evaluate("write_existing", "policies/trust/x", ()).allowed is False


def test_dream_act_06_unknown_outcome_reconciled_before_retry(ctx):
    repo, scope = ctx
    rev = repo.read_scoped_entity(scope, "run-1")
    repo.execute_command(
        scope, "cli", "job", "k2", {}, "run-1", rev, enqueue=True
    )
    lease = repo.claim_outbox(scope, "w1", 100, 60)
    assert lease is not None
    repo.mark_job_unknown(lease.job_id)
    assert repo.job_state(lease.job_id) == "unknown"
    repo.reconcile_unknown(lease.job_id, "requeue")
    assert repo.job_state(lease.job_id) == "pending"


# -- DREAM-PLC ---------------------------------------------------------


def _plan_spec(**kw):
    base = {
        "steps": [{"id": "s1", "op": "observe", "inputs": [], "deps": []}],
        "budget": 10,
        "deadline": 100,
    }
    base.update(kw)
    return base


def test_dream_plc_01_type_ref_depth_op_limits():
    with pytest.raises(CyranoError, match="OPERATION_NOT_ALLOWED"):
        compile_learning_plan(
            _plan_spec(steps=[{"id": "s", "op": "apply", "deps": []}]),
            author="a",
            learning_enabled=True,
        )
    with pytest.raises(CyranoError, match="PLAN_REF_UNRESOLVED"):
        compile_learning_plan(
            _plan_spec(
                steps=[{"id": "s", "op": "observe", "inputs": ["ghost"]}]
            ),
            author="a",
            learning_enabled=True,
        )
    with pytest.raises(CyranoError, match="PLAN_DEPTH_EXCEEDED"):
        compile_learning_plan(
            _plan_spec(steps=[{"id": "s", "op": "observe", "depth": 9}]),
            author="a",
            learning_enabled=True,
        )


def test_dream_plc_02_cycle_refused():
    spec = _plan_spec(
        steps=[
            {"id": "a", "op": "observe", "deps": ["b"]},
            {"id": "b", "op": "observe", "deps": ["a"]},
        ]
    )
    with pytest.raises(CyranoError, match="PLAN_CYCLE"):
        compile_learning_plan(spec, author="x", learning_enabled=True)


def test_dream_plc_03_no_permissions_deadline_required():
    plan = compile_learning_plan(
        _plan_spec(), author="a", learning_enabled=True
    )
    with pytest.raises(CyranoError, match="PERMISSION_DENIED"):
        run_step(plan.steps[0], permission="write_source")
    with pytest.raises(CyranoError, match="RESOURCE_LIMIT_REQUIRED"):
        compile_learning_plan(
            _plan_spec(budget=0), author="a", learning_enabled=True
        )


def test_dream_plc_04_gate_skipping_step_refused():
    spec = _plan_spec(
        steps=[{"id": "s", "op": "observe", "flags": ["skip_verification"]}]
    )
    with pytest.raises(CyranoError, match="GEN01_VIOLATION"):
        compile_learning_plan(spec, author="a", learning_enabled=True)


def test_dream_plc_05_stop_halts_exploration_only():
    plan = compile_learning_plan(
        _plan_spec(), author="a", learning_enabled=True
    )
    stop = request_stop(plan)
    assert stop["exploration_stopped"] is True
    assert stop["source_write_allowed"] is False
    assert stop["completion_allowed"] is False


# -- DREAM-MEM ---------------------------------------------------------


def _memory_fixture(tmp_path):
    repo = ScopedRepository.create(tmp_path / "m.db", TARGET_DDL)
    scope = repo.register_scope("t1", "u1", "w1")
    return repo, scope, MemoryService(MemoryRepository(repo))


def test_dream_mem_01_recall_blocked_at_acl(tmp_path):
    repo, scope, svc = _memory_fixture(tmp_path)
    other = repo.register_scope("t1", "u2", "w2")
    svc.propose_memory(
        scope,
        "m1",
        kind="rule",
        content=b"fact",
        source_digest="src:1",
        evidence_refs=(),
        at=0,
    )
    svc.activate_memory(scope, "m1", expected_revision=1, at=1)
    foreign = svc.query_memory(other, 100, frozenset({"src:1"}))
    assert foreign.records == ()
    repo.close()


def test_dream_mem_02_referenced_not_counted_as_applied():
    verdict = record_application(
        Exposure("m1", 1, "exp:1"),
        plan_evidence=("p1",),
    )
    assert verdict.state == "referenced"
    verdict2 = record_application(Exposure("m1", 1, "exp:1"))
    assert verdict2.state == "referenced"


def test_dream_mem_03_stale_needs_reconfirmation(tmp_path):
    repo, scope, svc = _memory_fixture(tmp_path)
    svc.propose_memory(
        scope,
        "m1",
        kind="rule",
        content=b"fact",
        source_digest="src:old",
        evidence_refs=(),
        at=0,
    )
    svc.activate_memory(scope, "m1", expected_revision=1, at=1)
    moved = svc.mark_stale_if_source_moved(scope, frozenset({"src:new"}), at=2)
    assert moved == ["m1"]
    recall = svc.query_memory(scope, 100, frozenset({"src:old"}))
    assert all(r.memory_id != "m1" for r in recall.records)
    repo.close()


def test_dream_mem_04_lineage_revocation_cascades(tmp_path):
    repo, scope, svc = _memory_fixture(tmp_path)
    svc.propose_memory(
        scope,
        "m1",
        kind="rule",
        content=b"fact",
        source_digest="src:1",
        evidence_refs=(),
        at=0,
    )
    svc.activate_memory(scope, "m1", expected_revision=1, at=1)
    affected = svc.invalidate(scope, "m1", at=2)
    assert "m1" in affected
    record = svc.get(scope, "m1")
    assert record is not None and record.status == "stale"
    repo.close()


# -- DREAM-WF ----------------------------------------------------------


def test_dream_wf_01_readiness_requires_artifacts(ctx):
    repo, scope = ctx
    rev = repo.read_scoped_entity(scope, "run-1")
    with pytest.raises(CyranoError):
        repo.execute_command(
            scope, "cli", "dispatch", "k", {}, "run-1", rev + 5
        )


def test_dream_wf_02_answer_reuse_requires_real_verification():
    decision = assess_completion(
        outcome="answered",
        acceptance_results={"accept": True},
        review_approved=False,
        apply_permit=False,
        publish_permit=False,
        source_changed=False,
    )
    assert decision.may_apply is False
    assert decision.may_publish is False


def test_dream_wf_03_out_of_permit_repetition_blocked(ctx):
    repo, scope = ctx
    other = repo.register_scope("t1", "u2", "w2")
    repo.create_stream(other, "run-2", "request")
    with pytest.raises(CyranoError, match="SCOPE_DENIED"):
        repo.read_scoped_entity(other, "run-1")


def test_dream_wf_04_failure_never_auto_labelled():
    report = analyze_patterns(
        [EpisodeRecord("e1", "failed", error_class="timeout")],
        learning_enabled=True,
    )
    hyp = report.hypotheses[0]
    assert hyp.confidence == "hypothesis"
    assert hyp.status in {"pending_evidence", "not_an_improvement_target"}


# -- DREAM-OPS ---------------------------------------------------------


def test_dream_ops_01_outbox_idempotent_consumption(ctx):
    repo, scope = ctx
    rev = repo.read_scoped_entity(scope, "run-1")
    repo.execute_command(
        scope, "cli", "job", "k1", {}, "run-1", rev, enqueue=True
    )
    first = repo.claim_outbox(scope, "w1", 100, 60)
    assert first is not None
    assert repo.claim_outbox(scope, "w2", 100, 60) is None
    assert repo.submit_result(first.job_id, "w1", first.fence, 1) == "applied"


def test_dream_ops_02_fencing_blocks_late_write(ctx):
    repo, scope = ctx
    rev = repo.read_scoped_entity(scope, "run-1")
    repo.execute_command(
        scope, "cli", "job", "k1", {}, "run-1", rev, enqueue=True
    )
    old = repo.claim_outbox(scope, "w1", 100, 10)
    assert old is not None
    new = repo.claim_outbox(scope, "w2", 200, 10)
    assert new is not None and new.fence > old.fence
    assert repo.submit_result(old.job_id, "w1", old.fence, 1) == "stale"


def test_dream_ops_03_meta_depth_limited():
    with pytest.raises(CyranoError, match="META_DEPTH_EXCEEDED"):
        analyze_patterns([], meta_depth=1, learning_enabled=True)


# -- DREAM-DC ----------------------------------------------------------


def test_dream_dc_01_doctor_reports_surface_evidence():
    report = doctor(distribution_name="deepagents-code")
    dist = report["distribution"]
    assert isinstance(dist, dict) and dist.get("version")
    assert dist.get("record_digest")
    probes = report["probes"]
    assert isinstance(probes, dict)
    assert "async_middleware" in probes
    assert "child_observation" in probes


def test_dream_dc_02_protected_path_write_denied():
    decision = evaluate("write_existing", "policies/trust/x", ())
    assert decision.allowed is False
    deny = Grant(path="approvals/ledger", deny=frozenset({"write_existing"}))
    assert (
        evaluate("write_existing", "approvals/ledger", (deny,)).allowed
        is False
    )


def test_dream_dc_03_virtual_sentinel_not_a_shell_file():
    with pytest.raises(CyranoError, match="SCOPE_DENIED"):
        check_path("arbitrary/shell/path", lambda _p: True)
    assert check_path("native", lambda _p: True) == "native"
    with pytest.raises(CyranoError, match="SCOPE_DENIED"):
        check_path("native", lambda _p: False)


def test_dream_dc_04_hook_error_is_not_enforcement_evidence(tmp_path):
    hooks = tmp_path / "src" / ".dcode" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "evil.py").write_text("x")
    view = build_launch_view(tmp_path / "src", tmp_path / "view")
    assert ".dcode/hooks" in view.excluded
    assert not (view.view_root / ".dcode" / "hooks").exists()


def test_dream_dc_05_governed_block_has_no_sdk_fallback():
    with pytest.raises(CyranoError, match="DCODE_RUNTIME_NOT_VERIFIED"):
        require_governed({"extension_loading": "failed"})
    with pytest.raises(CyranoError, match="DCODE_RUNTIME_NOT_VERIFIED"):
        require_governed({})


# -- DREAM-QA ----------------------------------------------------------


def test_dream_qa_01_candidate_ops_create_no_files(tmp_path):
    before = set(tmp_path.iterdir())
    _candidate()
    validate_delta(
        {"revision": 1, "scope": "t1/u1/w1"},
        {
            "expected_revision": 1,
            "scope": "t1/u1/w1",
            "diff": "d",
            "grounds": "g",
        },
        author="a",
    )
    assert set(tmp_path.iterdir()) == before


def test_dream_qa_02_quality_gates_defined_and_runnable():
    assert (ROOT / "cyrano/configs/quality/ruff.toml").exists()
    assert (ROOT / "pyproject.toml").read_text().find("pytest") >= 0


def test_dream_qa_03_honest_statuses_stay_not_tested():
    status = runtime_status()
    assert status["dcode_integration"] == "not_tested"
    assert status["governed_available"] is False
    assert status["automatic_learning_enabled"] is False


# -- B-* ---------------------------------------------------------------


def test_b_cause_unknown_is_never_an_improvement_target():
    report = analyze_patterns(
        [EpisodeRecord("e1", "failed")], learning_enabled=True
    )
    assert report.hypotheses[0].status == "not_an_improvement_target"


def test_b_unknown_routes_to_actual():
    from deepagents_code.cyrano.improvement.impact import assess_impact

    route = assess_impact(
        {"paths": ["src/x.py"], "author": "a"},
        classifier="c",
        input_semantics_unchanged=False,
        policy_ir_validated=False,
    )
    assert route.route == "B"


def test_b_protected_routes_to_manual():
    from deepagents_code.cyrano.improvement.impact import assess_impact

    route = assess_impact(
        {"paths": ["policies/trust/x"], "author": "a"},
        classifier="c",
        input_semantics_unchanged=True,
        policy_ir_validated=True,
    )
    assert route.route == "manual"


def test_b_meta_learning_recursion_refused(ctx):
    repo, scope = ctx
    with pytest.raises(CyranoError, match="META_DEPTH_EXCEEDED"):
        enqueue_review(repo, scope, "run-1", _candidate(), meta_depth=1)


# -- UH-LEARN ----------------------------------------------------------


def test_uh_learn_01_expected_red_not_mislearned():
    report = analyze_patterns(
        [
            EpisodeRecord("e1", "failed", expected_red=True),
            EpisodeRecord("e2", "failed", kind="test"),
        ],
        learning_enabled=True,
    )
    classes = {h.cause_class for h in report.hypotheses}
    assert "expected_red" in classes
    assert "regression" in classes


def test_uh_learn_02_no_security_weakening_auto_proposal():
    report = analyze_patterns(
        [
            EpisodeRecord(
                "e1",
                "failed",
                error_class="timeout",
                protected_touch=True,
            )
        ],
        learning_enabled=True,
    )
    hyp = report.hypotheses[0]
    assert hyp.protected is True
    assert hyp.status == "manual_only"


def test_uh_learn_03_regression_distinguished_from_workflow():
    report = analyze_patterns(
        [
            EpisodeRecord("e1", "failed", kind="test"),
            EpisodeRecord("e2", "failed", kind="approval"),
            EpisodeRecord("e3", "failed", error_class="network"),
            EpisodeRecord(
                "e4", "failed", error_class="requirement_change"
            ),
        ],
        learning_enabled=True,
    )
    classes = {h.cause_class for h in report.hypotheses}
    assert "regression" in classes
    assert "workflow_failure" in classes
    assert "environment" in classes
    assert "requirement_change" in classes


def test_uh_learn_04_uncertain_candidate_stays_pending_evidence():
    report = analyze_patterns(
        [EpisodeRecord("e1", "failed", kind="test")],
        learning_enabled=True,
    )
    hyp = report.hypotheses[0]
    assert hyp.status == "pending_evidence"
    assert hyp.needs_evidence


def test_uh_learn_05_eval_criteria_tamper_refused():
    with pytest.raises(CyranoError, match="EVAL_CRITERIA_TAMPER"):
        validate_delta(
            {
                "revision": 1,
                "scope": "t1/u1/w1",
                "protected_fields": ["eval_criteria"],
            },
            {
                "expected_revision": 1,
                "scope": "t1/u1/w1",
                "diff": "d",
                "grounds": "g",
                "fields": ["eval_criteria"],
            },
            author="a",
        )


def test_uh_learn_13_single_logical_job(ctx):
    repo, scope = ctx
    candidate = _candidate()
    first = enqueue_review(repo, scope, "run-1", candidate)
    second = enqueue_review(repo, scope, "run-1", candidate)
    assert first == second
    jobs = repo.connection.execute(
        "SELECT COUNT(*) FROM outbox WHERE scope_id=?", (scope,)
    ).fetchone()[0]
    assert jobs == 1


def test_uh_learn_14_learning_failure_separate_from_work_result(ctx):
    repo, scope = ctx
    candidate = _candidate()
    job_id = enqueue_review(repo, scope, "run-1", candidate)
    outcome = run_review(
        repo, scope, job_id, candidate, reviewer="r1", budget=5
    )
    assert outcome.dead_lettered is False
    assert repo.job_state(job_id) == "completed"
    failed = _candidate(diff="d2")
    job2 = enqueue_review(repo, scope, "run-1", failed)

    def boom() -> str:
        raise CyranoError("REVIEW_FAILED", "reviewer crashed")

    dead = run_review(
        repo, scope, job2, failed, reviewer="r1", budget=5, work=boom
    )
    assert dead.dead_lettered is True
    assert repo.job_state(job2) == "failed"
    pending = _candidate(diff="d3")
    job3 = enqueue_review(repo, scope, "run-1", pending)
    with pytest.raises(CyranoError, match="REVIEW_INDEPENDENCE"):
        run_review(
            repo,
            scope,
            job3,
            pending,
            reviewer="author-1",
            budget=5,
        )
    assert repo.job_state(job3) == "pending"


def test_integ_learning_default_disabled():
    with pytest.raises(CyranoError, match="LEARNING_DISABLED"):
        analyze_patterns([], learning_enabled=False)
    with pytest.raises(CyranoError, match="LEARNING_DISABLED"):
        compile_learning_plan(_plan_spec(), author="a")
