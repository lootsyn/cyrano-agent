"""WP09 review lifecycle: independence, findings, rounds, decisions."""

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.planning.decisions import DecisionDesk
from deepagents_code.cyrano.planning.review import (
    ReviewBoard,
    ReviewerBinding,
    ReviewFinding,
)


def _binding(reviewer="review-1", author="author-1", **kw):
    kw.setdefault("model_id", "m1")
    kw.setdefault("author_model_id", "m1")
    kw.setdefault("read_only", True)
    kw.setdefault("blind", True)
    return ReviewerBinding(
        reviewer_run_id=reviewer, author_run_id=author, **kw
    )


def _finding(board, record, fid="f1", severity="critical", evidence=("ev-1",)):
    finding = ReviewFinding(
        finding_id=fid,
        subject_digest=record.subject_digest,
        reviewer_run_id=record.reviewer_run_id,
        severity=severity,
        summary="s",
        evidence_ids=tuple(evidence),
    )
    return board.submit_finding(record, finding)


def test_review_001_independent_review_opens():
    board = ReviewBoard()
    record = board.request_review(
        "sd", _binding(), reviewer_input={"subject_digest": "sd"}
    )
    assert record.reviewer_run_id == "review-1"


def test_review_002_same_run_rejected():
    board = ReviewBoard()
    with pytest.raises(CyranoError) as exc:
        board.request_review(
            "sd",
            _binding(reviewer="author-1"),
            reviewer_input={"subject_digest": "sd"},
        )
    assert exc.value.code == "REVIEWER_NOT_INDEPENDENT"


def test_review_003_same_model_separate_run_allowed():
    board = ReviewBoard()
    record = board.request_review(
        "sd",
        _binding(model_id="m1", author_model_id="m1"),
        reviewer_input={"subject_digest": "sd"},
    )
    assert record is not None


def test_con_hil_04_disguised_reviewer_rejected():
    # Same worker behind a different label is still the author run.
    board = ReviewBoard()
    with pytest.raises(CyranoError) as exc:
        board.request_review(
            "sd",
            _binding(reviewer="author-1"),
            reviewer_input={"subject_digest": "sd"},
        )
    assert exc.value.code in {"REVIEWER_NOT_INDEPENDENT", "INPUT_INVALID"}


def test_review_004_stale_review_binding():
    board = ReviewBoard()
    record = board.request_review("sd-v1", _binding(), reviewer_input={})
    with pytest.raises(CyranoError) as exc:
        board.submit_finding(
            record,
            ReviewFinding(
                finding_id="f",
                subject_digest="sd-v2",
                reviewer_run_id="review-1",
                severity="info",
                summary="s",
                evidence_ids=("e",),
            ),
        )
    assert exc.value.code == "STALE_REVIEW"
    with pytest.raises(CyranoError) as exc2:
        board.require_reviewed("sd-v2")
    assert exc2.value.code == "STALE_REVIEW"


def test_review_005_blocking_finding_needs_evidence():
    board = ReviewBoard()
    record = board.request_review("sd", _binding(), reviewer_input={})
    with pytest.raises(CyranoError) as exc:
        board.submit_finding(
            record,
            ReviewFinding(
                finding_id="f",
                subject_digest="sd",
                reviewer_run_id="review-1",
                severity="critical",
                summary="no rollback",
                evidence_ids=(),
            ),
        )
    assert exc.value.code == "INVALID_FINDING"


def test_review_006_author_cannot_resolve():
    board = ReviewBoard()
    record = board.request_review("sd", _binding(), reviewer_input={})
    _finding(board, record)
    with pytest.raises(CyranoError) as exc:
        board.resolve_finding(
            "f1",
            "author-1",
            "fixed_verified",
            new_subject_digest="sd",
            evidence_ids=("ev-2",),
        )
    assert exc.value.code == "AUTHORITY_DENIED"


def test_review_007_fixed_verified_binds_revision():
    board = ReviewBoard()
    record = board.request_review("sd", _binding(), reviewer_input={})
    _finding(board, record)
    resolved = board.resolve_finding(
        "f1",
        "review-1",
        "fixed_verified",
        new_subject_digest="sd-v2",
        evidence_ids=("ev-2",),
    )
    assert resolved.state == "fixed_verified"
    assert resolved.subject_digest == "sd-v2"


