"""WP21 R4-RC35 contract scenarios: promote, stale, CAS, revoke."""

from __future__ import annotations

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.kernel.recovery import rollback_or_revoke
from deepagents_code.cyrano.kernel.releases import (
    Release,
    ReleaseLane,
    prepare_release,
)
from deepagents_code.cyrano.kernel.rollout import bind_dispatch


def _lane():
    return ReleaseLane(Release("r0", "genesis", "sha256:p0", ("e0",)))


def _subject(lane, patch="sha256:p1"):
    return prepare_release(
        {"patch_digest": patch, "evidence_refs": ["ev1"]},
        parent_id=lane.live.release_id,
        approval={"approval_id": "ap1"},
    )


def test_rc35_01_new_run_binds_promoted_old_run_keeps_pin():
    lane = _lane()
    promoted = lane.promote(_subject(lane), evaluated_digest="sha256:p1")
    new_run = bind_dispatch(
        lane, {"run_id": "b", "started_after_promotion": True}
    )
    old_run = bind_dispatch(lane, {"run_id": "a", "pinned_release_id": "r0"})
    assert new_run.release_id == promoted.release_id
    assert old_run.release_id == "r0"


def test_rc35_02_digest_changed_after_eval_invalidates_approval():
    lane = _lane()
    subject = _subject(lane, "sha256:p1")
    with pytest.raises(CyranoError, match="APPROVAL_INVALID"):
        lane.promote(subject, evaluated_digest="sha256:edited")
    assert lane.live.release_id == "r0"


def test_rc35_03_same_parent_concurrent_one_wins():
    lane = _lane()
    first = _subject(lane, "sha256:a")
    second = _subject(lane, "sha256:b")
    lane.promote(first, evaluated_digest="sha256:a")
    with pytest.raises(CyranoError, match="STALE_REVISION"):
        lane.promote(second, evaluated_digest="sha256:b")
    assert lane.live.parent_id == "r0"


def test_rc35_04_rollback_separates_dispatch_and_user_code():
    lane = _lane()
    promoted = lane.promote(_subject(lane), evaluated_digest="sha256:p1")
    report = rollback_or_revoke(
        lane,
        revoke_release=promoted.release_id,
        reason="canary regression",
        running_runs=[
            {"run_id": "u1", "release_id": promoted.release_id},
        ],
    )
    assert report.new_dispatch_stopped is True
    assert report.user_code_reverted is False
    assert report.impacted_sessions == ("u1",)
    assert report.new_live == "r0"
