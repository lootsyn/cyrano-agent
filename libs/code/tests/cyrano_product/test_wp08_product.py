"""WP08 product tests: worker results, blind review, contract export.

Session machines come from the real v2 contract document; approvals
flow through the real ledger command path. Nothing here fabricates a
reviewer result — a missing required review is a refusal, not a pass.
"""

import json
from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.interview.export import (
    Approval,
    compile_contract,
    export_approved_bundle,
    export_draft,
    resolve_task_profile,
)
from deepagents_code.cyrano.interview.service import InterviewService
from deepagents_code.cyrano.interview.worker_adapter import WorkerBinding
from deepagents_code.cyrano.interview.workers import (
    ReviewLedger,
    apply_worker_result,
    request_blind_review,
)
from deepagents_code.cyrano.kernel.session_state import SessionMachine
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

ROOT = Path(__file__).resolve().parents[2]
TARGET_DDL = (ROOT / "cyrano/contracts/sql/target-schema.sql").read_text()
CONTRACT = json.loads(
    (ROOT / "cyrano/contracts/v2/session-state-machine.json").read_text()
)
DIGEST = "sha256:" + "ab" * 32


@pytest.fixture()
def service(tmp_path):
    repo = ScopedRepository.create(tmp_path / "db.sqlite3", TARGET_DDL)
    sid = repo.register_scope("t1", "u1", "w1")
    repo.create_stream(sid, "s1", "interview")
    svc = InterviewService(
        repo, sid, "s1", SessionMachine.from_contract(CONTRACT)
    )
    yield svc
    repo.close()


def _approve(svc):
    svc.ingest_user_event(
        {"type": "approve"},
        actor="u1",
        idempotency_key="approve-1",
        expected_revision=0,
        trusted_user=True,
        attested=True,
    )


def _full_ledger(service):
    ledger = ReviewLedger()
    for role in ("critic", "blind-handoff-reviewer"):
        binding = WorkerBinding(
            task_id=f"t-{role}", role=role, revision=1,
            input_digest=DIGEST,
        )
        apply_worker_result(
            service,
            {
                "task_id": f"t-{role}",
                "role": "blind_reviewer"
                if role == "blind-handoff-reviewer"
                else role,
                "base_revision": 1,
                "input_digest": DIGEST.removeprefix("sha256:"),
            },
            binding,
            ledger,
        )
    return ledger


class TestBlindScope:
    """INT-BLIND: a blind reviewer never sees biasing fields."""

    def test_int_blind_forbidden_field_refused(self):
        with pytest.raises(CyranoError) as exc:
            request_blind_review(
                "t1", 1, DIGEST,
                visible_fields=frozenset({"diff", "author"}),
            )
        assert exc.value.code == "BLIND_SCOPE_VIOLATION"

    def test_int_blind_clean_fields_admit(self):
        binding = request_blind_review(
            "t1", 1, DIGEST, visible_fields=frozenset({"diff"})
        )
        assert binding.role == "blind-handoff-reviewer"


class TestWorkerResults:
    """Worker results bind to task, role, revision, and input."""

    def test_int_r09_missing_required_review_blocks(self, service):
        _approve(service)
        bundle = compile_contract(service, snapshot_digest="s1")
        ledger = ReviewLedger()  # no reviews recorded
        approval = Approval("a1", bundle.subject_digest, "s1")
        with pytest.raises(CyranoError) as exc:
            export_approved_bundle(
                bundle, approval, ledger=ledger, current_snapshot="s1"
            )
        assert exc.value.code == "REVIEW_INCOMPLETE"

    def test_int_r09_optional_advice_failure_not_blocking(
        self, service
    ):
        _approve(service)
        bundle = compile_contract(service, snapshot_digest="s1")
        ledger = _full_ledger(service)
        # An optional scout result failing changes nothing.
        ledger.record(
            WorkerBinding("t-x", "evidence-scout", 1, DIGEST),
            "stale_requeued",
        )
        approval = Approval("a1", bundle.subject_digest, "s1")
        out = export_approved_bundle(
            bundle, approval, ledger=ledger, current_snapshot="s1"
        )
        assert out["execution_authorized"] is True

    def test_stale_worker_result_requeues(self, service):
        ledger = ReviewLedger()
        binding = WorkerBinding("t1", "critic", 2, DIGEST)
        with pytest.raises(CyranoError) as exc:
            apply_worker_result(
                service,
                {
                    "task_id": "t1",
                    "role": "critic",
                    "base_revision": 1,
                    "input_digest": DIGEST.removeprefix("sha256:"),
                },
                binding,
                ledger,
            )
        assert exc.value.code == "STALE_REVISION"
        assert ledger.requeued == ("t1",)


