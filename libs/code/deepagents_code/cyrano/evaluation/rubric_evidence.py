"""WP23 live-effectiveness evidence admission and scoped verdicts.

Preparation artifacts never score. Every rubric item requires its own
raw evidence reference; a fixture-only submission leaves the official
score ``null`` and the item unevaluated. A zero-pair or incomplete
study is never a pass — inconclusive preserves the baseline.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.evaluation.budget import (
    BudgetAccount,
    authorize_experiment,
    begin_spend,
)
from deepagents_code.cyrano.evaluation.gates import (
    EffectVerdict,
    judge_candidate,
)
from deepagents_code.cyrano.evaluation.paired import (
    EvaluationManifest,
    TrialLedger,
    TrialResult,
    seal_experiment,
)
from deepagents_code.cyrano.evaluation.statistics import (
    analyze_families,
)

# Rubric items whose score requires an independent raw ground each.
RUBRIC_ITEMS = ("3-1", "3-2", "3-3", "3-4", "4-1", "4-2", "4-3", "4-4")

# Evidence kinds admitted as an item's raw ground. Fixture, design and
# preparation kinds are deliberately absent.
GROUND_KINDS = frozenset(
    {
        "run_binding",
        "events",
        "artifact",
        "receipt",
        "oracle_result",
        "review",
    }
)

# Rollout aspects WP23-I03 requires to be authorized individually.
LAUNCH_ASPECTS = ("activation", "learning", "canary", "trace")


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    """One raw evidence reference bound to a digest."""

    kind: str
    ref: str
    digest: str


def _refs(raw: object) -> tuple[EvidenceRef, ...]:
    """Normalize evidence references; malformed entries are dropped."""
    if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes)):
        return ()
    out = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        kind = item.get("kind")
        ref = item.get("ref")
        dg = item.get("digest")
        if kind and ref and dg:
            out.append(EvidenceRef(str(kind), str(ref), str(dg)))
    return tuple(out)


def item_verdicts(items: Mapping[str, object]) -> dict[str, str]:
    """Score each rubric item only when it carries a raw ground.

    An item without at least one admissible evidence reference is
    ``not_evaluated`` — designed-case existence counts for nothing.
    """
    verdicts = {}
    for cid in RUBRIC_ITEMS:
        entry = items.get(cid)
        refs = (
            _refs(entry.get("evidence_refs"))
            if isinstance(entry, Mapping)
            else ()
        )
        grounded = any(r.kind in GROUND_KINDS for r in refs)
        verdicts[cid] = "evaluated" if grounded else "not_evaluated"
    return verdicts


def evidence_admission_errors(
    record: Mapping[str, object],
    *,
    source_digest: str,
    policy_digest: str,
) -> list[str]:
    """Reject stale source/policy evidence and fixture-only grounds."""
    errors = []
    if record.get("source_digest") != source_digest:
        errors.append("stale_source_digest")
    if record.get("policy_digest") != policy_digest:
        errors.append("stale_policy_digest")
    raw_items = record.get("items")
    items = raw_items if isinstance(raw_items, Mapping) else {}
    for cid in RUBRIC_ITEMS:
        entry = items.get(cid)
        if (
            isinstance(entry, Mapping)
            and entry.get("grounds") == "fixture_only"
        ):
            errors.append(f"fixture_only_grounds:{cid}")
    return errors


def run_preregistered_study(
    manifest: EvaluationManifest,
    spec: Mapping[str, object],
    *,
    permit: Mapping[str, object] | None,
    trials: Iterable[TrialResult],
    now: int = 0,
) -> Mapping[str, object]:
    """Authorize, debit and record a sealed study's specimens.

    A missing or expired permit, a zero budget or an out-of-scope
    family refuses before any trial is recorded. The spec must
    reproduce the sealed manifest — a permit is never bound to a
    different experiment than the one being recorded. Spend is
    debited per completed specimen; an account never goes negative.
    """
    if seal_experiment(spec).manifest_id != manifest.manifest_id:
        raise CyranoError(
            "INPUT_INVALID", "spec does not reproduce the manifest"
        )
    experiment = authorize_experiment(spec, permit=permit, now=now)
    account = BudgetAccount(experiment.budget_units, 0)
    ledger = TrialLedger(manifest)
    for trial in trials:
        if trial.status == "completed" and trial.cost_units:
            account = begin_spend(account, trial.cost_units)
        ledger.record(trial)
    return {
        "permit_id": experiment.permit_id,
        "manifest_id": manifest.manifest_id,
        "ledger": ledger,
        "settle": ledger.settle(),
        "spent_units": account.spent,
        "remaining_units": account.total - account.spent,
    }


def cost_report(
    ledger: TrialLedger,
    *,
    learning_overhead_units: int = 0,
) -> Mapping[str, object]:
    """Report total cost including learning overhead (R5-RF11-04).

    A net-savings claim is allowed only when the candidate's total —
    run spend plus improvement overhead — is strictly below the
    baseline's spend, and only when every specimen's cost was
    actually observed; an unobserved cost is unknown, never zero.
    """
    baseline = sum(
        t.cost_units or 0 for t in ledger.trials if t.arm == "baseline"
    )
    candidate = sum(
        t.cost_units or 0 for t in ledger.trials if t.arm == "candidate"
    )
    missing = sum(1 for t in ledger.trials if t.cost_units is None)
    candidate_total = candidate + learning_overhead_units
    return {
        "baseline_units": baseline,
        "candidate_units": candidate,
        "learning_overhead_units": learning_overhead_units,
        "missing_costs": missing,
        "total_known": missing == 0,
        "total_units": baseline + candidate_total,
        "net_savings_claim_allowed": (
            missing == 0 and candidate_total < baseline
        ),
    }


def review_effectiveness(
    manifest: EvaluationManifest,
    ledger: TrialLedger,
    items: Mapping[str, object],
    *,
    safety_failures: int = 0,
    regressions: int = 0,
    learning_overhead_units: int = 0,
) -> Mapping[str, object]:
    """Produce a scoped effectiveness verdict bound to the manifest.

    Missing observation on any rubric item caps the verdict at
    inconclusive; a regression or safety failure is a hard rejection
    that no score offsets; an incomplete denominator preserves the
    baseline.
    """
    verdicts = item_verdicts(items)
    all_evaluated = all(v == "evaluated" for v in verdicts.values())
    analysis = analyze_families(
        manifest, ledger.trials, safety_failures=safety_failures
    )
    settle = ledger.settle()
    actual = settle["actual_pairs"]
    planned = settle["planned_pairs"]
    if regressions > 0:
        effect = EffectVerdict(
            "rejected", False, "HARD_GATE_FAILURE: regression"
        )
    else:
        effect = judge_candidate(
            verdict=analysis.verdict,
            safety_failures=safety_failures,
            actual_pairs=actual if isinstance(actual, int) else 0,
            planned_pairs=planned if isinstance(planned, int) else 0,
        )
    if not all_evaluated and effect.verdict == "improved":
        effect = EffectVerdict(
            "inconclusive", False, "items lack raw evidence"
        )
    return {
        "manifest_id": manifest.manifest_id,
        "scope": "manifest_bound_no_generalization",
        "verdict": effect.verdict,
        "eligible_for_review": effect.eligible_for_review,
        "reason": effect.reason,
        "items": verdicts,
        "official_score": None,
        "analysis": {
            "verdict": analysis.verdict,
            "completed_pairs": analysis.completed_pairs,
            "planned_pairs": analysis.planned_pairs,
            "families": [
                {
                    "family": f.family,
                    "pairs": f.pairs,
                    "delta": f.delta,
                    "interval": [f.lower, f.upper],
                }
                for f in analysis.families
            ],
        },
        "cost": cost_report(
            ledger, learning_overhead_units=learning_overhead_units
        ),
        "baseline_retained": effect.verdict != "improved",
    }


def request_launch_approval(
    review: Mapping[str, object],
    *,
    approvals: Mapping[str, object],
) -> Mapping[str, object]:
    """Route a scoped verdict to launch approval (WP23-I03).

    Activation, learning, canary and trace each require their own
    approval. An ineligible verdict is refused outright — review
    eligibility is never itself an approval.
    """
    if not review.get("eligible_for_review"):
        raise CyranoError(
            "RELEASE_APPROVAL_REQUIRED",
            "only an improved scoped verdict may request approval",
        )
    granted = {
        aspect: bool(approvals.get(aspect)) for aspect in LAUNCH_ASPECTS
    }
    missing = sorted(a for a, ok in granted.items() if not ok)
    return {
        "decision": "approved" if not missing else "refused",
        "aspects": granted,
        "missing": missing,
        "manifest_id": review.get("manifest_id"),
    }


def observe_rollout(
    decision: Mapping[str, object],
    *,
    healthy: bool,
    release_id: str,
) -> Mapping[str, object]:
    """Retain an approved healthy rollout; otherwise roll back.

    A refused decision or an unhealthy observation yields an explicit
    rollback — the release pointer is never left ambiguous.
    """
    if decision.get("decision") == "approved" and healthy:
        return {"action": "retain", "release_id": release_id}
    return {
        "action": "rollback",
        "release_id": release_id,
        "reason": (
            "approval_refused"
            if decision.get("decision") != "approved"
            else "unhealthy_observation"
        ),
    }


def coverage_verdict(
    tested: Iterable[str], required: Iterable[str]
) -> Mapping[str, object]:
    """Expose untested execution modes; block the release grade.

    Testing only the TUI while ACP/headless are unverified is a
    coverage gap — it is reported, never hidden, and blocks the
    corresponding operational release grade (R4-RC43-04).
    """
    missing = sorted(set(map(str, required)) - set(map(str, tested)))
    return {
        "complete": not missing,
        "missing_modes": missing,
        "release_grade_blocked": bool(missing),
    }


def capability_report(
    base_intact: bool, optional: Mapping[str, bool]
) -> Mapping[str, object]:
    """Disclose unavailable optional analyzers (R5-RF11-03).

    A missing optional analyzer leaves the base coding capability
    intact, but the limitation must be disclosed — it is never
    reported as covered.
    """
    unavailable = sorted(k for k, v in optional.items() if not v)
    return {
        "base_intact": bool(base_intact),
        "optional_unavailable": unavailable,
        "limits_disclosed": unavailable,
    }
