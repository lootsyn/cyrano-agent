"""WP23 product tests: live-effectiveness admission and verdicts.

The live run itself is not executed here — these tests pin the
evidence machinery's honest behavior: no permit means no study,
fixture grounds score nothing, incomplete pairs stay inconclusive,
and a regression hard-rejects.
"""

import hashlib
import importlib
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.evaluation.paired import (
    TrialLedger,
    TrialResult,
    seal_experiment,
)
from deepagents_code.cyrano.evaluation.rubric_evidence import (
    RUBRIC_ITEMS,
    capability_report,
    cost_report,
    evidence_admission_errors,
    observe_rollout,
    request_launch_approval,
    review_effectiveness,
    run_preregistered_study,
)

CODE = Path(__file__).resolve().parents[2]
ROOT = CODE / "cyrano"
STUDY = ROOT / "tests" / "live-study"
MANIFEST_PATH = ROOT / "evidence" / "live-evaluation" / "manifest.json"

sys.path.insert(0, str(CODE / "cyrano" / "scripts"))
seal_study = importlib.import_module("seal_study")


def _spec(**kw):
    base = {
        "baseline_digest": "sha256:base",
        "candidate_digest": "sha256:cand",
        "suite_digest": "sha256:suite",
        "runtime_digest": "sha256:rt",
        "plan_digest": "sha256:plan",
        "families": ["learn-episode", "convention-apply"],
        "holdout": ["task-b-holdout"],
        "budget_units": 500,
        "quality_margin": 0.05,
        "min_pairs": 1,
        "nondeterministic_provider": True,
        "changes": ["memory/service"],
        "model_digest": "sha256:model",
        "policy_digest": "sha256:pol",
        "route_digest": "sha256:route",
    }
    base.update(kw)
    return base


def _permit(**kw):
    base = {
        "permit_id": "p-live",
        "expires_at": 100,
        "budget_units": 500,
        "families": ["learn-episode", "convention-apply"],
    }
    base.update(kw)
    return base


def _grounded_items():
    return {
        cid: {
            "evidence_refs": [
                {
                    "kind": "events",
                    "ref": f"events.jsonl#{cid}",
                    "digest": "sha256:" + "a" * 64,
                }
            ]
        }
        for cid in RUBRIC_ITEMS
    }


def _winning_trials(n):
    return [
        TrialResult(
            f"p{i}",
            "convention-apply",
            arm,
            "completed",
            outcome,
            2,
            i * 2 + j,
        )
        for i in range(n)
        for j, (arm, outcome) in enumerate(
            [("baseline", "fail"), ("candidate", "pass")]
        )
    ]


def _study(manifest, trials, **kw):
    return run_preregistered_study(
        manifest, _spec(), permit=_permit(), trials=trials, **kw
    )


def _ledger(manifest, trials, **kw) -> TrialLedger:
    ledger = _study(manifest, trials, **kw)["ledger"]
    assert isinstance(ledger, TrialLedger)
    return ledger


def test_live_unauthorized_no_permit_no_study():
    """LIVE-UNAUTHORIZED: no permit means no study can run."""
    manifest = seal_experiment(_spec())
    with pytest.raises(CyranoError) as err:
        run_preregistered_study(manifest, _spec(), permit=None, trials=[])
    assert err.value.code == "PERMISSION_DENIED"
    with pytest.raises(CyranoError) as err:
        run_preregistered_study(
            manifest,
            _spec(),
            permit=_permit(budget_units=0),
            trials=[],
        )
    assert err.value.code == "BUDGET_EXHAUSTED"
    with pytest.raises(CyranoError) as err:
        run_preregistered_study(
            manifest,
            _spec(),
            permit=_permit(expires_at=0),
            trials=[],
            now=1,
        )
    assert err.value.code == "PERMISSION_DENIED"
    with pytest.raises(CyranoError) as err:
        run_preregistered_study(
            manifest,
            _spec(plan_digest="sha256:other"),
            permit=_permit(),
            trials=[],
        )
    assert err.value.code == "INPUT_INVALID"


