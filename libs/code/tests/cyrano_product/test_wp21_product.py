"""WP21 product cases: release CAS, pinning, revoke, rollback."""

from __future__ import annotations

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.kernel.recovery import rollback_or_revoke
from deepagents_code.cyrano.kernel.releases import (
    Release,
    ReleaseLane,
    prepare_release,
)
from deepagents_code.cyrano.kernel.rollout import (
    assign_canary,
    bind_dispatch,
    stop_dispatch,
)


def _lane():
    return ReleaseLane(Release("r0", "genesis", "sha256:p0", ("e0",)))


def _subject(lane, patch="sha256:p1", **kw):
    return prepare_release(
        {"patch_digest": patch, "evidence_refs": ["ev1"]},
        parent_id=lane.live.release_id,
        approval={"approval_id": "ap1"},
        **kw,
    )


# -- DREAM-REL ---------------------------------------------------------


def test_dream_rel_01_two_candidates_one_cas_winner():
    lane = _lane()
    first = _subject(lane, "sha256:p1")
    second = _subject(lane, "sha256:p2")
    lane.promote(first, evaluated_digest="sha256:p1")
    with pytest.raises(CyranoError, match="STALE_REVISION"):
        lane.promote(second, evaluated_digest="sha256:p2")


def test_dream_rel_02_running_pins_new_runs_bind_live():
    lane = _lane()
    subject = _subject(lane)
    promoted = lane.promote(subject, evaluated_digest="sha256:p1")
    old = bind_dispatch(lane, {"run_id": "a", "pinned_release_id": "r0"})
    assert old.release_id == "r0"
    new = bind_dispatch(
        lane,
        {"run_id": "b", "started_after_promotion": True},
    )
    assert new.release_id == promoted.release_id


def test_dream_rel_03_revoke_pauses_beats_pin():
    lane = _lane()
    lane.revoke("r0", reason="safety defect")
    bound = bind_dispatch(lane, {"run_id": "a", "release_id": "r0"})
    assert bound.state == "paused"
    assert bound.reason == "REVOKED_RELEASE"


def test_dream_rel_04_rollback_pointer_only_no_workspace_revert():
    lane = _lane()
    lane.promote(_subject(lane), evaluated_digest="sha256:p1")
    report = rollback_or_revoke(
        lane,
        running_runs=[{"run_id": "x", "release_id": lane.live.release_id}],
    )
    assert report.new_live == "r0"
    assert report.user_code_reverted is False
    assert "x" in report.impacted_sessions


def test_dream_rel_05_no_approval_no_auto_promotion():
    lane = _lane()
    with pytest.raises(CyranoError, match="RELEASE_APPROVAL_REQUIRED"):
        prepare_release(
            {"patch_digest": "sha256:p", "evidence_refs": ["e"]},
            parent_id=lane.live.release_id,
            approval=None,
        )
    delegated = prepare_release(
        {"patch_digest": "sha256:p", "evidence_refs": ["e"]},
        parent_id=lane.live.release_id,
        approval=None,
        scoped_delegation=True,
    )
    assert delegated.approval_ref.startswith("delegation:")


# -- REL-* / UH-LEARN --------------------------------------------------


def test_rel_pin_running_unchanged_new_bound():
    lane = _lane()
    lane.promote(_subject(lane), evaluated_digest="sha256:p1")
    assert (
        bind_dispatch(
            lane, {"run_id": "a", "pinned_release_id": "r0"}
        ).release_id
        == "r0"
    )


def test_rel_revoke_stops_dispatch_pauses_runs():
    lane = _lane()
    promoted = lane.promote(_subject(lane), evaluated_digest="sha256:p1")
    lane.revoke(promoted.release_id, reason="security")
    assert stop_dispatch(lane)["new_dispatch"] == "stopped"
    bound = bind_dispatch(
        lane, {"run_id": "r", "release_id": promoted.release_id}
    )
    assert bound.state == "paused"


def test_rel_code_rollback_separates_harness_from_user_code():
    lane = _lane()
    lane.promote(_subject(lane), evaluated_digest="sha256:p1")
    report = rollback_or_revoke(lane, reason="canary regression")
    assert report.action == "rollback"
    assert report.user_code_reverted is False


def test_uh_learn_09_same_parent_second_rebases():
    lane = _lane()
    first = _subject(lane, "sha256:a")
    second = _subject(lane, "sha256:b")
    lane.promote(first, evaluated_digest="sha256:a")
    with pytest.raises(CyranoError, match="STALE_REVISION"):
        lane.promote(second, evaluated_digest="sha256:b")


def test_uh_learn_10_context_of_running_run_unchanged():
    lane = _lane()
    promoted = lane.promote(_subject(lane), evaluated_digest="sha256:p1")
    bound = bind_dispatch(lane, {"run_id": "r", "pinned_release_id": "r0"})
    assert bound.release_id == "r0"
    assert lane.live.release_id == promoted.release_id


def test_uh_learn_11_canary_regression_stops_dispatch_reports():
    lane = _lane()
    promoted = lane.promote(_subject(lane), evaluated_digest="sha256:p1")
    cohort = assign_canary(lane, ["run-1", "run-2"], cohort_id="c1")
    assert cohort.release_id == promoted.release_id
    report = rollback_or_revoke(
        lane,
        revoke_release=promoted.release_id,
        reason="verification missing in canary",
        running_runs=[
            {"run_id": "run-1", "release_id": promoted.release_id},
            {"run_id": "run-0", "release_id": "r0"},
        ],
    )
    assert report.new_dispatch_stopped is True
    assert report.impacted_sessions == ("run-1",)
    assert lane.is_revoked(promoted.release_id)


def test_review_approval_without_id_refused():
    lane = _lane()
    with pytest.raises(CyranoError, match="RELEASE_APPROVAL_REQUIRED"):
        prepare_release(
            {"patch_digest": "sha256:p", "evidence_refs": ["e"]},
            parent_id=lane.live.release_id,
            approval={"note": "no id"},
        )


def test_review_revoked_live_release_binds_nothing_new():
    lane = _lane()
    promoted = lane.promote(_subject(lane), evaluated_digest="sha256:p1")
    lane.revoke(promoted.release_id, reason="security")
    bound = bind_dispatch(
        lane, {"run_id": "n", "started_after_promotion": True}
    )
    assert bound.state == "paused"


def test_review_revoke_non_live_does_not_move_pointer():
    lane = _lane()
    promoted = lane.promote(_subject(lane), evaluated_digest="sha256:p1")
    report = rollback_or_revoke(lane, revoke_release="r0", reason="old defect")
    assert report.new_live == promoted.release_id
    assert lane.is_revoked("r0")
