"""Validate the original worker binding after schema checks."""

import re
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError

ROLE_ALIASES = {
    "facilitator": "facilitator",
    "evidence-scout": "evidence_scout",
    "critic": "critic",
    "blind-handoff-reviewer": "blind_reviewer",
}


@dataclass(frozen=True, slots=True)
class WorkerBinding:
    """Expected immutable identity for one worker task."""

    task_id: str
    role: str
    revision: int
    input_digest: str


def validate_worker_binding(
    payload: dict[str, object], expected: WorkerBinding
) -> None:
    """Reject stale or wrong-role results; never issue authority."""
    if expected.role not in ROLE_ALIASES:
        raise CyranoError("UNKNOWN_INTERVIEW_ROLE", expected.role)
    if re.fullmatch(r"sha256:[a-f0-9]{64}", expected.input_digest) is None:
        raise CyranoError("INVALID_DIGEST", "explicit SHA256 digest required")
    if payload.get("task_id") != expected.task_id:
        raise CyranoError("WRONG_TASK", "result does not belong to this task")
    if payload.get("role") != ROLE_ALIASES[expected.role]:
        raise CyranoError("WRONG_ROLE", "worker role alias does not match")
    revision = payload.get("base_revision")
    if type(revision) is not int or revision != expected.revision:
        raise CyranoError(
            "STALE_REVISION", "result computed from another revision"
        )
    if payload.get("input_digest") != (
        expected.input_digest.removeprefix("sha256:")
    ):
        raise CyranoError("INPUT_DIGEST_MISMATCH", "worker input changed")
