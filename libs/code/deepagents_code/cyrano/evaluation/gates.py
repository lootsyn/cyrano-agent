"""Evidence interpretation for paired evaluation.

Not an approval issuer.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite

from deepagents_code.cyrano.contracts.types import CyranoError


@dataclass(frozen=True, slots=True)
class Evaluation:
    """Intervals from an independently owned analysis plan."""

    path: str
    actual_pairs: int
    planned_pairs: int
    safety_failures: int
    quality_delta_lower: float | None
    cost_delta_upper: float | None
    quality_margin: float
    minimum_saving: float
    evidence_valid: bool


def decision(result: Evaluation) -> str:
    """Require actual paired evidence; hard failures dominate."""
    if result.path not in {"A", "B"}:
        raise CyranoError("INVALID_PATH", result.path)
    if any(
        type(value) is not int or value < 0
        for value in (
            result.actual_pairs,
            result.planned_pairs,
            result.safety_failures,
        )
    ):
        raise CyranoError(
            "INVALID_COUNT", "nonnegative integer counts are required"
        )
    if not result.evidence_valid:
        return "invalid"
    if result.safety_failures > 0:
        return "rejected"
    if (
        result.planned_pairs <= 0
        or result.actual_pairs != result.planned_pairs
        or result.quality_delta_lower is None
        or result.cost_delta_upper is None
    ):
        return "inconclusive"
    values = [
        result.quality_delta_lower,
        result.cost_delta_upper,
        result.quality_margin,
        result.minimum_saving,
    ]
    if not all(isfinite(value) for value in values):
        raise CyranoError("INVALID_METRIC", "finite numbers are required")
    if result.quality_margin < 0 or result.minimum_saving < 0:
        raise CyranoError("INVALID_MARGIN", "margins cannot be negative")
    if result.quality_delta_lower < -result.quality_margin:
        return "inconclusive"
    if result.cost_delta_upper > -result.minimum_saving:
        return "inconclusive"
    return "eligible_for_review"


def validate_splits(families_by_split: dict[str, set[str]]) -> None:
    """Reject a family shared across split boundaries."""
    seen: set[str] = set()
    for families in families_by_split.values():
        if seen & families:
            raise CyranoError(
                "DATA_LEAKAGE",
                "a family crosses split boundaries",
            )
        seen.update(families)


@dataclass(frozen=True, slots=True)
class EffectVerdict:
    """The effect decision; eligibility for review, never approval."""

    verdict: str  # improved|inconclusive|regressed|rejected|invalid
    eligible_for_review: bool
    reason: str


def judge_candidate(
    *,
    verdict: str,
    safety_failures: int,
    actual_pairs: int,
    planned_pairs: int,
) -> EffectVerdict:
    """Decide eligibility; a judge never approves, only routes.

    Any safety failure is a hard rejection that no quality or cost
    gain can offset. Zero actual pairs is never eligible — a replay
    score is not an actual pair. Incomplete denominators stay
    inconclusive.
    """
    if safety_failures > 0:
        return EffectVerdict(
            "rejected", False, "HARD_GATE_FAILURE: safety regression"
        )
    if actual_pairs == 0:
        return EffectVerdict("invalid", False, "no actual paired evidence")
    if actual_pairs < planned_pairs:
        return EffectVerdict(
            "inconclusive",
            False,
            "incomplete denominator",
        )
    if verdict == "improved":
        return EffectVerdict("improved", True, "eligible_for_review")
    if verdict == "regressed":
        return EffectVerdict("regressed", False, "regression")
    return EffectVerdict("inconclusive", False, "uncertain effect")


@dataclass(frozen=True, slots=True)
class BundleAdmission:
    """An evidence bundle's admission verdict."""

    admitted: bool
    status: str
    reason: str


