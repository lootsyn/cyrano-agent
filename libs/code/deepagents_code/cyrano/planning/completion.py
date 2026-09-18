"""Completion judgment: acceptance, review, and publish stay separate.

A candidate is complete only when its acceptance evidence, independent
review, and scope checks each pass on the real artifacts. An answered
question, a verified no-change result, and a code change are different
outcomes — none is reported as another. Publication is a distinct
permission and never implied by acceptance.
"""

from __future__ import annotations

from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError

OUTCOMES = frozenset({"changed", "answered", "verified_no_change", "failed"})


@dataclass(frozen=True, slots=True)
class CompletionDecision:
    """What may be claimed about a finished piece of work."""

    outcome: str
    acceptance_met: bool
    review_complete: bool
    may_apply: bool
    may_publish: bool
    unmet: tuple[str, ...] = ()


def assess_completion(
    *,
    outcome: str,
    acceptance_results: dict[str, bool],
    review_approved: bool,
    apply_permit: bool,
    publish_permit: bool,
    source_changed: bool,
) -> CompletionDecision:
    """Judge a candidate from evidence; never from intent alone.

    ``verified_no_change`` requires a digest check proving the source
    did not change — claiming it on a changed tree fabricates a
    receipt. ``answered`` is for analysis requests and grants no apply
    or publish right.
    """
    if outcome not in OUTCOMES:
        raise CyranoError("INVALID_OUTCOME", outcome)
    unmet = tuple(sorted(k for k, v in acceptance_results.items() if not v))
    acceptance_met = not unmet
    if outcome == "verified_no_change" and source_changed:
        raise CyranoError(
            "STALE_SOURCE",
            "verified_no_change claims the source did not change",
        )
    return CompletionDecision(
        outcome=outcome,
        acceptance_met=acceptance_met,
        review_complete=review_approved,
        may_apply=(
            outcome == "changed"
            and acceptance_met
            and review_approved
            and apply_permit
        ),
        may_publish=publish_permit and acceptance_met and review_approved,
        unmet=unmet,
    )
