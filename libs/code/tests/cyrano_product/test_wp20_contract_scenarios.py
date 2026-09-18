"""WP20 contract scenarios: CON-EVI evidence gates + R5-RF06."""

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.evaluation.assessment import (
    bind_baseline_failures,
    reconstruction_report,
    tamper_evidence_scope,
)
from deepagents_code.cyrano.evaluation.gates import (
    Release,
    ReleaseLane,
    admit_bundle,
    judge_candidate,
    verify_next_run,
)
from deepagents_code.cyrano.evaluation.paired import (
    TrialLedger,
    TrialResult,
    check_leakage,
    seal_experiment,
)
from deepagents_code.cyrano.evaluation.statistics import (
    analyze_families,
    estimate_utility,
)

EXPECTED_SUITE = frozenset({"t1", "t2"})
TRUSTED = frozenset({"trusted_runner"})


def _spec(**kw):
    base = {
        "baseline_digest": "sha256:base",
        "candidate_digest": "sha256:cand",
        "suite_digest": "sha256:suite",
        "runtime_digest": "sha256:rt",
        "plan_digest": "sha256:plan",
        "families": ["f1"],
        "holdout": ["h1"],
        "budget_units": 50,
        "quality_margin": 0.05,
        "min_pairs": 2,
    }
    base.update(kw)
    return base


def _bundle(**kw):
    base = {
        "source_digest": "sha256:src",
        "suite": {"t1", "t2"},
        "tests_collected": 12,
        "producer": "trusted_runner",
        "raw_artifacts": ["log://1"],
        "evidence_kind": "execution",
    }
    base.update(kw)
    return base


def _admit(bundle, **kw):
    args = {
        "expected_source_digest": "sha256:src",
        "expected_suite": EXPECTED_SUITE,
        "trusted_producers": TRUSTED,
    }
    args.update(kw)
    return admit_bundle(bundle, **args)


# -- CON-EVI -----------------------------------------------------------


def test_con_evi_01_matching_bundle_admitted():
    result = _admit(_bundle())
    assert result.admitted is True
    assert result.status == "admitted"


def test_con_evi_02_stale_source_digest_refused():
    result = _admit(_bundle(source_digest="sha256:old"))
    assert result.admitted is False
    assert "STALE_EVIDENCE" in result.reason


def test_con_evi_03_shrunken_suite_blocked():
    result = _admit(_bundle(suite={"t1"}))
    assert result.admitted is False
    assert result.status == "blocked"


def test_con_evi_04_zero_collected_is_not_run():
    result = _admit(_bundle(tests_collected=0))
    assert result.admitted is False
    assert result.status == "not_run"


def test_con_evi_05_self_report_forgery_denied():
    result = _admit(_bundle(producer="agent"))
    assert result.admitted is False
    assert "ACL_DENIED" in result.reason


def test_con_evi_06_summary_without_raw_unverifiable():
    result = _admit(_bundle(raw_artifacts=[]))
    assert result.admitted is False
    assert result.status == "unverifiable"


def test_con_evi_07_fixture_only_is_not_evaluated():
    result = _admit(_bundle(evidence_kind="fixture"))
    assert result.admitted is False
    assert result.status == "not_evaluated"


def test_con_evi_08_redacted_body_not_reconstructable():
    report = reconstruction_report({"prompt_body_redacted": True})
    assert report["full_reconstruction"] is False
    assert "prompt_body" in report["redacted_fields"]


def test_con_evi_09_no_trusted_head_limits_tamper_scope():
    report = tamper_evidence_scope(has_trusted_head=False)
    assert report["tamper_evidence_scope"] == "intra_bundle_only"
    assert report["chain_anchor"] is False


def test_con_evi_10_baseline_failures_bound_to_cases():
    bound = bind_baseline_failures(["t1"], {"t1", "t2"})
    assert bound["blocked"] is True
    assert bound["affected"] == ("t1",)


def test_con_evi_11_tampered_body_digest_refused():
    result = _admit(
        _bundle(body_digest="sha256:forged"),
        expected_body_digest="sha256:real",
    )
    assert result.admitted is False
    assert "INPUT_INVALID" in result.reason


def test_con_evi_12_cancelled_arm_is_incomplete():
    manifest = seal_experiment(_spec())
    ledger = TrialLedger(manifest)
    ledger.record(
        TrialResult("p1", "f1", "baseline", "completed", "pass", 1, 0)
    )
    ledger.record(
        TrialResult("p1", "f1", "candidate", "cancelled", "unknown", None, 1)
    )
    settled = ledger.settle()
    assert settled["incomplete_pairs"] == 1
    assert settled["denominator_intact"] is False


# -- R5-RF06 -----------------------------------------------------------


def test_rf06_01_same_repo_clone_split_is_leakage():
    assert check_leakage(["repo-a"], ["repo-a"]) == ("repo-a",)
    with pytest.raises(CyranoError, match="DATA_LEAKAGE"):
        seal_experiment(_spec(families=["repo-a"], holdout=["repo-a"]))


def test_rf06_02_secret_leak_hard_rejects_despite_gain():
    verdict = judge_candidate(
        verdict="improved",
        safety_failures=1,
        actual_pairs=6,
        planned_pairs=6,
    )
    assert verdict.verdict == "rejected"
    assert verdict.eligible_for_review is False


def test_rf06_03_small_mixed_sample_no_auto_promotion():
    manifest = seal_experiment(_spec(min_pairs=2))
    trials = [
        TrialResult("p1", "f1", "baseline", "completed", "pass", 1, 0),
        TrialResult("p1", "f1", "candidate", "completed", "fail", 1, 1),
        TrialResult("p2", "f1", "baseline", "completed", "fail", 1, 0),
        TrialResult("p2", "f1", "candidate", "completed", "pass", 1, 1),
    ]
    analysis = analyze_families(manifest, trials)
    verdict = judge_candidate(
        verdict=analysis.verdict,
        safety_failures=0,
        actual_pairs=analysis.completed_pairs,
        planned_pairs=manifest.min_pairs,
    )
    assert verdict.verdict == "inconclusive"
    assert verdict.eligible_for_review is False


def test_rf06_04_exposed_memory_gets_no_causal_reward():
    verdicts = estimate_utility(
        [{"memory_id": f"m{i}"} for i in range(5)],
        [{"status": "success", "applied_memories": ()}],
    )
    assert all(v.reward == "correlated" for v in verdicts)
    causal = estimate_utility(
        [{"memory_id": "m0"}],
        [{"status": "success", "applied_memories": ("m0",)}],
    )
    assert causal[0].reward == "causal"


def test_rf06_05_replay_only_never_promotes_changed_skill():
    verdict = judge_candidate(
        verdict="improved",
        safety_failures=0,
        actual_pairs=0,
        planned_pairs=4,
    )
    assert verdict.verdict == "invalid"


def test_rf06_06_promoted_but_new_run_on_old_release_fails():
    lane = ReleaseLane(Release("r1", "r0", "m1", ("ev1",)))
    lane.promote(Release("r2", "r1", "m2", ("ev2",)))
    result = verify_next_run(
        lane,
        {
            "run_id": "run-9",
            "started_after_promotion": True,
            "release_id": "r1",
        },
    )
    assert result["ok"] is False
    assert result["rollback_target"] == "r1"
    lane.rollback("r1")
    assert lane.current.release_id == "r1"
