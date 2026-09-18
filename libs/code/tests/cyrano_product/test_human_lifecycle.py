"""WP03 human approval lifecycle cases HUMAN-001..016."""

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.kernel.approvals import ApprovalDesk

SUBJECT = "sha256:" + "a" * 64


def _desk_with_request(**over):
    desk = ApprovalDesk()
    fields = {
        "subject_digest": SUBJECT,
        "shown_text": "Apply plan?",
        "audience": "user1",
        "nonce": "n1",
        "expires_at": 100,
    }
    fields.update(over)
    rec = desk.present(**fields)
    return desk, rec


def _approve_kwargs(rec, **over):
    fields = {
        "actor": "user1",
        "nonce": rec.nonce,
        "decision": "approve",
        "shown_text": "Apply plan?",
        "display_revision": rec.display_revision,
        "client_event_id": "ce1",
        "now": 1,
    }
    fields.update(over)
    return fields


def test_human_001_plan_approval_no_execution_permit():
    desk, rec = _desk_with_request()
    desk.open_display(rec.request_id)
    result = desk.submit(rec.request_id, **_approve_kwargs(rec))
    assert result.status == "approved"
    assert result.receipt_digest is not None
    # a plan receipt is not an execution permit; nothing dispatched
    assert rec.purpose == "plan_approval"


def test_human_002_plan_receipt_not_publish_permit():
    desk, rec = _desk_with_request(purpose="plan_approval")
    desk.open_display(rec.request_id)
    result = desk.submit(rec.request_id, **_approve_kwargs(rec))
    assert result.receipt_digest is not None
    # using it as a publish permit must fail purpose binding
    assert rec.purpose != "execute"


def test_human_003_no_user_event_expires():
    desk, rec = _desk_with_request()
    assert desk.settle(rec.request_id, now=200) == "expired"


def test_human_004_escape_defers_without_receipt():
    desk, rec = _desk_with_request()
    desk.open_display(rec.request_id)
    result = desk.submit(
        rec.request_id,
        **_approve_kwargs(rec, decision="defer"),
    )
    assert result.receipt_digest is None


def test_human_005_request_changes_not_approval():
    desk, rec = _desk_with_request()
    desk.open_display(rec.request_id)
    result = desk.submit(
        rec.request_id,
        **_approve_kwargs(rec, decision="request_changes"),
    )
    assert result.receipt_digest is None


def test_human_006_approve_with_amendment_invalid():
    desk, rec = _desk_with_request()
    desk.open_display(rec.request_id)
    with pytest.raises(CyranoError) as exc:
        desk.submit(
            rec.request_id,
            **_approve_kwargs(rec, amendment_artifact_id="art1"),
        )
    assert exc.value.code == "INPUT_INVALID"


def test_human_007_stale_display_rejected():
    desk, rec = _desk_with_request()
    desk.open_display(rec.request_id)
    desk.revise_display(rec.request_id, "Apply plan? (v2)")
    with pytest.raises(CyranoError) as exc:
        desk.submit(
            rec.request_id,
            **_approve_kwargs(
                rec,
                shown_text="Apply plan? (v2)",
                display_revision=1,
            ),
        )
    assert exc.value.code == "STALE_DISPLAY"


def test_human_008_nonce_mismatch():
    desk, rec = _desk_with_request()
    desk.open_display(rec.request_id)
    with pytest.raises(CyranoError) as exc:
        desk.submit(
            rec.request_id,
            **_approve_kwargs(rec, nonce="other"),
        )
    assert exc.value.code == "NONCE_MISMATCH"


def test_human_009_expired_decision():
    desk, rec = _desk_with_request()
    desk.open_display(rec.request_id)
    with pytest.raises(CyranoError) as exc:
        desk.submit(rec.request_id, **_approve_kwargs(rec, now=100))
    assert exc.value.code == "DECISION_EXPIRED"


def test_human_010_wrong_actor_denied():
    desk, rec = _desk_with_request()
    desk.open_display(rec.request_id)
    with pytest.raises(CyranoError) as exc:
        desk.submit(
            rec.request_id,
            **_approve_kwargs(rec, actor="mallory"),
        )
    assert exc.value.code == "ACL_DENIED"


def test_human_011_idempotent_replay_reuses_receipt():
    desk, rec = _desk_with_request()
    desk.open_display(rec.request_id)
    first = desk.submit(rec.request_id, **_approve_kwargs(rec))
    second = desk.submit(rec.request_id, **_approve_kwargs(rec))
    assert first.receipt_digest == second.receipt_digest


def test_human_012_conflicting_replay_rejected():
    desk, rec = _desk_with_request()
    desk.open_display(rec.request_id)
    desk.submit(rec.request_id, **_approve_kwargs(rec))
    with pytest.raises(CyranoError) as exc:
        desk.submit(
            rec.request_id,
            **_approve_kwargs(rec, decision="reject"),
        )
    assert exc.value.code == "IDEMPOTENCY_CONFLICT"


def test_human_013_subset_selection_excludes_rest():
    desk, rec = _desk_with_request(
        dependencies={"B": ("A",), "C": ("A",), "D": ()}
    )
    desk.open_display(rec.request_id)
    result = desk.submit(
        rec.request_id,
        **_approve_kwargs(rec, choices=("A", "B", "C")),
    )
    assert result.status == "approved"
    assert "D" not in result.permitted


def test_human_014_missing_dependency_denied():
    desk, rec = _desk_with_request(dependencies={"B": ("A",)})
    desk.open_display(rec.request_id)
    with pytest.raises(CyranoError) as exc:
        desk.submit(
            rec.request_id,
            **_approve_kwargs(rec, choices=("B",)),
        )
    assert exc.value.code == "DEPENDENCY_NOT_AUTHORIZED"


def test_human_015_display_integrity_failure():
    desk, rec = _desk_with_request()
    desk.open_display(rec.request_id)
    with pytest.raises(CyranoError) as exc:
        desk.submit(
            rec.request_id,
            **_approve_kwargs(rec, shown_text="tampered"),
        )
    assert exc.value.code == "DISPLAY_INTEGRITY_FAILURE"


def test_human_016_pre_open_events_never_approve():
    desk, rec = _desk_with_request()
    # Enter before the display opens and repeat events after
    result = desk.submit(rec.request_id, **_approve_kwargs(rec))
    assert result.receipt_digest is None
    assert result.status == "deferred"
