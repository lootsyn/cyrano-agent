"""Obligation projection: eligible ``scope_rule`` memories.

A ``scope_rule`` memory is data, never authority. It becomes a work
obligation only through this projection, which reuses the recall
eligibility order — scope, active status, expiry, source freshness,
evidence, revocation — and binds the exact revision, a declarative
applicability selector, exception clauses and a trusted checker id
into each obligation. The selector is data: it is matched against
work-unit paths by ``fnmatch`` and can never execute. Projected
obligations link into ``WorkUnitSpec.requirement_ids`` /
``acceptance_ids`` so the sealed ``work_plan_digest`` covers them;
no field signatures change. Human/model-readable text derived from
these objects is explanatory only — enforcement lives in the plan,
permit, broker and checker path.
"""

from __future__ import annotations

import fnmatch
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from deepagents_code.cyrano.context.binding import (
    MemoryView,
    memory_entry_usable,
)
from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError

if TYPE_CHECKING:
    from deepagents_code.cyrano.memory.models import MemoryRecord
    from deepagents_code.cyrano.planning.subject import GovernedWorkPlan

#: The governed knowledge kind eligible for obligation projection.
RULE_KIND = "scope_rule"

#: Closed operation vocabulary for declarative selectors.
OPERATIONS = frozenset({"create", "modify", "rename", "delete", "repair"})

_SPEC_KEYS = frozenset(
    {"rule_id", "checker_id", "applicability", "exceptions", "summary"}
)
_SELECTOR_KEYS = frozenset({"write_globs", "operations"})
_EXCEPTION_KEYS = frozenset({"exception_id", "path_globs"})


@dataclass(frozen=True, slots=True)
class RuleSelector:
    """Declarative applicability; matched against paths, never run."""

    write_globs: tuple[str, ...] = ()
    operations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RuleException:
    """An exception clause holding while its paths go untouched."""

    exception_id: str
    path_globs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScopeRuleSpec:
    """The validated declarative body of a ``scope_rule`` memory."""

    rule_id: str
    checker_id: str
    selector: RuleSelector
    exceptions: tuple[RuleException, ...]
    summary: str


@dataclass(frozen=True, slots=True)
class RuleObligation:
    """A governed rule bound to revision, selector and checker."""

    obligation_id: str
    memory_id: str
    revision: int
    scope_id: str
    checker_id: str
    checker_digest: str
    spec: ScopeRuleSpec
    requirement_id: str
    acceptance_id: str
    provenance: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ObligationProjection:
    """Projection output: obligations plus honest exclusion reasons."""

    obligations: tuple[RuleObligation, ...]
    excluded: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class ObligationAttachment:
    """A plan rewritten with obligation linkage, plus unbound items."""

    plan: GovernedWorkPlan
    attached: tuple[tuple[str, str], ...]
    unattached: tuple[RuleObligation, ...]


def _str_tuple(value: object, *, field: str) -> tuple[str, ...]:
    """A selector field is a sequence of strings or it is invalid."""
    if not isinstance(value, (list, tuple)):
        raise CyranoError("INPUT_INVALID", f"{field} must be a list")
    items = tuple(str(v) for v in value)
    if any(not isinstance(v, str) or not v for v in value):
        raise CyranoError("INPUT_INVALID", f"{field} holds non-strings")
    return items


def parse_scope_rule(content: object) -> ScopeRuleSpec:
    """Validate a declarative rule body; executable content impossible.

    The body is a mapping with a closed key set. ``applicability``
    holds only glob and operation lists — any other key, a string
    instead of a mapping, or a non-sequence value is refused, so a
    proposal can never smuggle code through the selector.
    """
    if isinstance(content, bytes):
        try:
            content = json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise CyranoError(
                "INPUT_INVALID", f"scope_rule body is not JSON: {exc}"
            ) from exc
    if not isinstance(content, Mapping):
        raise CyranoError("INPUT_INVALID", "scope_rule body must be a mapping")
    unknown = set(content) - _SPEC_KEYS
    if unknown:
        raise CyranoError(
            "INPUT_INVALID", f"scope_rule unknown keys {sorted(unknown)}"
        )
    rule_id = content.get("rule_id")
    checker_id = content.get("checker_id")
    if not isinstance(rule_id, str) or not rule_id:
        raise CyranoError("INPUT_INVALID", "scope_rule needs rule_id")
    if not isinstance(checker_id, str) or not checker_id:
        raise CyranoError("INPUT_INVALID", "scope_rule needs checker_id")
    applicability = content.get("applicability", {})
    if not isinstance(applicability, Mapping):
        raise CyranoError("INPUT_INVALID", "applicability must be a mapping")
    unknown = set(applicability) - _SELECTOR_KEYS
    if unknown:
        raise CyranoError(
            "INPUT_INVALID",
            f"applicability unknown keys {sorted(unknown)}",
        )
    write_globs = _str_tuple(
        applicability.get("write_globs", ()), field="write_globs"
    )
    operations = _str_tuple(
        applicability.get("operations", ()), field="operations"
    )
    bad_ops = set(operations) - OPERATIONS
    if bad_ops:
        raise CyranoError(
            "INPUT_INVALID", f"operations {sorted(bad_ops)} unsupported"
        )
    exceptions: list[RuleException] = []
    raw_exceptions = content.get("exceptions", ())
    if not isinstance(raw_exceptions, (list, tuple)):
        raise CyranoError("INPUT_INVALID", "exceptions must be a list")
    for index, item in enumerate(raw_exceptions):
        if not isinstance(item, Mapping):
            raise CyranoError(
                "INPUT_INVALID", f"exception {index} must be a mapping"
            )
        unknown = set(item) - _EXCEPTION_KEYS
        if unknown:
            raise CyranoError(
                "INPUT_INVALID",
                f"exception unknown keys {sorted(unknown)}",
            )
        exception_id = item.get("exception_id")
        if not isinstance(exception_id, str) or not exception_id:
            raise CyranoError("INPUT_INVALID", "exception needs exception_id")
        exceptions.append(
            RuleException(
                exception_id=exception_id,
                path_globs=_str_tuple(
                    item.get("path_globs", ()), field="path_globs"
                ),
            )
        )
    summary = content.get("summary", "")
    if not isinstance(summary, str):
        raise CyranoError("INPUT_INVALID", "summary must be a string")
    return ScopeRuleSpec(
        rule_id=rule_id,
        checker_id=checker_id,
        selector=RuleSelector(write_globs=write_globs, operations=operations),
        exceptions=tuple(exceptions),
        summary=summary,
    )


