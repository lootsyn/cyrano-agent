"""Path A actual-validation handoff; replay never activates.

A screened candidate earns only an experiment request bound to one
execution signature — model, endpoint, runtime, tool inventory, and
skill digests. A result recorded under a different signature is not
evidence for this candidate. Activation additionally requires the
paired-evaluation verdict, an independent review, and a bounded
approval; a replay score is screening input, never proof.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.evaluation.paired import (
    EvaluationManifest,
    seal_experiment,
)
from deepagents_code.cyrano.improvement.search import PolicyCandidate
from deepagents_code.cyrano.improvement.worlds import ExecutionSignature


@dataclass(frozen=True, slots=True)
class ValidationRequest:
    """An experiment request; never itself an activation."""

    candidate_id: str
    signature_digest: str
    manifest: EvaluationManifest
    replay_score: float | None
    state: str  # evaluation_required


def request_actual_validation(
    candidate: PolicyCandidate,
    *,
    signature: ExecutionSignature,
    spec: Mapping[str, object],
    replay_score: float | None = None,
) -> ValidationRequest:
    """Bind a candidate to a sealed experiment under one signature.

    The manifest must pin this candidate's IR digest as the candidate
    digest so the evaluated artifact is exactly the screened one.
    """
    if spec.get("candidate_digest") != candidate.ir.ir_digest:
        raise CyranoError(
            "BINDING_MISMATCH",
            "manifest candidate must be the screened IR digest",
        )
    manifest = seal_experiment(spec)
    return ValidationRequest(
        candidate_id=candidate.candidate_id,
        signature_digest=signature.signature_digest,
        manifest=manifest,
        replay_score=replay_score,
        state="evaluation_required",
    )


@dataclass(frozen=True, slots=True)
class ActivationDecision:
    """The activation gate's verdict; replay alone never promotes."""

    allowed: bool
    reason: str


def decide_activation(
    request: ValidationRequest,
    *,
    current_signature: ExecutionSignature,
    actual_verdict: str | None,
    review_independent: bool = False,
    approval_bounded: bool = False,
) -> ActivationDecision:
    """Decide whether the candidate may activate.

    Every gate is required: the recorded signature must match the
    live signature, an actual paired verdict of ``improved`` must
    exist, an independent reviewer must have approved, and a bounded
    approval must be on record. A replay score changes nothing.
    """
    if request.signature_digest != current_signature.signature_digest:
        return ActivationDecision(
            False, "SIGNATURE_MISMATCH: results are not reusable"
        )
    if actual_verdict != "improved":
        return ActivationDecision(
            False, "ACTUAL_EVALUATION_REQUIRED: replay is not proof"
        )
    if not review_independent:
        return ActivationDecision(
            False, "REVIEW_REQUIRED: independent review missing"
        )
    if not approval_bounded:
        return ActivationDecision(
            False, "APPROVAL_REQUIRED: bounded approval missing"
        )
    return ActivationDecision(True, "eligible_for_activation")
