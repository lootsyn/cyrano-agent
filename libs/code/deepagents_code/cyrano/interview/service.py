"""Interview kernel service over the scoped ledger.

User events are ingested as ledger commands so idempotency, revision
checks, and the audit trail come from the transaction layer, not from
service-level bookkeeping. A payload that merely looks like an
approval (``approved: true``, ``[from-user]`` text) is stored as data;
only a trusted user channel with attestation can mark approval.
Scores never offset blockers and there is no minimum-rounds rule.
"""

from dataclasses import dataclass, replace
from typing import Mapping

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.interview.decisions import DecisionLog
from deepagents_code.cyrano.interview.readiness import (
    Obligation,
    Readiness,
    affected_closure,
    assess,
)
from deepagents_code.cyrano.interview.worker_adapter import (
    WorkerBinding,
    validate_worker_binding,
)
from deepagents_code.cyrano.kernel.session_state import (
    Session,
    SessionMachine,
)
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

STATEMENT_KINDS = frozenset({"observation", "intended_change"})


@dataclass(frozen=True, slots=True)
class Statement:
    """A normalized statement; source decides the kind, never text."""

    statement_id: str
    text: str
    kind: str
    source: str


class InterviewService:
    """Obligation/decision/readiness kernel bound to one stream."""

    def __init__(
        self,
        repo: ScopedRepository,
        scope_id: str,
        stream_id: str,
        machine: SessionMachine,
    ) -> None:
        """Bind the ledger stream; session starts in INTAKE."""
        self._repo = repo
        self._scope = scope_id
        self._stream = stream_id
        self._machine = machine
        self._session = Session(work_state="INTAKE")
        self._obligations: dict[str, Obligation] = {}
        self._decisions = DecisionLog()
        self._statements: dict[str, Statement] = {}
        self._snapshot_digest = ""
        self._invalidated: set[str] = set()
        self._rereview: list[str] = []
        self._reviews: set[str] = set()
        self._approved = False
        self._paused = False

    # -- ledger-backed ingestion

    def ingest_user_event(
        self,
        payload: Mapping[str, object],
        *,
        actor: str,
        idempotency_key: str,
        expected_revision: int,
        trusted_user: bool,
        attested: bool = False,
    ) -> int:
        """Record a user event as a command; returns the revision.

        ``trusted_user``/``attested`` describe the transport, never the
        payload. A payload claim like ``approved: true`` inside a model
        result is stored as data and grants nothing.
        """
        if self._machine.is_terminal(self._session.work_state):
            raise CyranoError("INVALID_TRANSITION", "terminal session")
        if self._session.work_state in {"CANCELLING"}:
            raise CyranoError("INVALID_TRANSITION", "cancelled session")
        receipt = self._repo.execute_command(
            self._scope,
            actor,
            "user_event",
            idempotency_key,
            dict(payload),
            self._stream,
            expected_revision,
        )
        if receipt.idempotent_replay:
            return receipt.revision
        kind = payload.get("type")
        if kind == "cancel":
            self._session = replace(
                self._session,
                work_state=self._machine.candidate(
                    self._session.work_state, "user_cancel"
                ).to_state,
            )
        elif kind == "approve" and trusted_user and attested:
            self._approved = True
        return receipt.revision

    # -- normalization

    def normalize_statement(
        self, statement_id: str, text: str, *, source: str
    ) -> Statement:
        """Observed facts and intended changes coexist; neither wins."""
        kind = "intended_change" if source == "user" else "observation"
        statement = Statement(
            statement_id=statement_id,
            text=text,
            kind=kind,
            source=source,
        )
        self._statements[statement_id] = statement
        return statement

    def statement(self, statement_id: str) -> Statement:
        """Return the stored statement."""
        return self._statements[statement_id]

    # -- obligations

    def add_obligation(self, obligation: Obligation) -> None:
        """Register an obligation; it starts unresolved."""
        self._obligations[obligation.obligation_id] = obligation

    def apply_obligation_change(
        self,
        obligation_id: str,
        change: str,
        *,
        authorized: bool,
        reason: str | None = None,
        dependents: Mapping[str, set[str]] | None = None,
    ) -> Obligation:
        """Apply a proposed obligation change with authority checks.

        Removing or downgrading a critical obligation without an
        authorized reason is refused; the denominator cannot be
        shrunk by fiat.
        """
        current = self._obligations.get(obligation_id)
        if current is None:
            raise CyranoError("UNKNOWN_OBLIGATION", obligation_id)
        if change in {"not_applicable", "remove"}:
            if not authorized or not reason:
                raise CyranoError("UNAUTHORIZED_DECISION", obligation_id)
            if dependents:
                self._invalidated |= affected_closure(
                    {obligation_id}, dict(dependents)
                )
            self._obligations.pop(obligation_id)
            return current
        if change == "resolve":
            updated = replace(current, resolved=True)
            self._obligations[obligation_id] = updated
            return updated
        if change == "defer":
            updated = replace(current, authorized_deferral=authorized)
            self._obligations[obligation_id] = updated
            return updated
        raise CyranoError("INVALID_INPUT", change)

    # -- decisions

    @property
    def decisions(self) -> DecisionLog:
        """The decision log; proposals never skip authority checks."""
        return self._decisions

    # -- worker results

    def ingest_worker_result(
        self, payload: Mapping[str, object], binding: WorkerBinding
    ) -> str:
        """Validate a worker result; stale results queue re-review."""
        if self._session.work_state in {"CANCELLING", "CANCELLED"}:
            raise CyranoError("INVALID_TRANSITION", "cancelled session")
        try:
            validate_worker_binding(dict(payload), binding)
        except CyranoError as exc:
            if exc.code == "STALE_REVISION":
                self._rereview.append(binding.task_id)
                raise
            raise
        return "accepted"

    @property
    def rereview_queue(self) -> tuple[str, ...]:
        """Stale-but-material evidence preserved for re-review."""
        return tuple(self._rereview)

    # -- observations

    def record_observation(
        self, subject: str, *, found: bool | None, bounded: bool
    ) -> str:
        """A bounded search that finds nothing is 'unconfirmed'."""
        if found is None or (not found and bounded):
            return "unconfirmed"
        return "observed" if found else "absent"

    # -- readiness / next action

    def assess_readiness(
        self,
        target_stage: str,
        *,
        required_review_current: bool = True,
        important_assumptions: int = 0,
        stale_evidence: int = 0,
        unresolved_conflicts: int = 0,
        clarity_score: float = 0.0,
    ) -> Readiness:
        """Blockers decide readiness; scores never offset them."""
        result = assess(
            list(self._obligations.values()),
            target_stage=target_stage,
            required_review_current=required_review_current,
            important_assumptions=important_assumptions,
            stale_evidence=stale_evidence,
            unresolved_conflicts=unresolved_conflicts,
        )
        return result

    def next_action(
        self, target_stage: str, *, budget_exhausted: bool = False
    ) -> str:
        """Pause with blockers, or advance when obligations are met.

        There is no minimum-question quota: a fully specified intake
        goes straight to review, and an exhausted budget pauses with
        the unresolved list instead of reporting READY.
        """
        readiness = self.assess_readiness(target_stage)
        if readiness.blockers or budget_exhausted:
            self._paused = True
            return "pause"
        return "review"

    @property
    def paused(self) -> bool:
        """Whether the session is paused with unresolved work."""
        return self._paused

    # -- export-facing accessors

    @property
    def approved(self) -> bool:
        """Whether an attested user approval was ingested."""
        return self._approved

    @property
    def statements(self) -> Mapping[str, Statement]:
        """All normalized statements, by id."""
        return dict(self._statements)

    @property
    def obligations(self) -> tuple[str, ...]:
        """Ids of registered obligations."""
        return tuple(sorted(self._obligations))

    # -- review credit

    def note_done(self, reviewer_id: str, *, trusted: bool) -> int:
        """Only distinct trusted reviewers add review credit."""
        if trusted:
            self._reviews.add(reviewer_id)
        return len(self._reviews)

    # -- snapshot invalidation

    def apply_snapshot(
        self,
        digest_value: str,
        *,
        dependents: Mapping[str, set[str]] | None = None,
    ) -> frozenset[str]:
        """A changed snapshot invalidates bound evidence and reviews."""
        if self._snapshot_digest and digest_value != self._snapshot_digest:
            changed = {"snapshot"}
            if dependents:
                changed |= affected_closure({"snapshot"}, dict(dependents))
            self._invalidated |= changed
            self._reviews.clear()
        self._snapshot_digest = digest_value
        return frozenset(self._invalidated)

    @property
    def invalidated(self) -> frozenset[str]:
        """Entities awaiting re-review after invalidation."""
        return frozenset(self._invalidated)

    # -- session

    @property
    def session(self) -> Session:
        """Current work and candidate states (separate domains)."""
        return self._session

    def complete_work(self) -> None:
        """Completing work never mutates the candidate domain."""
        transition = self._machine.candidate(
            self._session.work_state, "required_checks_passed"
        )
        self._session = replace(self._session, work_state=transition.to_state)

    def pause(self, checkpoint: str) -> None:
        """Persist a resume checkpoint and move to PAUSED."""
        transition = self._machine.candidate(
            self._session.work_state, "pause_required"
        )
        self._session = replace(
            self._session,
            work_state=transition.to_state,
            checkpoint=checkpoint,
        )

    def resume(self) -> str:
        """Resume to the stored checkpoint; caller picks no target."""
        if self._session.checkpoint is None:
            raise CyranoError("INVALID_TRANSITION", "no checkpoint")
        target = self._machine.resume_target(self._session.checkpoint)
        self._session = replace(
            self._session, work_state=target, checkpoint=None
        )
        return target
