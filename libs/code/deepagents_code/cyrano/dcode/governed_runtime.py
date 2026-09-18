"""Governed-obligation run: the WP06 seam into real dcode assembly.

``run_governed_work`` composes the existing governed components in
order and drives the *native* agent loop — no parallel executor:

    active scope_rule records → eligibility projection → plan
    requirement/acceptance linkage → sealed subject digests →
    static validation → approval desk → SignedPermit → context bind →
    verified-runtime attempt bridge → extension middleware on the real
    ``create_*`` agent graph → broker-mediated tool calls → trusted
    checker verification → bounded correction → application evidence.

The model-readable reference channel stays context; enforcement is
the permit, the broker and the deterministic checkers. Every fail
path is closed: stale revisions, revocation, stale views, checker
digest drift and budget exhaustion all abort or refuse the run.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage

from deepagents_code.cyrano.context.binding import (
    BindingReceipt,
    MemoryView,
    bind_context,
)
from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.dcode.bridge import (
    AttemptBridge,
    AttemptReceipt,
    start_verified_runtime,
)
from deepagents_code.cyrano.dcode.governed_middleware import (
    GovernedObligationMiddleware,
    GovernedSession,
)
from deepagents_code.cyrano.dcode.memory_adapter import (
    InjectionReceipt,
    ReadonlyProjection,
    injection_receipt,
    project_readonly_memory,
)
from deepagents_code.cyrano.dcode.recall import (
    RecallContext,
    RecallEvidence,
    RecallOutcome,
)
from deepagents_code.cyrano.dcode.wire import WireCapture, WireEvidence
from deepagents_code.cyrano.kernel.actions import ActionBroker, Grant
from deepagents_code.cyrano.kernel.approvals import (
    ApprovalDesk,
    issue_permit,
)
from deepagents_code.cyrano.memory.application import (
    Exposure,
    record_application,
)
from deepagents_code.cyrano.memory.checkers import TrustedCheckerRegistry
from deepagents_code.cyrano.memory.models import (
    ApplicationVerdict,
    MemoryRecord,
)
from deepagents_code.cyrano.memory.obligation_check import (
    AttemptCost,
    CorrectionLedger,
    CorrectionTracker,
    ObligationCheckReport,
    obligations_satisfied,
    verify_obligations,
)
from deepagents_code.cyrano.memory.obligations import (
    ObligationProjection,
    RuleObligation,
    assert_obligations_current,
    attach_obligations,
    missing_obligations,
    obligations_requirements_doc,
    project_obligations,
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

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )

    from deepagents_code.cyrano.context.compiler import CompiledContext
    from deepagents_code.cyrano.context.epochs import ContextEpoch
    from deepagents_code.cyrano.kernel.approvals import DisplayRecord
    from deepagents_code.extensions.registry import (
        ExtensionRegistry,
    )

FEEDBACK_MARKER = "OBLIGATION CHECK FAILED"

#: Run status vocabulary. ``refused`` = rejected before dispatch;
#: ``aborted`` = a fail-closed gate fired mid-run; the rest mirror the
#: final checker verdicts. ``unverifiable`` never maps to a pass.
RUN_STATUSES = frozenset(
    {
        "satisfied",
        "corrected",
        "violated",
        "unverifiable",
        "refused",
        "aborted",
    }
)


@dataclass(frozen=True, slots=True)
class GovernedRunConfig:
    """Plan, workspace, grant and budget inputs for one governed run."""

    plan: GovernedWorkPlan
    task_text: str
    scope_id: str
    workspace: Path
    grants: tuple[Grant, ...]
    tools: frozenset[str]
    requirements_doc: Mapping[str, object]
    source_snapshot: Mapping[str, object]
    scope: Mapping[str, str]
    now: Callable[[], int]
    unmediated_tools: frozenset[str] = frozenset()
    known_recipes: frozenset[str] = frozenset()
    known_interfaces: Mapping[str, str] | None = None
    obligation_targets: Mapping[str, tuple[str, ...]] | None = None
    epoch: ContextEpoch | None = None
    compiled: CompiledContext | None = None
    cost_cap: int | None = None
    max_attempts: int = 4
    permit_ttl: int = 3600
    recall_limit: int = 10
    run_id: str = "run"
    agent_context: object | None = None


@dataclass(frozen=True, slots=True)
class MemoryGate:
    """Live memory inputs the run binds and rechecks.

    When ``recall`` is set the run resolves records, rule bodies and
    the pinned view from the live store per task — ``records`` and
    ``rule_bodies`` stay empty and nothing caller-staged is trusted.
    The recall provider also re-runs inside ``currency_check`` so a
    rule becoming applicable after approval forces rebind, never a
    silent plan mutation.
    """

    records: tuple[MemoryRecord, ...]
    rule_bodies: Mapping[str, bytes]
    available_source_digests: frozenset[str]
    registry: TrustedCheckerRegistry
    is_current: Callable[[str, int], bool]
    memory_view: MemoryView | None = None
    view_provider: Callable[[], MemoryView | None] | None = None
    recall: Callable[[RecallContext], RecallOutcome] | None = None
    admitted_kinds: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class ApprovalGate:
    """The human-approval boundary and permit signing material."""

    desk: ApprovalDesk
    signing_key: Ed25519PrivateKey
    trust_root: Ed25519PublicKey
    audience: str
    is_revoked: Callable[[str], bool]
    audit: Callable[[str], None]
    decide: Callable[[DisplayRecord], str] | None = None


@dataclass(frozen=True, slots=True)
class GovernedRunEvidence:
    """Everything the run leaves behind — receipts, not claims."""

    status: str
    refusal_code: str | None
    subject_digest: str
    requirements_digest: str
    work_plan_digest: str
    obligations: tuple[RuleObligation, ...]
    excluded: tuple[tuple[str, str], ...]
    attached: tuple[tuple[str, str], ...]
    unattached: tuple[str, ...]
    reports: tuple[ObligationCheckReport, ...]
    ledgers: tuple[CorrectionLedger, ...]
    verdicts: tuple[ApplicationVerdict, ...]
    receipts: tuple[InjectionReceipt, ...]
    wire: tuple[WireEvidence, ...]
    attempt_receipts: tuple[AttemptReceipt, ...]
    attempts: int
    touched_paths: tuple[str, ...]
    denials: tuple[str, ...]
    permit_id: str | None
    binding: BindingReceipt | None
    check_report: PlanCheckReport | None
    readonly: ReadonlyProjection | None
    recall: RecallEvidence | None = None


def _feedback(reports: tuple[ObligationCheckReport, ...]) -> str:
    """Deterministic correction input — the checker's own evidence."""
    lines = [FEEDBACK_MARKER]
    for report in reports:
        if report.verdict.state != "satisfied":
            lines.append(
                f"- {report.verdict.state.upper()} "
                f"{report.obligation_id}: {report.verdict.detail}"
            )
    return "\n".join(lines)


