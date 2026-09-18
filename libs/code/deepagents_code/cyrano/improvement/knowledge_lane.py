"""Path B knowledge lane: memory candidates by kind, scope promotion.

Facts, preferences, and procedures carry different obligations and
are validated differently: a fact is authoritative only inside the
scope and dependency set of the snapshot that observed it, a
preference may supersede only for the trusted subject who stated it,
and a procedure must declare its precondition so an already-migrated
environment applies it conditionally instead of re-running effects.
A scope promotion to a wider scope is a new evaluation, never an
inheritance of the narrow evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.memory.obligations import parse_scope_rule

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

KNOWLEDGE_KINDS = frozenset({"fact", "preference", "procedure", "scope_rule"})
SEQ = (list, tuple, set, frozenset)


@dataclass(frozen=True, slots=True)
class KnowledgeCandidate:
    """A validated memory proposal; proposing changes nothing active."""

    candidate_id: str
    kind: str
    scope_id: str
    subject: str
    supersedes: str | None
    evidence_refs: tuple[str, ...]
    freshness_epoch: int
    requires_scope_evaluation: bool


def validate_knowledge_candidate(
    proposal: Mapping[str, object],
    *,
    superseded: Mapping[str, object] | None = None,
) -> KnowledgeCandidate:
    """Validate a proposal under its kind's obligations.

    A fact must bind the scope and snapshot that observed it — global
    generalization from one observation is refused. A preference that
    supersedes must come from the same trusted subject it replaces.
    A procedure must declare a precondition.
    """
    kind = proposal.get("kind")
    if kind not in KNOWLEDGE_KINDS:
        raise CyranoError("INPUT_INVALID", f"kind {kind!r}")
    scope = str(proposal.get("scope_id", ""))
    subject = str(proposal.get("subject", ""))
    if not scope or not subject:
        raise CyranoError("INPUT_INVALID", "scope and subject required")
    evidence = proposal.get("evidence_refs", ())
    refs = tuple(str(e) for e in evidence) if isinstance(evidence, SEQ) else ()
    if not refs:
        raise CyranoError("EVIDENCE_REQUIRED", "proposal needs evidence")
    freshness = proposal.get("freshness_epoch", 0)
    if not isinstance(freshness, int) or freshness < 0:
        raise CyranoError("INPUT_INVALID", "freshness epoch required")
    if kind == "fact":
        if not proposal.get("source_snapshot"):
            raise CyranoError(
                "EVIDENCE_REQUIRED", "a fact binds its source snapshot"
            )
        if proposal.get("generalize", False):
            raise CyranoError(
                "SCOPE_DENIED",
                "one snapshot's fact has no global authority",
            )
    if kind == "preference":
        supersedes = proposal.get("supersedes")
        if supersedes is not None:
            if superseded is None:
                raise CyranoError(
                    "INPUT_INVALID", "superseded record required"
                )
            if not proposal.get("trusted", False):
                raise CyranoError(
                    "PERMISSION_DENIED", "untrusted preference edit"
                )
            if str(superseded.get("subject", "")) != subject:
                raise CyranoError(
                    "SCOPE_DENIED",
                    "a preference never supersedes another subject's",
                )
    if kind == "procedure" and not proposal.get("precondition"):
        raise CyranoError(
            "INPUT_INVALID", "a procedure declares its precondition"
        )
    if kind == "scope_rule":
        # A scope rule declares a declarative body — glob selectors,
        # exception clauses and a trusted checker id. The validator
        # only checks the closed shape; the rule gains no authority
        # here and is never executed.
        _ = parse_scope_rule(proposal.get("rule", {}))
    supersedes = proposal.get("supersedes")
    return KnowledgeCandidate(
        candidate_id=digest([kind, scope, subject, sorted(refs)]),
        kind=str(kind),
        scope_id=scope,
        subject=subject,
        supersedes=str(supersedes) if supersedes is not None else None,
        evidence_refs=refs,
        freshness_epoch=freshness,
        requires_scope_evaluation=False,
    )


def evaluate_memory_pairs(
    exposures: Iterable[Mapping[str, object]],
    outcomes: Iterable[Mapping[str, object]],
) -> Mapping[str, object]:
    """Pair memory exposure with outcomes into honest evidence.

    Only ``applied`` records bound to a successful outcome count as
    causal support; raw exposure is correlation and never a reason to
    promote.
    """
    applied_ok: set[str] = set()
    for outcome in outcomes:
        if str(outcome.get("status", "")) != "success":
            continue
        am = outcome.get("applied_memories")
        if isinstance(am, SEQ):
            applied_ok.update(str(m) for m in am)
    exposed: set[str] = set()
    causal: set[str] = set()
    for exposure in exposures:
        mid = str(exposure.get("memory_id", ""))
        if not mid:
            continue
        exposed.add(mid)
        if mid in applied_ok:
            causal.add(mid)
    return {
        "exposed": len(exposed),
        "causal": len(causal),
        "correlated_only": len(exposed - causal),
        "promotable": False,
    }


def promote_scope(
    candidate: KnowledgeCandidate,
    *,
    to_scope: str,
    evaluation: Mapping[str, object] | None,
    approval: str | None,
) -> KnowledgeCandidate:
    """Promote a candidate to a wider scope under fresh obligations.

    A workspace lesson becomes global only with a scope-bound
    evaluation and an approval that is not the proposal's own evidence
    — narrow evidence is never inherited upward.
    """
    if to_scope == candidate.scope_id:
        raise CyranoError("INPUT_INVALID", "already in that scope")
    if evaluation is None or not evaluation.get("scope_evaluated", False):
        raise CyranoError(
            "SCOPE_DENIED",
            "wider scope requires its own evaluation",
        )
    if approval is None or str(evaluation.get("scope_id")) != to_scope:
        raise CyranoError(
            "SCOPE_DENIED", "scope promotion needs bound approval"
        )
    return KnowledgeCandidate(
        candidate_id=digest([candidate.candidate_id, to_scope, str(approval)]),
        kind=candidate.kind,
        scope_id=to_scope,
        subject=candidate.subject,
        supersedes=candidate.supersedes,
        evidence_refs=candidate.evidence_refs,
        freshness_epoch=candidate.freshness_epoch,
        requires_scope_evaluation=False,
    )


@dataclass(frozen=True, slots=True)
class RecipeOutcome:
    """A conditional recipe application; no duplicate side effects."""

    applied: bool
    reason: str


def apply_recipe(
    recipe: Mapping[str, object],
    *,
    environment: Mapping[str, object],
) -> RecipeOutcome:
    """Apply a procedure only when its precondition still holds.

    A migration already completed satisfies its own precondition —
    the recipe is reported ``already_satisfied`` and performs no
    operational side effect a second time.
    """
    precondition = str(recipe.get("precondition", ""))
    if not precondition:
        raise CyranoError("INPUT_INVALID", "a recipe needs a precondition")
    done = environment.get("completed", ())
    satisfied = (
        precondition in {str(d) for d in done}
        if isinstance(done, SEQ)
        else False
    )
    if satisfied:
        return RecipeOutcome(False, "already_satisfied")
    return RecipeOutcome(True, "applied")
