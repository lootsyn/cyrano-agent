"""verify_artifact: separated outcomes bound to the verified digest.

A green exit code is not a pass: zero executed checks, a skipped
mandatory case, and a runner failure are distinct outcomes and none of
them is ``verified``. Verification binds to the artifact digest it ran
against — a merged or edited artifact is a new digest and needs fresh
verification. A mandatory check that disappeared from the run is a
tamper finding, not an absent pass.
"""

from __future__ import annotations

import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from deepagents_code.cyrano.contracts.types import CyranoError

CHECK_STATES = frozenset({"passed", "failed", "skipped", "not_run"})
VERDICTS = frozenset(
    {"verified", "failed", "not_run", "unverifiable", "tampered"}
)


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One acceptance check's observed outcome."""

    check_id: str
    status: str
    evidence_ref: str = ""


@dataclass(frozen=True, slots=True)
class VerificationReport:
    """The verdict for exactly one artifact digest."""

    artifact_digest: str
    verdict: str
    results: tuple[CheckResult, ...]
    findings: tuple[str, ...]
    raw_evidence_ref: str | None


@dataclass(frozen=True, slots=True)
class RawRunReport:
    """A test runner's raw output; exit code alone proves nothing."""

    exit_code: int
    results: tuple[CheckResult, ...]
    raw_ref: str
    summary: str


def verify_artifact(
    *,
    artifact_digest: str,
    results: Iterable[CheckResult],
    mandatory: Iterable[str],
    raw_evidence_ref: str | None,
    expected_oracle: Mapping[str, str] | None = None,
) -> VerificationReport:
    """Separate verified/failed/not_run/unverifiable/tampered.

    Args:
        artifact_digest: Digest of the exact artifact that was run.
        results: Per-check outcomes observed by the trusted runner.
        mandatory: Check ids that must execute and pass.
        raw_evidence_ref: Durable raw runner output; without it the
            run is unverifiable rather than passed.
        expected_oracle: ``check_id -> oracle digest`` from the
            approved test plan; a missing or altered oracle is a
            tamper finding.
    """
    checks = tuple(results)
    required = tuple(dict.fromkeys(mandatory))
    if raw_evidence_ref is None:
        return VerificationReport(
            artifact_digest,
            "unverifiable",
            checks,
            ("RAW_EVIDENCE_MISSING",),
            None,
        )
    executed = [c for c in checks if c.status in {"passed", "failed"}]
    if not executed:
        return VerificationReport(
            artifact_digest,
            "not_run",
            checks,
            ("NO_CHECKS_EXECUTED",),
            raw_evidence_ref,
        )
    by_id = {c.check_id: c for c in checks}
    oracle = expected_oracle or {}
    tampered: list[str] = []
    not_run: list[str] = []
    for check_id in required:
        seen = by_id.get(check_id)
        if seen is None:
            if check_id in oracle:
                tampered.append(f"TEST_TAMPERED:{check_id} removed")
            else:
                not_run.append(check_id)
            continue
        expected = oracle.get(check_id)
        if expected is not None and seen.evidence_ref != expected:
            tampered.append(f"TEST_TAMPERED:{check_id} oracle changed")
        elif seen.status in {"skipped", "not_run"}:
            not_run.append(check_id)
    if tampered:
        return VerificationReport(
            artifact_digest,
            "tampered",
            checks,
            tuple(tampered),
            raw_evidence_ref,
        )
    if not_run:
        return VerificationReport(
            artifact_digest,
            "not_run",
            checks,
            tuple(f"MANDATORY_NOT_RUN:{c}" for c in not_run),
            raw_evidence_ref,
        )
    failed = [c.check_id for c in checks if c.status == "failed"]
    if failed:
        return VerificationReport(
            artifact_digest,
            "failed",
            checks,
            tuple(f"CHECK_FAILED:{c}" for c in failed),
            raw_evidence_ref,
        )
    return VerificationReport(
        artifact_digest, "verified", checks, (), raw_evidence_ref
    )


def require_fresh_verification(
    report: VerificationReport,
    current_artifact_digest: str,
    *,
    code: str = "STALE_EVIDENCE",
) -> None:
    """Refuse to reuse a verdict for a different artifact digest."""
    if report.verdict != "verified":
        raise CyranoError("UNVERIFIED", report.verdict)
    if report.artifact_digest != current_artifact_digest:
        raise CyranoError(code, "artifact changed since verification")


