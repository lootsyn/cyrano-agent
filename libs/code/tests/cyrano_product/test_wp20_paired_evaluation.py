"""WP20 paired evaluation: R3-34 effect cases and PEQ-PY-T55..60."""

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.evaluation.budget import authorize_experiment
from deepagents_code.cyrano.evaluation.gates import (
    Release,
    ReleaseLane,
    judge_candidate,
    verify_next_run,
)
from deepagents_code.cyrano.evaluation.paired import (
    TrialLedger,
    TrialResult,
    seal_experiment,
)
from deepagents_code.cyrano.evaluation.statistics import (
    analyze_families,
    cost_report,
)


def _spec(**kw):
    base = {
        "baseline_digest": "sha256:base",
        "candidate_digest": "sha256:cand",
        "suite_digest": "sha256:suite",
        "runtime_digest": "sha256:rt",
        "plan_digest": "sha256:plan",
        "families": ["f1"],
        "holdout": ["h1"],
        "budget_units": 100,
        "quality_margin": 0.05,
        "min_pairs": 4,
    }
    base.update(kw)
    return base


def _winning_pairs(manifest, n, family="f1"):
    ledger = TrialLedger(manifest)
    for i in range(n):
        ledger.record(
            TrialResult(
                f"p{i}",
                family,
                "baseline",
                "completed",
                "fail",
                2,
                i * 2,
            )
        )
        ledger.record(
            TrialResult(
                f"p{i}",
                family,
                "candidate",
                "completed",
                "pass",
                2,
                i * 2 + 1,
            )
        )
    return ledger


def test_r3_34_01_promotion_only_after_all_gates():
    manifest = seal_experiment(_spec())
    ledger = _winning_pairs(manifest, 6)
    analysis = analyze_families(manifest, ledger.trials)
    assert analysis.verdict == "improved"
    verdict = judge_candidate(
        verdict=analysis.verdict,
        safety_failures=0,
        actual_pairs=analysis.completed_pairs,
        planned_pairs=manifest.min_pairs,
    )
    assert verdict.eligible_for_review is True
    assert verdict.verdict == "improved"


def test_r3_34_02_small_or_mixed_sample_inconclusive():
    manifest = seal_experiment(_spec())
    analysis = analyze_families(manifest, [])
    assert analysis.verdict == "inconclusive"
    verdict = judge_candidate(
        verdict=analysis.verdict,
        safety_failures=0,
        actual_pairs=analysis.completed_pairs,
        planned_pairs=manifest.min_pairs,
    )
    assert verdict.eligible_for_review is False


def test_r3_34_03_cost_saving_cannot_offset_accuracy_break():
    verdict = judge_candidate(
        verdict="improved",
        safety_failures=1,
        actual_pairs=4,
        planned_pairs=4,
    )
    assert verdict.verdict == "rejected"
    assert "HARD_GATE_FAILURE" in verdict.reason


def test_r3_34_04_changed_skill_needs_live_rerun():
    # A changed skill cited through replay alone has zero actual pairs.
    verdict = judge_candidate(
        verdict="improved",
        safety_failures=0,
        actual_pairs=0,
        planned_pairs=4,
    )
    assert verdict.verdict == "invalid"
    assert verdict.eligible_for_review is False


def test_r3_34_05_pre_post_promotion_run_binding():
    lane = ReleaseLane(Release("r1", "r0", "m1", ("ev1",)))
    lane.promote(Release("r2", "r1", "m2", ("ev2",)))
    old_run = verify_next_run(
        lane,
        {
            "run_id": "run-old",
            "started_after_promotion": False,
            "pinned_release_id": "r1",
            "release_id": "r1",
        },
    )
    assert old_run["ok"] is True
    stale_run = verify_next_run(
        lane,
        {
            "run_id": "run-stale",
            "started_after_promotion": True,
            "release_id": "r1",
        },
    )
    assert stale_run["ok"] is False
    assert stale_run["rollback_target"] == "r1"


def test_r3_34_06_parallel_promotion_cas_and_rollback():
    lane = ReleaseLane(Release("r1", "r0", "m1", ("ev1",)))
    first = lane.promote(Release("r2", "r1", "m2", ("ev2",)))
    assert first.release_id == "r2"
    with pytest.raises(CyranoError, match="REBASE_REQUIRED"):
        lane.promote(Release("r3", "r1", "m3", ("ev3",)))
    rolled = lane.rollback("r1")
    assert lane.current.release_id == "r1"
    # The rolled-forward release stays in history as evidence.
    assert rolled is lane.current


def test_peq_t55_changed_skill_replay_score_refused():
    verdict = judge_candidate(
        verdict="improved",
        safety_failures=0,
        actual_pairs=0,
        planned_pairs=2,
    )
    assert verdict.eligible_for_review is False


def test_peq_t56_holdout_overlap_fails_manifest_check():
    with pytest.raises(CyranoError, match="DATA_LEAKAGE"):
        seal_experiment(_spec(families=["train-fam"], holdout=["train-fam"]))


def test_peq_t57_zero_budget_makes_no_provider_call():
    with pytest.raises(CyranoError, match="BUDGET_EXHAUSTED"):
        authorize_experiment(
            _spec(),
            permit={
                "permit_id": "p0",
                "budget_units": 0,
                "families": {"f1"},
                "expires_at": 999,
            },
            now=10,
        )


def test_peq_t58_lint_gain_with_acceptance_regression_refused():
    verdict = judge_candidate(
        verdict="regressed",
        safety_failures=0,
        actual_pairs=4,
        planned_pairs=4,
    )
    assert verdict.eligible_for_review is False
    assert verdict.verdict == "regressed"


def test_peq_t59_missing_cache_usage_is_unknown_not_zero():
    report = cost_report(
        [
            TrialResult("p1", "f1", "baseline", "completed", "pass", None, 0),
            TrialResult("p1", "f1", "candidate", "completed", "pass", 5, 1),
        ]
    )
    assert report.total_known is False
    assert report.missing == 1


def test_peq_t60_rollback_restores_prior_release_keeps_evidence():
    lane = ReleaseLane(Release("r1", "r0", "m1", ("ev1",)))
    lane.promote(Release("r2", "r1", "m2", ("ev2",)))
    rolled = lane.rollback("r1")
    assert rolled.release_id == "r1"
    assert lane.current.release_id == "r1"
    with pytest.raises(CyranoError, match="MISSING_RELEASE"):
        lane.rollback("ghost")