def admit_bundle(
    bundle: Mapping[str, object],
    *,
    expected_source_digest: str,
    expected_suite: frozenset[str],
    trusted_producers: frozenset[str],
    expected_body_digest: str | None = None,
) -> BundleAdmission:
    """Admit or refuse an evidence bundle before any review.

    Stale source digests, shrunken suites, zero collected tests,
    forged producers, missing raw artifacts, fixture-only claims, and
    tampered bodies are all refused with explicit codes.
    """
    if bundle.get("source_digest") != expected_source_digest:
        return BundleAdmission(
            False, "stale", "STALE_EVIDENCE: source digest mismatch"
        )
    suite_raw = bundle.get("suite", ())
    suite = (
        {str(s) for s in suite_raw}
        if isinstance(suite_raw, (list, tuple, set, frozenset))
        else set()
    )
    if expected_suite - suite:
        return BundleAdmission(
            False, "blocked", "SUITE_REDUCED: mandatory cases excluded"
        )
    collected = bundle.get("tests_collected", 0)
    if not isinstance(collected, int) or collected <= 0:
        return BundleAdmission(
            False, "not_run", "blocked: zero collected tests"
        )
    producer = str(bundle.get("producer", ""))
    if producer not in trusted_producers:
        return BundleAdmission(
            False, "denied", f"ACL_DENIED: producer {producer!r}"
        )
    if (
        expected_body_digest is not None
        and bundle.get("body_digest") != expected_body_digest
    ):
        return BundleAdmission(
            False, "invalid", "INPUT_INVALID: body digest mismatch"
        )
    raw = bundle.get("raw_artifacts", ())
    if isinstance(raw, (list, tuple)) and not raw:
        return BundleAdmission(
            False, "unverifiable", "summary without raw output"
        )
    if bundle.get("evidence_kind") in {"fixture", "self_report"}:
        return BundleAdmission(
            False, "not_evaluated", "fixture evidence is not execution"
        )
    return BundleAdmission(True, "admitted", "evidence in scope")


@dataclass(frozen=True, slots=True)
class Release:
    """An immutable promoted release; history never rewrites it."""

    release_id: str
    parent_id: str
    manifest_id: str
    evidence_refs: tuple[str, ...]


class ReleaseLane:
    """CAS promotion lane; only one child of a parent may promote."""

    def __init__(self, current: Release) -> None:
        """Bind the lane to the live release; history keeps it."""
        self._current: Release = current
        self._history: list[Release] = [current]

    @property
    def current(self) -> Release:
        """The live release."""
        return self._current

    def promote(self, candidate: Release) -> Release:
        """Promote a candidate whose parent is the live release.

        A second candidate from the same parent is refused — it must
        rebase onto the new release and re-evaluate.
        """
        if candidate.parent_id != self._current.release_id:
            raise CyranoError(
                "REBASE_REQUIRED",
                f"parent {candidate.parent_id} is not live",
            )
        self._history.append(candidate)
        self._current = candidate
        return candidate

    def rollback(self, target_id: str) -> Release:
        """Re-point the lane to a prior immutable release.

        The rolled-forward release stays in history as evidence; only
        the live pointer moves.
        """
        for release in self._history:
            if release.release_id == target_id:
                self._current = release
                return release
        raise CyranoError("MISSING_RELEASE", target_id)


def verify_next_run(
    lane: ReleaseLane, run: Mapping[str, object]
) -> Mapping[str, object]:
    """Check that a run actually used the release it should have.

    Runs started before a promotion stay pinned to the old release;
    runs started after must bind the live one. A mismatch fails and
    reports the affected runs plus the rollback pointer.
    """
    started_after = bool(run.get("started_after_promotion", False))
    used = str(run.get("release_id", ""))
    pinned = run.get("pinned_release_id")
    expected = (
        lane.current.release_id
        if started_after
        else str(pinned)
        if pinned is not None
        else "__unpinned__"
    )
    ok = used == expected
    return {
        "run_id": str(run.get("run_id", "")),
        "ok": ok,
        "expected_release": expected,
        "used_release": used,
        "rollback_target": (lane.current.parent_id if not ok else None),
    }
