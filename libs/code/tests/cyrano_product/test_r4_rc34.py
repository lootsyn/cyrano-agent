"""WP20 R4-RC34: actual paired trials, hard gate, sealed split."""

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.evaluation.gates import judge_candidate
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
        "min_pairs": 2,
    }
    base.update(kw)
    return base


def _trial(
    pair, family, arm, outcome="pass", status="completed", cost=1, order=0
):
    return TrialResult(pair, family, arm, status, outcome, cost, order)


def test_rc34_01_actual_pairs_preserve_raw_conditions():
    manifest = seal_experiment(_spec())
    ledger = TrialLedger(manifest)
    # Counterbalanced order: candidate first in p1, second in p2.
    ledger.record(_trial("p1", "f1", "candidate", order=0, cost=4))
    ledger.record(_trial("p1", "f1", "baseline", order=1, cost=3))
    ledger.record(_trial("p2", "f1", "baseline", order=0, cost=3))
    ledger.record(_trial("p2", "f1", "candidate", order=1, cost=4))
    pairs = ledger.pairs()
    assert all(p.complete for p in pairs)
    costs = cost_report(ledger.trials)
    assert costs.observed_units == 14
    assert costs.total_known is True
    # Replay never substitutes: the manifest binds actual digests.
    assert manifest.baseline_digest != manifest.candidate_digest


def test_rc34_02_safety_regression_hard_fails_despite_success():
    verdict = judge_candidate(
        verdict="improved",
        safety_failures=1,
        actual_pairs=8,
        planned_pairs=8,
    )
    assert verdict.verdict == "rejected"
    assert verdict.eligible_for_review is False


def test_rc34_03_overlapping_interval_never_rounds_to_passed():
    manifest = seal_experiment(_spec(min_pairs=2))
    trials = [
        _trial("p1", "f1", "baseline", outcome="pass"),
        _trial("p1", "f1", "candidate", outcome="pass"),
        _trial("p2", "f1", "baseline", outcome="pass"),
        _trial("p2", "f1", "candidate", outcome="fail"),
    ]
    analysis = analyze_families(manifest, trials)
    assert analysis.verdict in {"inconclusive", "regressed"}
    assert analysis.verdict != "improved"


def test_rc34_04_same_issue_variant_in_train_and_holdout():
    with pytest.raises(CyranoError, match="DATA_LEAKAGE"):
        seal_experiment(_spec(families=["issue-7"], holdout=["issue-7"]))