class TestExportAuthority:
    """INT-R20/R22/NOORIGIN/EXPORT: approval binds subject+snapshot."""

    def test_int_r22_noorigin_draft_only(self, service):
        bundle = compile_contract(service, snapshot_digest="s1")
        assert bundle.status == "draft_unapproved"
        draft = export_draft(bundle)
        assert draft["status"] == "draft_unapproved"
        assert draft["execution_authorized"] is False
        with pytest.raises(CyranoError) as exc:
            export_approved_bundle(
                bundle,
                Approval("a1", bundle.subject_digest, "s1"),
                ledger=ReviewLedger(),
                current_snapshot="s1",
            )
        assert exc.value.code == "UNAPPROVED_EXPORT"

    def test_int_r20_other_approval_not_reused(self, service):
        _approve(service)
        ledger = _full_ledger(service)
        bundle = compile_contract(service, snapshot_digest="s1")
        foreign = Approval("a-other", "sha256:" + "ff" * 32, "s1")
        with pytest.raises(CyranoError) as exc:
            export_approved_bundle(
                bundle, foreign, ledger=ledger, current_snapshot="s1"
            )
        assert exc.value.code == "APPROVAL_MISMATCH"

    def test_int_export_snapshot_change_requires_rereview(
        self, service
    ):
        _approve(service)
        ledger = _full_ledger(service)
        bundle = compile_contract(service, snapshot_digest="s1")
        approval = Approval("a1", bundle.subject_digest, "s1")
        with pytest.raises(CyranoError) as exc:
            export_approved_bundle(
                bundle, approval, ledger=ledger,
                current_snapshot="s2",
            )
        assert exc.value.code == "STALE_SNAPSHOT"

    def test_int_r18_new_statement_changes_subject(self, service):
        _approve(service)
        before = compile_contract(service, snapshot_digest="s1")
        approval = Approval("a1", before.subject_digest, "s1")
        # A new observation arrives after approval.
        service.normalize_statement("st-new", "new fact", source="tool")
        after = compile_contract(service, snapshot_digest="s1")
        assert after.subject_digest != before.subject_digest
        with pytest.raises(CyranoError) as exc:
            export_approved_bundle(
                after, approval, ledger=_full_ledger(service),
                current_snapshot="s1",
            )
        assert exc.value.code == "APPROVAL_MISMATCH"


class TestReviewProfile:
    """INTEG-REVIEW-PROFILE: risk never shrinks mandatory reviews."""

    def test_integ_review_profile_refuses_removal(self):
        with pytest.raises(CyranoError) as exc:
            resolve_task_profile(
                "low", frozenset({"blind_handoff"})
            )
        assert exc.value.code == "REVIEW_DUTY_REQUIRED"

    def test_integ_review_profile_keeps_duties(self):
        profile = resolve_task_profile("low", frozenset())
        assert "blind_handoff" in profile.reviews


class TestIntakeContract:
    """R3-21-*: intake completeness gates plan readiness."""

    def test_r3_21_01_full_intake_ready(self, service):
        service.normalize_statement("s1", "add export", source="user")
        readiness = service.assess_readiness("PLAN")
        assert readiness.ready is True
        assert service.next_action("PLAN") == "review"

    def test_r3_21_02_no_oracle_blocks(self, service):
        from deepagents_code.cyrano.interview.readiness import (
            Obligation,
        )

        service.add_obligation(
            Obligation("ob-oracle", critical=True, resolved=False)
        )
        readiness = service.assess_readiness("PLAN")
        assert readiness.ready is False
        assert service.next_action("PLAN") == "pause"

    def test_r3_21_03_conflicts_preserved(self, service):
        service.normalize_statement(
            "s-keep", "do not delete data", source="user"
        )
        service.normalize_statement(
            "s-wipe", "reset all data", source="model"
        )
        res = service.assess_readiness("PLAN", unresolved_conflicts=1)
        assert res.ready is False
        assert service.statement("s-keep").kind == "intended_change"
        assert service.statement("s-wipe").kind == "observation"

    def test_r3_21_04_scope_expansion_needs_approval(self, service):
        with pytest.raises(CyranoError) as exc:
            service.decisions.propose(
                "d-expand",
                "include forbidden path",
                proposer="model",
                domain="scope",
                impact="high",
                revision=1,
            )
        assert exc.value.code == "UNAUTHORIZED_DECISION"
        decided = service.decisions.propose(
            "d-expand",
            "include forbidden path",
            proposer="model",
            domain="scope",
            impact="high",
            revision=1,
            user_authorized=True,
        )
        assert decided.status == "decided"

    def test_r3_21_05_correction_invalidates_dependents(
        self, service
    ):
        service.decisions.propose(
            "d1", "oracle: pytest green",
            proposer="user", domain="acceptance", impact="high",
            revision=1,
        )
        closure = service.decisions.rescind(
            "d1",
            dependents={
                "plan-v1": {"d1"},
                "review-9": {"plan-v1"},
            },
        )
        assert {"plan-v1", "review-9"} <= set(closure)
        history = service.decisions.history("d1")
        assert [d.status for d in history] == ["decided", "revoked"]

    # R3-21-06 is a live_dcode case — recorded not_run in evidence.
