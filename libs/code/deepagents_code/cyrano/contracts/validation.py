"""Semantic consistency checks after JSON Schema validation.

These checks reject contradictory documents. They do not authenticate
evidence, verify signatures, query scope ACLs, or authorize state
transitions.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Mapping

from deepagents_code.cyrano.contracts.types import CyranoError


def _mapping(value: object) -> dict[str, object]:
    """Require a string-keyed mapping at a parsing boundary."""
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise CyranoError("INVALID_DOCUMENT", "expected an object")
    return {str(key): item for key, item in value.items()}


def _items(value: object) -> list[object]:
    """Require a list without silently coercing a missing field."""
    if not isinstance(value, list):
        raise CyranoError("INVALID_DOCUMENT", "expected an array")
    return list(value)


def _integer(value: object) -> int:
    """Exclude bool even though Python bool subclasses int."""
    if type(value) is not int or value < 0:
        raise CyranoError("INVALID_COUNT", "expected nonnegative integer")
    return value


def _decimal(value: object) -> Decimal:
    """Parse finite decimal strings, preserving monetary precision."""
    if not isinstance(value, str):
        raise CyranoError("INVALID_METRIC", "expected a decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise CyranoError("INVALID_METRIC", "not a decimal") from error
    if not parsed.is_finite():
        raise CyranoError("INVALID_METRIC", "finite values are required")
    return parsed


def _aware(value: object) -> datetime:
    """Reject timestamps without a timezone."""
    if not isinstance(value, str):
        raise CyranoError("INVALID_TIME", "expected an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise CyranoError("INVALID_TIME", "invalid ISO timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CyranoError("INVALID_TIME", "timezone required")
    return parsed


def _active_scope(document: Mapping[str, object]) -> None:
    """Forbid placeholders or wildcard scope in active artifacts."""
    scope = _mapping(document.get("scope"))
    for value in scope.values():
        unbound = (
            not isinstance(value, str)
            or not value
            or "__BIND" in value
            or value == "*"
        )
        if unbound:
            raise CyranoError(
                "UNBOUND_SCOPE",
                "bind an exact authorized scope",
            )


def validate_semantics(document: Mapping[str, object]) -> None:
    """Check cross-field consistency; authority stays with broker."""
    kind, status = document.get("kind"), document.get("status")
    if kind == "evaluation_report":
        actual = _integer(document.get("actual_pairs"))
        planned = _integer(document.get("planned_pairs"))
        missing = _integer(document.get("missing_pairs"))
        supported = _integer(document.get("replay_supported"))
        scheduled = _integer(document.get("replay_scheduled"))
        invalid = (
            supported > scheduled
            or actual > planned
            or actual + missing != planned
        )
        if invalid:
            raise CyranoError(
                "INVALID_DENOMINATOR",
                "all planned pairs must remain accounted for",
            )
        if status == "eligible_for_review":
            refs = _items(document.get("execution_refs"))
            failures = _integer(document.get("safety_failures"))
            if actual == 0 or missing or failures:
                raise CyranoError(
                    "INSUFFICIENT_ACTUAL_EVIDENCE",
                    "actual safe complete pairs required",
                )
            distinct = len(set(map(str, refs)))
            if len(refs) < 2 * actual or distinct != len(refs):
                raise CyranoError(
                    "MISSING_EXECUTION_REFS",
                    "each pair needs distinct actual executions",
                )
            if _integer(document.get("independent_families")) == 0:
                raise CyranoError(
                    "INSUFFICIENT_FAMILIES",
                    "declare independently sampled families",
                )
        intervals = _items(document.get("intervals"))
        if status == "eligible_for_review" and not intervals:
            raise CyranoError(
                "MISSING_INTERVALS",
                "declare uncertainty for the preregistered metrics",
            )
        for raw in intervals:
            interval = _mapping(raw)
            values = [
                interval.get(key) for key in ("lower", "estimate", "upper")
            ]
            if any(value is None for value in values):
                if status == "eligible_for_review":
                    raise CyranoError(
                        "UNKNOWN_INTERVAL",
                        "unknown intervals cannot establish eligibility",
                    )
                continue
            low, estimate, high = [_decimal(value) for value in values]
            if not low <= estimate <= high:
                raise CyranoError(
                    "INVALID_INTERVAL",
                    "lower <= estimate <= upper required",
                )
    elif kind == "context_manifest":
        observed = document.get("wire_observed")
        if observed is True and document.get("wire_digest") is None:
            raise CyranoError(
                "MISSING_WIRE_EVIDENCE",
                "an observed wire needs its raw digest",
            )
        if observed is False and document.get("wire_digest") is not None:
            raise CyranoError(
                "FALSE_WIRE_CLAIM",
                "an unobserved wire has no observed hash",
            )
        if (
            document.get("token_count") is not None
            and document.get("token_measurement_source") == "unknown"
        ):
            raise CyranoError(
                "FALSE_TOKEN_PRECISION",
                "byte estimates are not measured tokens",
            )
    elif kind == "memory_record":
        if _aware(document.get("valid_until")) <= _aware(
            document.get("valid_from")
        ):
            raise CyranoError(
                "INVALID_VALIDITY",
                "memory validity interval must be positive",
            )
        if status == "active":
            _active_scope(document)
            evidence = [
                _mapping(item)
                for item in _items(document.get("evidence_refs"))
            ]
            grounded = any(
                item.get("trust") != "model_report" for item in evidence
            )
            if not evidence or not grounded:
                raise CyranoError(
                    "UNGROUNDED_MEMORY",
                    "self-report alone is not active knowledge",
                )
            if document.get("approval_ref") is None:
                raise CyranoError(
                    "MISSING_MEMORY_AUTHORITY",
                    "active memory needs policy/user authority",
                )
    elif kind == "skill_manifest" and status == "active":
        _active_scope(document)
        if (
            document.get("approval_ref") is None
            or document.get("release_digest") is None
        ):
            raise CyranoError(
                "UNAPPROVED_SKILL",
                "active skill requires a verified release",
            )
    elif kind == "plan_bundle" and status in {
        "approved",
        "executing",
        "completed",
    }:
        if document.get("plan_approval_ref") is None or not _items(
            document.get("review_refs")
        ):
            raise CyranoError(
                "UNAPPROVED_PLAN",
                "review and plan authority are separate requirements",
            )
        if (
            status in {"executing", "completed"}
            and document.get("execution_permit_ref") is None
        ):
            raise CyranoError(
                "MISSING_EXECUTION_PERMIT",
                "plan approval alone cannot execute",
            )
    elif kind == "learning_work_plan" and status == "authorized":
        if (
            not _items(document.get("review_refs"))
            or document.get("authorization_ref") is None
        ):
            raise CyranoError(
                "UNREVIEWED_LEARNING_PLAN",
                "review and experiment authority required",
            )
    elif kind == "experiment_plan":
        budget = _mapping(document.get("budget"))
        if _decimal(budget.get("cost_limit")) < 0:
            raise CyranoError(
                "INVALID_BUDGET",
                "cost cap cannot be negative",
            )
        if (
            status in {"authorized", "running", "completed"}
            and document.get("permit_ref") is None
        ):
            raise CyranoError(
                "MISSING_EXPERIMENT_PERMIT",
                "a key in the environment is not authorization",
            )
    elif kind == "harness_release" and status == "active":
        _active_scope(document)
        if (
            document.get("promotion_approval_ref") is None
            or document.get("signature_ref") is None
        ):
            raise CyranoError(
                "UNAPPROVED_RELEASE",
                "trusted release approval/signature required",
            )
    elif (
        kind == "interview_contract"
        and document.get("execution_authorized") is not False
    ):
        raise CyranoError(
            "WRONG_APPROVAL_PURPOSE",
            "interview can authorize planning only",
        )
