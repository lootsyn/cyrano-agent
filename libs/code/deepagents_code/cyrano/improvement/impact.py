"""Independent impact routing: A (replay-screened), B (actual), manual.

Routing is conservative: a protected path always goes to manual
review, unknown effect goes to the B actual route, and a
``scheduling_only`` claim is ignored unless the invariant is attested
by validated policy IR and unchanged input semantics. The classifier
must be independent — the candidate's author never routes their own
change.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.improvement.candidates import Candidate
from deepagents_code.cyrano.improvement.classification import classify


@dataclass(frozen=True, slots=True)
class ImpactRoute:
    """A routed candidate; ``route`` is A, B, or manual."""

    route: str
    effect_class: str
    requires_live: bool
    classifier: str


def assess_impact(
    candidate: Candidate | Mapping[str, object],
    *,
    classifier: str,
    input_semantics_unchanged: bool,
    policy_ir_validated: bool,
) -> ImpactRoute:
    """Route a candidate; self-declared lanes are never trusted.

    The classifier must differ from the candidate's author — the same
    principal may not both propose and route a change. Author claims
    recorded on the candidate are evidence, not routing input.
    """
    if isinstance(candidate, Candidate):
        author = candidate.author
        paths = list(candidate.paths)
    else:
        author = str(candidate.get("author", ""))
        paths_raw = candidate.get("paths", ())
        paths = (
            [str(p) for p in paths_raw]
            if isinstance(paths_raw, (list, tuple))
            else []
        )
    if classifier == author:
        raise CyranoError(
            "REVIEW_INDEPENDENCE", "author cannot route own candidate"
        )
    impact = classify(
        paths,
        input_semantics_unchanged=input_semantics_unchanged,
        policy_ir_validated=policy_ir_validated,
    )
    route = {
        "protected_change": "manual",
        "scheduling_only": "A",
        "transition_changing": "B",
    }[impact.effect_class]
    return ImpactRoute(
        route=route,
        effect_class=impact.effect_class,
        requires_live=impact.requires_live,
        classifier=classifier,
    )
