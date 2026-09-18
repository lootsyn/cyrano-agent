"""Skill evolution: evaluation, refinement, CAS apply, consolidation.

An active skill's bytes never change while a candidate is evaluated or
refined — refinement produces a new candidate revision bound to the
active revision. Application is a compare-and-swap: the first approval
at the expected revision applies; a second writer holding the stale
revision is refused and must rebase and re-evaluate. Consolidation
refuses when key exceptions are missing and never destroys the memory
records it summarizes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.improvement.candidates import (
    Candidate,
    propose_candidate,
)
from deepagents_code.cyrano.improvement.classification import classify
from deepagents_code.cyrano.sqlite.repository import ScopedRepository


@dataclass(frozen=True, slots=True)
class SkillVersion:
    """One sealed skill revision; history never rewrites it."""

    skill_id: str
    revision: int
    content_digest: str
    status: str
    author: str


@dataclass(frozen=True, slots=True)
class Evaluation:
    """A routed evaluation; the active digest is echoed, not changed."""

    route: str
    active_digest: str
    active_changed: bool
    requires_live: bool


class SkillLane:
    """CAS lane for one skill; apply requires the live revision."""

    def __init__(self, active: SkillVersion) -> None:
        """Bind the lane to the live version; history keeps it."""
        self._active: SkillVersion = active
        self._history: list[SkillVersion] = [active]

    @property
    def active(self) -> SkillVersion:
        """The live version; callers never mutate it."""
        return self._active

    def evaluate(
        self,
        candidate: Candidate,
        *,
        paths: Iterable[str],
        input_semantics_unchanged: bool,
        policy_ir_validated: bool,
        classifier: str,
    ) -> Evaluation:
        """Route a candidate without touching the active bytes."""
        if classifier == candidate.author:
            raise CyranoError(
                "REVIEW_INDEPENDENCE", "author cannot evaluate own diff"
            )
        impact = classify(
            list(paths),
            input_semantics_unchanged=input_semantics_unchanged,
            policy_ir_validated=policy_ir_validated,
        )
        route = {
            "protected_change": "manual",
            "scheduling_only": "A",
            "transition_changing": "B",
        }[impact.effect_class]
        return Evaluation(
            route,
            self._active.content_digest,
            False,
            impact.requires_live,
        )

    def refine(
        self,
        delta: Mapping[str, object],
        *,
        author: str,
    ) -> Candidate:
        """Open a new candidate bound to the active revision.

        The active version is untouched; the candidate records the
        revision it was based on so a later apply can detect drift.
        """
        diff = str(delta.get("diff", ""))
        grounds = str(delta.get("grounds", ""))
        return propose_candidate(
            base_revision=self._active.revision,
            diff=diff,
            scope=str(delta.get("scope", "")),
            author=author,
            grounds=grounds,
        )

    def apply(
        self,
        candidate: Candidate,
        *,
        approver: str,
        new_digest: str,
    ) -> SkillVersion:
        """Apply a candidate via CAS on the live revision.

        A stale base refuses — the writer must rebase onto the new
        active revision and re-evaluate; nothing is silently merged.
        """
        if approver == candidate.author:
            raise CyranoError(
                "REVIEW_INDEPENDENCE", "author cannot approve own apply"
            )
        if candidate.base_revision != self._active.revision:
            msg = (
                f"candidate bases {candidate.base_revision}, "
                f"active is {self._active.revision}"
            )
            raise CyranoError("REBASE_REQUIRED", msg)
        new = SkillVersion(
            skill_id=self._active.skill_id,
            revision=self._active.revision + 1,
            content_digest=new_digest,
            status="active",
            author=approver,
        )
        self._history.append(new)
        self._active = new
        return new


@dataclass(frozen=True, slots=True)
class Consolidation:
    """A summarized corpus; inputs are preserved, never destroyed."""

    consolidated_id: str
    kept: tuple[str, ...]
    exceptions_checked: tuple[str, ...]
    destroyed: tuple[str, ...]


def consolidate(
    records: Iterable[Mapping[str, object]],
    *,
    required_exceptions: Iterable[str],
) -> Consolidation:
    """Merge records only when every required exception is present.

    A missing key exception refuses the consolidation rather than
    dropping the exception silently; the input records are never
    deleted or marked destroyed.
    """
    kept = [str(r.get("id", "")) for r in records]
    required = frozenset(map(str, required_exceptions))
    present = frozenset(kept)
    missing = sorted(required - present)
    if missing:
        raise CyranoError(
            "CONSOLIDATION_INCOMPLETE",
            f"missing required exceptions: {missing[0]}",
        )
    return Consolidation(
        consolidated_id=digest(sorted(kept)),
        kept=tuple(kept),
        exceptions_checked=tuple(sorted(required)),
        destroyed=(),
    )


def resume_learning(
    repo: ScopedRepository,
    scope_id: str,
    owner: str,
    now: int,
    ttl_seconds: int,
) -> str | None:
    """Reclaim one pending or expired learning job after a restart.

    ``claim_outbox`` already re-claims leases whose deadline passed,
    bumping the fence so a restarted worker resumes the unfinished job
    instead of duplicating it.
    """
    lease = repo.claim_outbox(scope_id, owner, now, ttl_seconds)
    return lease.job_id if lease else None
