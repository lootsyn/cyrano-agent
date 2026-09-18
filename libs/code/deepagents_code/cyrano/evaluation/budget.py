"""Experiment authorization and budget control.

A paired evaluation needs an explicit permit bound to the experiment
spec before any trial may run — a zero budget is a refusal, not a
free pass, and no provider call is made without remaining budget.
Spending is recorded per trial; the account never silently goes
negative, it refuses and reports.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError


@dataclass(frozen=True, slots=True)
class ExperimentPermit:
    """A permit-bound experiment spec; required before any trial."""

    permit_id: str
    spec_digest: str
    budget_units: int
    allowed_families: frozenset[str]
    expires_at: int


def authorize_experiment(
    spec: Mapping[str, object],
    *,
    permit: Mapping[str, object] | None,
    now: int = 0,
) -> ExperimentPermit:
    """Bind a spec to its permit; no permit means no experiment.

    The permit must carry positive budget, list the spec's families,
    and be unexpired. Anything else refuses — a missing permit is
    PERMISSION_DENIED, not a default grant.
    """
    if permit is None:
        raise CyranoError(
            "PERMISSION_DENIED", "an experiment requires a permit"
        )
    expires = permit.get("expires_at", 0)
    if isinstance(expires, int) and expires <= now:
        raise CyranoError("PERMISSION_DENIED", "permit expired")
    budget = permit.get("budget_units", 0)
    if not isinstance(budget, int) or budget <= 0:
        raise CyranoError(
            "BUDGET_EXHAUSTED", "a zero budget runs no paid call"
        )
    spec_digest = digest({str(k): str(v) for k, v in sorted(spec.items())})
    fam_raw = permit.get("families", ())
    allowed = (
        frozenset(str(f) for f in fam_raw)
        if isinstance(fam_raw, (list, tuple, set, frozenset))
        else frozenset()
    )
    spec_fam_raw = spec.get("families", ())
    spec_families = (
        {str(f) for f in spec_fam_raw}
        if isinstance(spec_fam_raw, (list, tuple, set, frozenset))
        else set()
    )
    if spec_families - allowed:
        raise CyranoError(
            "SCOPE_DENIED",
            f"family outside permit: {sorted(spec_families - allowed)[0]}",
        )
    return ExperimentPermit(
        permit_id=str(permit.get("permit_id", spec_digest)),
        spec_digest=spec_digest,
        budget_units=budget,
        allowed_families=allowed,
        expires_at=expires if isinstance(expires, int) else 0,
    )


@dataclass(frozen=True, slots=True)
class BudgetAccount:
    """Remaining budget; spend is checked before a trial starts."""

    total: int
    spent: int


def begin_spend(account: BudgetAccount, units: int) -> BudgetAccount:
    """Debit budget atomically; insufficient funds refuse the trial."""
    if units <= 0:
        raise CyranoError("INPUT_INVALID", "spend must be positive")
    if account.spent + units > account.total:
        raise CyranoError(
            "BUDGET_EXHAUSTED",
            f"need {units}, have {account.total - account.spent}",
        )
    return BudgetAccount(account.total, account.spent + units)
