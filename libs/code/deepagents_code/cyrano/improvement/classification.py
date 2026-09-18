"""Server-owned impact classification.

Filenames alone never prove replayability.
"""

from dataclasses import dataclass
from pathlib import PurePosixPath

from deepagents_code.cyrano.contracts.types import CyranoError

PROTECTED = (
    "policies/trust/",
    "policies/permissions/",
    "policies/promotion/",
    "evaluation/sealed/",
    "evaluation/judges/",
    "approvals/",
    "audit/",
)


@dataclass(frozen=True, slots=True)
class Impact:
    """Required evaluation route for a candidate diff."""

    effect_class: str
    path: str
    requires_live: bool
    reason: str


def classify(
    paths: list[str],
    *,
    input_semantics_unchanged: bool,
    policy_ir_validated: bool,
) -> Impact:
    """Choose B unless a scheduling-only change is attested."""
    if not paths:
        raise CyranoError(
            "EMPTY_CANDIDATE", "a candidate must contain a real change"
        )
    for path in paths:
        parts = PurePosixPath(path).parts
        if path.startswith("/") or ".." in parts or "\\" in path:
            raise CyranoError("INVALID_PATCH_PATH", path)
    if any(path.startswith(PROTECTED) for path in paths):
        return Impact(
            "protected_change",
            "manual_policy_change",
            True,
            "protected owner",
        )
    if (
        all(path.startswith("policies/exploration/") for path in paths)
        and input_semantics_unchanged
        and policy_ir_validated
    ):
        return Impact(
            "scheduling_only", "A", True, "screen by supported replay"
        )
    return Impact(
        "transition_changing",
        "B",
        True,
        "input semantics changed or unknown",
    )
