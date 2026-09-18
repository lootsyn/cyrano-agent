"""Sealed paired evaluation: manifest, trial ledger, memory arms.

An experiment is sealed before any run: baseline/candidate digests,
the suite, task families, the train/holdout split, the budget, and the
pre-registered statistical criteria are all fixed in the manifest.
A family appearing in both train and holdout leaks — the manifest is
refused before any cost is billed. Trial records preserve every
specimen including failures and aborts; a dropped pair shrinks the
denominator and is a contract violation, not a cleanup.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.improvement.classification import PROTECTED

_ARM_NAMES = ("baseline", "candidate")
_SEQ = (list, tuple, set, frozenset)


@dataclass(frozen=True, slots=True)
class EvaluationManifest:
    """A sealed experiment; every comparison input is pinned."""

    manifest_id: str
    baseline_digest: str
    candidate_digest: str
    suite_digest: str
    runtime_digest: str
    plan_digest: str
    families: tuple[str, ...]
    holdout: tuple[str, ...]
    budget_units: int
    quality_margin: float
    min_pairs: int
    nondeterministic_provider: bool
    changes: tuple[str, ...]
    policy_digest: str = ""
    model_digest: str = ""
    route_digest: str = ""


def check_leakage(
    train: Iterable[str], holdout: Iterable[str]
) -> tuple[str, ...]:
    """Return the families present in both sides of a split."""
    return tuple(sorted(set(map(str, train)) & set(map(str, holdout))))


def seal_experiment(spec: Mapping[str, object]) -> EvaluationManifest:
    """Seal an experiment; every missing prerequisite refuses.

    A train/holdout family overlap is DATA_LEAKAGE and invalidates the
    evaluation before any run or billing. Unregistered statistical
    criteria or budget are MISSING_PREREGISTRATION — the analysis
    method may not be chosen after results exist.
    """
    required = (
        "baseline_digest",
        "candidate_digest",
        "suite_digest",
        "runtime_digest",
        "plan_digest",
    )
    missing = [k for k in required if not spec.get(k)]
    if missing:
        raise CyranoError("MISSING_PREREGISTRATION", f"missing {missing[0]}")
    budget = spec.get("budget_units")
    margin = spec.get("quality_margin")
    min_pairs = spec.get("min_pairs")
    if (
        not isinstance(budget, int)
        or budget <= 0
        or not isinstance(margin, (int, float))
        or not isinstance(min_pairs, int)
        or min_pairs <= 0
    ):
        raise CyranoError(
            "MISSING_PREREGISTRATION",
            "budget, margin and min_pairs must be registered",
        )
    fam_raw = spec.get("families", ())
    hold_raw = spec.get("holdout", ())
    families = (
        tuple(str(f) for f in fam_raw) if isinstance(fam_raw, _SEQ) else ()
    )
    holdout = (
        tuple(str(f) for f in hold_raw) if isinstance(hold_raw, _SEQ) else ()
    )
    leak = check_leakage(families, holdout)
    if leak:
        raise CyranoError(
            "DATA_LEAKAGE", f"family in train and holdout: {leak[0]}"
        )
    after_cutoff = spec.get("memory_refs_after_cutoff", ())
    if isinstance(after_cutoff, _SEQ) and after_cutoff:
        raise CyranoError(
            "DATA_LEAKAGE",
            "post-cutoff evaluation evidence entered memory",
        )
    changes_raw = spec.get("changes", ())
    changes = (
        tuple(str(c) for c in changes_raw)
        if isinstance(changes_raw, _SEQ)
        else ()
    )
    protected = [c for c in changes if any(c.startswith(p) for p in PROTECTED)]
    if protected:
        raise CyranoError(
            "PROTECTED_FIELD",
            f"protected change needs manual route: {protected[0]}",
        )
    policy_digest = str(spec.get("policy_digest", ""))
    model_digest = str(spec.get("model_digest", ""))
    route_digest = str(spec.get("route_digest", ""))
    manifest_id = digest(
        {
            "base": str(spec["baseline_digest"]),
            "cand": str(spec["candidate_digest"]),
            "suite": str(spec["suite_digest"]),
            "runtime": str(spec["runtime_digest"]),
            "plan": str(spec["plan_digest"]),
            "policy": policy_digest,
            "model": model_digest,
            "route": route_digest,
            "budget": budget,
            "families": sorted(families),
            "holdout": sorted(holdout),
        }
    )
    return EvaluationManifest(
        manifest_id=manifest_id,
        baseline_digest=str(spec["baseline_digest"]),
        candidate_digest=str(spec["candidate_digest"]),
        suite_digest=str(spec["suite_digest"]),
        runtime_digest=str(spec["runtime_digest"]),
        plan_digest=str(spec["plan_digest"]),
        families=families,
        holdout=holdout,
        budget_units=budget,
        quality_margin=float(margin),
        min_pairs=min_pairs,
        nondeterministic_provider=bool(
            spec.get("nondeterministic_provider", False)
        ),
        changes=changes,
        policy_digest=policy_digest,
        model_digest=model_digest,
        route_digest=route_digest,
    )


@dataclass(frozen=True, slots=True)
class TrialResult:
    """One arm of a pair; failures and aborts are kept."""

    pair_id: str
    family: str
    arm: str
    status: str  # completed | failed | cancelled | aborted
    outcome: str  # pass | fail | unknown
    cost_units: int | None
    order_index: int


@dataclass(frozen=True, slots=True)
class PairSummary:
    """Per-pair outcome; a one-sided pair is incomplete."""

    pair_id: str
    family: str
    complete: bool
    baseline_outcome: str
    candidate_outcome: str


class TrialLedger:
    """Append-only paired-trial record bound to a manifest."""

    def __init__(self, manifest: EvaluationManifest) -> None:
        """Bind the ledger to a sealed manifest."""
        self._manifest: EvaluationManifest = manifest
        self._trials: list[TrialResult] = []

    @property
    def manifest(self) -> EvaluationManifest:
        """The sealed manifest this ledger serves."""
        return self._manifest

    @property
    def trials(self) -> tuple[TrialResult, ...]:
        """All recorded specimens, including failures and aborts."""
        return tuple(self._trials)

    def record(self, trial: TrialResult) -> TrialResult:
        """Append one trial; duplicates and unknowns are refused."""
        if trial.arm not in _ARM_NAMES:
            raise CyranoError("INPUT_INVALID", f"arm {trial.arm!r}")
        if (
            self._manifest.families
            and trial.family not in self._manifest.families
        ):
            raise CyranoError(
                "INPUT_INVALID", f"family {trial.family!r} not in manifest"
            )
        if trial.outcome not in {"pass", "fail", "unknown"}:
            raise CyranoError("INPUT_INVALID", trial.outcome)
        for prior in self._trials:
            if prior.pair_id == trial.pair_id and prior.arm == trial.arm:
                raise CyranoError(
                    "INPUT_INVALID",
                    f"duplicate specimen {trial.pair_id}/{trial.arm}",
                )
        self._trials.append(trial)
        return trial

    def pairs(self) -> tuple[PairSummary, ...]:
        """Fold trials into pairs; one-sided pairs stay incomplete."""
        by_pair: dict[str, dict[str, TrialResult]] = {}
        for trial in self._trials:
            by_pair.setdefault(trial.pair_id, {})[trial.arm] = trial
        out: list[PairSummary] = []
        for pair_id in sorted(by_pair):
            arms = by_pair[pair_id]
            base = arms.get("baseline")
            cand = arms.get("candidate")
            complete = (
                base is not None
                and cand is not None
                and base.status == "completed"
                and cand.status == "completed"
            )
            if base is not None:
                family = base.family
            elif cand is not None:
                family = cand.family
            else:
                family = ""
            out.append(
                PairSummary(
                    pair_id=pair_id,
                    family=family,
                    complete=complete,
                    baseline_outcome=base.outcome if base else "unknown",
                    candidate_outcome=cand.outcome if cand else "unknown",
                )
            )
        return tuple(out)

    def settle(self) -> Mapping[str, object]:
        """Summarize; dropped pairs never shrink the count."""
        pairs = self.pairs()
        completed = [p for p in pairs if p.complete]
        incomplete = [p for p in pairs if not p.complete]
        planned = self._manifest.min_pairs
        return {
            "manifest_id": self._manifest.manifest_id,
            "planned_pairs": planned,
            "actual_pairs": len(completed),
            "incomplete_pairs": len(incomplete),
            "denominator_intact": len(pairs) >= planned and not incomplete,
            "nondeterministic_provider": (
                self._manifest.nondeterministic_provider
            ),
        }


def build_memory_arms(
    candidate: Mapping[str, object],
    dataset: Iterable[str],
) -> Mapping[str, object]:
    """Build independent memory arms with the policy fixed.

    A0 is no memory, A1 retrieval-only, A2 retrieval+application, A3 the
    full candidate. When a bundle changes policy and memory together the
    bundle is marked non-attributable — a single cause may not be
    claimed without an ablation.
    """
    changes = candidate.get("changes", ())
    changed = {str(c) for c in changes} if isinstance(changes, _SEQ) else set()
    bundled = "policy" in changed and "memory" in changed
    arms = {
        "A0": {"memory": "none", "policy": "fixed"},
        "A1": {"memory": "retrieval", "policy": "fixed"},
        "A2": {"memory": "retrieval+application", "policy": "fixed"},
        "A3": {"memory": "full_candidate", "policy": "fixed"},
    }
    return {
        "arms": arms,
        "dataset": tuple(str(d) for d in dataset),
        "attributable": not bundled,
        "note": (
            "bundle requires ablation; no single cause"
            if bundled
            else "independent arms"
        ),
    }
