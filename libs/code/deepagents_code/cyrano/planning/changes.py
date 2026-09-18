"""Change classification and reverse-impact closure.

A change is judged by what it does to execution meaning — scope,
budget, interfaces, oracles, or inventory — never by its diff size.
Presentation-only edits keep the subject digest. Anything that
widens scope, raises budget, weakens verification, or changes the
delivery mode produces a new subject needing fresh review and fresh
approval; prior receipts are never reused. When the impact cannot be
classified the affected work pauses — it does not proceed on a
guess.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.planning.subject import (
    GovernedWorkPlan,
    plan_projection,
    presentation_only_change,
)

CLASSIFICATIONS = frozenset(
    {
        "presentation_only",
        "delegated_choice",
        "execution_meaning_change",
        "unknown",
    }
)


@dataclass(frozen=True, slots=True)
class ChangeImpact:
    """The classified change plus everything it invalidates."""

    classification: str
    changed_requirements: tuple[str, ...]
    changed_paths: tuple[str, ...]
    affected_units: tuple[str, ...]
    invalidated_reviews: tuple[str, ...]
    requires_new_review: bool
    requires_new_approval: bool


def classify_change(
    old_plan: GovernedWorkPlan,
    new_plan: GovernedWorkPlan,
    *,
    authorized_alternatives: frozenset[str] | None = None,
    unclassifiable: bool = False,
) -> ChangeImpact:
    """Classify old→new and compute the invalidation closure.

    ``authorized_alternatives`` names choices pre-approved inside the
    subject; picking among them is a ``delegated_choice`` that only
    needs a decision record, not re-review.
    """
    old_units = {u.unit_id: u for u in old_plan.units}
    new_units = {u.unit_id: u for u in new_plan.units}
    changed_paths = tuple(
        sorted(
            {p for u in new_plan.units for p in u.write_paths}
            - {p for u in old_plan.units for p in u.write_paths}
        )
    )
    if unclassifiable:
        return ChangeImpact(
            classification="unknown",
            changed_requirements=(),
            changed_paths=changed_paths,
            affected_units=tuple(sorted(new_units)),
            invalidated_reviews=(),
            requires_new_review=True,
            requires_new_approval=True,
        )
    if presentation_only_change(
        plan_projection(old_plan), plan_projection(new_plan)
    ):
        return ChangeImpact(
            classification="presentation_only",
            changed_requirements=(),
            changed_paths=(),
            affected_units=(),
            invalidated_reviews=(),
            requires_new_review=False,
            requires_new_approval=False,
        )
    # Delegated choice: identical except one unit picks a different
    # pre-authorized implementation name.
    delegated = _delegated_only(
        old_plan, new_plan, authorized_alternatives or frozenset()
    )
    if delegated:
        return ChangeImpact(
            classification="delegated_choice",
            changed_requirements=(),
            changed_paths=(),
            affected_units=(),
            invalidated_reviews=(),
            requires_new_review=False,
            requires_new_approval=False,
        )
    changed_reqs = tuple(
        sorted(set(new_plan.requirements) ^ set(old_plan.requirements))
    )
    affected = _reverse_closure(old_units, new_units, changed_paths)
    return ChangeImpact(
        classification="execution_meaning_change",
        changed_requirements=changed_reqs,
        changed_paths=changed_paths,
        affected_units=affected,
        invalidated_reviews=(),
        requires_new_review=True,
        requires_new_approval=True,
    )


def _delegated_only(
    old_plan: GovernedWorkPlan,
    new_plan: GovernedWorkPlan,
    alternatives: frozenset[str],
) -> bool:
    """True when the only delta swaps between authorized choices."""
    base_old = replace(old_plan, units=(), revision=0)
    base_new = replace(new_plan, units=(), revision=0)
    if base_old != base_new:
        return False
    if len(old_plan.units) != len(new_plan.units):
        return False
    old = {u.unit_id: u for u in old_plan.units}
    for unit in new_plan.units:
        prev = old.get(unit.unit_id)
        if prev is None:
            return False
        if prev == unit:
            continue
        old_recipe = prev.test_recipe or ""
        new_recipe = unit.test_recipe or ""
        if replace(prev, test_recipe=new_recipe) != unit:
            return False
        if new_recipe not in alternatives or old_recipe not in alternatives:
            return False
    return True


def _reverse_closure(
    old_units: Mapping[str, Any],
    new_units: Mapping[str, Any],
    changed_paths: tuple[str, ...],
) -> tuple[str, ...]:
    """Units whose inputs or dependencies touch a changed unit."""
    seeds = {
        uid
        for uid, unit in new_units.items()
        if uid not in old_units or old_units[uid] != unit
    }
    seeds |= {
        uid
        for uid, unit in new_units.items()
        if set(unit.write_paths) & set(changed_paths)
    }
    dependents: dict[str, set[str]] = {}
    producers: dict[str, str] = {}
    for uid, unit in new_units.items():
        for dep in unit.dependencies:
            dependents.setdefault(dep, set()).add(uid)
        for name in unit.produces:
            producers[name] = uid
    for uid, unit in new_units.items():
        for name in unit.consumes:
            owner = producers.get(name)
            if owner:
                dependents.setdefault(owner, set()).add(uid)
    affected = set(seeds)
    frontier = list(seeds)
    while frontier:
        node = frontier.pop()
        for dep in dependents.get(node, set()):
            if dep not in affected:
                affected.add(dep)
                frontier.append(dep)
    return tuple(sorted(affected))


class PlanRevisions:
    """CAS store for plan revisions; one commit wins per base."""

    def __init__(self) -> None:
        """Revisions and their commitments live in memory here."""
        self._plans: dict[str, dict[int, GovernedWorkPlan]] = {}
        self._head: dict[str, int] = {}

    def commit(self, plan: GovernedWorkPlan, *, expected_revision: int) -> int:
        """Commit a revision; a stale base loses and must rebase."""
        head = self._head.get(plan.plan_id, -1)
        if expected_revision != head:
            raise CyranoError(
                "CAS_CONFLICT",
                f"expected revision {expected_revision}, head is {head}",
            )
        if plan.delivery_mode not in {"patch_only", "apply_to_source"}:
            raise CyranoError("INVALID_PLAN", "unknown delivery mode")
        revisions = self._plans.setdefault(plan.plan_id, {})
        revisions[plan.revision] = plan
        self._head[plan.plan_id] = plan.revision
        return plan.revision

    def head(self, plan_id: str) -> GovernedWorkPlan | None:
        """Return the latest committed revision of a plan."""
        rev = self._head.get(plan_id)
        if rev is None:
            return None
        return self._plans[plan_id][rev]

    def delivery_mode_changed(
        self, old: GovernedWorkPlan, new: GovernedWorkPlan
    ) -> bool:
        """Delivery-mode flips always need a fresh subject+permit."""
        return old.delivery_mode != new.delivery_mode


def compute_impact(
    plan: GovernedWorkPlan, changed_unit_ids: frozenset[str]
) -> tuple[str, ...]:
    """Reverse dependency+interface closure of changed units.

    A unit is affected when it depends on a changed unit or consumes
    an interface a changed unit produces. Units untouched by the
    closure keep their evidence — unrelated display edits force no
    re-run. An unresolvable unit id pauses the whole plan.
    """
    units = {u.unit_id: u for u in plan.units}
    if not changed_unit_ids <= set(units):
        return tuple(sorted(units))
    dependents: dict[str, set[str]] = {}
    producers: dict[str, str] = {}
    for uid, unit in units.items():
        for dep in unit.dependencies:
            dependents.setdefault(dep, set()).add(uid)
        for name in unit.produces:
            producers[name] = uid
    for uid, unit in units.items():
        for name in unit.consumes:
            owner = producers.get(name)
            if owner is not None and owner != uid:
                dependents.setdefault(owner, set()).add(uid)
    affected = set(changed_unit_ids)
    frontier = list(changed_unit_ids)
    while frontier:
        node = frontier.pop()
        for dep in dependents.get(node, set()):
            if dep not in affected:
                affected.add(dep)
                frontier.append(dep)
    return tuple(sorted(affected))


def invalidate_requirements(
    plan: GovernedWorkPlan, retracted: frozenset[str]
) -> ChangeImpact:
    """A user retracting a requirement stales its dependents.

    Every unit binding a retracted requirement — plus its reverse
    closure — loses its evidence and any approval bound to the old
    subject is stale.
    """
    units = {u.unit_id: u for u in plan.units}
    seeds = {
        uid
        for uid, unit in units.items()
        if set(unit.requirement_ids) & set(retracted)
    }
    affected = compute_impact(plan, frozenset(seeds))
    return ChangeImpact(
        classification="execution_meaning_change",
        changed_requirements=tuple(sorted(retracted)),
        changed_paths=(),
        affected_units=affected,
        invalidated_reviews=(),
        requires_new_review=True,
        requires_new_approval=True,
    )


def apply_policy_change(
    current_cap: int, new_cap: int, reserved: int
) -> dict[str, Any]:
    """Shrink a cap without hiding negative headroom.

    Existing reservations still settle; new ones block. The
    reported headroom may be negative — it is never clamped.
    """
    if new_cap < 0 or current_cap < 0 or reserved < 0:
        raise CyranoError("INVALID_BUDGET", "negative budget")
    return {
        "cap": new_cap,
        "reserved": reserved,
        "new_reservations_allowed": reserved < new_cap,
        "headroom": new_cap - reserved,
        "shrunk_below_reserved": new_cap < reserved,
    }
