"""Stage readiness is a blocker check, not an averaged LLM score."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Obligation:
    """An applicable duty with explicit deferral bounds."""

    obligation_id: str
    critical: bool
    resolved: bool
    deferred_to: str | None = None
    authorized_deferral: bool = False


@dataclass(frozen=True, slots=True)
class Readiness:
    """Preparation status does not grant execution authority."""

    ready: bool
    blockers: tuple[str, ...]
    execution_authorized: bool = False


def assess(
    obligations: list[Obligation],
    *,
    target_stage: str,
    required_review_current: bool,
    important_assumptions: int,
    stale_evidence: int,
    unresolved_conflicts: int,
) -> Readiness:
    """Return all blockers; there is no minimum-rounds rule."""
    blockers = []
    for item in obligations:
        deferred = (
            item.authorized_deferral
            and item.deferred_to == target_stage
            and not item.critical
        )
        if not item.resolved and not deferred:
            blockers.append(f"obligation:{item.obligation_id}")
    if not required_review_current:
        blockers.append("review_missing_or_stale")
    if important_assumptions:
        blockers.append("unauthorized_assumptions")
    if stale_evidence:
        blockers.append("stale_evidence")
    if unresolved_conflicts:
        blockers.append("unresolved_conflicts")
    return Readiness(not blockers, tuple(blockers))


def affected_closure(
    changed: set[str], dependencies: dict[str, set[str]]
) -> set[str]:
    """Transitive invalidation, cycles included; input unchanged."""
    affected = set(changed)
    while True:
        extra = {
            node
            for node, parents in dependencies.items()
            if parents & affected
        }
        if extra.issubset(affected):
            return affected
        affected.update(extra)
