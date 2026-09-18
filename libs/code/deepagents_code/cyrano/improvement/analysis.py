"""Pattern analysis over recorded episodes.

Analysis produces hypotheses, never verdicts: every cluster keeps its
alternatives, counterexamples, and the evidence still required. An
expected-red run is never a failure to fix, an unknown cause is never
an improvement target, and a hypothesis touching protected paths is
marked manual-only rather than auto-generated. Learning of learning
(meta depth ≥ 1) is refused outright — recursion is not billed.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError

MAX_META_DEPTH = 0

CAUSE_CLASSES = frozenset(
    {
        "agent_failure",
        "expected_red",
        "environment",
        "requirement_change",
        "workflow_failure",
        "regression",
        "unknown",
    }
)

_ENV_ERRORS = frozenset({"timeout", "provider", "network", "resource"})
_WORKFLOW_KINDS = frozenset({"approval", "permit", "scope", "dispatch"})

#: Lesson fragments that would skip a mandatory gate; never promoted.
_BLOCKED_LESSON_MARKERS = (
    "skip_approval",
    "skip_review",
    "skip_verification",
    "skip_test",
    "auto_apply",
    "bypass_gate",
)


@dataclass(frozen=True, slots=True)
class EpisodeRecord:
    """One run's analysis-relevant fields; nothing is inferred twice."""

    episode_id: str
    outcome: str
    error_class: str = ""
    kind: str = ""
    expected_red: bool = False
    protected_touch: bool = False
    lesson: str | None = None


@dataclass(frozen=True, slots=True)
class Hypothesis:
    """A clustered failure hypothesis.

    ``confidence`` never exceeds the hypothesis level.
    """

    cluster_id: str
    cause_class: str
    summary: str
    confidence: str
    alternatives: tuple[str, ...]
    counterexamples: tuple[str, ...]
    needs_evidence: tuple[str, ...]
    protected: bool
    status: str


@dataclass(frozen=True, slots=True)
class AnalysisReport:
    """The bound analysis artifact: hypotheses + eval plan + cost."""

    report_id: str
    hypotheses: tuple[Hypothesis, ...]
    blocked_lessons: tuple[str, ...]
    eval_plan_digest: str
    cost_digest: str
    active_changed: bool


def _classify(record: EpisodeRecord) -> str:
    if record.expected_red:
        return "expected_red"
    if record.error_class in _ENV_ERRORS:
        return "environment"
    if record.error_class == "requirement_change":
        return "requirement_change"
    if record.kind in _WORKFLOW_KINDS:
        return "workflow_failure"
    if record.outcome == "failed" and record.kind == "test":
        return "regression"
    if record.outcome == "failed" and record.kind == "agent":
        return "agent_failure"
    return "unknown"


def analyze_patterns(
    records: Iterable[EpisodeRecord],
    *,
    meta_depth: int = 0,
    learning_enabled: bool = False,
) -> AnalysisReport:
    """Cluster records into hypotheses; no cause is asserted as fact.

    Requires explicit learning enablement — a default-off gate, not a
    flag that starts work silently. ``meta_depth`` above zero refuses
    learning-of-learning; the recursion is never billed.
    """
    if not learning_enabled:
        raise CyranoError("LEARNING_DISABLED", "explicit enable required")
    if meta_depth > MAX_META_DEPTH:
        raise CyranoError(
            "META_DEPTH_EXCEEDED", "learning recursion is not permitted"
        )
    clusters: dict[str, list[EpisodeRecord]] = {}
    blocked: list[str] = []
    for record in records:
        if record.lesson is not None and any(
            marker in record.lesson for marker in _BLOCKED_LESSON_MARKERS
        ):
            blocked.append(record.episode_id)
            continue
        key = record.error_class or record.kind or "none"
        clusters.setdefault(key, []).append(record)
    hypotheses: list[Hypothesis] = []
    for key, members in sorted(clusters.items()):
        failures = [m for m in members if m.outcome == "failed"]
        successes = [m for m in members if m.outcome != "failed"]
        cause = _classify(members[0])
        if cause == "unknown":
            status = "not_an_improvement_target"
        elif any(m.protected_touch for m in members):
            status = "manual_only"
        else:
            status = "pending_evidence"
        hypotheses.append(
            Hypothesis(
                cluster_id=f"cluster:{key}",
                cause_class=cause,
                summary=f"{len(failures)} failure(s) in {key}",
                confidence="hypothesis",
                alternatives=(
                    ("environment", "workflow_failure")
                    if cause not in ("environment", "workflow_failure")
                    else ("agent_failure",)
                ),
                counterexamples=tuple(m.episode_id for m in successes),
                needs_evidence=("independent_reproduction", "owner_review"),
                protected=any(m.protected_touch for m in members),
                status=status,
            )
        )
    return AnalysisReport(
        report_id=digest([h.cluster_id for h in hypotheses] + blocked),
        hypotheses=tuple(hypotheses),
        blocked_lessons=tuple(blocked),
        eval_plan_digest=digest(
            [[h.cluster_id, h.cause_class] for h in hypotheses]
        ),
        cost_digest=digest(
            [len(clusters), sum(len(v) for v in clusters.values())]
        ),
        active_changed=False,
    )
