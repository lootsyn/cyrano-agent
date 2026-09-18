"""Executable specification helpers; NOT a production authority implementation.

Inputs to readiness are already-verified test facts. A real Broker must compute
those facts from authenticated events, signatures, current scope and evidence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


def canonical_bytes(value: Any) -> bytes:
    """Encode canonical-json-v1, rejecting floats and non-JSON values."""

    def check(item: Any) -> None:
        if item is None or isinstance(item, (str, bool, int)):
            return
        if isinstance(item, list):
            for child in item:
                check(child)
            return
        if isinstance(item, dict):
            if not all(isinstance(key, str) for key in item):
                raise ValueError("NON_STRING_KEY")
            for child in item.values():
                check(child)
            return
        raise ValueError("NON_CANONICAL_VALUE")

    check(value)
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    """Return the SHA-256 digest of a canonical JSON value."""
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


@dataclass(frozen=True)
class VerifiedGateFacts:
    """Synthetic verified facts for a pure readiness oracle, not an API DTO."""

    unresolved: int = 0
    required_review_missing: bool = False
    reviews_current: bool = True
    spec_approved: bool = True
    plan_approved: bool = True
    execution_authorized: bool = True
    scope_valid: bool = True
    audit_healthy: bool = True
    adapter_governed: bool = True
    verification_satisfied: bool = True
    final_review_satisfied: bool = True
    cancelled: bool = False


def readiness(stage: str, facts: VerifiedGateFacts) -> tuple[str, ...]:
    """Return blockers; advisory scores cannot authorize transitions."""
    if stage not in {"spec", "plan", "execution", "completion"}:
        raise ValueError("UNKNOWN_STAGE")
    blockers: list[str] = []
    if facts.cancelled:
        blockers.append("CANCELLED")
    if facts.unresolved:
        blockers.append("UNRESOLVED_OBLIGATION")
    if facts.required_review_missing:
        blockers.append("REQUIRED_REVIEW_MISSING")
    if not facts.reviews_current:
        blockers.append("STALE_REVIEW")
    if stage in {"plan", "execution", "completion"}:
        if not facts.spec_approved:
            blockers.append("SPEC_APPROVAL_REQUIRED")
    if stage in {"execution", "completion"}:
        for passed, code in (
            (facts.plan_approved, "PLAN_APPROVAL_REQUIRED"),
            (facts.execution_authorized, "EXECUTION_APPROVAL_REQUIRED"),
            (facts.scope_valid, "SCOPE_DENIED"),
            (facts.audit_healthy, "AUDIT_UNAVAILABLE"),
            (facts.adapter_governed, "UNSUPPORTED_RUNTIME"),
        ):
            if not passed:
                blockers.append(code)
    if stage == "completion":
        if not facts.verification_satisfied:
            blockers.append("VERIFICATION_MISSING")
        if not facts.final_review_satisfied:
            blockers.append("FINAL_REVIEW_MISSING")
    return tuple(blockers)


def validate_dag(
    dependencies: dict[str, list[str]],
) -> tuple[str, ...]:
    """Reject unknown dependencies and cycles; return topological task IDs."""
    if not dependencies:
        raise ValueError("EMPTY_PLAN")
    done: set[str] = set()
    active: set[str] = set()
    ordered: list[str] = []

    def visit(task_id: str) -> None:
        if task_id not in dependencies:
            raise ValueError("UNKNOWN_DEPENDENCY")
        if task_id in active:
            raise ValueError("INVALID_DAG")
        if task_id in done:
            return
        active.add(task_id)
        for dependency in dependencies[task_id]:
            visit(dependency)
        active.remove(task_id)
        done.add(task_id)
        ordered.append(task_id)

    for task_id in sorted(dependencies):
        visit(task_id)
    return tuple(ordered)


def promotion_blockers(
    verdict: str,
    hard_failures: int,
    receipt_verified: bool,
    parent_matches: bool,
) -> tuple[str, ...]:
    """Evaluate synthetic promotion facts, not actual authorization inputs."""
    result: list[str] = []
    if verdict != "improved":
        result.append("NOT_PROVEN_IMPROVED")
    if hard_failures:
        result.append("HARD_GATE_FAILURE")
    if not receipt_verified:
        result.append("APPROVAL_REQUIRED")
    if not parent_matches:
        result.append("RELEASE_CONFLICT")
    return tuple(result)