def _obligation_digest(obligations: tuple[RuleObligation, ...]) -> str:
    return digest(
        {
            "obligations": [
                {
                    "obligation_id": o.obligation_id,
                    "memory_id": o.memory_id,
                    "revision": o.revision,
                    "checker_id": o.checker_id,
                    "checker_digest": o.checker_digest,
                }
                for o in sorted(obligations, key=lambda o: o.obligation_id)
            ]
        }
    )


def _refusal(
    code: str,
    *,
    projection: ObligationProjection | None = None,
    attached: tuple[tuple[str, str], ...] = (),
    unattached: tuple[str, ...] = (),
    check_report: PlanCheckReport | None = None,
    subject: PlanReviewSubject | None = None,
    recall: RecallEvidence | None = None,
) -> GovernedRunEvidence:
    return GovernedRunEvidence(
        status="refused",
        refusal_code=code,
        subject_digest="" if subject is None else subject_digest(subject),
        requirements_digest=(
            "" if subject is None else subject.requirements_digest
        ),
        work_plan_digest=("" if subject is None else subject.work_plan_digest),
        obligations=() if projection is None else projection.obligations,
        excluded=() if projection is None else projection.excluded,
        attached=attached,
        unattached=unattached,
        reports=(),
        ledgers=(),
        verdicts=(),
        receipts=(),
        wire=(),
        attempt_receipts=(),
        attempts=0,
        touched_paths=(),
        denials=(),
        permit_id=None,
        binding=None,
        check_report=check_report,
        readonly=None,
        recall=recall,
    )