def test_review_008_refuted_needs_counter_evidence():
    board = ReviewBoard()
    record = board.request_review("sd", _binding(), reviewer_input={})
    _finding(board, record)
    with pytest.raises(CyranoError) as exc:
        board.resolve_finding(
            "f1",
            "review-1",
            "refuted_verified",
            new_subject_digest="sd",
            evidence_ids=(),
        )
    assert exc.value.code == "INVALID_FINDING"


def test_review_009_round_cap_deferred():
    board = ReviewBoard(max_rounds=3)
    record = board.request_review("sd", _binding(), reviewer_input={})
    _finding(board, record)
    record.rounds = 3
    assert board.finish_review(record) == "deferred"
    assert record.verdict == "changes_required"


def test_con_hil_09_unresolved_after_limit_blocked():
    board = ReviewBoard(max_rounds=5)
    record = board.request_review("sd", _binding(), reviewer_input={})
    _finding(board, record)
    record.rounds = 5
    assert board.finish_review(record) == "deferred"


def test_review_010_majority_never_clears_blocker():
    board = ReviewBoard()
    record = board.request_review("sd", _binding(), reviewer_input={})
    _finding(board, record, "f1", severity="critical")
    _finding(board, record, "f2", severity="info")
    assert board.finish_review(record) == "changes_required"
    assert record.verdict != "approve"


def test_review_011_reviewer_failure_unverifiable():
    board = ReviewBoard()
    record = board.request_review("sd", _binding(), reviewer_input={})
    assert board.finish_review(record, reviewer_ok=False) == ("unverifiable")
    assert record.verdict == "unverifiable"


def test_review_012_oracle_change_is_new_subject():
    board = ReviewBoard()
    record = board.request_review("sd", _binding(), reviewer_input={})
    _finding(board, record)
    with pytest.raises(CyranoError) as exc:
        board.resolve_finding(
            "f1",
            "review-1",
            "fixed_verified",
            new_subject_digest="sd",
            evidence_ids=("e",),
            test_plan_changed=True,
        )
    assert exc.value.code == "TEST_PLAN_CHANGED"


def test_uh_plan_05_self_review_rejected():
    board = ReviewBoard()
    with pytest.raises(CyranoError) as exc:
        board.request_review(
            "sd", _binding(reviewer="author-1"), reviewer_input={}
        )
    assert exc.value.code == "REVIEWER_NOT_INDEPENDENT"


def test_uh_plan_08_small_change_still_reviewed():
    board = ReviewBoard()
    record = board.request_review("tiny", _binding(), reviewer_input={})
    assert board.finish_review(record) == "reviewed"


def test_con_hil_03_no_review_no_permit():
    board = ReviewBoard()
    with pytest.raises(CyranoError) as exc:
        board.require_reviewed("sd")
    assert exc.value.code == "STALE_REVIEW"


def test_con_hil_05_conditional_approval_is_amendment():
    desk = DecisionDesk()
    req = desk.present(
        "d1",
        "scope",
        "plan_approval",
        "sd",
        "dd",
        revision=1,
    )
    outcome = desk.record_response(
        "d1",
        "request_changes",
        nonce=req.nonce,
        subject_digest="sd",
        display_digest="dd",
        expected_revision=1,
    )
    assert not outcome.granted
    assert outcome.state == "amend_requested"


def test_con_hil_06_stale_display_rejected():
    desk = DecisionDesk()
    req = desk.present("d1", "scope", "plan_approval", "sd", "dd", revision=1)
    with pytest.raises(CyranoError) as exc:
        desk.record_response(
            "d1",
            "approve",
            nonce=req.nonce,
            subject_digest="sd",
            display_digest="dd",
            expected_revision=2,
        )
    assert exc.value.code == "PERMIT_STALE"


def test_con_hil_07_silence_is_deferred_or_expired():
    desk = DecisionDesk(now=0)
    desk.present("d1", "scope", "plan_approval", "sd", "dd", ttl=10)
    desk.set_clock(20)
    assert desk.expire_pending() == ("d1",)
    outcome = desk.record_response(
        "d1",
        "approve",
        nonce="x",
        subject_digest="sd",
        display_digest="dd",
        expected_revision=0,
    )
    assert not outcome.granted
    assert outcome.state == "expired"


def test_con_hil_01_representation_reuses_request():
    desk = DecisionDesk()
    first = desk.present("d1", "scope", "plan_approval", "sd", "dd")
    again = desk.present("d1", "scope", "plan_approval", "sd", "dd")
    assert again.nonce == first.nonce