def test_live_claim_effectiveness_not_verified_by_fixtures():
    """LIVE-CLAIM: preparation-only evidence yields no verdict."""
    manifest = seal_experiment(_spec())
    ledger = _ledger(manifest, _winning_trials(1))
    review = review_effectiveness(manifest, ledger, {})
    assert review["official_score"] is None
    assert review["verdict"] != "improved"
    assert review["eligible_for_review"] is False
    report = json.loads(
        (ROOT / "evidence" / "release-readiness.json").read_text()
    )
    assert report["required_gates"]["live_effectiveness"] != "passed"
    assert report["release_eligible"] is False


def test_live_scope_verdict_is_manifest_bound():
    """LIVE-SCOPE: the verdict is bound, never generalized."""
    manifest = seal_experiment(_spec())
    ledger = _ledger(manifest, _winning_trials(1))
    review = review_effectiveness(manifest, ledger, _grounded_items())
    assert review["manifest_id"] == manifest.manifest_id
    assert review["scope"] == "manifest_bound_no_generalization"


def test_r5_rf11_01_case_existence_scores_nothing():
    """R5-RF11-01: designed-case existence is not a score."""
    manifest = seal_experiment(_spec())
    ledger = _ledger(manifest, _winning_trials(6))
    items = {cid: {"designed_cases": 5} for cid in RUBRIC_ITEMS}
    review = review_effectiveness(manifest, ledger, items)
    verdicts = review["items"]
    assert isinstance(verdicts, dict)
    assert all(v == "not_evaluated" for v in verdicts.values())
    assert review["verdict"] == "inconclusive"
    assert review["official_score"] is None


def test_r5_rf11_02_stale_evidence_rejected():
    """R5-RF11-02: stale source/policy digests are refused."""
    record = {
        "source_digest": "sha256:old",
        "policy_digest": "sha256:old-pol",
        "items": {},
    }
    errors = evidence_admission_errors(
        record,
        source_digest="sha256:new",
        policy_digest="sha256:new-pol",
    )
    assert "stale_source_digest" in errors
    assert "stale_policy_digest" in errors
    fixture = {
        "source_digest": "sha256:new",
        "policy_digest": "sha256:new-pol",
        "items": {"3-1": {"grounds": "fixture_only"}},
    }
    errors = evidence_admission_errors(
        fixture,
        source_digest="sha256:new",
        policy_digest="sha256:new-pol",
    )
    assert errors == ["fixture_only_grounds:3-1"]


def test_r5_rf11_03_optional_analyzer_limit_disclosed():
    """R5-RF11-03: missing optional analyzer discloses, base intact."""
    report = capability_report(
        True, {"lsp_type_check": False, "static_lint": True}
    )
    assert report["base_intact"] is True
    assert report["limits_disclosed"] == ["lsp_type_check"]


def test_r5_rf11_04_total_cost_includes_learning_overhead():
    """R5-RF11-04: no net-savings claim when total cost is higher."""
    manifest = seal_experiment(_spec())
    cheap = _ledger(
        manifest,
        [
            TrialResult(
                "p0",
                "convention-apply",
                arm,
                "completed",
                "pass",
                cost,
                index,
            )
            for index, (arm, cost) in enumerate(
                [("baseline", 10), ("candidate", 3)]
            )
        ],
    )
    report = cost_report(cheap, learning_overhead_units=0)
    assert report["net_savings_claim_allowed"] is True
    report = cost_report(cheap, learning_overhead_units=20)
    assert report["candidate_units"] == 3
    assert report["learning_overhead_units"] == 20
    assert report["total_units"] == 33
    assert report["net_savings_claim_allowed"] is False


