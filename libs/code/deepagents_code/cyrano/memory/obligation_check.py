"""Obligation verification and bounded-correction evidence.

``verify_obligations`` is the only path from a projected rule to an
application claim: it re-checks the bound revision, re-checks the
pinned view, resolves the checker through the trusted registry and
evaluates the post-apply workspace state. A model assertion that it
followed the rule is never an input — only deterministic evidence
counts. ``CorrectionTracker`` keeps the first failure immutable,
gates retries inside the unit's cost cap, and records the corrected
outcome and its extra cost separately.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from deepagents_code.cyrano.context.binding import (
    MemoryView,
    memory_entry_usable,
)
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.memory.checkers import (
    CheckerVerdict,
    TrustedCheckerRegistry,
    evaluate,
)
from deepagents_code.cyrano.memory.obligations import (
    RuleObligation,
    released_exceptions,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class ObligationCheckReport:
    """One obligation's verification outcome plus evidence."""

    obligation_id: str
    memory_id: str
    verdict: CheckerVerdict


@dataclass(frozen=True, slots=True)
class AttemptCost:
    """Measured correction cost in caller-defined budget units."""

    model_calls: int = 0
    tokens: int = 0
    latency_ms: int = 0
    retries: int = 0
    units: int = 0


@dataclass(frozen=True, slots=True)
class CorrectionLedger:
    """First failure, each correction attempt, and separate cost."""

    obligation_id: str
    first_failure: ObligationCheckReport | None
    attempts: tuple[tuple[ObligationCheckReport, AttemptCost], ...]
    outcome: str  # satisfied | open | corrected | budget_exhausted
    spent_units: int


def _covered_paths(
    obligation: RuleObligation,
    root: Path,
    released: frozenset[str],
) -> frozenset[str]:
    """Concrete paths protected by still-held exception clauses."""
    covered: set[str] = set()
    for exception in obligation.spec.exceptions:
        if exception.exception_id in released:
            continue
        for glob in exception.path_globs:
            covered.update(
                path.relative_to(root).as_posix() for path in root.glob(glob)
            )
    return frozenset(covered)


def verify_obligations(
    obligations: tuple[RuleObligation, ...],
    *,
    registry: TrustedCheckerRegistry,
    root: Path,
    touched_paths: tuple[str, ...],
    is_current: Callable[[str, int], bool] | None = None,
    memory_view: MemoryView | None = None,
) -> tuple[ObligationCheckReport, ...]:
    """Verify each obligation against post-apply state; fail closed.

    A revoked entry, a moved revision, an unknown or digest-mismatched
    checker and an evaluator error all produce ``unverifiable`` —
    the honest bucket, never a pass. Exception clauses hold only for
    untouched paths, so a grandfathered legacy file is skipped while
    the same file touched forfeits the clause.
    """
    reports: list[ObligationCheckReport] = []
    for obligation in obligations:
        verdict: CheckerVerdict | None = None
        if memory_view is not None and not memory_entry_usable(
            obligation.memory_id, memory_view
        ):
            verdict = CheckerVerdict(
                "unverifiable",
                f"MEMORY_REVOKED {obligation.memory_id}",
            )
        elif is_current is not None and not is_current(
            obligation.memory_id, obligation.revision
        ):
            verdict = CheckerVerdict(
                "unverifiable",
                f"STALE_REVISION {obligation.memory_id}"
                f" r{obligation.revision}",
            )
        if verdict is None:
            try:
                spec = registry.resolve(
                    obligation.checker_id, obligation.checker_digest
                )
            except CyranoError as exc:
                verdict = CheckerVerdict("unverifiable", f"{exc.code} {exc}")
            else:
                released = released_exceptions(obligation.spec, touched_paths)
                covered = _covered_paths(obligation, root, released)
                verdict = evaluate(
                    spec,
                    root=root,
                    touched_paths=touched_paths,
                    covered_paths=covered,
                )
        reports.append(
            ObligationCheckReport(
                obligation.obligation_id,
                obligation.memory_id,
                verdict,
            )
        )
    return tuple(reports)


def obligations_satisfied(
    reports: tuple[ObligationCheckReport, ...],
) -> bool:
    """True only when every obligation's checker is satisfied."""
    return all(r.verdict.state == "satisfied" for r in reports)


class CorrectionTracker:
    """Separate first-failure, correction, and cost evidence."""

    def __init__(self) -> None:
        """Start with no failures and no attempts."""
        self._ledgers: dict[str, CorrectionLedger] = {}

    def record_outcome(
        self, obligation_id: str, report: ObligationCheckReport
    ) -> CorrectionLedger:
        """Record the first verdict; failure opens the ledger.

        A first-pass success lands as ``satisfied`` with no failure
        record; a failure is pinned as ``first_failure`` and can
        never be overwritten by a later correction.
        """
        ledger = self._ledgers.get(obligation_id)
        if ledger is not None:
            return ledger
        if report.verdict.state == "satisfied":
            ledger = CorrectionLedger(obligation_id, None, (), "satisfied", 0)
        else:
            ledger = CorrectionLedger(obligation_id, report, (), "open", 0)
        self._ledgers[obligation_id] = ledger
        return ledger

    def may_correct(self, obligation_id: str, *, cost_cap: int | None) -> bool:
        """True while the unit's cost cap still has headroom.

        No cap means no bound — an unbounded correction is refused
        the same way ``validate_plan`` refuses an unbounded budget.
        """
        if cost_cap is None:
            return False
        ledger = self._ledgers.get(obligation_id)
        if ledger is None or ledger.outcome != "open":
            return False
        return ledger.spent_units < cost_cap

    def record_attempt(
        self,
        obligation_id: str,
        report: ObligationCheckReport,
        cost: AttemptCost,
        *,
        cost_cap: int | None,
    ) -> CorrectionLedger:
        """Append a bounded correction attempt; never rewrite history.

        The caller asks ``may_correct`` first; an attempt recorded
        anyway still consumes budget and lands as
        ``budget_exhausted`` when the cap is crossed, so overrun
        evidence is preserved rather than silently dropped.
        """
        ledger = self._ledgers.get(obligation_id)
        if ledger is None:
            raise CyranoError(
                "INPUT_INVALID",
                f"no open failure for {obligation_id}",
            )
        if ledger.outcome not in {"open", "budget_exhausted"}:
            raise CyranoError(
                "INPUT_INVALID",
                f"ledger {obligation_id} is {ledger.outcome}",
            )
        spent = ledger.spent_units + cost.units
        attempts = (*ledger.attempts, (report, cost))
        if report.verdict.state == "satisfied":
            outcome = "corrected"
        elif spent >= (cost_cap or 0):
            outcome = "budget_exhausted"
        else:
            outcome = "open"
        ledger = replace(
            ledger, attempts=attempts, outcome=outcome, spent_units=spent
        )
        self._ledgers[obligation_id] = ledger
        return ledger

    def mark_exhausted(self, obligation_id: str) -> CorrectionLedger:
        """Close an open ledger when correction may not continue."""
        ledger = self._ledgers.get(obligation_id)
        if ledger is None:
            raise CyranoError(
                "INPUT_INVALID",
                f"no open failure for {obligation_id}",
            )
        if ledger.outcome == "open":
            ledger = replace(ledger, outcome="budget_exhausted")
            self._ledgers[obligation_id] = ledger
        return ledger

    def ledger(self, obligation_id: str) -> CorrectionLedger | None:
        """The ledger for one obligation, if any."""
        return self._ledgers.get(obligation_id)
