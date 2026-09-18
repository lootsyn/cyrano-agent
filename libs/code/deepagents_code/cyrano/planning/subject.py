"""Plan review subject: the sealed object every approval binds to.

The subject digest covers requirements, design choices, the work plan,
allowed runtime/tool policy, tests, budget, external effects, and the
recovery procedure. Progress markers, cursors, review responses,
receipts, and signatures are never part of it — a digest field that
feeds back into the subject is a hash cycle and is refused.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError

#: Keys that describe presentation or lifecycle, never execution
#: meaning. Changing only these leaves the subject digest identical.
PRESENTATION_KEYS = frozenset(
    {
        "progress",
        "display_text",
        "cursor",
        "review_response",
        "approval_ref",
        "execution_permit_ref",
        "signature",
        "execution_result",
        "title",
        "notes",
    }
)


@dataclass(frozen=True, slots=True)
class WorkUnitSpec:
    """One verifiable unit of work inside a plan."""

    unit_id: str
    requirement_ids: tuple[str, ...]
    acceptance_ids: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    write_paths: tuple[str, ...] = ()
    read_refs: tuple[str, ...] = ()
    consumes: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()
    exclusive_resources: tuple[str, ...] = ()
    test_recipe: str | None = None
    test_oracle: str | None = None
    cost_cap: int | None = None
    effects: tuple[str, ...] = ()
    recovery: str | None = None
    owner: str = "implementer"


@dataclass(frozen=True, slots=True)
class GovernedWorkPlan:
    """An approved-mode plan: delivery mode, units, budget, effects."""

    plan_id: str
    revision: int
    requirements: tuple[str, ...]
    units: tuple[WorkUnitSpec, ...]
    delivery_mode: str = "patch_only"
    budget_cap: int | None = None
    external_effects: tuple[str, ...] = ()
    rollback: str | None = None


@dataclass(frozen=True, slots=True)
class PlanReviewSubject:
    """Sealed projection of a plan that reviews and approvals bind."""

    subject_id: str
    plan_id: str
    revision: int
    scope: Mapping[str, str]
    requirements_digest: str
    work_plan_digest: str
    source_snapshot_digest: str
    test_plan_digest: str
    budget_cap: int | None
    external_effects: tuple[str, ...]
    recovery_ref: str | None


def _strip_presentation(value: Any) -> Any:
    """Drop presentation keys so wording changes keep the digest."""
    if isinstance(value, Mapping):
        return {
            k: _strip_presentation(v)
            for k, v in value.items()
            if k not in PRESENTATION_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_strip_presentation(v) for v in value]
    return value


def _reject_subject_refs(value: Any, path: str = "plan") -> None:
    """A subject may not embed its own digest or downstream receipts."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in {"subject_digest", "approval_receipt", "permit"}:
                raise CyranoError(
                    "INVALID_SUBJECT_PROJECTION",
                    f"{path}.{key} feeds back into the subject",
                )
            _reject_subject_refs(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_subject_refs(item, f"{path}[{index}]")


def plan_projection(plan: GovernedWorkPlan) -> dict[str, Any]:
    """Canonical execution-meaning projection of a work plan."""
    return {
        "plan_id": plan.plan_id,
        "revision": plan.revision,
        "delivery_mode": plan.delivery_mode,
        "budget_cap": plan.budget_cap,
        "external_effects": sorted(plan.external_effects),
        "rollback": plan.rollback,
        "requirements": sorted(plan.requirements),
        "units": [
            {
                "unit_id": u.unit_id,
                "requirement_ids": sorted(u.requirement_ids),
                "acceptance_ids": sorted(u.acceptance_ids),
                "dependencies": sorted(u.dependencies),
                "write_paths": sorted(u.write_paths),
                "consumes": sorted(u.consumes),
                "produces": sorted(u.produces),
                "exclusive_resources": sorted(u.exclusive_resources),
                "test_recipe": u.test_recipe,
                "test_oracle": u.test_oracle,
                "cost_cap": u.cost_cap,
                "effects": sorted(u.effects),
                "recovery": u.recovery,
                "owner": u.owner,
            }
            for u in sorted(plan.units, key=lambda u: u.unit_id)
        ],
    }


def build_subject(
    plan: GovernedWorkPlan,
    requirements_doc: Mapping[str, Any],
    source_snapshot: Mapping[str, Any],
    scope: Mapping[str, str],
    *,
    subject_id: str = "subject",
) -> PlanReviewSubject:
    """Seal a plan into the immutable subject approvals bind to."""
    projection = _strip_presentation(plan_projection(plan))
    _reject_subject_refs(projection)
    for name, value in (
        ("scope", scope),
        ("requirements", requirements_doc),
        ("source_snapshot", source_snapshot),
    ):
        _reject_subject_refs(value, name)
    if not plan.requirements:
        raise CyranoError("INVALID_PLAN", "a plan needs requirements")
    return PlanReviewSubject(
        subject_id=subject_id,
        plan_id=plan.plan_id,
        revision=plan.revision,
        scope=dict(scope),
        requirements_digest=digest(
            _strip_presentation(dict(requirements_doc))
        ),
        work_plan_digest=digest(projection),
        source_snapshot_digest=digest(
            _strip_presentation(dict(source_snapshot))
        ),
        test_plan_digest=digest(
            sorted(u.test_recipe or "" for u in plan.units)
        ),
        budget_cap=plan.budget_cap,
        external_effects=tuple(sorted(plan.external_effects)),
        recovery_ref=plan.rollback,
    )


def subject_digest(subject: PlanReviewSubject) -> str:
    """Canonical digest of the sealed subject."""
    return digest(
        {
            "subject_id": subject.subject_id,
            "plan_id": subject.plan_id,
            "revision": subject.revision,
            "scope": dict(subject.scope),
            "requirements_digest": subject.requirements_digest,
            "work_plan_digest": subject.work_plan_digest,
            "source_snapshot_digest": subject.source_snapshot_digest,
            "test_plan_digest": subject.test_plan_digest,
            "budget_cap": subject.budget_cap,
            "external_effects": sorted(subject.external_effects),
            "recovery_ref": subject.recovery_ref,
        }
    )


def presentation_only_change(
    old: Mapping[str, Any], new: Mapping[str, Any]
) -> bool:
    """True when two plan documents differ only in display fields."""
    return _strip_presentation(dict(old)) == _strip_presentation(dict(new))
