"""Run controls: budget, cancellation, and completion gates.

Retry budgets and stagnation limits are deterministic; a claimed
completion without implementation evidence never transitions to
COMPLETE; a missing or timed-out stop hook permits native exit but
never a governed COMPLETE; a prompt-only subagent is detected as
lacking governed capability.
"""

from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError

GOVERNED_CAPABILITIES = frozenset(
    {"permit_check", "ledger_write", "evidence_emit"}
)


@dataclass(frozen=True, slots=True)
class StopVerdict:
    """What a stop request may conclude."""

    native_exit_allowed: bool
    complete_allowed: bool


class RunControls:
    """Deterministic retry/cancel/complete governance."""

    def __init__(
        self, *, max_same_error: int = 3, max_stagnant: int = 2
    ) -> None:
        """Fix the budget; it is data, not a policy suggestion."""
        self._max_same = max_same_error
        self._max_stagnant = max_stagnant
        self._same = 0
        self._stagnant = 0
        self._last_error: str | None = None
        self._cancelled = False

    def record_attempt(self, error_digest: str, *, changed: bool) -> str:
        """Count same-error and stagnation; abort at budget."""
        if self._cancelled:
            raise CyranoError("RUN_CANCELLED", "run already cancelled")
        if error_digest == self._last_error:
            self._same += 1
        else:
            self._same = 1
            self._last_error = error_digest
        if not changed:
            self._stagnant += 1
        else:
            self._stagnant = 0
        if self._same >= self._max_same or self._stagnant >= (
            self._max_stagnant
        ):
            return "abort"
        return "continue"

    def cancel(self) -> str:
        """Cancel terminates children; the run ends CANCELLED."""
        self._cancelled = True
        return "CANCELLED"

    @property
    def cancelled(self) -> bool:
        """Whether the run has been cancelled."""
        return self._cancelled

    def request_complete(self, *, implemented: bool) -> None:
        """A bare 'done' claim never completes the run."""
        if self._cancelled:
            raise CyranoError("RUN_CANCELLED", "cancelled run")
        if not implemented:
            raise CyranoError(
                "COMPLETE_WITHOUT_EVIDENCE",
                "no implementation evidence",
            )

    def evaluate_stop_hook(
        self, *, hook_installed: bool, hook_timed_out: bool
    ) -> StopVerdict:
        """Native exit is always possible; COMPLETE is not."""
        return StopVerdict(
            native_exit_allowed=True,
            complete_allowed=hook_installed and not hook_timed_out,
        )

    def governed_capability_met(self, capabilities: frozenset[str]) -> bool:
        """A prompt-only subagent lacks governed capability."""
        return GOVERNED_CAPABILITIES <= set(capabilities)
