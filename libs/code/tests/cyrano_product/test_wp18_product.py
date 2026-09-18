"""WP18 product cases: interview/context/workflow evaluation."""

from __future__ import annotations

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.evaluation.context import (
    detect_eval_tamper,
    evaluate_context_candidate,
    rebind_evaluation,
)
from deepagents_code.cyrano.evaluation.interview import (
    bind_answer,
    evaluate_interview_scenario,
)
from deepagents_code.cyrano.improvement.workflow_lane import (
    analyze_failure_episode,
    classify_episode_outcome,
    enqueue_learning_followups,
    evaluate_actual_workflow,
)

# -- B-* ---------------------------------------------------------------


def test_b_question_wording_change_labels_simulation():
    stored = {
        "q1": bind_answer("What is the goal?", "ship it"),
        "q2": bind_answer("Any constraints?", "none"),
    }
    result = evaluate_interview_scenario(
        {"id": "sc1"},
        current_questions={
            "q1": "What is the goal?",
            "q2": "Any constraints at all?",
        },
        stored_answers=stored,
    )
    assert result["actual_answers"] == 1
    assert result["simulated_answers"] == 1
    assert result["all_actual"] is False
    statuses = {a["status"] for a in result["answers"]}
    assert statuses == {"actual", "simulation"}


def test_b_plan_fewer_tasks_less_coverage_no_promotion():
    verdict = evaluate_actual_workflow(
        {"tasks_completed": 10, "requirement_coverage": 0.9},
        {"tasks_completed": 7, "requirement_coverage": 0.6},
    )
    assert verdict["verdict"] == "regressed"
    assert verdict["promotable"] is False


def test_b_context_cache_gain_with_dropped_obligation_fails():
    verdict = evaluate_context_candidate(
        {"cache_reads": 10, "tokens": 900},
        {
            "cache_reads": 40,
            "tokens": 400,
            "summary_obligations": ["tests", "review"],
        },
        required_obligations=["tests", "review", "approval"],
    )
    assert verdict.verdict == "regressed"
    assert "approval" in verdict.reason


def test_b_recipe_echo_success_is_tamper():
    result = detect_eval_tamper(
        {"verification_commands": ["echo success"]},
        baseline_commands=["pytest -q", "ruff check"],
    )
    assert result["tamper"] is True
    assert result["verdict"] == "rejected"
    assert "pytest -q" in result["removed_commands"]


def test_integ_b_stale_eval_rebinds_on_body_change():
    eval_ = {"candidate_digest": "sha256:old-body"}
    result = rebind_evaluation("sha256:new-body", eval_)
    assert result["valid"] is False
    assert result["requires_reevaluation"] is True
    ok = rebind_evaluation(
        "sha256:new-body",
        {"candidate_digest": "sha256:new-body", "cached_conditions": True},
    )
    assert ok["valid"] is True
    assert ok["condition_class"] == "cached"


# -- R3-33 -------------------------------------------------------------


def _episode(**kw):
    base = {
        "cause": "verification step missing",
        "candidate_kind": "task_directive",
        "paths": ["workflows/verify.md"],
        "diff": "+ run pytest before completion",
        "expected_effect": "red suites surface before done",
        "counterexamples": ["docs-only task"],
        "rollback": "revert directive",
    }
    base.update(kw)
    return base


def test_r3_33_01_directive_candidate_carries_full_contract():
    candidate = analyze_failure_episode(
        _episode(), scope_id="task-1", freshness_epoch=4
    )
    assert candidate.candidate_kind == "task_directive"
    assert candidate.cause == "verification step missing"
    assert candidate.rollback == "revert directive"
    assert candidate.counterexamples == ("docs-only task",)


def test_r3_33_02_skill_body_change_is_path_b():
    candidate = analyze_failure_episode(
        _episode(
            candidate_kind="skill_body",
            paths=["skills/review/body.md"],
            diff="add import check",
        ),
        scope_id="ws",
        freshness_epoch=2,
    )
    assert candidate.candidate_kind == "skill_body"


def test_r3_33_03_memory_candidate_scoped_not_global():
    candidate = analyze_failure_episode(
        _episode(candidate_kind="memory"),
        scope_id="task-env-9",
        freshness_epoch=7,
    )
    assert candidate.scope_id == "task-env-9"
    assert candidate.freshness_epoch == 7


def test_r3_33_04_expected_vs_defect_classification():
    assert classify_episode_outcome({"outcome": "tdd_red"}) == "expected"
    assert (
        classify_episode_outcome({"outcome": "user_cancelled"}) == "expected"
    )
    assert (
        classify_episode_outcome({"outcome": "denied_correctly"}) == "expected"
    )
    assert (
        classify_episode_outcome({"outcome": "network_timeout"}) == "transient"
    )
    assert classify_episode_outcome({"outcome": "failed"}) == "defect"
    with pytest.raises(CyranoError, match="PROTECTED_FIELD"):
        analyze_failure_episode(
            _episode(paths=["evaluation/judges/j1.py"]),
            scope_id="t",
            freshness_epoch=1,
        )


def test_r3_33_05_eval_boundary_change_is_protected():
    with pytest.raises(CyranoError, match="PROTECTED_FIELD"):
        analyze_failure_episode(
            _episode(paths=["evaluation/sealed/holdout.json"]),
            scope_id="t",
            freshness_epoch=1,
        )


def test_r3_33_06_learning_origins_filtered_budget_bounded():
    result = enqueue_learning_followups(
        [
            {"event_id": "e1", "outcome": "failed"},
            {
                "event_id": "e2",
                "outcome": "failed",
                "origin_kind": "learning",
            },
            {"event_id": "e3", "outcome": "failed"},
        ],
        budget=5,
    )
    assert result["enqueued"] == ("e1", "e3")
    assert result["filtered_learning_origins"] == 1
    exhausted = enqueue_learning_followups(
        [{"event_id": "e9", "outcome": "failed"}], budget=0
    )
    assert exhausted["terminated"] is True
    assert exhausted["enqueued"] == ()
