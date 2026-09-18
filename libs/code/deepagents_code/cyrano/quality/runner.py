"""Native quality check execution.

Runs real tools (``ruff``, ``ty``, ``pytest``) against an immutable
file snapshot. A tool exit code is never the verdict — diagnostics are
parsed into a typed multiset and compared against baselines.
Unknown external outcomes stay ``ERROR``/``BLOCKED_*``; they are never
coerced to pass.
"""

import hashlib
import json
import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.quality.policy import QualityPolicy
from deepagents_code.cyrano.sqlite.repository import (
    Receipt,
    ScopedRepository,
)

DEFAULT_OUTPUT_LIMIT = 1_048_576
DEFAULT_TIMEOUT_S = 120.0


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One parsed finding; exit codes alone never produce these."""

    path: str
    line: int
    rule: str
    message: str


@dataclass(frozen=True, slots=True)
class FileEntry:
    """Digest-bound file identity inside a snapshot."""

    path: str
    digest: str


@dataclass(frozen=True, slots=True)
class SnapshotManifest:
    """Immutable ordered inventory of snapshotted source files."""

    entries: tuple[FileEntry, ...]

    @property
    def digest(self) -> str:
        """Content digest over the ordered (path, digest) pairs."""
        lines = "".join(f"{e.path}:{e.digest}\n" for e in self.entries)
        return "sha256:" + hashlib.sha256(lines.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class RawCheckReport:
    """Typed outcome of one tool run against one snapshot."""

    status: str  # PASS | FAIL | ERROR_* | BLOCKED_*
    tool: str
    diagnostics: tuple[Diagnostic, ...]
    exit_code: int | None
    raw_digest: str
    snapshot_digest: str


@dataclass(frozen=True, slots=True)
class BaselineDecision:
    """Result of comparing a report's diagnostics to a baseline."""

    decision: str  # PASS | PASS_WITH_BASELINE | FAIL | STALE_BASELINE
    report_status: str


