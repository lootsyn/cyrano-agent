"""R4-RC43: live-effectiveness evidence machinery, not fake scores."""

import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.evaluation.paired import (
    TrialLedger,
    TrialResult,
    seal_experiment,
)
from deepagents_code.cyrano.evaluation.rubric_evidence import (
    RUBRIC_ITEMS,
    coverage_verdict,
    item_verdicts,
    review_effectiveness,
    run_preregistered_study,
)
from deepagents_code.cyrano.kernel.actions import ActionBroker, Grant
from deepagents_code.cyrano.kernel.approvals import issue_permit

_KEY = Ed25519PrivateKey.generate()

CODE = Path(__file__).resolve().parents[2]


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
        "min_pairs": 4,
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


def _winning_ledger(manifest, n) -> TrialLedger:
    study = run_preregistered_study(
        manifest,
        _spec(),
        permit=_permit(),
        trials=(
            t
            for i in range(n)
            for t in (
                TrialResult(
                    f"p{i}",
                    "convention-apply",
                    "baseline",
                    "completed",
                    "fail",
                    2,
                    i * 2,
                ),
                TrialResult(
                    f"p{i}",
                    "convention-apply",
                    "candidate",
                    "completed",
                    "pass",
                    2,
                    i * 2 + 1,
                ),
            )
        ),
    )
    ledger = study["ledger"]
    assert isinstance(ledger, TrialLedger)
    return ledger


def _grounded_items():
    return {
        cid: {
            "evidence_refs": [
                {
                    "kind": "events",
                    "ref": f"events.jsonl#{cid}",
                    "digest": "sha256:" + cid.replace("-", "") * 16,
                }
            ]
        }
        for cid in RUBRIC_ITEMS
    }


def test_rc43_01_one_scenario_completed_with_linkage():
    """A -> improvement -> B scores only from raw grounds."""
    manifest = seal_experiment(_spec())
    ledger = _winning_ledger(manifest, 6)
    items = _grounded_items()
    items["3-2"]["evidence_refs"].append(
        {
            "kind": "run_binding",
            "ref": "run-binding.json#task-b-candidate",
            "digest": "sha256:" + "b" * 64,
        }
    )
    items["3-4"]["evidence_refs"].append(
        {
            "kind": "artifact",
            "ref": "release-subject.json#candidate",
            "digest": "sha256:" + "c" * 64,
        }
    )
    review = review_effectiveness(manifest, ledger, items)
    assert review["verdict"] == "improved"
    assert review["eligible_for_review"] is True
    verdicts = review["items"]
    assert isinstance(verdicts, dict)
    assert all(v == "evaluated" for v in verdicts.values())
    assert review["official_score"] is None
    assert review["scope"] == "manifest_bound_no_generalization"


def test_rc43_02_fixture_only_observation_scores_nothing():
    """Fixture-only grounds leave items unevaluated, score null."""
    manifest = seal_experiment(_spec())
    ledger = _winning_ledger(manifest, 6)
    items = {
        cid: {"grounds": "fixture_only", "evidence_refs": []}
        for cid in RUBRIC_ITEMS
    }
    review = review_effectiveness(manifest, ledger, items)
    verdicts = review["items"]
    assert isinstance(verdicts, dict)
    assert all(v == "not_evaluated" for v in verdicts.values())
    assert review["official_score"] is None
    assert review["verdict"] == "inconclusive"
    assert review["baseline_retained"] is True


def test_rc43_03_local_ledger_survives_exporter_failure():
    """Exporter-down keeps local durable evidence; audit fail blocks."""
    manifest = seal_experiment(_spec())
    ledger = _winning_ledger(manifest, 6)
    settle = ledger.settle()
    assert settle["actual_pairs"] == 6
    assert settle["denominator_intact"] is True
    assert len(ledger.trials) == 12

    def failing_audit(_detail):
        raise CyranoError("EXPORT_UNAVAILABLE", "exporter down")

    broker = ActionBroker(
        frozenset({"edit_file"}),
        (Grant("a.py", allow=frozenset({"write_existing"})),),
        failing_audit,
    )
    subject = "sha256:" + "0" * 64
    permit = issue_permit(
        _KEY,
        permit_id="p-audit",
        subject_digest=subject,
        shown_digest="s",
        user_event_id="u1",
        scope_id="sc",
        purpose="execute",
        audience="cyrano",
        nonce="n",
        issued_at=0,
        expires_at=10_000,
    )
    applied = []
    with pytest.raises(CyranoError):
        broker.apply_scoped_patch(
            permit=permit,
            trust_root=None,
            subject_digest=subject,
            now=1,
            is_revoked=lambda pid: False,
            apply_fn=lambda: applied.append(True),
        )
    assert applied == []
    assert len(ledger.trials) == 12


def test_rc43_04_untested_modes_block_release_grade():
    """TUI-only coverage exposes ACP/headless gaps and blocks."""
    verdict = coverage_verdict(["tui"], ["tui", "acp", "headless"])
    assert verdict["complete"] is False
    assert verdict["missing_modes"] == ["acp", "headless"]
    assert verdict["release_grade_blocked"] is True
    full = coverage_verdict(
        ["tui", "acp", "headless"], ["tui", "acp", "headless"]
    )
    assert full["complete"] is True
    assert full["release_grade_blocked"] is False


def test_rc43_sealed_manifest_is_persisted_and_digest_bound():
    """The sealed manifest exists, reports its terminal verdict, verifies."""
    path = CODE / "cyrano" / "evidence" / "live-evaluation" / "manifest.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["kind"] == "sealed_experiment_manifest"
    assert record["status"] == "executed_inconclusive"
    assert record["manifest"]["manifest_id"].startswith("sha256:")
    assert record["manifest"]["model_digest"].startswith("sha256:")
    assert record["sealed_manifest_digest"].startswith("sha256:")
    recomputed = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(record["manifest"], sort_keys=True).encode()
        ).hexdigest()
    )
    assert recomputed == record["sealed_manifest_digest"]


def test_item_verdicts_requires_raw_grounds():
    """Items without admissible refs stay not_evaluated."""
    items = {
        "3-1": {
            "evidence_refs": [{"kind": "fixture", "ref": "f", "digest": "d"}]
        },
        "3-2": {
            "evidence_refs": [
                {
                    "kind": "events",
                    "ref": "events.jsonl#3-2",
                    "digest": "sha256:x",
                }
            ]
        },
    }
    verdicts = item_verdicts(items)
    assert verdicts["3-1"] == "not_evaluated"
    assert verdicts["3-2"] == "evaluated"
    assert verdicts["4-4"] == "not_evaluated"