def is_scope_rule(record: MemoryRecord) -> bool:
    """A record is a scope rule by exact or namespaced kind."""
    return record.kind == RULE_KIND or record.kind.startswith(RULE_KIND + ".")


def obligation_requirement_id(memory_id: str, revision: int) -> str:
    """Requirement id a projected rule adds to a plan and unit."""
    return f"RULE:{memory_id}:r{revision}"


def obligation_acceptance_id(
    memory_id: str, revision: int, checker_id: str
) -> str:
    """Acceptance id binding the rule revision to its checker."""
    return f"RULE:{memory_id}:r{revision}:{checker_id}"


def project_obligations(
    records: list[MemoryRecord],
    *,
    scope_id: str,
    now: int,
    available_source_digests: frozenset[str],
    rule_bodies: Mapping[str, bytes] | None = None,
    memory_view: MemoryView | None = None,
    checker_digests: Mapping[str, str] | None = None,
) -> ObligationProjection:
    """Project eligible ``scope_rule`` records into obligations.

    The eligibility order mirrors ``select_recall``: cross-scope
    records leave no trace; inactive, expired, stale-source,
    evidence-less, revoked, malformed or uncheckable rules are
    excluded with their reason. ``rule_bodies`` carries the scoped
    repository's content per memory id — bodies are access
    controlled, never read inside this pure projection. Each active
    record projects at most one obligation — running projection
    twice changes nothing.
    """
    checkers = dict(checker_digests or {})
    bodies = dict(rule_bodies or {})
    obligations: list[RuleObligation] = []
    excluded: list[tuple[str, str]] = []
    seen: set[str] = set()
    for record in sorted(records, key=lambda r: r.memory_id):
        if record.scope_id != scope_id:
            continue
        if not is_scope_rule(record):
            continue
        if record.memory_id in seen:
            continue
        seen.add(record.memory_id)
        reason: str | None = None
        if record.status != "active":
            reason = f"inactive:{record.status}"
        elif record.expires_at is not None and now >= record.expires_at:
            reason = "expired"
        elif record.source_digest not in available_source_digests:
            reason = "stale_source"
        elif not record.evidence_refs:
            reason = "no_evidence"
        elif memory_view is not None and not memory_entry_usable(
            record.memory_id, memory_view
        ):
            reason = "revoked"
        spec: ScopeRuleSpec | None = None
        if reason is None:
            body = bodies.get(record.memory_id)
            if body is None:
                reason = "no_rule_body"
            else:
                try:
                    spec = parse_scope_rule(body)
                except CyranoError as exc:
                    reason = f"invalid_rule:{exc.code}"
        if (
            reason is None
            and spec is not None
            and spec.checker_id not in checkers
        ):
            reason = "checker_unresolved"
        if reason is not None:
            excluded.append((record.memory_id, reason))
            continue
        assert spec is not None
        oid = digest(
            {
                "memory_id": record.memory_id,
                "revision": record.revision,
                "checker_id": spec.checker_id,
                "scope_id": record.scope_id,
            }
        )
        obligations.append(
            RuleObligation(
                obligation_id=oid,
                memory_id=record.memory_id,
                revision=record.revision,
                scope_id=record.scope_id,
                checker_id=spec.checker_id,
                checker_digest=checkers[spec.checker_id],
                spec=spec,
                requirement_id=obligation_requirement_id(
                    record.memory_id, record.revision
                ),
                acceptance_id=obligation_acceptance_id(
                    record.memory_id, record.revision, spec.checker_id
                ),
                provenance=(
                    record.source_digest,
                    *record.evidence_refs,
                ),
            )
        )
    return ObligationProjection(tuple(obligations), tuple(excluded))


