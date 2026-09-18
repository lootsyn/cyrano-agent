"""Static plan validation: findings carry check ids, never one bool.

``validate_plan`` runs the cross-artifact checks in a fixed order and
returns a report. Validation grants no authority: a ``passed`` check
is evidence for review, not an execution permit. Unknown results stay
``unverifiable`` and are never folded into ``passed``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.planning.subject import (
    GovernedWorkPlan,
    WorkUnitSpec,
)

CHECK_IDS = (
    "plan_shape",
    "requirement_coverage",
    "test_binding",
    "interface_compatibility",
    "dag_acyclic",
    "write_conflict",
    "effect_declaration",
    "budget_bound",
    "recipe_capability",
    "write_scope_bounded",
)


@dataclass(frozen=True, slots=True)
class PlanCheck:
    """One check result with a concrete observation."""

    check_id: str
    status: str  # passed | failed | unverifiable | not_applicable
    detail: str
    refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PlanCheckReport:
    """All check results plus the refusal codes reviewers act on."""

    checks: tuple[PlanCheck, ...]
    violations: tuple[str, ...]
    cycle_path: tuple[str, ...] = ()
    ready_for_review: bool = False


def _check(
    check_id: str, status: str, detail: str, refs: tuple[str, ...] = ()
) -> PlanCheck:
    return PlanCheck(check_id, status, detail, refs)


def _find_cycle(units: Mapping[str, WorkUnitSpec]) -> tuple[str, ...]:
    """Return one dependency cycle path, or empty when acyclic."""
    white, gray, black = 0, 1, 2
    color = {u: white for u in units}
    stack: list[str] = []

    def visit(node: str) -> tuple[str, ...]:
        color[node] = gray
        stack.append(node)
        for dep in units[node].dependencies:
            if dep not in units:
                continue
            if color[dep] == gray:
                return tuple(stack[stack.index(dep) :] + [dep])
            if color[dep] == white:
                found = visit(dep)
                if found:
                    return found
        stack.pop()
        color[node] = black
        return ()

    for node in units:
        if color[node] == white:
            found = visit(node)
            if found:
                return found
    return ()


def validate_plan(
    plan: GovernedWorkPlan,
    *,
    active_requirements: tuple[str, ...] | None = None,
    verified_no_change: Mapping[str, str] | None = None,
    known_recipes: frozenset[str] | None = None,
    known_interfaces: Mapping[str, str] | None = None,
) -> PlanCheckReport:
    """Run every structural check; collect violations, grant nothing.

    ``verified_no_change`` maps a requirement id to the digest of the
    evidence that the current source already satisfies it — the only
    way a requirement may be covered without a work unit. Active
    requirements default to the plan's declared requirements.
    """
    checks: list[PlanCheck] = []
    violations: list[str] = []
    failed_checks: set[str] = set()
    no_change = dict(verified_no_change or {})
    interfaces = dict(known_interfaces or {})
    required = (
        plan.requirements
        if active_requirements is None
        else active_requirements
    )

    def fail(
        check_id: str, code: str, detail: str, refs: tuple[str, ...] = ()
    ) -> None:
        checks.append(_check(check_id, "failed", detail, refs))
        violations.append(code)
        failed_checks.add(check_id)

    def ok(check_id: str, detail: str) -> None:
        if check_id not in failed_checks:
            checks.append(_check(check_id, "passed", detail))

    # 1. shape: units exist, ids unique, refs resolve.
    if not plan.units:
        fail("plan_shape", "INVALID_PLAN", "work_units is empty")
    ids = [u.unit_id for u in plan.units]
    if len(set(ids)) != len(ids):
        fail("plan_shape", "INPUT_INVALID", "duplicate work unit ids")
    by_id = {u.unit_id: u for u in plan.units}
    for unit in plan.units:
        missing = set(unit.dependencies) - set(by_id)
        if missing or unit.unit_id in unit.dependencies:
            fail(
                "plan_shape",
                "MISSING_DEPENDENCY",
                f"{unit.unit_id}: {sorted(missing)}",
                (unit.unit_id,),
            )
        if not unit.requirement_ids or not unit.acceptance_ids:
            fail(
                "plan_shape",
                "UNTRACEABLE_WORK",
                f"{unit.unit_id} lacks requirement/acceptance ids",
                (unit.unit_id,),
            )
        if not unit.write_paths:
            fail(
                "plan_shape",
                "PLAN_INCOMPLETE",
                f"{unit.unit_id} declares no create/write targets",
                (unit.unit_id,),
            )
    ok("plan_shape", "shape ok")

    # 2. requirement coverage.
    covered = {r for u in plan.units for r in u.requirement_ids}
    uncovered = [
        r for r in required if r not in covered and r not in no_change
    ]
    if uncovered:
        fail(
            "requirement_coverage",
            "UNBOUND_REQUIREMENT",
            f"no work or verified_no_change evidence: {uncovered}",
            tuple(uncovered),
        )
    else:
        ok("requirement_coverage", "all covered")

    # 3. test binding: every acceptance needs a recipe + oracle.
    weak = [
        u.unit_id for u in plan.units if not u.test_recipe or not u.test_oracle
    ]
    if weak:
        fail(
            "test_binding",
            "TEST_RECIPE_MISSING",
            f"acceptance without trusted recipe/oracle: {weak}",
            tuple(weak),
        )
    else:
        ok("test_binding", "oracles bound")

    # 4. interface compatibility: consumed names must be produced
    #    with the same contract signature.
    produced = {name: u.unit_id for u in plan.units for name in u.produces}
    mismatched: list[str] = []
    for unit in plan.units:
        for name in unit.consumes:
            producer = produced.get(name)
            if producer is None:
                mismatched.append(f"{unit.unit_id}:{name}:unproduced")
            elif interfaces.get(f"{producer}.{name}") != interfaces.get(
                f"{unit.unit_id}.{name}"
            ):
                mismatched.append(f"{unit.unit_id}:{name}:mismatch")
    if mismatched:
        fail(
            "interface_compatibility",
            "INTERFACE_MISMATCH",
            "; ".join(mismatched),
            tuple(mismatched),
        )
    else:
        ok("interface_compatibility", "signatures align")

    # 5. DAG cycle.
    cycle = _find_cycle(by_id) if len(by_id) == len(plan.units) else ()
    if cycle:
        fail("dag_acyclic", "DAG_CYCLE", " -> ".join(cycle), cycle)
    else:
        ok("dag_acyclic", "acyclic")

    # 6. write-set conflicts need an explicit serialization edge.
    writers: dict[str, list[str]] = {}
    for unit in plan.units:
        for path in unit.write_paths:
            writers.setdefault(path, []).append(unit.unit_id)
    conflicts: list[str] = []
    for path, owners in writers.items():
        if len(owners) < 2:
            continue
        # A conflict edge exists when the units are ordered by deps.
        for left in owners:
            for right in owners:
                if left == right:
                    continue
                ordered = _reachable(by_id, left, right) or _reachable(
                    by_id, right, left
                )
                if not ordered:
                    conflicts.append(path)
    if conflicts:
        fail(
            "write_conflict",
            "RESOURCE_CONFLICT",
            f"unordered writers share {sorted(set(conflicts))}",
            tuple(sorted(set(conflicts))),
        )
    else:
        ok("write_conflict", "writes serialized")

    # 7. declared effects: external effects must be on the plan and
    #    risky unit effects must be declared per unit.
    undeclared = [
        f"{u.unit_id}:{e}"
        for u in plan.units
        for e in u.effects
        if e not in plan.external_effects
    ]
    if undeclared:
        fail(
            "effect_declaration",
            "UNDECLARED_EFFECT",
            f"unit effects absent from plan effects: {undeclared}",
            tuple(undeclared),
        )
    else:
        ok("effect_declaration", "effects declared")

    # 8. budget: a cap must exist and cover unit caps.
    if plan.budget_cap is None:
        fail("budget_bound", "BUDGET_UNBOUND", "no plan budget cap")
    else:
        uncapped = [u.unit_id for u in plan.units if u.cost_cap is None]
        total = sum(u.cost_cap or 0 for u in plan.units)
        if uncapped:
            fail(
                "budget_bound",
                "BUDGET_UNBOUND",
                f"units without cost cap: {uncapped}",
                tuple(uncapped),
            )
        elif total > plan.budget_cap:
            fail(
                "budget_bound",
                "BUDGET_UNBOUND",
                f"unit caps {total} exceed plan cap {plan.budget_cap}",
            )
        else:
            ok("budget_bound", "budget bounded")

    # 9. recipes must resolve to registered trusted recipes.
    if known_recipes:
        unknown = [
            u.unit_id
            for u in plan.units
            if u.test_recipe and u.test_recipe not in known_recipes
        ]
        if unknown:
            fail(
                "recipe_capability",
                "CAPABILITY_UNAVAILABLE",
                f"unregistered recipes: {unknown}",
                tuple(unknown),
            )
        else:
            ok("recipe_capability", "recipes known")
    else:
        checks.append(
            _check(
                "recipe_capability",
                "unverifiable",
                "no recipe registry supplied",
            )
        )

    # 10. bounded write scope: no wildcard, absolute, or escaping
    #     path without an explicit file list.
    wild = [
        u.unit_id
        for u in plan.units
        if any(
            p in {"*", "**", "**/*"}
            or p.startswith("/")
            or ".." in p.split("/")
            for p in u.write_paths
        )
    ]
    if wild:
        fail(
            "write_scope_bounded",
            "UNBOUNDED_WRITE_SET",
            f"wildcard write scope: {wild}",
            tuple(wild),
        )
    else:
        ok("write_scope_bounded", "writes bounded")

    ready = not violations and all(c.status != "unverifiable" for c in checks)
    return PlanCheckReport(
        checks=tuple(checks),
        violations=tuple(violations),
        cycle_path=cycle,
        ready_for_review=ready,
    )


def _reachable(units: Mapping[str, WorkUnitSpec], src: str, dst: str) -> bool:
    """True when ``dst`` is a transitive dependency of ``src``."""
    seen: set[str] = set()
    stack = [src]
    while stack:
        node = stack.pop()
        if node == dst:
            return True
        if node in seen or node not in units:
            continue
        seen.add(node)
        stack.extend(units[node].dependencies)
    return False


def require_ready(report: PlanCheckReport) -> None:
    """Raise when a plan may not proceed to review."""
    if not report.ready_for_review:
        raise CyranoError(
            violations_code(report),
            "plan is not ready for review",
        )


def violations_code(report: PlanCheckReport) -> str:
    """First violation code, else ``PLAN_INCOMPLETE``."""
    if report.violations:
        return report.violations[0]
    return "PLAN_INCOMPLETE"
