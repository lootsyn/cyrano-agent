"""WP20 product tests: sealed manifest, statistics, gates, budget."""

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.evaluation.assessment import (
    dedupe_dataset,
    read_sealed_output,
)
from deepagents_code.cyrano.evaluation.budget import (
    BudgetAccount,
    authorize_experiment,
    begin_spend,
)
from deepagents_code.cyrano.evaluation.gates import (
    judge_candidate,
    validate_splits,
)
from deepagents_code.cyrano.evaluation.paired import (
    TrialLedger,
    TrialResult,
    build_memory_arms,
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
        "families": ["f1", "f2"],
        "holdout": ["h1"],
        "budget_units": 100,
        "quality_margin": 0.05,
        "min_pairs": 2,
    }
    base.update(kw)
    return base


def _trial(
    pair, family, arm, outcome="pass", status="completed", cost=1, order=0
):
    return TrialResult(pair, family, arm, status, outcome, cost, order)


# -- DREAM-EVA ---------------------------------------------------------


def test_dream_eva_01_test_deletion_is_protected():
    with pytest.raises(CyranoError, match="PROTECTED_FIELD"):
        seal_experiment(_spec(changes=("policies/trust/eval_gate.py",)))


def test_dream_eva_02_family_overlap_is_data_leakage():
    with pytest.raises(CyranoError, match="DATA_LEAKAGE"):
        seal_experiment(_spec(holdout=["f1"]))


def test_dream_eva_03_post_cutoff_memory_leak_invalidates():
    with pytest.raises(CyranoError, match="DATA_LEAKAGE"):
        seal_experiment(_spec(memory_refs_after_cutoff=["m1"]))


def test_dream_eva_04_unregistered_statistics_blocked():
    with pytest.raises(CyranoError, match="MISSING_PREREGISTRATION"):
        seal_experiment(_spec(budget_units=0))
    with pytest.raises(CyranoError, match="MISSING_PREREGISTRATION"):
        seal_experiment(_spec(quality_margin=None))
    with pytest.raises(CyranoError, match="MISSING_PREREGISTRATION"):
        seal_experiment(_spec(min_pairs=0))


def test_dream_eva_05_safety_failure_hard_rejects():
    verdict = judge_candidate(
        verdict="improved",
        safety_failures=1,
        actual_pairs=10,
        planned_pairs=10,
    )
    assert verdict.verdict == "rejected"
    assert verdict.eligible_for_review is False
    assert "HARD_GATE_FAILURE" in verdict.reason


def test_dream_eva_06_uncertain_effect_stays_inconclusive():
    verdict = judge_candidate(
        verdict="inconclusive",
        safety_failures=0,
        actual_pairs=10,
        planned_pairs=10,
    )
    assert verdict.verdict == "inconclusive"
    assert verdict.eligible_for_review is False
    assert "passed" not in verdict.verdict
    assert "success" not in verdict.reason


def test_dream_eva_07_unknown_cost_never_zero_filled():
    trials = [
        _trial("p1", "f1", "baseline", cost=3),
        _trial("p1", "f1", "candidate", cost=None),
    ]
    report = cost_report(trials)
    assert report.total_known is False
    assert report.missing == 1
    assert report.coverage == 0.5
    assert report.observed_units == 3


def test_dream_eva_08_nondeterminism_recorded_not_hidden():
    manifest = seal_experiment(_spec(nondeterministic_provider=True))
    ledger = TrialLedger(manifest)
    ledger.record(_trial("p1", "f1", "candidate", order=1))
    ledger.record(_trial("p1", "f1", "baseline", order=0))
    settled = ledger.settle()
    assert settled["nondeterministic_provider"] is True
    orders = [t.order_index for t in ledger.trials]
    assert orders == [1, 0]


def test_dream_eva_09_bundled_change_not_single_cause():
    arms = build_memory_arms({"changes": {"policy", "memory"}}, ["d1", "d2"])
    assert arms["attributable"] is False
    assert "ablation" in arms["note"]
    independent = build_memory_arms({"changes": {"memory"}}, ["d1"])
    assert independent["attributable"] is True


# -- EVAL-* ------------------------------------------------------------


def test_eval_zero_actual_pairs_never_eligible():
    verdict = judge_candidate(
        verdict="improved",
        safety_failures=0,
        actual_pairs=0,
        planned_pairs=4,
    )
    assert verdict.eligible_for_review is False
    assert verdict.verdict == "invalid"


def test_eval_family_split_leakage():
    with pytest.raises(CyranoError, match="DATA_LEAKAGE"):
        validate_splits({"train": {"f1"}, "holdout": {"f1", "f2"}})


