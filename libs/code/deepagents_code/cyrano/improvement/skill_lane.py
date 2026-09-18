"""Path B skill lane: proposal, impact honesty, CAS promotion.

A repeated lesson with scope, counterexamples, and a parent release
is stored as a candidate — never active. Impact classification is
honest about what changed: a ``.py`` resource edit described as a
wording fix is a code change routed to high-risk review, and a
candidate touching protected evaluation or approval paths is
blocked. Promotion needs actual paired evidence bound to the exact
candidate body; a one-character edit after evaluation is stale
evidence. Competing promotions compare-and-swap on the live
release, revocation pauses running tasks and demands a new binding,
and a merge that drops a counterexample is invalid.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.improvement.classification import (
    PROTECTED,
    classify,
)

SEQ = (list, tuple, set, frozenset)


@dataclass(frozen=True, slots=True)
class SkillRelease:
    """One immutable skill release; revocation never erases it."""

    skill_id: str
    release_id: str
    parent_release_id: str | None
    content_digest: str
    status: str  # active | revoked


@dataclass(frozen=True, slots=True)
class SkillCandidate:
    """A proposal; stored as a candidate, never active by default."""

    candidate_id: str
    skill_id: str
    parent_release_id: str
    content_digest: str
    author: str
    counterexamples: tuple[str, ...]
    state: str  # candidate


def propose_skill_candidate(
    lesson: Mapping[str, object],
    *,
    skill_id: str,
    parent_release_id: str,
    author: str,
) -> SkillCandidate:
    """Store a repeated lesson as a candidate only.

    The proposal must carry evidence of repetition, its scope, its
    counterexamples, and the parent release it builds on — anything
    missing refuses the candidate rather than weakening the record.
    """
    repeats = lesson.get("repeats", 0)
    if not isinstance(repeats, int) or repeats < 2:
        raise CyranoError(
            "EVIDENCE_REQUIRED", "a skill needs a repeated lesson"
        )
    scope = lesson.get("scope_id")
    counter = lesson.get("counterexamples", ())
    counters = (
        tuple(str(c) for c in counter) if isinstance(counter, SEQ) else ()
    )
    if not scope or not counters:
        raise CyranoError(
            "EVIDENCE_REQUIRED", "scope and counterexamples required"
        )
    body = str(lesson.get("body", ""))
    if not body:
        raise CyranoError("EMPTY_CANDIDATE", "lesson body required")
    return SkillCandidate(
        candidate_id=digest([skill_id, body, str(scope)]),
        skill_id=skill_id,
        parent_release_id=parent_release_id,
        content_digest=digest(body),
        author=author,
        counterexamples=counters,
        state="candidate",
    )


def extract_lesson(event: Mapping[str, object]) -> Mapping[str, object]:
    """Classify an episode event before it becomes a lesson.

    An expected-red failure is classified ``expected_failure`` — it
    is evidence the gate worked, never a defect lesson.
    """
    if event.get("expected_red") or event.get("expected_failure"):
        return {
            "kind": "expected_failure",
            "lesson": None,
            "reason": "planned red path; not a defect",
        }
    if str(event.get("outcome", "")) == "failed":
        return {
            "kind": "failure_lesson",
            "lesson": str(event.get("summary", "")) or None,
            "reason": "unplanned failure",
        }
    return {"kind": "observation", "lesson": None, "reason": "no signal"}


def check_skill_impact(
    paths: Iterable[str],
    *,
    claimed_kind: str,
    input_semantics_unchanged: bool,
    policy_ir_validated: bool,
) -> Mapping[str, object]:
    """Classify what the candidate actually changed.

    Protected paths block outright. A code-resource change claimed as
    wording-only is reported as a code change — the claim is never
    trusted over the path evidence.
    """
    path_list = [str(p) for p in paths]
    if any(p.startswith(PROTECTED) for p in path_list):
        return {
            "effect_class": "protected_change",
            "blocked": True,
            "route": "manual",
        }
    claimed = claimed_kind in {"docs", "wording", "description"}
    code_changed = any(p.endswith(".py") for p in path_list)
    actual = "code" if code_changed else claimed_kind
    impact = classify(
        path_list,
        input_semantics_unchanged=input_semantics_unchanged,
        policy_ir_validated=policy_ir_validated,
    )
    return {
        "effect_class": impact.effect_class,
        "blocked": False,
        "route": (
            "high_risk_review" if claimed and code_changed else impact.path
        ),
        "claimed_kind": claimed_kind,
        "actual_kind": actual,
    }


class SkillRegistry:
    """CAS lane for skill releases with revocation and run binding."""

    def __init__(self, initial: SkillRelease) -> None:
        """Bind the registry to the live release."""
        self._live = initial
        self._history: list[SkillRelease] = [initial]
        self._revoked: set[str] = set()

    @property
    def live(self) -> SkillRelease:
        """The live release; revoked only after another is live."""
        return self._live

    def history(self) -> tuple[SkillRelease, ...]:
        """All releases including revoked ones; evidence persists."""
        return tuple(self._history)

    def promote(
        self,
        candidate: SkillCandidate,
        *,
        evidence: Mapping[str, object],
    ) -> SkillRelease:
        """Promote a candidate via CAS bound to actual evidence.

        Replay-only evidence is blocked, evidence bound to a different
        body digest is stale, and a candidate whose parent is no longer
        live must rebase and re-evaluate.
        """
        if evidence.get("kind") != "actual_paired":
            raise CyranoError(
                "BLOCKED",
                "replay or absent evidence cannot promote a skill",
            )
        if evidence.get("body_digest") != candidate.content_digest:
            raise CyranoError(
                "STALE_EVIDENCE", "evidence predates the current body"
            )
        if candidate.parent_release_id != self._live.release_id:
            raise CyranoError(
                "REBASE_REQUIRED",
                f"parent {candidate.parent_release_id} is not live",
            )
        release = SkillRelease(
            skill_id=candidate.skill_id,
            release_id=digest([candidate.candidate_id, self._live.release_id]),
            parent_release_id=self._live.release_id,
            content_digest=candidate.content_digest,
            status="active",
        )
        self._history.append(release)
        self._live = release
        return release

    def revoke(self, release_id: str) -> Mapping[str, object]:
        """Revoke a release; running tasks pause pending re-binding."""
        self._revoked.add(release_id)
        return {
            "revoked": release_id,
            "running_tasks": "paused",
            "requires_new_binding": True,
        }

    def bind_run(self, run: Mapping[str, object]) -> Mapping[str, object]:
        """Bind a run to the correct release honestly.

        Runs started before a promotion stay on their pinned release;
        new runs must bind the live one. A run pinned to a revoked
        release is paused, not allowed to continue on it.
        """
        used = str(run.get("release_id", ""))
        if used in self._revoked:
            return {
                "ok": False,
                "state": "paused",
                "reason": "REVOKED_RELEASE",
            }
        started_after = bool(run.get("started_after_promotion", False))
        known = {r.release_id for r in self._history}
        pinned = run.get("pinned_release_id")
        if not started_after and str(pinned) not in known:
            return {
                "ok": False,
                "state": "paused",
                "reason": "UNKNOWN_PINNED_RELEASE",
            }
        expected = self._live.release_id if started_after else str(pinned)
        return {
            "ok": used == expected,
            "expected_release": expected,
            "used_release": used,
        }


def prepare_memory_skill_bundle(
    memories: Iterable[Mapping[str, object]],
    skills: Iterable[Mapping[str, object]],
) -> Mapping[str, object]:
    """Bundle memory and skill changes for one review input.

    A merge may not drop counterexamples — every counterexample seen
    on an input must survive into the bundle, or the bundle is
    invalid rather than quietly weaker.
    """
    counter_in: set[str] = set()
    merged_ids: list[str] = []
    for item in list(memories) + list(skills):
        merged_ids.append(str(item.get("id", "")))
        c = item.get("counterexamples", ())
        if isinstance(c, SEQ):
            counter_in.update(str(x) for x in c)
        dropped = item.get("dropped_counterexamples", ())
        if isinstance(dropped, SEQ) and dropped:
            raise CyranoError(
                "INPUT_INVALID",
                "a merge may not drop counterexamples",
            )
    return {
        "bundle_id": digest(sorted(merged_ids)),
        "members": tuple(sorted(merged_ids)),
        "counterexamples": tuple(sorted(counter_in)),
        "review_only": True,
    }