def applies_to_paths(selector: RuleSelector, paths: tuple[str, ...]) -> bool:
    """A selector with no globs is workspace-wide; else fnmatch."""
    if not selector.write_globs:
        return True
    return any(
        fnmatch.fnmatchcase(path, glob)
        for path in paths
        for glob in selector.write_globs
    )


def attach_obligations(
    plan: GovernedWorkPlan,
    obligations: tuple[RuleObligation, ...],
    *,
    targets: Mapping[str, tuple[str, ...]] | None = None,
) -> ObligationAttachment:
    """Link obligations into requirement/acceptance ids.

    An obligation whose selector matches no unit is returned
    ``unattached`` — the caller amends the plan or drops the rule;
    a declared requirement with no covering unit still fails
    ``requirement_coverage`` at validation.
    """
    explicit = dict(targets or {})
    attached: list[tuple[str, str]] = []
    unattached: list[RuleObligation] = []
    requirement_ids = set(plan.requirements)
    units = {u.unit_id: u for u in plan.units}
    for obligation in obligations:
        if obligation.obligation_id in explicit:
            unit_ids = tuple(explicit[obligation.obligation_id])
        else:
            unit_ids = tuple(
                u.unit_id
                for u in plan.units
                if applies_to_paths(obligation.spec.selector, u.write_paths)
            )
        bound = [uid for uid in dict.fromkeys(unit_ids) if uid in units]
        if not bound:
            unattached.append(obligation)
            continue
        requirement_ids.add(obligation.requirement_id)
        for uid in bound:
            unit = units[uid]
            reqs = tuple(
                dict.fromkeys(
                    (*unit.requirement_ids, obligation.requirement_id)
                )
            )
            accs = tuple(
                dict.fromkeys((*unit.acceptance_ids, obligation.acceptance_id))
            )
            units[uid] = replace(
                unit, requirement_ids=reqs, acceptance_ids=accs
            )
            attached.append((obligation.obligation_id, uid))
    new_plan = replace(
        plan,
        requirements=tuple(sorted(requirement_ids)),
        units=tuple(units[u.unit_id] for u in plan.units),
    )
    return ObligationAttachment(new_plan, tuple(attached), tuple(unattached))


def missing_obligations(
    plan: GovernedWorkPlan, obligations: tuple[RuleObligation, ...]
) -> tuple[RuleObligation, ...]:
    """Applicable obligations the plan silently dropped."""
    return tuple(
        o for o in obligations if o.requirement_id not in plan.requirements
    )


def obligations_requirements_doc(
    obligations: tuple[RuleObligation, ...],
) -> dict[str, dict[str, dict[str, object]]]:
    """Obligation metadata for the requirements doc sealing.

    Merge this mapping into ``requirements_doc`` before
    ``build_subject`` so ``requirements_digest`` binds each
    obligation's revision and checker content digest into the
    approved subject — a later checker swap breaks the permit.
    """
    return {
        "obligations": {
            o.obligation_id: {
                "memory_id": o.memory_id,
                "revision": o.revision,
                "checker_id": o.checker_id,
                "checker_digest": o.checker_digest,
                "requirement_id": o.requirement_id,
                "acceptance_id": o.acceptance_id,
                "provenance": list(o.provenance),
            }
            for o in sorted(obligations, key=lambda o: o.obligation_id)
        }
    }


def released_exceptions(
    spec: ScopeRuleSpec, touched_paths: tuple[str, ...]
) -> frozenset[str]:
    """Exception ids whose covered paths the bundle touched."""
    released: set[str] = set()
    for exception in spec.exceptions:
        if any(
            fnmatch.fnmatchcase(path, glob)
            for path in touched_paths
            for glob in exception.path_globs
        ):
            released.add(exception.exception_id)
    return frozenset(released)


def assert_obligations_current(
    obligations: tuple[RuleObligation, ...],
    *,
    is_current: Callable[[str, int], bool],
    memory_view: MemoryView | None = None,
) -> None:
    """Fail closed before dispatch when a bound rule moved.

    A rule revised, superseded or revoked after plan approval is
    never silently upgraded: the bound revision must still be the
    live one and still servable in the pinned view, else the caller
    takes the existing rebind/replan path.
    """
    for obligation in obligations:
        if memory_view is not None and not memory_entry_usable(
            obligation.memory_id, memory_view
        ):
            raise CyranoError(
                "MEMORY_REVOKED",
                f"rule {obligation.memory_id} revoked in pinned view",
            )
        if not is_current(obligation.memory_id, obligation.revision):
            raise CyranoError(
                "STALE_REVISION",
                f"rule {obligation.memory_id} moved past "
                f"r{obligation.revision}",
            )
