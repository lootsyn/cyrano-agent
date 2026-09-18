"""PlanService composes the governed plan lifecycle in one seam.

Order is fixed: subject build → static validation → independent
review → human decision → execution permission → dispatch →
completion assessment. Each gate is a separate authority; approval is
never permission and permission is never application.
"""

from __future__ import annotations

from collections.abc import Mapping

from deepagents_code.cyrano.contracts.canonical import JSON
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.kernel.transitions import plan_transition
from deepagents_code.cyrano.planning.changes import (
    PlanRevisions,
    classify_change,
)
from deepagents_code.cyrano.planning.completion import (
    CompletionDecision,
    assess_completion,
)
from deepagents_code.cyrano.planning.decisions import (
    DecisionDesk,
    DecisionRequest,
)
from deepagents_code.cyrano.planning.review import (
    ReviewBoard,
    ReviewerBinding,
    ReviewRecord,
)
from deepagents_code.cyrano.planning.subject import (
    GovernedWorkPlan,
    PlanReviewSubject,
    build_subject,
    subject_digest,
)
from deepagents_code.cyrano.planning.validation import (
    PlanCheckReport,
    validate_plan,
)
from deepagents_code.cyrano.workflow.compiler import (
    CompiledWorkflow,
    compile_workflow,
    units_to_nodes,
)
from deepagents_code.cyrano.workflow.dispatch import (
    Dispatcher,
    ExecutionPermit,
    make_permit,
)


