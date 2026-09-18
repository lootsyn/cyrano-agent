"""Shared value objects for CYRANO contracts.

Parsing and authorization remain separate operations owned by
their respective modules.
"""

from dataclasses import dataclass
from enum import StrEnum


class CyranoError(Exception):
    """Stable machine-readable error with a readable explanation."""

    def __init__(self, code: str, message: str) -> None:
        """Store the machine code beside the human message."""
        self.code = code
        super().__init__(f"{code}: {message}")


class EvidenceLevel(StrEnum):
    """A declaration of completed verification, never a target."""

    DESIGN = "design_only"
    CONTRACT = "contract_tested"
    INTEGRATED = "runtime_integrated"
    EFFECTIVE = "effectiveness_validated"


@dataclass(frozen=True, slots=True)
class Scope:
    """Exact tenant/user/workspace scope; wildcards not authorized."""

    tenant: str
    user: str
    workspace: str

    def __post_init__(self) -> None:
        """Reject empty or wildcard scope components."""
        fields = (self.tenant, self.user, self.workspace)
        if any(not x or x == "*" for x in fields):
            raise CyranoError(
                "INVALID_SCOPE", "all scope fields must be exact"
            )


@dataclass(frozen=True, slots=True)
class Outcome:
    """Keep execution, correctness and acceptance on separate axes."""

    execution: str
    correctness: str
    acceptance: str

    @property
    def complete(self) -> bool:
        """True only for verified correctness and acceptance."""
        return (
            self.execution == "finished"
            and self.correctness == "passed"
            and self.acceptance == "accepted"
        )
