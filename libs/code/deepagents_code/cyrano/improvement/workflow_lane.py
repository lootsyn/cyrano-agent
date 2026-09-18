"""Path B workflow lane: episode analysis into typed candidates.

A failed episode yields a typed improvement candidate — task
directive, skill body, or task-scoped memory — carrying cause,
alternative, exact diff, expected effect, counterexamples, and
rollback. A single failure never generalizes to a global rule, and
an episode's expected outcomes (TDD red, user cancel, a legitimate
denial) are classified as expected, never mined as defects. Learning
events that would enqueue more learning are filtered by origin —
there is no unbounded recursion, and an exhausted budget terminates
the loop.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.improvement.classification import PROTECTED

SEQ = (list, tuple, set, frozenset)


def _as_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value)


def _as_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


#: Outcomes that are expected behavior, never defect lessons.
_EXPECTED_OUTCOMES = frozenset(
    {"tdd_red", "user_cancelled", "denied_correctly"}
)


@dataclass(frozen=True, slots=True)
class WorkflowCandidate:
    """A typed improvement proposal; proposing changes nothing."""

    candidate_id: str
    candidate_kind: str  # task_directive | skill_body | memory
    scope_id: str
    cause: str
    alternatives: tuple[str, ...]
    diff: str
    expected_effect: str
    counterexamples: tuple[str, ...]
    rollback: str
    freshness_epoch: int


def classify_episode_outcome(
    event: Mapping[str, object],
) -> str:
    """Classify an episode outcome as expected, transient, or defect.

    TDD red, a user cancellation, and a correct denial are expected;
    a transient network error is a transient failure; anything else
    failed is a defect worth analysis.
    """
    outcome = str(event.get("outcome", ""))
    if outcome in _EXPECTED_OUTCOMES:
        return "expected"
    if outcome in {"transient_error", "network_timeout"}:
        return "transient"
    if outcome == "failed":
        return "defect"
    return "observation"


def analyze_failure_episode(
    episode: Mapping[str, object],
    *,
    scope_id: str,
    freshness_epoch: int,
) -> WorkflowCandidate:
    """Mine a failed episode into one typed, rollback-bound candidate.

    The episode must name a missing or failed step as the cause;
    candidates touching protected evaluation/approval paths are
    refused rather than produced.
    """
    cause = str(episode.get("cause", ""))
    if not cause:
        raise CyranoError(
            "EVIDENCE_REQUIRED", "an episode needs a named cause"
        )
    kind = str(episode.get("candidate_kind", "task_directive"))
    if kind not in {"task_directive", "skill_body", "memory"}:
        raise CyranoError("INPUT_INVALID", f"kind {kind!r}")
    paths = episode.get("paths", ())
    touched = tuple(str(p) for p in paths) if isinstance(paths, SEQ) else ()
    if any(p.startswith(PROTECTED) for p in touched):
        raise CyranoError(
            "PROTECTED_FIELD", "candidate would change protected paths"
        )
    diff = str(episode.get("diff", ""))
    rollback = str(episode.get("rollback", ""))
    effect = str(episode.get("expected_effect", ""))
    if not diff or not rollback or not effect:
        raise CyranoError(
            "INPUT_INVALID",
            "diff, expected effect, and rollback are required",
        )
    alts_raw = episode.get("alternatives", ())
    alternatives = (
        tuple(str(a) for a in alts_raw) if isinstance(alts_raw, SEQ) else ()
    )
    counters = episode.get("counterexamples", ())
    counterexamples = (
        tuple(str(c) for c in counters) if isinstance(counters, SEQ) else ()
    )
    if not counterexamples:
        raise CyranoError("EVIDENCE_REQUIRED", "counterexamples required")
    return WorkflowCandidate(
        candidate_id=digest([kind, scope_id, cause, diff]),
        candidate_kind=kind,
        scope_id=scope_id,
        cause=cause,
        alternatives=alternatives,
        diff=diff,
        expected_effect=effect,
        counterexamples=counterexamples,
        rollback=rollback,
        freshness_epoch=freshness_epoch,
    )


def evaluate_actual_workflow(
    baseline: Mapping[str, object],
    candidate: Mapping[str, object],
) -> Mapping[str, object]:
    """Compare workflow runs; efficiency never offsets coverage.

    Fewer tasks and lower requirement coverage is a regression in
    obligation, not an efficiency improvement — the verdict refuses
    promotion.
    """
    base_tasks = _as_int(baseline.get("tasks_completed", 0))
    cand_tasks = _as_int(candidate.get("tasks_completed", 0))
    base_cov = _as_float(baseline.get("requirement_coverage", 0.0))
    cand_cov = _as_float(candidate.get("requirement_coverage", 0.0))
    coverage_regressed = cand_cov < base_cov
    if coverage_regressed or cand_tasks < base_tasks:
        return {
            "verdict": "regressed",
            "promotable": False,
            "reason": (
                "coverage or task completion regressed; "
                "efficiency cannot offset obligations"
            ),
        }
    if cand_cov == base_cov and cand_tasks == base_tasks:
        return {
            "verdict": "inconclusive",
            "promotable": False,
            "reason": "no measurable improvement",
        }
    return {
        "verdict": "improved",
        "promotable": True,
        "reason": "obligations met or exceeded",
    }


def enqueue_learning_followups(
    events: Iterable[Mapping[str, object]],
    *,
    budget: int,
    max_followups: int = 8,
) -> Mapping[str, object]:
    """Filter learning events into bounded follow-up jobs.

    Events already originating in learning never enqueue more
    learning — the origin filter breaks the recursion. The budget and
    the follow-up cap bound the loop; exhaustion terminates cleanly.
    """
    if budget <= 0:
        return {
            "enqueued": (),
            "terminated": True,
            "reason": "budget exhausted",
        }
    queued: list[str] = []
    filtered = 0
    for event in events:
        if len(queued) >= max_followups or len(queued) >= budget:
            break
        if str(event.get("origin_kind", "")) == "learning":
            filtered += 1
            continue
        if str(event.get("outcome", "")) == "failed":
            queued.append(str(event.get("event_id", "")))
    return {
        "enqueued": tuple(queued),
        "filtered_learning_origins": filtered,
        "terminated": False,
    }
