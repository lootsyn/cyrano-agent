"""WP15 product cases: bounded Path A policy IR, screen, activation."""

from __future__ import annotations

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.improvement.policy_ir import validate_ir
from deepagents_code.cyrano.improvement.policy_runner import (
    decide_activation,
    request_actual_validation,
)
from deepagents_code.cyrano.improvement.search import (
    decide,
    generate_policy_candidate,
    screen_replay,
)
from deepagents_code.cyrano.improvement.worlds import ExecutionSignature

_SIG = ExecutionSignature(
    model_id="m1",
    endpoint="ep1",
    runtime_digest="rt1",
    tool_inventory_digest="ti1",
    skill_digest="sk1",
)


def _ir(**kw):
    spec = {
        "id": "p1",
        "rules": [
            {
                "feature": "test_outcome",
                "op": "==",
                "value": "fail",
                "then": "retry",
            }
        ],
        "default": "proceed",
    }
    spec.update(kw)
    return spec


def _spec(ir):
    return {
        "baseline_digest": "sha256:base",
        "candidate_digest": ir.ir_digest,
        "suite_digest": "sha256:suite",
        "runtime_digest": "sha256:rt",
        "plan_digest": "sha256:plan",
        "families": ["f1"],
        "holdout": ["h1"],
        "budget_units": 10,
        "quality_margin": 0.05,
        "min_pairs": 2,
    }


# -- A-IR --------------------------------------------------------------


def test_a_ir_unbounded_loop_statically_refused():
    with pytest.raises(CyranoError, match="UNBOUNDED_LOOP"):
        validate_ir(_ir(rules=[{"kind": "loop", "feature": "attempts_used"}]))
    with pytest.raises(CyranoError, match="UNBOUNDED_LOOP"):
        validate_ir(_ir(rules=[{"kind": "while", "feature": "attempts_used"}]))


def test_a_ir_import_refused():
    with pytest.raises(CyranoError, match="IMPORT_FORBIDDEN"):
        validate_ir(_ir(rules=[{"kind": "import"}]))


def test_a_ir_unknown_feature_refused():
    with pytest.raises(CyranoError, match="UNKNOWN_FEATURE"):
        validate_ir(
            _ir(
                rules=[
                    {
                        "feature": "hidden_score",
                        "op": "==",
                        "value": 1,
                        "then": "proceed",
                    }
                ]
            )
        )


def test_a_ir_unbounded_literal_and_action_refused():
    with pytest.raises(CyranoError, match="BOUND_REQUIRED"):
        validate_ir(
            _ir(
                rules=[
                    {
                        "feature": "attempts_used",
                        "op": "<",
                        "value": 10**12,
                        "then": "retry",
                    }
                ]
            )
        )
    with pytest.raises(CyranoError, match="OPERATION_NOT_ALLOWED"):
        validate_ir(
            _ir(
                rules=[
                    {
                        "feature": "attempts_used",
                        "op": "<",
                        "value": 3,
                        "then": "delete_repo",
                    }
                ]
            )
        )


# -- A-NOMENU ----------------------------------------------------------


def test_a_nomenu_new_combo_expresses_new_policy():
    menu = [_ir(), _ir(default="abort")]
    candidate = generate_policy_candidate(
        _ir(default="escalate"), author="agent", profile_menu=menu
    )
    assert candidate.novel is True
    assert (
        decide(
            candidate.ir,
            {"test_outcome": "pass", "attempts_used": 0},
        )
        == "escalate"
    )


def test_a_nomenu_menu_duplicate_reported_not_hidden():
    candidate = generate_policy_candidate(
        _ir(), author="agent", profile_menu=[_ir()]
    )
    assert candidate.novel is False


# -- A-ACTUAL ----------------------------------------------------------


def test_a_actual_replay_improvement_cannot_promote():
    ir = validate_ir(_ir())
    candidate = generate_policy_candidate(_ir(), author="agent")
    request = request_actual_validation(
        candidate,
        signature=_SIG,
        spec=_spec(ir),
        replay_score=0.99,
    )
    assert request.state == "evaluation_required"
    verdict = decide_activation(
        request,
        current_signature=_SIG,
        actual_verdict=None,
        review_independent=True,
        approval_bounded=True,
    )
    assert verdict.allowed is False
    assert "ACTUAL_EVALUATION_REQUIRED" in verdict.reason


# -- integration -------------------------------------------------------


def test_wp15_i01_fixed_observations_only_exclude_future():
    candidate = generate_policy_candidate(_ir(), author="agent")
    observations = [
        {"seq": 1, "test_outcome": "fail"},
        {"seq": 2, "test_outcome": "pass"},
        {"seq": 9, "test_outcome": "fail"},  # future data
    ]
    screen = screen_replay(candidate, observations, cutoff_seq=5)
    assert screen.support == 2
    assert screen.excluded_future == 1
    assert screen.score == 0.5


def test_wp15_i02_different_signature_reuses_nothing():
    ir = validate_ir(_ir())
    candidate = generate_policy_candidate(_ir(), author="agent")
    request = request_actual_validation(
        candidate, signature=_SIG, spec=_spec(ir)
    )
    other = ExecutionSignature(
        model_id="m2",
        endpoint="ep1",
        runtime_digest="rt1",
        tool_inventory_digest="ti1",
        skill_digest="sk1",
    )
    verdict = decide_activation(
        request,
        current_signature=other,
        actual_verdict="improved",
        review_independent=True,
        approval_bounded=True,
    )
    assert verdict.allowed is False
    assert "SIGNATURE_MISMATCH" in verdict.reason


def test_wp15_i03_activation_needs_verdict_review_approval():
    ir = validate_ir(_ir())
    candidate = generate_policy_candidate(_ir(), author="agent")
    request = request_actual_validation(
        candidate, signature=_SIG, spec=_spec(ir)
    )
    missing_review = decide_activation(
        request,
        current_signature=_SIG,
        actual_verdict="improved",
        review_independent=False,
        approval_bounded=True,
    )
    assert missing_review.allowed is False
    missing_approval = decide_activation(
        request,
        current_signature=_SIG,
        actual_verdict="improved",
        review_independent=True,
        approval_bounded=False,
    )
    assert missing_approval.allowed is False
    full = decide_activation(
        request,
        current_signature=_SIG,
        actual_verdict="improved",
        review_independent=True,
        approval_bounded=True,
    )
    assert full.allowed is True


def test_wp15_i03_manifest_must_bind_screened_ir():
    ir = validate_ir(_ir())
    candidate = generate_policy_candidate(_ir(), author="agent")
    bad = _spec(ir)
    bad["candidate_digest"] = "sha256:other"
    with pytest.raises(CyranoError, match="BINDING_MISMATCH"):
        request_actual_validation(candidate, signature=_SIG, spec=bad)