async def _invoke(
    agent: Any,
    prompt: str,
    run_id: str,
    context: object | None,
) -> str:
    """One real agent-loop invocation; returns a result reference."""
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=prompt)]},
        {"configurable": {"thread_id": run_id}},
        context=context,
    )
    raw = result.get("messages", []) if isinstance(result, Mapping) else []
    messages = list(raw) if isinstance(raw, list) else []
    finals = [digest(getattr(m, "content", "") or "") for m in messages[-4:]]
    return digest({"messages": finals, "count": len(messages)})


async def run_governed_work(
    *,
    config: GovernedRunConfig,
    memory: MemoryGate,
    approval: ApprovalGate,
    probe_report: Mapping[str, str],
    agent_factory: Callable[[ExtensionRegistry], Any],
    on_attempt_start: Callable[[int], None] | None = None,
) -> GovernedRunEvidence:
    """Drive one governed work plan through the real agent path.

    The caller owns every input: records/bodies are caller-resolved
    (access control stays outside), the approval desk decides whether
    the plan is approved, and ``agent_factory`` assembles the native
    agent around the registry carrying the governed middleware.
    """
    from deepagents_code.cyrano.dcode.adapter import AttemptRequest
    from deepagents_code.extensions.registry import (
        ExtensionRegistry,
        SourceInfo,
    )

    now = config.now

    def recall_context() -> RecallContext:
        """Derive the authorized query from real task inputs."""
        hints = tuple(
            sorted({p for u in config.plan.units for p in u.write_paths})
        )
        return RecallContext(
            task_id=config.run_id,
            scope_id=config.scope_id,
            path_hints=hints,
            query_terms=None,
            limit=config.recall_limit,
            now=now(),
            epoch=None if config.epoch is None else config.epoch.epoch_id,
            source_digests=memory.available_source_digests,
        )

    # 0. Task-triggered recall — before the plan is sealed, so every
    # applicable rule lands inside the approved subject digest. The
    # pinned view comes from this recall, never a reused snapshot.
    recall_evidence: RecallEvidence | None = None
    records = list(memory.records)
    rule_bodies: Mapping[str, bytes] = memory.rule_bodies
    recall_view = memory.memory_view
    if memory.recall is not None:
        try:
            outcome = memory.recall(recall_context())
        except CyranoError as exc:
            return _refusal(exc.code)
        records = list(outcome.records)
        rule_bodies = outcome.rule_bodies
        recall_view = outcome.memory_view
        recall_evidence = outcome.evidence

    # The staleness view prefers the live provider; without one it
    # falls back to the recall-pinned view (never a stale snapshot).
    live_view = memory.view_provider or (lambda: recall_view)

    # 1–2. Eligibility projection and plan linkage.
    projection = project_obligations(
        records,
        scope_id=config.scope_id,
        now=now(),
        available_source_digests=memory.available_source_digests,
        rule_bodies=rule_bodies,
        memory_view=recall_view,
        checker_digests=memory.registry.digests(),
        admitted_kinds=memory.admitted_kinds,
    )
    obligations_t = projection.obligations
    attachment = attach_obligations(
        config.plan, obligations_t, targets=config.obligation_targets
    )
    plan = attachment.plan
    missing = missing_obligations(plan, obligations_t)
    if attachment.unattached or missing:
        ids = [o.obligation_id for o in attachment.unattached]
        ids.extend(o.obligation_id for o in missing)
        return _refusal(
            "UNBOUND_OBLIGATION",
            projection=projection,
            attached=attachment.attached,
            unattached=tuple(sorted(set(ids))),
            recall=recall_evidence,
        )

    # 3–4. Requirements doc merge + sealed subject digests.
    req_doc = dict(config.requirements_doc)
    obligation_doc = obligations_requirements_doc(obligations_t)
    if "obligations" in req_doc:
        return _refusal(
            "INPUT_INVALID",
            projection=projection,
            recall=recall_evidence,
        )
    req_doc.update(obligation_doc)
    subject = build_subject(
        plan, req_doc, config.source_snapshot, config.scope
    )
    sd = subject_digest(subject)

    # 5. Static validation; checker ids double as recipe ids.
    check_report = validate_plan(
        plan,
        known_recipes=frozenset(
            memory.registry.ids() | set(config.known_recipes)
        ),
        known_interfaces=config.known_interfaces,
    )
    if not check_report.ready_for_review:
        return _refusal(
            "PLAN_INVALID",
            projection=projection,
            attached=attachment.attached,
            check_report=check_report,
            subject=subject,
            recall=recall_evidence,
        )

    # 6. Currency gate — moved/revoked rules refuse pre-dispatch.
    try:
        assert_obligations_current(
            obligations_t,
            is_current=memory.is_current,
            memory_view=live_view(),
        )
    except CyranoError as exc:
        return _refusal(
            exc.code,
            projection=projection,
            attached=attachment.attached,
            check_report=check_report,
            subject=subject,
            recall=recall_evidence,
        )

    # 7. Approval boundary: explicit approve over the shown subject.
    desk = approval.desk
    shown_text = json.dumps(
        {
            "plan_id": plan.plan_id,
            "revision": plan.revision,
            "subject_digest": sd,
            "requirements_digest": subject.requirements_digest,
            "work_plan_digest": subject.work_plan_digest,
            "source_snapshot_digest": subject.source_snapshot_digest,
            "obligations": sorted(o.obligation_id for o in obligations_t),
        },
        sort_keys=True,
    )
    record = desk.present(
        subject_digest=sd,
        shown_text=shown_text,
        audience=approval.audience,
        nonce=f"{config.run_id}-nonce",
        expires_at=now() + config.permit_ttl,
        purpose="execute",
    )
    desk.open_display(record.request_id)
    decision = (
        approval.decide(record) if approval.decide is not None else "approve"
    )
    outcome = desk.submit(
        record.request_id,
        actor=approval.audience,
        nonce=record.nonce,
        decision=decision,
        shown_text=shown_text,
        display_revision=record.display_revision,
        client_event_id=f"{config.run_id}-decision",
        now=now(),
    )
    if outcome.status != "approved":
        return _refusal(
            "APPROVAL_REQUIRED",
            projection=projection,
            attached=attachment.attached,
            check_report=check_report,
            subject=subject,
            recall=recall_evidence,
        )
    permit = issue_permit(
        approval.signing_key,
        permit_id=f"permit-{record.request_id}",
        subject_digest=sd,
        shown_digest=record.display_digest,
        user_event_id=outcome.receipt_digest or record.request_id,
        scope_id=config.scope_id,
        purpose="execute",
        audience=approval.audience,
        nonce=record.nonce,
        issued_at=now(),
        expires_at=now() + config.permit_ttl,
    )

    # 8. Context binding when the caller supplied epoch + compiled.
    binding: BindingReceipt | None = None
    if config.epoch is not None and config.compiled is not None:
        binding_view = live_view()
        if binding_view is None:
            # No pinned view exists to bind against — fail closed.
            return _refusal(
                "STALE_EPOCH",
                projection=projection,
                attached=attachment.attached,
                check_report=check_report,
                subject=subject,
                recall=recall_evidence,
            )
        try:
            binding = bind_context(
                config.compiled,
                config.epoch,
                permit_id=permit.permit_id,
                is_revoked=approval.is_revoked,
                memory_view=binding_view,
            )
        except CyranoError as exc:
            return _refusal(
                exc.code,
                projection=projection,
                attached=attachment.attached,
                check_report=check_report,
                subject=subject,
                recall=recall_evidence,
            )

    # 9. Verified-runtime handle and the brokered session.
    try:
        lock = digest(
            {
                "probe_report": dict(probe_report),
                "subject_digest": sd,
                "work_plan_digest": subject.work_plan_digest,
            }
        )
        handle = start_verified_runtime(dict(probe_report), lock)
    except CyranoError as exc:
        return _refusal(
            exc.code,
            projection=projection,
            attached=attachment.attached,
            check_report=check_report,
            subject=subject,
            recall=recall_evidence,
        )

    def currency_check() -> None:
        """Fail closed if a bound obligation went stale or revoked."""
        assert_obligations_current(
            obligations_t,
            is_current=memory.is_current,
            memory_view=live_view(),
        )
        if memory.recall is None:
            return
        # A rule becoming applicable after approval must rebind/replan
        # — never mutate the sealed plan. Re-project from the live
        # store and refuse on any drift from the bound set.
        fresh = memory.recall(recall_context())
        drifted = project_obligations(
            list(fresh.records),
            scope_id=config.scope_id,
            now=now(),
            available_source_digests=memory.available_source_digests,
            rule_bodies=fresh.rule_bodies,
            memory_view=fresh.memory_view,
            checker_digests=memory.registry.digests(),
        )
        if {o.obligation_id for o in drifted.obligations} != {
            o.obligation_id for o in obligations_t
        }:
            raise CyranoError(
                "OBLIGATION_DRIFT",
                "applicable rule set changed after approval; replan",
            )

    session = GovernedSession(
        broker=ActionBroker(
            tools=config.tools,
            grants=config.grants,
            audit=approval.audit,
        ),
        permit=permit,
        trust_root=approval.trust_root,
        subject_digest=sd,
        root=config.workspace,
        currency_check=currency_check,
        is_revoked=approval.is_revoked,
        now=now,
        audit=approval.audit,
        obligations=obligations_t,
        unmediated=config.unmediated_tools,
    )
    wire = WireCapture(
        run_id=config.run_id,
        context_digest=(
            "" if config.compiled is None else config.compiled.stable_digest
        ),
        obligation_digest=_obligation_digest(obligations_t),
    )
    registry = ExtensionRegistry()
    middleware = GovernedObligationMiddleware(
        session, wire=wire, tool_units=registry.tool_units
    )
    registry.add_middleware(
        middleware,
        SourceInfo(path=Path("cyrano-governed"), source_id="cyrano-governed"),
    )
    agent = agent_factory(registry)

    spent = {"units": 0}

    def budget_remaining() -> int:
        """Return the plan-level budget units not yet spent."""
        cap = config.plan.budget_cap or 0
        return max(0, cap - spent["units"])

    bridge = AttemptBridge(
        handle,
        guard=lambda _a: not approval.is_revoked(permit.permit_id),
        budget_remaining=budget_remaining,
    )
    tracker = CorrectionTracker()
    unit_caps: dict[str, int | None] = {}
    for oid, uid in attachment.attached:
        unit = next(u for u in plan.units if u.unit_id == uid)
        cap = unit.cost_cap
        if config.cost_cap is not None:
            cap = (
                min(cap, config.cost_cap)
                if cap is not None
                else config.cost_cap
            )
        unit_caps[oid] = cap

    def correction_cap(obligation_id: str) -> int | None:
        """Return the effective correction cap for an obligation."""
        cap = unit_caps.get(obligation_id)
        if cap is None:
            cap = config.cost_cap
        return cap

    # 10. Attempt loop through the real agent + bridge pipeline.
    reports: tuple[ObligationCheckReport, ...] = ()
    attempt_receipts: list[AttemptReceipt] = []
    status = "satisfied"
    refusal: str | None = None
    dispatched = False
    attempt = 0
    while attempt < config.max_attempts:
        attempt += 1
        if on_attempt_start is not None:
            on_attempt_start(attempt)
        try:
            currency_check()
        except CyranoError as exc:
            status = "aborted" if dispatched else "refused"
            refusal = exc.code
            break
        prompt = config.task_text if attempt == 1 else _feedback(reports)
        request = AttemptRequest(
            attempt_id=f"{config.run_id}-a{attempt}",
            input_snapshot=digest(prompt),
            context_digest=wire.context_digest,
            permit_ref=permit.permit_id,
            runtime_lock_digest=handle.runtime_lock_digest,
        )
        wire_before = len(wire.evidence)
        started = time.monotonic()
        try:
            receipt = await bridge.execute_attempt(
                request,
                lambda req: _invoke(
                    agent, prompt, config.run_id, config.agent_context
                ),
            )
        except CyranoError as exc:
            # A model call that passed currency left wire evidence —
            # the attempt was genuinely dispatched even if it never
            # returned, so partial effects are reported as "aborted",
            # not "refused".
            dispatched = dispatched or len(wire.evidence) > wire_before
            status = "aborted" if dispatched else "refused"
            refusal = exc.code
            break
        dispatched = True
        attempt_receipts.append(receipt)
        spent["units"] += 1
        reports = verify_obligations(
            obligations_t,
            registry=memory.registry,
            root=config.workspace,
            touched_paths=tuple(sorted(middleware.touched)),
            is_current=memory.is_current,
            memory_view=live_view(),
        )
        cost = AttemptCost(
            model_calls=len(wire.evidence) - wire_before,
            latency_ms=int((time.monotonic() - started) * 1000),
            units=1,
        )
        for report in reports:
            ledger = tracker.ledger(report.obligation_id)
            if ledger is None:
                tracker.record_outcome(report.obligation_id, report)
            elif ledger.outcome in {"open", "budget_exhausted"}:
                tracker.record_attempt(
                    report.obligation_id,
                    report,
                    cost,
                    cost_cap=correction_cap(report.obligation_id),
                )
        if obligations_satisfied(reports):
            break
        unmet = [r for r in reports if r.verdict.state != "satisfied"]
        if not any(
            tracker.may_correct(
                r.obligation_id,
                cost_cap=correction_cap(r.obligation_id),
            )
            for r in unmet
        ):
            for report in unmet:
                ledger = tracker.ledger(report.obligation_id)
                if ledger is not None and ledger.outcome == "open":
                    tracker.mark_exhausted(report.obligation_id)
            break

    if refusal is None:
        if obligations_satisfied(reports):
            ledgers = (tracker.ledger(o.obligation_id) for o in obligations_t)
            corrected = any(
                ledger is not None and ledger.first_failure is not None
                for ledger in ledgers
            )
            status = "corrected" if corrected else "satisfied"
        elif any(r.verdict.state == "violated" for r in reports):
            status = "violated"
        else:
            status = "unverifiable"

    # 11. Application evidence — only real satisfied checks apply.
    touched = tuple(sorted(middleware.touched))
    tool_evidence = tuple(
        f"apply:{permit.permit_id}:{path}" for path in touched
    )
    final = {r.obligation_id: r for r in reports}
    verdicts: list[ApplicationVerdict] = []
    for obligation in obligations_t:
        report = final.get(obligation.obligation_id)
        plan_ev = (
            obligation.requirement_id,
            obligation.acceptance_id,
            subject.work_plan_digest,
        )
        if report is not None and report.verdict.state == "satisfied":
            verdicts.append(
                record_application(
                    Exposure(
                        obligation.memory_id,
                        obligation.revision,
                        obligation.obligation_id,
                    ),
                    plan_evidence=plan_ev,
                    tool_evidence=tool_evidence,
                    test_evidence=(
                        digest(
                            {
                                "verdict": report.verdict.state,
                                "detail": report.verdict.detail,
                            }
                        ),
                    ),
                )
            )
        else:
            detail = (
                "no verification report"
                if report is None
                else f"{report.verdict.state}:{report.verdict.detail}"
            )
            verdicts.append(
                record_application(
                    Exposure(
                        obligation.memory_id,
                        obligation.revision,
                        obligation.obligation_id,
                    ),
                    plan_evidence=plan_ev,
                    tool_evidence=tool_evidence,
                    unknowns=(detail,),
                )
            )
    receipts = tuple(
        injection_receipt(
            o.memory_id,
            o.revision,
            "obligation",
            dispatch_confirmed=bool(wire.evidence),
            evidence_refs=wire.digests(),
        )
        for o in obligations_t
    )
    readonly = project_readonly_memory(records, obligations_t)
    return GovernedRunEvidence(
        status=status,
        refusal_code=refusal,
        subject_digest=sd,
        requirements_digest=subject.requirements_digest,
        work_plan_digest=subject.work_plan_digest,
        obligations=obligations_t,
        excluded=projection.excluded,
        attached=attachment.attached,
        unattached=(),
        reports=reports,
        ledgers=tuple(
            ledger
            for o in obligations_t
            if (ledger := tracker.ledger(o.obligation_id)) is not None
        ),
        verdicts=tuple(verdicts),
        receipts=receipts,
        wire=wire.evidence,
        attempt_receipts=tuple(attempt_receipts),
        attempts=attempt,
        touched_paths=touched,
        denials=tuple(middleware.denials),
        permit_id=permit.permit_id,
        binding=binding,
        check_report=check_report,
        readonly=readonly,
        recall=recall_evidence,
    )
