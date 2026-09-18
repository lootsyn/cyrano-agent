"""Application evidence: referenced is not applied.

A memory id appearing in a prompt or plan is ``referenced``; it is
``applied`` only when a verifiable chain links the memory revision to
plan, tool, and test artifacts. Anything unverifiable is ``unknown``.
"""

from dataclasses import dataclass

from deepagents_code.cyrano.memory.models import ApplicationVerdict


@dataclass(frozen=True, slots=True)
class Exposure:
    """One recorded exposure of a memory to a work unit."""

    memory_id: str
    revision: int
    exposure_ref: str


def record_application(
    exposure: Exposure,
    *,
    plan_evidence: tuple[str, ...] = (),
    tool_evidence: tuple[str, ...] = (),
    test_evidence: tuple[str, ...] = (),
    unknowns: tuple[str, ...] = (),
) -> ApplicationVerdict:
    """Classify how far the exposure is proven.

    ``referenced`` when only the exposure exists; ``applied`` when the
    plan, tool and test evidence all link the same memory revision;
    ``unknown`` when any link is unverifiable.
    """
    if unknowns:
        return ApplicationVerdict("unknown", tuple(unknowns))
    evidence = tuple(
        dict.fromkeys(plan_evidence + tool_evidence + test_evidence)
    )
    if plan_evidence and tool_evidence and test_evidence:
        return ApplicationVerdict("applied", evidence)
    return ApplicationVerdict("referenced", (exposure.exposure_ref,))
