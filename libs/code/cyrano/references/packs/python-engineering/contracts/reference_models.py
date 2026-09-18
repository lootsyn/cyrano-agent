"""Validate quality wire contracts, not runtime authority or tool execution."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    model_validator,
)

Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
OpaqueId = Annotated[str, Field(min_length=1, max_length=128)]
NonNegative = Annotated[StrictInt, Field(ge=0)]
RawStatus = Literal["PASS", "FAIL", "ERROR", "BLOCKED", "SKIPPED"]
GateVerdict = Literal[
    "PASS", "PASS_WITH_BASELINE", "FAIL", "ERROR", "BLOCKED", "STALE"
]


def validate_relative_path(value: str) -> str:
    """Reject unsafe or ambiguous repository-relative root paths."""
    if value == ".":
        return value
    if not value or value.startswith("/") or "\\" in value or ":" in value:
        raise ValueError("A root must be a relative POSIX path.")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError("Empty, dot, and parent path segments are forbidden.")
    if any(ord(character) < 32 for character in value):
        raise ValueError("Control characters are unsupported in root paths.")
    return value


RelativePath = Annotated[str, AfterValidator(validate_relative_path)]


class Contract(BaseModel):
    """Reject unknown fields and prevent accidental model mutation."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1.0"] = "1.0"


class QualityPolicy(Contract):
    """Describe repository quality choices without granting any approval."""

    policy_id: OpaqueId
    style_profile: Literal["team88-doc72", "pep8-79-doc72"]
    python_version: Annotated[str, Field(pattern=r"^3\.[0-9]+$")]
    formatter: Literal["black"] = "black"
    type_checker: Literal["mypy", "pyright"]
    mode: Literal["clean", "legacy"]
    source_roots: Annotated[tuple[RelativePath, ...], Field(min_length=1)]
    test_roots: tuple[RelativePath, ...]
    required_check_ids: Annotated[tuple[OpaqueId, ...], Field(min_length=1)]
    max_repair_rounds: Annotated[StrictInt, Field(ge=0, le=10)] = 3
    max_external_retries: Annotated[StrictInt, Field(ge=0, le=3)] = 1
    max_no_progress: Annotated[StrictInt, Field(ge=1, le=10)] = 2

    @model_validator(mode="after")
    def validate_collections(self) -> Self:
        """Require nonduplicated roots and required checks."""
        for values in (
            self.source_roots,
            self.test_roots,
            self.required_check_ids,
        ):
            if len(values) != len(set(values)):
                raise ValueError("Duplicate roots or required checks.")
        essentials = {"policy_guard", "inventory", "format", "lint", "type"}
        if not essentials.issubset(self.required_check_ids):
            raise ValueError("The Python policy is missing essential checks.")
        return self


class CheckResult(Contract):
    """Preserve raw execution status and separate legacy matching."""

    check_id: OpaqueId
    tool: OpaqueId
    raw_status: RawStatus
    exit_code: StrictInt | None
    diagnostic_count: NonNegative
    baseline_covered: StrictBool = False
    baseline_comparison_digest: Digest | None = None
    duration_ms: NonNegative
    stdout_digest: Digest | None
    stderr_digest: Digest | None
    receipt_id: OpaqueId | None
    executed: StrictBool

    @model_validator(mode="after")
    def validate_execution(self) -> Self:
        """Reject contradictory execution and baseline claims."""
        if not self.executed:
            if self.exit_code is not None:
                raise ValueError("Unexecuted checks cannot have an exit code.")
            if self.raw_status not in {"BLOCKED", "SKIPPED"}:
                raise ValueError("Unexecuted checks cannot claim execution.")
        elif self.receipt_id is None:
            raise ValueError("Executed checks require a receipt reference.")
        if self.raw_status == "PASS" and self.exit_code != 0:
            raise ValueError("PASS requires exit code zero.")
        if self.baseline_covered:
            if self.raw_status != "FAIL":
                raise ValueError("Only a raw failure may be baseline-covered.")
            if self.baseline_comparison_digest is None:
                raise ValueError("Baseline coverage requires comparison evidence.")
            if self.check_id not in {"format", "lint", "type"}:
                raise ValueError("This version permits only static-check debt.")
            if not self.executed:
                raise ValueError("An unexecuted check cannot be baseline-covered.")
        elif self.baseline_comparison_digest is not None:
            raise ValueError("Unexpected baseline comparison on an uncovered check.")
        return self


