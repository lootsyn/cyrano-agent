"""Independent plan review: separation is run identity, not the model.

A reviewer needs a distinct run id, a read-only tool grant, and an
input that does not carry the author's verdict. The same model may
review — the requirement is separate execution context and separate
evidence, not statistical independence.

Findings bind to a subject digest; a review produced for one subject
can never satisfy another. Authors can answer findings but can never
mark their own finding resolved. A round limit is a budget cap, not
an approval after N rounds.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from deepagents_code.cyrano.contracts.types import CyranoError

BLOCKING = frozenset({"critical", "high"})
FINDING_STATES = frozenset(
    {"open", "fixed_verified", "refuted_verified", "risk_accepted"}
)


@dataclass(frozen=True, slots=True)
class ReviewerBinding:
    """Who reviews and with which isolated input."""

    reviewer_run_id: str
    author_run_id: str
    model_id: str
    author_model_id: str
    read_only: bool
    blind: bool  # author verdict and prior verdicts are excluded


@dataclass(frozen=True, slots=True)
class ReviewFinding:
    """One finding bound to the reviewed subject digest."""

    finding_id: str
    subject_digest: str
    reviewer_run_id: str
    severity: str
    summary: str
    evidence_ids: tuple[str, ...]
    requirement_refs: tuple[str, ...] = ()
    state: str = "open"


@dataclass(slots=True)
class ReviewRecord:
    """One review round for one subject digest."""

    subject_digest: str
    reviewer_run_id: str
    verdict: str  # approve | changes_required | unverifiable
    findings: tuple[ReviewFinding, ...] = ()
    rounds: int = 1


class ReviewBoard:
    """Track review rounds, findings, and their resolutions."""

    def __init__(self, *, max_rounds: int = 3) -> None:
        """Round limit is a cost bound, not an eventual approval."""
        self._max_rounds: int = max_rounds
        self._reviews: list[ReviewRecord] = []
        self._findings: dict[str, ReviewFinding] = {}

    def request_review(
        self,
        subject_digest: str,
        binding: ReviewerBinding,
        *,
        reviewer_input: Mapping[str, Any],
    ) -> ReviewRecord:
        """Open a review round after the independence checks.

        A review fails ``REVIEWER_NOT_INDEPENDENT`` when the reviewer
        run is the author's run, and ``INPUT_INVALID`` when the input
        carries the author's verdict or a prior verdict — a blind
        handoff reviews evidence, not conclusions.
        """
        if binding.reviewer_run_id == binding.author_run_id:
            raise CyranoError(
                "REVIEWER_NOT_INDEPENDENT",
                "reviewer run must differ from the author run",
            )
        if not binding.read_only:
            raise CyranoError(
                "REVIEWER_NOT_INDEPENDENT", "reviewer holds write grant"
            )
        leaked = {
            key
            for key in reviewer_input
            if key in {"author_verdict", "prior_verdict", "author_notes"}
        }
        if binding.blind and leaked:
            raise CyranoError(
                "INPUT_INVALID",
                f"blind review input carries {sorted(leaked)}",
            )
        record = ReviewRecord(
            subject_digest=subject_digest,
            reviewer_run_id=binding.reviewer_run_id,
            verdict="unverifiable",
        )
        self._reviews.append(record)
        return record

    def submit_finding(
        self,
        record: ReviewRecord,
        finding: ReviewFinding,
    ) -> ReviewFinding:
        """Store a finding bound to the reviewed subject digest."""
        if finding.subject_digest != record.subject_digest:
            raise CyranoError(
                "STALE_REVIEW", "finding targets a different subject"
            )
        if finding.severity in BLOCKING and not finding.evidence_ids:
            raise CyranoError(
                "INVALID_FINDING",
                "a blocking finding requires evidence ids",
            )
        self._findings[finding.finding_id] = finding
        object.__setattr__(record, "findings", record.findings + (finding,))
        return finding

    def resolve_finding(
        self,
        finding_id: str,
        resolving_run_id: str,
        decision: str,
        *,
        new_subject_digest: str,
        evidence_ids: tuple[str, ...],
        test_plan_changed: bool = False,
    ) -> ReviewFinding:
        """Close a finding; only the reviewer may close, per revision.

        ``TEST_PLAN_CHANGED`` fires when the fix replaced or removed a
        failing oracle — that is a new subject needing re-review, not
        a resolution.
        """
        finding = self._findings[finding_id]
        if resolving_run_id != finding.reviewer_run_id:
            raise CyranoError(
                "AUTHORITY_DENIED",
                "only the finding reviewer or adjudicator resolves",
            )
        if test_plan_changed:
            raise CyranoError(
                "TEST_PLAN_CHANGED",
                "the oracle changed; the fix is a new subject",
            )
        if decision not in FINDING_STATES - {"open"}:
            raise CyranoError(
                "INVALID_FINDING", f"bad resolution {decision!r}"
            )
        if decision == "fixed_verified" and not evidence_ids:
            raise CyranoError(
                "INVALID_FINDING", "a fix needs verification evidence"
            )
        if decision == "refuted_verified" and not evidence_ids:
            raise CyranoError(
                "INVALID_FINDING", "a rebuttal needs counter-evidence"
            )
        resolved = replace(
            finding,
            state=decision,
            subject_digest=new_subject_digest,
        )
        self._findings[finding_id] = resolved
        return resolved

    def finish_review(
        self, record: ReviewRecord, *, reviewer_ok: bool = True
    ) -> str:
        """Judge the round's outcome; majority never clears a blocker.

        Returns ``reviewed``, ``changes_required``, ``deferred`` or
        ``unverifiable``. ``reviewed`` means presentable to a human —
        it is not an execution permit.
        """
        if not reviewer_ok:
            record.verdict = "unverifiable"
            return "unverifiable"
        open_blocking = [
            f
            for f in record.findings
            if self._findings[f.finding_id].state == "open"
            and f.severity in BLOCKING
        ]
        if record.rounds >= self._max_rounds and open_blocking:
            record.verdict = "changes_required"
            return "deferred"
        if open_blocking:
            record.verdict = "changes_required"
            return "changes_required"
        record.verdict = "approve"
        return "reviewed"

    def is_reviewed(self, subject_digest: str) -> bool:
        """True only for an approved review bound to this digest."""
        return any(
            r.subject_digest == subject_digest and r.verdict == "approve"
            for r in self._reviews
        )

    def require_reviewed(self, subject_digest: str) -> None:
        """Raise ``STALE_REVIEW``/``REVIEW_FINDINGS_OPEN`` as fits."""
        rounds = [
            r for r in self._reviews if r.subject_digest == subject_digest
        ]
        if not rounds:
            raise CyranoError(
                "STALE_REVIEW", "no review binds this subject digest"
            )
        latest = rounds[-1]
        open_blocking = [
            f.finding_id
            for f in latest.findings
            if self._findings[f.finding_id].state == "open"
            and f.severity in BLOCKING
        ]
        if open_blocking:
            raise CyranoError(
                "REVIEW_FINDINGS_OPEN",
                f"unresolved: {open_blocking}",
            )
        if latest.verdict != "approve":
            raise CyranoError(
                "STALE_REVIEW", f"latest verdict is {latest.verdict}"
            )