def run_test_recipe(
    target: Path,
    *,
    junit_path: Path,
    timeout: int = 120,
) -> RawRunReport:
    """Run pytest and keep the JUnit XML as durable raw evidence.

    The exit code is parsed together with the XML so a red suite, an
    empty collection, an all-skipped run, and a runner error are four
    distinguishable outcomes.
    """
    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--tb=no",
            "-p",
            "no:cacheprovider",
            f"--junit-xml={junit_path}",
            str(target),
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    results: list[CheckResult] = []
    root_el: ET.Element[str] | None = None
    if junit_path.exists():
        try:
            root_el = ET.parse(junit_path).getroot()
        except ET.ParseError:
            root_el = None
    if root_el is not None:
        for case in root_el.iter("testcase"):
            check_id = f"{case.get('classname')}.{case.get('name')}"
            if case.find("failure") is not None:
                status = "failed"
            elif case.find("skipped") is not None:
                status = "skipped"
            elif case.find("error") is not None:
                status = "failed"
            else:
                status = "passed"
            results.append(CheckResult(check_id, status, str(junit_path)))
    summary = proc.stdout.strip().splitlines()[-1] if proc.stdout else ""
    summary = re.sub(r"\s+", " ", summary)[:200]
    return RawRunReport(
        exit_code=proc.returncode,
        results=tuple(results),
        raw_ref=str(junit_path),
        summary=summary,
    )


def report_from_run(
    run: RawRunReport,
    *,
    artifact_digest: str,
    mandatory: Iterable[str],
) -> VerificationReport:
    """Fold a raw run into a verdict; runner errors are not failures.

    pytest exit codes: 0 pass, 1 test failures, 2 interrupted or
    usage error, 3/4 internal errors, 5 no tests collected. A runner
    error makes the run unverifiable even if partial XML exists; an
    empty collection is ``not_run``, not a pass and not a failure.
    """
    if run.exit_code in {2, 3, 4}:
        return VerificationReport(
            artifact_digest,
            "unverifiable",
            run.results,
            ("RUNNER_ERROR", run.summary),
            run.raw_ref,
        )
    return verify_artifact(
        artifact_digest=artifact_digest,
        results=run.results,
        mandatory=mandatory,
        raw_evidence_ref=run.raw_ref,
    )


@dataclass(frozen=True, slots=True)
class CompletionAssessment:
    """What may be claimed; learning and publish stay separate."""

    status: str
    outcome: str
    may_apply: bool
    source_changed: bool
    learning_status: str
    findings: tuple[str, ...]


def assess_run(
    *,
    request_kind: str,
    delivery_mode: str,
    verification: VerificationReport | None,
    reviewed_digest: str | None,
    current_digest: str | None,
    source_changed: bool,
    lesson_status: str = "not_requested",
) -> CompletionAssessment:
    """Judge a finished run from evidence, never from intent.

    ``verified_no_change`` requires a digest proving no change; an
    ``analysis`` request ends at ``answered``; a merged artifact whose
    digest differs from the verified one needs revalidation.
    """
    if request_kind == "analysis":
        return CompletionAssessment(
            "answered",
            "answered",
            False,
            False,
            lesson_status,
            (),
        )
    findings: list[str] = []
    if verification is None:
        return CompletionAssessment(
            "unverifiable",
            "failed",
            False,
            source_changed,
            lesson_status,
            ("VERIFICATION_MISSING",),
        )
    if verification.verdict == "tampered":
        return CompletionAssessment(
            "blocked",
            "failed",
            False,
            source_changed,
            lesson_status,
            verification.findings,
        )
    if verification.verdict in {"not_run", "unverifiable"}:
        return CompletionAssessment(
            "blocked",
            "failed",
            False,
            source_changed,
            lesson_status,
            verification.findings or ("NOT_RUN",),
        )
    if (
        reviewed_digest is not None
        and current_digest is not None
        and reviewed_digest != current_digest
    ):
        raise CyranoError(
            "STALE_EVIDENCE",
            "code changed after the reviewed digest",
        )
    if verification.verdict == "failed":
        return CompletionAssessment(
            "blocked",
            "failed",
            False,
            source_changed,
            lesson_status,
            verification.findings,
        )
    if not source_changed:
        return CompletionAssessment(
            "complete",
            "verified_no_change",
            False,
            False,
            lesson_status,
            (),
        )
    may_apply = delivery_mode == "apply_to_source"
    return CompletionAssessment(
        "complete",
        "changed",
        may_apply,
        source_changed,
        lesson_status,
        tuple(findings),
    )