class PlanService:
    """Facade over the plan lifecycle; state lives in its parts."""

    def __init__(
        self,
        *,
        revisions: PlanRevisions | None = None,
        board: ReviewBoard | None = None,
        desk: DecisionDesk | None = None,
        dispatcher: Dispatcher | None = None,
        known_recipes: frozenset[str] | None = None,
    ) -> None:
        """Compose the lifecycle stores; each stays replaceable."""
        self._revisions: PlanRevisions = revisions or PlanRevisions()
        self._board: ReviewBoard = board or ReviewBoard()
        self._desk: DecisionDesk = desk or DecisionDesk()
        self._dispatcher: Dispatcher = dispatcher or Dispatcher()
        self._known_recipes: frozenset[str] | None = known_recipes
        self._states: dict[str, str] = {}
        self._subjects: dict[str, PlanReviewSubject] = {}

    # -- intake and validation ----------------------------------------

    def submit_plan(
        self,
        plan: GovernedWorkPlan,
        *,
        requirements_doc: Mapping[str, JSON],
        source_snapshot: Mapping[str, JSON],
        scope: Mapping[str, str],
        active_requirements: tuple[str, ...] | None = None,
        verified_no_change: Mapping[str, str] | None = None,
        known_interfaces: Mapping[str, str] | None = None,
    ) -> tuple[PlanReviewSubject, PlanCheckReport]:
        """Build the sealed subject and run static cross-checks.

        The plan commits by CAS only when validation passes; a failed
        check leaves the plan in ``rejected`` and commits nothing.
        """
        subject = build_subject(plan, requirements_doc, source_snapshot, scope)
        report = validate_plan(
            plan,
            active_requirements=(
                plan.requirements
                if active_requirements is None
                else active_requirements
            ),
            verified_no_change=verified_no_change,
            known_recipes=self._known_recipes or frozenset(),
            known_interfaces=(
                known_interfaces if known_interfaces is not None else {}
            ),
        )
        if report.ready_for_review:
            head = self._revisions.head(plan.plan_id)
            _ = self._revisions.commit(
                plan,
                expected_revision=(-1 if head is None else head.revision),
            )
            self._states[plan.plan_id] = "static_validated"
            self._subjects[plan.plan_id] = subject
        else:
            self._states[plan.plan_id] = "rejected"
        return subject, report

    # -- independent review -------------------------------------------

    def request_review(
        self, subject: PlanReviewSubject, binding: ReviewerBinding
    ):
        """Open a blind review round for the current subject digest."""
        state = self._states.get(subject.plan_id, "draft")
        _ = plan_transition(state, "in_review", decision_ready=True)
        self._states[subject.plan_id] = "in_review"
        return self._board.request_review(
            subject_digest(subject),
            binding,
            reviewer_input={"subject_digest": subject_digest(subject)},
        )

    def finish_review(self, record: ReviewRecord, plan_id: str) -> str:
        """Judge the round; only a clean round reaches human review."""
        outcome = self._board.finish_review(record)
        state = self._states[plan_id]
        if outcome == "reviewed":
            _ = plan_transition(
                state,
                "human_review",
                reviewed=self._board.is_reviewed(record.subject_digest),
            )
            self._states[plan_id] = "human_review"
        elif outcome == "changes_required":
            _ = plan_transition(
                state, "amendment_requested", decision_ready=True
            )
            self._states[plan_id] = "amendment_requested"
        return outcome

    # -- human decision ------------------------------------------------

    def present_decision(
        self,
        subject: PlanReviewSubject,
        *,
        purpose: str,
        display_digest: str,
        ttl: int = 600,
    ) -> DecisionRequest:
        """Present a decision bound to subject+display digests."""
        self._board.require_reviewed(subject_digest(subject))
        return self._desk.present(
            f"{purpose}-{subject.plan_id}-r{subject.revision}",
            subject.scope.get("scope_id", "scope"),
            purpose,
            subject_digest(subject),
            display_digest,
            revision=subject.revision,
            ttl=ttl,
        )

    def record_decision(
        self,
        plan_id: str,
        decision_id: str,
        response: str,
        *,
        nonce: str,
        subject_digest_value: str,
        display_digest: str,
        expected_revision: int,
        approved_units: tuple[str, ...] = (),
    ):
        """Adjudicate a response and move the plan state machine."""
        outcome = self._desk.record_response(
            decision_id,
            response,
            nonce=nonce,
            subject_digest=subject_digest_value,
            display_digest=display_digest,
            expected_revision=expected_revision,
            approved_units=approved_units,
        )
        if outcome.purpose == "plan_approval":
            state = self._states.get(plan_id, "draft")
            moves = {
                "approved": "approved",
                "rejected": "rejected",
                "deferred": "deferred",
                "cancelled": "cancelled",
                "amend_requested": "amendment_requested",
            }
            target = moves.get(outcome.state)
            if target is not None and state in {
                "human_review",
                "deferred",
                "approved",
            }:
                _ = plan_transition(state, target, decision_ready=True)
                self._states[plan_id] = target
        return outcome

    # -- execution permission ------------------------------------------

    def issue_permit(
        self,
        subject: PlanReviewSubject,
        decision_id: str,
        *,
        source_snapshot_digest: str,
        generation: int,
    ) -> ExecutionPermit:
        """Mint the execution permit; plan approval alone is not it."""
        head = self._revisions.head(subject.plan_id)
        if head is None or head.revision != subject.revision:
            raise CyranoError(
                "PERMIT_STALE", "permit needs the committed subject"
            )
        permit = make_permit(
            self._desk,
            decision_id,
            subject_digest=subject_digest(subject),
            source_snapshot_digest=source_snapshot_digest,
            generation=generation,
            plan=head,
        )
        state = self._states.get(subject.plan_id, "draft")
        _ = plan_transition(state, "executable", permit_ready=True)
        self._states[subject.plan_id] = "executable"
        return permit

    def compile(self, plan: GovernedWorkPlan) -> CompiledWorkflow:
        """Compile the committed plan into the typed workflow IR."""
        head = self._revisions.head(plan.plan_id)
        if head is None or head.revision != plan.revision:
            raise CyranoError(
                "PERMIT_STALE", "compile needs the committed revision"
            )
        return compile_workflow(
            units_to_nodes(plan.units),
            revision=plan.revision,
            known_recipes=self._known_recipes,
        )

    def reserve_ready_work(
        self,
        plan: GovernedWorkPlan,
        permit: ExecutionPermit,
        worker_id: str,
        *,
        completed: frozenset[str] | None = None,
        failed: frozenset[str] | None = None,
        source_snapshot_digest: str,
    ) -> tuple[str, int]:
        """Lease one ready unit under a re-checked live permit."""
        head = self._revisions.head(plan.plan_id)
        subject = self._subjects.get(plan.plan_id)
        if head is None or subject is None:
            raise CyranoError("TASK_UNKNOWN", plan.plan_id)
        _ = self._dispatcher.check_permit(
            permit,
            subject_digest(subject),
            source_snapshot_digest,
        )
        return self._dispatcher.reserve_ready_work(
            plan,
            permit,
            worker_id,
            completed=completed or frozenset(),
            failed=failed or frozenset(),
        )

    # -- change and completion ---------------------------------------

    def assess_change(self, old: GovernedWorkPlan, new: GovernedWorkPlan):
        """Classify a change and compute its invalidation closure."""
        return classify_change(old, new)

    def assess_completion(
        self,
        *,
        outcome: str,
        acceptance_results: dict[str, bool],
        subject_digest_value: str,
        apply_permit: bool = False,
        publish_permit: bool = False,
        source_changed: bool = False,
    ) -> CompletionDecision:
        """Judge completion from evidence; approval grants nothing."""
        return assess_completion(
            outcome=outcome,
            acceptance_results=acceptance_results,
            review_approved=self._board.is_reviewed(subject_digest_value),
            apply_permit=apply_permit,
            publish_permit=publish_permit,
            source_changed=source_changed,
        )