def test_eval_denom_failed_pair_not_dropped():
    manifest = seal_experiment(_spec())
    ledger = TrialLedger(manifest)
    ledger.record(_trial("p1", "f1", "baseline", outcome="pass"))
    ledger.record(_trial("p1", "f1", "candidate", outcome="fail"))
    ledger.record(_trial("p2", "f2", "baseline", outcome="pass"))
    ledger.record(_trial("p2", "f2", "candidate", status="aborted"))
    settled = ledger.settle()
    assert settled["actual_pairs"] == 1
    assert settled["incomplete_pairs"] == 1
    assert settled["denominator_intact"] is False


def test_eval_cost_unknown_stays_unknown():
    report = cost_report([_trial("p1", "f1", "baseline", cost=None)])
    assert report.observed_units == 0
    assert report.total_known is False


def test_eval_safe_hard_rejected():
    verdict = judge_candidate(
        verdict="improved",
        safety_failures=1,
        actual_pairs=4,
        planned_pairs=4,
    )
    assert verdict.verdict == "rejected"


def test_eval_seal_author_denied_detail():
    denied = read_sealed_output({"detail": "rows"}, requester_role="author")
    assert denied["status"] == "denied"
    assert denied["detail"] is None
    allowed = read_sealed_output({"detail": "rows"}, requester_role="reviewer")
    assert allowed["status"] == "ok"
    assert allowed["detail"] == "rows"


def test_eval_interval_inconclusive_keeps_baseline():
    manifest = seal_experiment(_spec(min_pairs=2))
    trials = [
        _trial("p1", "f1", "baseline", outcome="pass"),
        _trial("p1", "f1", "candidate", outcome="fail"),
        _trial("p2", "f2", "baseline", outcome="fail"),
        _trial("p2", "f2", "candidate", outcome="pass"),
    ]
    analysis = analyze_families(manifest, trials)
    assert analysis.verdict == "inconclusive"


# -- UH-LEARN / INTEG --------------------------------------------------


def test_uh_learn_06_repo_family_overlap_invalidates():
    with pytest.raises(CyranoError, match="DATA_LEAKAGE"):
        seal_experiment(_spec(families=["repo-a"], holdout=["repo-a"]))


def test_uh_learn_07_small_mixed_sample_no_promotion():
    verdict = judge_candidate(
        verdict="inconclusive",
        safety_failures=0,
        actual_pairs=3,
        planned_pairs=3,
    )
    assert verdict.verdict == "inconclusive"
    assert verdict.eligible_for_review is False


def test_uh_learn_08_unauthorized_execution_hard_rejects():
    verdict = judge_candidate(
        verdict="improved",
        safety_failures=1,
        actual_pairs=5,
        planned_pairs=5,
    )
    assert "HARD_GATE_FAILURE" in verdict.reason
    assert verdict.verdict == "rejected"


def test_integ_dataset_count_dedupes_shared_cases():
    merged = dedupe_dataset([["R01", "R02", "R03"], ["R01", "R04"]])
    assert merged["independent_count"] == 4
    assert merged["deduplicated"] == ("R01",)


# -- budget ------------------------------------------------------------


def test_budget_zero_permit_runs_no_paid_call():
    with pytest.raises(CyranoError, match="BUDGET_EXHAUSTED"):
        authorize_experiment(
            _spec(), permit={"budget_units": 0, "expires_at": 100}
        )
    with pytest.raises(CyranoError, match="PERMISSION_DENIED"):
        authorize_experiment(_spec(), permit=None)
    account = BudgetAccount(total=10, spent=8)
    with pytest.raises(CyranoError, match="BUDGET_EXHAUSTED"):
        begin_spend(account, 5)


# -- review regressions ------------------------------------------------


def test_review_protected_prefixes_beyond_trust():
    with pytest.raises(CyranoError, match="PROTECTED_FIELD"):
        seal_experiment(_spec(changes=("evaluation/sealed/gate.py",)))
    with pytest.raises(CyranoError, match="PROTECTED_FIELD"):
        seal_experiment(_spec(changes=("audit/ledger.py",)))


def test_review_set_typed_splits_still_leak_checked():
    with pytest.raises(CyranoError, match="DATA_LEAKAGE"):
        seal_experiment(_spec(families={"f1"}, holdout={"f1"}))


def test_review_duplicate_arm_record_refused():
    manifest = seal_experiment(_spec())
    ledger = TrialLedger(manifest)
    ledger.record(_trial("p1", "f1", "baseline"))
    with pytest.raises(CyranoError, match="INPUT_INVALID"):
        ledger.record(_trial("p1", "f1", "baseline", outcome="fail"))


def test_review_set_typed_scope_denied():
    spec = _spec()
    spec["families"] = {"f9"}
    with pytest.raises(CyranoError, match="SCOPE_DENIED"):
        authorize_experiment(
            spec,
            permit={
                "budget_units": 10,
                "expires_at": 100,
                "families": {"f1", "f2"},
            },
        )
