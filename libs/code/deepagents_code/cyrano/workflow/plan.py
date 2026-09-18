"""Work-plan structural checks; semantic review is separate."""

from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError


@dataclass(frozen=True, slots=True)
class WorkUnit:
    """One independently verifiable unit and its dependencies."""

    unit_id: str
    dependencies: tuple[str, ...]
    requirement_ids: tuple[str, ...]
    acceptance_ids: tuple[str, ...]
    write_paths: tuple[str, ...]


def order_plan(units: list[WorkUnit]) -> tuple[str, ...]:
    """Reject bad references and cycles; order stably."""
    by_id = {unit.unit_id: unit for unit in units}
    if len(by_id) != len(units):
        raise CyranoError("DUPLICATE_WORK_UNIT", "work ids must be unique")
    for unit in units:
        if not unit.requirement_ids or not unit.acceptance_ids:
            raise CyranoError("UNTRACEABLE_WORK", unit.unit_id)
        if not set(unit.dependencies).issubset(by_id):
            raise CyranoError("MISSING_DEPENDENCY", unit.unit_id)
    result: list[str] = []
    while len(result) < len(units):
        ready = sorted(
            key
            for key, unit in by_id.items()
            if key not in result and set(unit.dependencies).issubset(result)
        )
        if not ready:
            raise CyranoError("PLAN_CYCLE", "work dependency graph is cyclic")
        result.extend(ready)
    return tuple(result)
