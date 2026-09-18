"""Session transition guards computed from typed kernel evidence.

Guards are evaluated against a ``GuardEvidence`` record produced by
trusted kernel services. A request body's ``true``/``target`` fields
are never consulted. Every contract guard id maps to an explicit
predicate; an unregistered id is UNKNOWN_GUARD, never default-true.
"""

from collections.abc import Callable
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError


@dataclass(frozen=True, slots=True)
class GuardEvidence:
    """Typed facts computed by trusted kernel services only."""

    runtime_policy_bound: bool = False
    trusted_input: bool = False
    memory_view_ready: bool = False
    read_scope_available: bool = False
    read_or_probe_authorized: bool = False
    redundant_question: bool = False
    unresolved_mandatory_obligations: int = 0
    blockers: int = 0
    snapshot_provenance_valid: bool = False
    trusted_user_event: bool = False
    model_reported: bool = False
    bundle_content_addressed: bool = False
    findings_current: bool = False
    reviews_current: bool = False
    spec_receipt_verified: bool = False
    spec_approval_current: bool = False
    spec_still_valid: bool = False
    plan_valid: bool = False
    plan_receipt_verified: bool = False
    display_bound: bool = False
    exec_receipt_verified: bool = False
    apply_receipt_verified: bool = False
    scope_unchanged: bool = False
    adapter_governed: bool = False
    budget_preimage_valid: bool = False
    unknown_effects: int = 0
    repair_possible: bool = False
    postimage_current: bool = False
    evidence_complete: bool = False
    permit_current: bool = False
    completion_gates_passed: bool = False
    apply_checks_passed: bool = False
    preimage_current: bool = False
    manifest_matched: bool = False
    final_checks_passed: bool = False
    journal_present: bool = False
    partial_state_recorded: bool = False
    dependents_invalidated: bool = False
    permits_revoked: bool = False
    new_dispatch_stopped: bool = False
    cancel_trusted: bool = False
    checkpoint_persisted: bool = False


_GUARDS: dict[str, Callable[[GuardEvidence], bool]] = {
    "workspace_runtime_policy_bound": lambda e: e.runtime_policy_bound,
    "trusted_input_and_memory_view_ready": (
        lambda e: e.trusted_input and e.memory_view_ready
    ),
    "read_scope_available": lambda e: e.read_scope_available,
    "no_redundant_question": lambda e: not e.redundant_question,
    "no_unresolved_mandatory_obligation": (
        lambda e: e.unresolved_mandatory_obligations == 0
    ),
    "evidence_snapshot_provenance_valid": (
        lambda e: e.snapshot_provenance_valid
    ),
    "read_or_probe_authorized": lambda e: e.read_or_probe_authorized,
    "trusted_user_event_not_model_report": (
        lambda e: e.trusted_user_event and not e.model_reported
    ),
    "bundle_strict_and_content_addressed": (
        lambda e: e.bundle_content_addressed
    ),
    "finding_targets_current_digest": lambda e: e.findings_current,
    "required_current_independent_reviews_and_no_blockers": (
        lambda e: e.reviews_current and e.blockers == 0
    ),
    "trusted_exact_approve_spec_for_planning": (
        lambda e: e.spec_receipt_verified
    ),
    "spec_approval_current": lambda e: e.spec_approval_current,
    "dag_scope_traceability_verification_budget_valid": (
        lambda e: e.plan_valid
    ),
    "current_plan_findings": lambda e: e.findings_current,
    "independent_current_plan_review_no_blockers": (
        lambda e: e.reviews_current and e.blockers == 0
    ),
    "trusted_exact_approve_plan": lambda e: e.plan_receipt_verified,
    "display_exact_files_recipes_budget": lambda e: e.display_bound,
    "trusted_authorize_execution_scope_intersection": (
        lambda e: e.exec_receipt_verified and e.scope_unchanged
    ),
    "governed_adapter_audit_budget_preimage_valid": (
        lambda e: e.adapter_governed and e.budget_preimage_valid
    ),
    "observed_changes_no_unknown_side_effects": (
        lambda e: e.unknown_effects == 0
    ),
    "same_scope_repair_possible": (
        lambda e: e.repair_possible and e.scope_unchanged
    ),
    "repair_within_current_contract_possible": (
        lambda e: e.repair_possible and e.scope_unchanged
    ),
    "current_postimage_all_required_evidence": (
        lambda e: e.postimage_current and e.evidence_complete
    ),
    "current_findings_within_approved_scope": (
        lambda e: e.findings_current and e.scope_unchanged
    ),
    "existing_or_new_permit_current_and_scope_unchanged": (
        lambda e: e.permit_current and e.scope_unchanged
    ),
    "delivery_patch_only_and_all_completion_gates": (
        lambda e: e.completion_gates_passed
    ),
    "delivery_apply_to_source_and_all_patch_checks": (
        lambda e: e.apply_checks_passed
    ),
    "trusted_authorize_apply_patch_and_source_preimage_current": (
        lambda e: e.apply_receipt_verified and e.preimage_current
    ),
    "source_manifest_and_required_final_checks_passed": (
        lambda e: e.manifest_matched and e.final_checks_passed
    ),
    "durable_journal_exists_or_gap_explicit": (lambda e: e.journal_present),
    "actual_partial_state_and_recovery_next_action_recorded": (
        lambda e: e.partial_state_recorded
    ),
    "affected_entities_invalidated": lambda e: e.dependents_invalidated,
    "spec_still_valid_and_plan_dependents_invalidated": (
        lambda e: e.spec_still_valid and e.dependents_invalidated
    ),
    "no_new_dispatch_and_all_running_ops_accounted_for": (
        lambda e: e.new_dispatch_stopped and e.unknown_effects == 0
    ),
    "trusted_cancel_stop_new_dispatch_immediately": (
        lambda e: e.cancel_trusted and e.new_dispatch_stopped
    ),
    "persist_resume_checkpoint_and_operation_status": (
        lambda e: e.checkpoint_persisted
    ),
    "revoke_affected_permits_and_invalidate_dependents": (
        lambda e: e.permits_revoked and e.dependents_invalidated
    ),
}


def evaluate_guard(guard_id: str, evidence: GuardEvidence) -> bool:
    """Evaluate one contract guard; unknown ids are typed failures."""
    predicate = _GUARDS.get(guard_id)
    if predicate is None:
        raise CyranoError("UNKNOWN_GUARD", guard_id)
    return predicate(evidence)


def guard_ids() -> frozenset[str]:
    """All registered guard ids, for contract-coverage checks."""
    return frozenset(_GUARDS)