def snapshot_python_files(
    root: Path, scope_patterns: tuple[str, ...] = ("*.py",)
) -> SnapshotManifest:
    """Inventory Python files under root bound by content digest.

    An empty inventory for a Python work scope is ``BLOCKED`` — it is
    never silently a zero-violation pass.
    """
    entries: list[FileEntry] = []
    for path in sorted(root.rglob("*.py")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if not any(
            fnmatch(rel, p) or fnmatch(path.name, p) for p in scope_patterns
        ):
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append(FileEntry(rel, digest))
    if not entries:
        raise CyranoError(
            "BLOCKED", "python work scope contains no governed files"
        )
    return SnapshotManifest(tuple(entries))


def _tool_argv(policy: QualityPolicy, target: str) -> list[str]:
    """Build the real tool invocation for the policy identity."""
    if policy.tool == "ruff":
        argv = ["ruff", "check", "--output-format=json"]
        if policy.select:
            argv += ["--select", ",".join(sorted(policy.select))]
        if policy.line_length:
            argv += ["--line-length", str(policy.line_length)]
        if policy.max_doc_length is not None:
            argv += [
                "--config",
                f"lint.pycodestyle.max-doc-length={policy.max_doc_length}",
            ]
        return [*argv, target]
    if policy.tool == "ruff-format":
        return ["ruff", "format", "--check", target]
    if policy.tool == "ty":
        return ["ty", "check", "--output-format", "concise", target]
    if policy.tool == "basedpyright":
        return ["basedpyright", "--outputjson", target]
    if policy.tool == "pytest":
        return ["pytest", "-q", "--no-header", "-x", target]
    raise CyranoError(
        "CAPABILITY_UNAVAILABLE", f"no adapter for tool {policy.tool}"
    )


def _parse_diagnostics(
    policy: QualityPolicy, stdout: str, root: Path
) -> tuple[Diagnostic, ...]:
    """Parse tool output into diagnostics; never infer from exit."""
    findings: list[Diagnostic] = []
    if policy.tool in {"ruff"}:
        items = json.loads(stdout or "[]")
        if not isinstance(items, list):
            items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            loc = item.get("location") or {}
            rel = os.path.relpath(str(item.get("filename", "")), root)
            findings.append(
                Diagnostic(
                    path=rel,
                    line=int(loc.get("row", 0)),
                    rule=str(item.get("code") or "UNKNOWN"),
                    message=str(item.get("message", "")),
                )
            )
    elif policy.tool in {"ty", "basedpyright"}:
        for line in stdout.splitlines():
            parts = line.split(":", 3)
            if len(parts) >= 3 and parts[1].strip().isdigit():
                findings.append(
                    Diagnostic(
                        path=parts[0].strip(),
                        line=int(parts[1]),
                        rule="typecheck",
                        message=parts[-1].strip(),
                    )
                )
    return tuple(findings)


def run_native_checks(
    manifest: SnapshotManifest,
    policy: QualityPolicy,
    root: Path,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    output_limit: int = DEFAULT_OUTPUT_LIMIT,
    cancel_flag: Callable[[], bool] | None = None,
) -> RawCheckReport:
    """Run the policy's tool against the snapshot and parse results."""
    if cancel_flag is not None and cancel_flag():
        return RawCheckReport(
            "CANCELLED", policy.tool, (), None, "", manifest.digest
        )
    tool = shutil.which(_tool_argv(policy, ".")[0])
    if tool is None:
        raise CyranoError(
            "CAPABILITY_UNAVAILABLE",
            f"tool {policy.tool!r} not on PATH",
        )
    argv = _tool_argv(policy, ".")
    argv[0] = tool
    try:
        proc = subprocess.run(
            argv,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return RawCheckReport(
            "ERROR_RUNNER_LOST",
            policy.tool,
            (),
            None,
            "",
            manifest.digest,
        )
    raw = proc.stdout + proc.stderr
    if len(raw.encode()) > output_limit:
        return RawCheckReport(
            "ERROR_OUTPUT_LIMIT",
            policy.tool,
            (),
            proc.returncode,
            hashlib.sha256(raw.encode()).hexdigest(),
            manifest.digest,
        )
    raw_digest = hashlib.sha256(raw.encode()).hexdigest()
    if policy.tool == "pytest" and proc.returncode == 5:
        return RawCheckReport(
            "BLOCKED_NO_TESTS",
            policy.tool,
            (),
            proc.returncode,
            raw_digest,
            manifest.digest,
        )
    diagnostics = _parse_diagnostics(policy, proc.stdout, root)
    if proc.returncode not in (0, 1) and not diagnostics:
        return RawCheckReport(
            "ERROR_TOOL_PROTOCOL",
            policy.tool,
            (),
            proc.returncode,
            raw_digest,
            manifest.digest,
        )
    status = "PASS" if proc.returncode == 0 else "FAIL"
    return RawCheckReport(
        status,
        policy.tool,
        diagnostics,
        proc.returncode,
        raw_digest,
        manifest.digest,
    )


def attempt_outcome(reports: list[RawCheckReport]) -> str:
    """``COMPLETE`` only when every report is a verified pass.

    A ``FAIL``, ``ERROR_*``, ``BLOCKED_*`` or ``CANCELLED`` report can
    never be averaged away by other passes.
    """
    if not reports:
        return "INCOMPLETE"
    for report in reports:
        if report.status != "PASS":
            return "INCOMPLETE"
    return "COMPLETE"


def compare_diagnostic_multisets(
    report: RawCheckReport,
    baseline: tuple[Diagnostic, ...] | None,
    baseline_snapshot_digest: str | None = None,
) -> BaselineDecision:
    """Compare parsed diagnostics against the stored baseline.

    A raw ``FAIL`` equal to the baseline is ``PASS_WITH_BASELINE`` —
    the raw result is preserved, never rewritten. Equal counts with a
    different multiset are still ``FAIL``. A baseline bound to a
    different snapshot digest is ``STALE_BASELINE``.
    """
    if baseline is None:
        return BaselineDecision(
            "PASS"
            if report.status == "PASS"
            else report.status
            if report.status != "FAIL"
            else "FAIL",
            report.status,
        )
    if (
        baseline_snapshot_digest is not None
        and baseline_snapshot_digest != report.snapshot_digest
    ):
        return BaselineDecision("STALE_BASELINE", report.status)
    current = sorted((d.path, d.line, d.rule) for d in report.diagnostics)
    base = sorted((d.path, d.line, d.rule) for d in baseline)
    if current == base:
        return BaselineDecision(
            "PASS_WITH_BASELINE" if report.status == "FAIL" else "PASS",
            report.status,
        )
    return BaselineDecision("FAIL", report.status)


class QualityReportStore:
    """Ledger-bound report store with idempotency and CAS semantics.

    Submission goes through ``ScopedRepository.execute_command``, so a
    replayed report returns ``idempotent_replay`` without a new event,
    a conflicting payload under the same key is
    ``IDEMPOTENCY_CONFLICT``, and a stale ``expected_revision`` is a
    CAS refusal with no success event.
    """

    def __init__(
        self,
        repository: ScopedRepository,
        scope_id: str,
        stream_id: str,
    ) -> None:
        """Bind the store to a scoped ledger stream."""
        self._repo: ScopedRepository = repository
        self._scope_id: str = scope_id
        self._stream_id: str = stream_id
        self._trusted_sources: dict[str, str] = {}

    def register_source(self, report_id: str, source_identity: str) -> None:
        """Pin a report id to the identity that may write it."""
        existing = self._trusted_sources.get(report_id)
        if existing is not None and existing != source_identity:
            raise CyranoError(
                "TRUST_MISMATCH",
                f"report {report_id} bound to another source",
            )
        self._trusted_sources[report_id] = source_identity

    def submit(
        self,
        report_id: str,
        report: RawCheckReport,
        *,
        actor: str,
        idempotency_key: str,
        expected_revision: int,
        source_identity: str,
    ) -> Receipt:
        """Submit a report through the ledger command path."""
        self.register_source(report_id, source_identity)
        payload = {
            "status": report.status,
            "tool": report.tool,
            "raw_digest": report.raw_digest,
            "snapshot_digest": report.snapshot_digest,
            "diagnostics": [
                [d.path, d.line, d.rule] for d in report.diagnostics
            ],
        }
        return self._repo.execute_command(
            self._scope_id,
            actor,
            "quality.report",
            idempotency_key,
            payload,
            self._stream_id,
            expected_revision,
        )