def test_r5_rf11_05_frozen_inputs_not_mutated_by_sealing():
    """R5-RF11-05: sealing leaves the study inputs byte-identical."""

    def tree_digest():
        entries = {}
        for path in sorted(STUDY.rglob("*")):
            if path.is_file():
                entries[path.as_posix()] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
        return hashlib.sha256(
            json.dumps(entries, sort_keys=True).encode()
        ).hexdigest()

    before = tree_digest()
    manifest = seal_experiment(seal_study.build_spec())
    assert manifest.manifest_id.startswith("sha256:")
    assert tree_digest() == before
    record = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert record["manifest"]["manifest_id"] == manifest.manifest_id


def test_r5_rf11_06_missing_approval_or_regression_hard_rejects():
    """R5-RF11-06: missing approval, observation, regression rejects."""
    manifest = seal_experiment(_spec())
    ledger = _ledger(manifest, _winning_trials(6))
    review = review_effectiveness(manifest, ledger, _grounded_items())
    assert review["eligible_for_review"] is True
    refused = request_launch_approval(review, approvals={})
    assert refused["decision"] == "refused"
    missing = refused["missing"]
    assert isinstance(missing, list)
    assert sorted(missing) == [
        "activation",
        "canary",
        "learning",
        "trace",
    ]
    regressed = review_effectiveness(
        manifest,
        ledger,
        _grounded_items(),
        regressions=1,
    )
    assert regressed["verdict"] == "rejected"
    assert regressed["baseline_retained"] is True
    partial = dict(_grounded_items())
    partial["4-1"] = {"evidence_refs": []}
    observed = review_effectiveness(manifest, ledger, partial)
    assert observed["verdict"] == "inconclusive"
    assert observed["baseline_retained"] is True


def test_wp23_i01_same_release_comparison_no_model_specialization():
    """WP23-I01: one model digest pins both arms' comparison."""
    record = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest = record["manifest"]
    assert manifest["model_digest"].startswith("sha256:")
    assert manifest["baseline_digest"] != manifest["candidate_digest"]
    assert manifest["nondeterministic_provider"] is True
    suite = json.loads((STUDY / "suite.json").read_text(encoding="utf-8"))
    assert manifest["min_pairs"] == suite["min_pairs"]
    assert len(manifest["holdout"]) == len(suite["holdout"])


def test_three_pairs_under_sealed_margin_aggregate_honestly():
    """The aggregate verdict follows the registered margin rules."""
    manifest = seal_experiment(_spec(quality_margin=0.5, min_pairs=3))
    strong = _ledger(manifest, _winning_trials(3))
    review = review_effectiveness(manifest, strong, _grounded_items())
    assert review["verdict"] == "improved"
    partial = _ledger(
        manifest,
        [
            TrialResult(
                "p0",
                "convention-apply",
                "baseline",
                "completed",
                "pass",
                2,
                0,
            ),
            TrialResult(
                "p0",
                "convention-apply",
                "candidate",
                "completed",
                "fail",
                2,
                1,
            ),
            *[
                replace(t, pair_id=f"p{i + 1}")
                for i, t in enumerate(_winning_trials(2))
            ],
        ],
    )
    review = review_effectiveness(manifest, partial, _grounded_items())
    assert review["verdict"] == "inconclusive"
    assert review["baseline_retained"] is True


def test_provider_routing_is_pinned_and_fail_closed():
    """OpenRouter routing cannot silently leave the study boundary."""
    record = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    policy = record["provider_routing"]["policy"]
    assert policy["allow_fallbacks"] is False
    assert policy["require_parameters"] is True
    assert policy["only"] == ["DeepInfra"]
    baseline = json.loads((STUDY / "arms" / "baseline.json").read_text())
    candidate = json.loads((STUDY / "arms" / "candidate.json").read_text())
    assert baseline["model"] == candidate["model"]
    assert baseline["provider_routing"] == candidate["provider_routing"]
    assert (
        baseline["model"]["parameters"]["openrouter_provider"]
        == (candidate["model"]["parameters"]["openrouter_provider"])
    )


