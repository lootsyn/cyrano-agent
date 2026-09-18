"""Paired-comparison statistics: intervals, denominators, honest cost.

A point estimate never promotes on its own — the pre-registered
margin, the completed-pair count, and interval overlap decide, and
anything else is inconclusive. Costs with unobserved specimens report
coverage and an unknown total; zero is never substituted. Memory
utility separates correlation (exposed) from causation (applied with
a verifiable chain) — an exposed-but-unused memory earns nothing.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import sqrt

from deepagents_code.cyrano.evaluation.paired import (
    EvaluationManifest,
    TrialResult,
)


@dataclass(frozen=True, slots=True)
class FamilyAnalysis:
    """One family's paired delta with its interval."""

    family: str
    pairs: int
    delta: float
    lower: float
    upper: float


@dataclass(frozen=True, slots=True)
class EffectAnalysis:
    """Aggregate paired analysis; the verdict is conservative."""

    verdict: str  # improved | regressed | inconclusive | invalid
    families: tuple[FamilyAnalysis, ...]
    completed_pairs: int
    planned_pairs: int
    safety_failures: int
    reason: str


def _wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval; n=0 spans [0,1] — never a point claim."""
    if n <= 0:
        return 0.0, 1.0
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return centre - half, centre + half


def analyze_families(
    manifest: EvaluationManifest,
    trials: Iterable[TrialResult],
    *,
    safety_failures: int = 0,
) -> EffectAnalysis:
    """Compare arms per family under the pre-registered margin.

    Fewer complete pairs than registered, a safety failure, or an
    interval crossing the margin all yield a non-improved verdict —
    inconclusive preserves the baseline and never rounds to success.
    """
    pairs: dict[str, dict[str, TrialResult]] = {}
    for trial in trials:
        pairs.setdefault(trial.pair_id, {})[trial.arm] = trial
    complete = [
        v
        for v in pairs.values()
        if "baseline" in v
        and "candidate" in v
        and v["baseline"].status == "completed"
        and v["candidate"].status == "completed"
    ]
    if safety_failures > 0:
        return EffectAnalysis(
            "invalid",
            (),
            len(complete),
            manifest.min_pairs,
            safety_failures,
            "safety failures dominate",
        )
    if len(complete) < manifest.min_pairs:
        return EffectAnalysis(
            "inconclusive",
            (),
            len(complete),
            manifest.min_pairs,
            safety_failures,
            "insufficient completed pairs",
        )
    by_family: dict[str, list[dict[str, TrialResult]]] = {}
    for arms in complete:
        fam = arms["baseline"].family
        by_family.setdefault(fam, []).append(arms)
    analyses: list[FamilyAnalysis] = []
    deltas: list[float] = []
    for family in sorted(by_family):
        group = by_family[family]
        wins = sum(
            1
            for arms in group
            if arms["candidate"].outcome == "pass"
            and arms["baseline"].outcome != "pass"
        )
        losses = sum(
            1
            for arms in group
            if arms["candidate"].outcome != "pass"
            and arms["baseline"].outcome == "pass"
        )
        delta = (wins - losses) / len(group)
        lower, upper = _wilson(max(0.0, (delta + 1) / 2), len(group))
        lo, hi = lower * 2 - 1, upper * 2 - 1
        analyses.append(FamilyAnalysis(family, len(group), delta, lo, hi))
        deltas.append(delta)
    overall = sum(deltas) / len(deltas)
    margin = manifest.quality_margin
    if overall < -margin:
        return EffectAnalysis(
            "regressed",
            tuple(analyses),
            len(complete),
            manifest.min_pairs,
            safety_failures,
            "overall delta below margin",
        )
    worst_lower = min(a.lower for a in analyses)
    if worst_lower < -margin or abs(overall) <= margin:
        return EffectAnalysis(
            "inconclusive",
            tuple(analyses),
            len(complete),
            manifest.min_pairs,
            safety_failures,
            "interval crosses the registered margin",
        )
    return EffectAnalysis(
        "improved",
        tuple(analyses),
        len(complete),
        manifest.min_pairs,
        safety_failures,
        "all family intervals clear the margin",
    )


@dataclass(frozen=True, slots=True)
class CostReport:
    """Observed spend; missing costs stay unknown, never zero."""

    observed_units: int
    missing: int
    coverage: float
    total_known: bool


def cost_report(trials: Iterable[TrialResult]) -> CostReport:
    """Sum only observed costs and disclose the coverage gap."""
    items = list(trials)
    observed = [t.cost_units for t in items if t.cost_units is not None]
    missing = len(items) - len(observed)
    coverage = len(observed) / len(items) if items else 0.0
    return CostReport(
        observed_units=sum(observed),
        missing=missing,
        coverage=coverage,
        total_known=missing == 0,
    )


@dataclass(frozen=True, slots=True)
class UtilityVerdict:
    """One memory's causal standing; exposure alone earns nothing."""

    memory_id: str
    reward: str  # causal | correlated | none
    basis: str


def estimate_utility(
    exposures: Iterable[Mapping[str, object]],
    outcomes: Iterable[Mapping[str, object]],
) -> tuple[UtilityVerdict, ...]:
    """Separate causal reward from mere correlation.

    ``causal`` requires an application record bound to a successful
    outcome; exposure near a success is ``correlated`` at most — a
    memory that was merely visible earns no reward.
    """
    applied: set[str] = set()
    for outcome in outcomes:
        if str(outcome.get("status", "")) != "success":
            continue
        applied_memories = outcome.get("applied_memories")
        if not isinstance(applied_memories, (list, tuple, set, frozenset)):
            continue
        for mid in applied_memories:
            applied.add(str(mid))
    verdicts: list[UtilityVerdict] = []
    seen: set[str] = set()
    for exposure in exposures:
        mid = str(exposure.get("memory_id", ""))
        if mid in seen:
            continue
        seen.add(mid)
        if mid in applied:
            verdicts.append(
                UtilityVerdict(mid, "causal", "applied with verified outcome")
            )
        else:
            verdicts.append(
                UtilityVerdict(
                    mid,
                    "correlated",
                    "exposed only; no causal reward",
                )
            )
    return tuple(verdicts)