def derive_verdict(
    required_check_ids: tuple[str, ...],
    checks: tuple[CheckResult, ...],
    snapshot_before: str,
    snapshot_after: str,
) -> GateVerdict:
    """Derive a structural verdict; receipt authenticity is external."""
    if snapshot_before != snapshot_after:
        return "STALE"
    if not required_check_ids or len(set(required_check_ids)) != len(
        required_check_ids
    ):
        return "BLOCKED"
    by_id = {check.check_id: check for check in checks}
    if len(by_id) != len(checks):
        return "BLOCKED"
    present = [by_id[key] for key in required_check_ids if key in by_id]
    if any(check.raw_status == "ERROR" for check in present):
        return "ERROR"
    if len(present) != len(required_check_ids):
        return "BLOCKED"
    if any(check.raw_status in {"BLOCKED", "SKIPPED"} for check in present):
        return "BLOCKED"
    if any(
        check.raw_status == "FAIL" and not check.baseline_covered
        for check in present
    ):
        return "FAIL"
    if any(check.baseline_covered for check in present):
        return "PASS_WITH_BASELINE"
    return "PASS"


class QualityReport(Contract):
    """Hold a report whose declared verdict agrees with its contents."""

    report_id: OpaqueId
    workspace_id: OpaqueId
    attempt_id: OpaqueId
    plan_digest: Digest
    policy_digest: Digest
    toolchain_digest: Digest
    suite_digest: Digest
    snapshot_before: Digest
    snapshot_after: Digest
    required_check_ids: Annotated[tuple[OpaqueId, ...], Field(min_length=1)]
    checks: tuple[CheckResult, ...]
    verdict: GateVerdict
    verification_level: Literal["local_advisory", "governed"]
    created_at: datetime

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        """Check timestamp, duplicates, and the claimed verdict."""
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must include a timezone.")
        check_ids = [check.check_id for check in self.checks]
        if len(check_ids) != len(set(check_ids)):
            raise ValueError("Duplicate check results.")
        if len(self.required_check_ids) != len(set(self.required_check_ids)):
            raise ValueError("Duplicate required checks.")
        actual = derive_verdict(
            self.required_check_ids,
            self.checks,
            self.snapshot_before,
            self.snapshot_after,
        )
        if self.verdict != actual:
            raise ValueError(f"Claimed verdict disagrees with reducer: {actual}.")
        return self


class CompletionRequirement(Contract):
    """Mirror requirements fetched from a trusted controller, not the model."""

    workspace_id: OpaqueId
    attempt_id: OpaqueId
    plan_digest: Digest
    policy_digest: Digest
    toolchain_digest: Digest
    suite_digest: Digest
    approved_snapshot_digest: Digest
    required_check_ids: Annotated[tuple[OpaqueId, ...], Field(min_length=1)]
    allow_baseline: StrictBool
    review_snapshot_digest: Digest
    review_disposition: Literal["approve", "request_changes", "blocked"]
    review_open_blockers: NonNegative

    @model_validator(mode="after")
    def validate_required_checks(self) -> Self:
        """Prevent duplicate check requirements."""
        if len(self.required_check_ids) != len(set(self.required_check_ids)):
            raise ValueError("Duplicate required checks.")
        return self


def structural_completion_rejections(
    requirement: CompletionRequirement,
    report: QualityReport,
) -> tuple[str, ...]:
    """Return binding errors, without claiming authority to complete work.

    The caller must additionally authenticate receipts, review/permit
    provenance, workspace revision, cancellation, and atomic state change.
    Neither a report field nor this pure function grants those powers.
    """
    reasons: list[str] = []
    for field in (
        "workspace_id",
        "attempt_id",
        "plan_digest",
        "policy_digest",
        "toolchain_digest",
        "suite_digest",
    ):
        if getattr(requirement, field) != getattr(report, field):
            reasons.append(f"MISMATCH_{field.upper()}")
    if report.snapshot_after != requirement.approved_snapshot_digest:
        reasons.append("MISMATCH_SNAPSHOT")
    if set(requirement.required_check_ids) != set(report.required_check_ids):
        reasons.append("MISMATCH_REQUIRED_CHECKS")
    if report.verification_level != "governed":
        reasons.append("LOCAL_ADVISORY_ONLY")
    if report.verdict not in {"PASS", "PASS_WITH_BASELINE"}:
        reasons.append("GATE_NOT_ACCEPTED")
    if report.verdict == "PASS_WITH_BASELINE" and not requirement.allow_baseline:
        reasons.append("BASELINE_NOT_AUTHORIZED")
    if requirement.review_disposition != "approve":
        reasons.append("REVIEW_NOT_APPROVED")
    if requirement.review_open_blockers != 0:
        reasons.append("REVIEW_HAS_BLOCKERS")
    if requirement.review_snapshot_digest != report.snapshot_after:
        reasons.append("STALE_REVIEW")
    return tuple(reasons)