def test_wp23_i02_inconclusive_preserves_baseline():
    """WP23-I02: inconclusive keeps the baseline, never upgrades."""
    manifest = seal_experiment(_spec())
    ledger = _ledger(
        manifest,
        [
            TrialResult(
                "p0",
                "convention-apply",
                arm,
                "completed",
                "pass",
                2,
                index,
            )
            for index, arm in enumerate(["baseline", "candidate"])
        ],
    )
    review = review_effectiveness(manifest, ledger, _grounded_items())
    assert review["verdict"] != "improved"
    assert review["baseline_retained"] is True
    assert review["eligible_for_review"] is False


def test_wp23_i03_each_launch_aspect_needs_its_own_approval():
    """WP23-I03: activation, learning, canary, trace are separate."""
    manifest = seal_experiment(_spec())
    ledger = _ledger(manifest, _winning_trials(6))
    review = review_effectiveness(manifest, ledger, _grounded_items())
    assert review["eligible_for_review"] is True
    refused = request_launch_approval(review, approvals={"activation": True})
    assert refused["decision"] == "refused"
    missing = refused["missing"]
    assert isinstance(missing, list)
    assert sorted(missing) == ["canary", "learning", "trace"]
    granted = request_launch_approval(
        review,
        approvals={
            "activation": True,
            "learning": True,
            "canary": True,
            "trace": True,
        },
    )
    assert granted["decision"] == "approved"
    retained = observe_rollout(granted, healthy=True, release_id="rel-1")
    assert retained["action"] == "retain"
    rolled = observe_rollout(refused, healthy=True, release_id="rel-1")
    assert rolled["action"] == "rollback"


def test_zero_pairs_never_pass():
    """A zero-pair study is invalid, not a pass."""
    manifest = seal_experiment(_spec())
    ledger = _ledger(manifest, [])
    review = review_effectiveness(manifest, ledger, _grounded_items())
    assert review["verdict"] == "invalid"
    assert review["baseline_retained"] is True


def test_incomplete_pair_stays_incomplete():
    """A one-sided pair cannot complete the denominator."""
    manifest = seal_experiment(_spec())
    study = _study(
        manifest,
        [
            TrialResult(
                "p0",
                "convention-apply",
                "baseline",
                "completed",
                "fail",
                2,
                0,
            )
        ],
    )
    settle = study["settle"]
    assert isinstance(settle, dict)
    assert settle["actual_pairs"] == 0
    assert settle["incomplete_pairs"] == 1
    ledger = study["ledger"]
    assert isinstance(ledger, TrialLedger)
    review = review_effectiveness(manifest, ledger, _grounded_items())
    assert review["verdict"] != "improved"


def test_budget_enforcement_debits_and_refuses():
    """Budget is debited per completed trial and never negative."""
    manifest = seal_experiment(_spec())
    with pytest.raises(CyranoError) as err:
        run_preregistered_study(
            manifest,
            _spec(),
            permit=_permit(budget_units=3),
            trials=_winning_trials(1),
        )
    assert err.value.code == "BUDGET_EXHAUSTED"
    study = run_preregistered_study(
        manifest,
        _spec(),
        permit=_permit(budget_units=10),
        trials=_winning_trials(1),
    )
    assert study["spent_units"] == 4
    assert study["remaining_units"] == 6


def test_leakage_check_before_any_live_run():
    """Seal refuses train/holdout overlap before any call."""
    with pytest.raises(CyranoError) as err:
        seal_experiment(
            _spec(
                families=["learn-episode", "convention-apply"],
                holdout=["convention-apply"],
            )
        )
    assert err.value.code == "DATA_LEAKAGE"
    record = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert not (
        set(record["manifest"]["families"])
        & set(record["manifest"]["holdout"])
    )
