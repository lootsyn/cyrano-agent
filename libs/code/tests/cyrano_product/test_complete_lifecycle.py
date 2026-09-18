"""WP10 completion lifecycle: evidence-bound completion judgment."""

from hashlib import sha256

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.kernel.patches import (
    ApplyGrant,
    FilePatch,
    apply_to_target,
    authorize_publish,
    deliver_result,
    rollback_source,
)
from deepagents_code.cyrano.workflow.verification import (
    CheckResult,
    assess_run,
    require_fresh_verification,
    verify_artifact,
)


def _digest(data: bytes) -> str:
    return "sha256:" + sha256(data).hexdigest()


def _verified(digest_str: str, mandatory=("c1",)):
    return verify_artifact(
        artifact_digest=digest_str,
        results=tuple(CheckResult(c, "passed", "ev") for c in mandatory),
        mandatory=mandatory,
        raw_evidence_ref="junit.xml",
    )


def test_complete_001_verified_no_change():
    report = _verified("sha256:src")
    assessment = assess_run(
        request_kind="change",
        delivery_mode="patch_only",
        verification=report,
        reviewed_digest="sha256:src",
        current_digest="sha256:src",
        source_changed=False,
    )
    assert assessment.status == "complete"
    assert assessment.outcome == "verified_no_change"
    assert assessment.may_apply is False


def test_complete_002_analysis_request_is_answered():
    assessment = assess_run(
        request_kind="analysis",
        delivery_mode="patch_only",
        verification=None,
        reviewed_digest=None,
        current_digest=None,
        source_changed=False,
    )
    assert assessment.status == "answered"
    assert assessment.may_apply is False


def test_complete_003_missing_mandatory_run_blocks():
    report = verify_artifact(
        artifact_digest="sha256:x",
        results=(CheckResult("unit", "passed", "ev"),),
        mandatory=("unit", "integration"),
        raw_evidence_ref="junit.xml",
    )
    assert report.verdict == "not_run"
    assessment = assess_run(
        request_kind="change",
        delivery_mode="apply_to_source",
        verification=report,
        reviewed_digest="sha256:x",
        current_digest="sha256:x",
        source_changed=True,
    )
    assert assessment.status == "blocked"


def test_complete_004_zero_executed_is_not_run():
    report = verify_artifact(
        artifact_digest="sha256:x",
        results=(),
        mandatory=("c1",),
        raw_evidence_ref="junit.xml",
    )
    # Zero executed checks is not_run even when a mandatory id
    # was expected to appear.
    assert report.verdict == "not_run"
    report2 = verify_artifact(
        artifact_digest="sha256:x",
        results=(),
        mandatory=(),
        raw_evidence_ref="junit.xml",
    )
    assert report2.verdict == "not_run"


def test_complete_005_mandatory_skip_is_blocked():
    report = verify_artifact(
        artifact_digest="sha256:x",
        results=(
            CheckResult("c1", "passed", "ev"),
            CheckResult("c2", "skipped", "ev"),
        ),
        mandatory=("c1", "c2"),
        raw_evidence_ref="junit.xml",
    )
    assert report.verdict == "not_run"
    assessment = assess_run(
        request_kind="change",
        delivery_mode="apply_to_source",
        verification=report,
        reviewed_digest="sha256:x",
        current_digest="sha256:x",
        source_changed=True,
    )
    assert assessment.status == "blocked"


def test_complete_006_merged_artifact_revalidation():
    report = _verified("sha256:branch")
    with pytest.raises(CyranoError) as exc:
        require_fresh_verification(
            report,
            "sha256:merged-tree",
            code="MERGE_REVALIDATION_REQUIRED",
        )
    assert exc.value.code == "MERGE_REVALIDATION_REQUIRED"


def test_complete_007_patch_only_delivers_no_source_write(tmp_path):
    delivery = deliver_result(
        "patch_only", patch_ref="artifact:patch", journal=None
    )
    assert delivery.source_changed is False


def test_complete_008_publish_needs_publish_purpose():
    with pytest.raises(CyranoError) as exc:
        authorize_publish(None)
    assert exc.value.code == "PURPOSE_MISMATCH"
    with pytest.raises(CyranoError) as exc:
        authorize_publish(ApplyGrant("acceptance", "subj"))
    assert exc.value.code == "PURPOSE_MISMATCH"
    authorize_publish(ApplyGrant("publish", "subj"))


def test_complete_009_post_review_edit_is_stale():
    report = _verified("sha256:reviewed")
    with pytest.raises(CyranoError) as exc:
        _ = assess_run(
            request_kind="change",
            delivery_mode="apply_to_source",
            verification=report,
            reviewed_digest="sha256:reviewed",
            current_digest="sha256:one-byte-later",
            source_changed=True,
        )
    assert exc.value.code == "STALE_EVIDENCE"


def test_complete_010_lost_raw_evidence_is_unverifiable():
    report = verify_artifact(
        artifact_digest="sha256:x",
        results=(CheckResult("c1", "passed"),),
        mandatory=("c1",),
        raw_evidence_ref=None,
    )
    assert report.verdict == "unverifiable"
    assert "RAW_EVIDENCE_MISSING" in report.findings


def test_complete_011_rollback_halts_on_user_modified(tmp_path):
    root = tmp_path / "src"
    root.mkdir()
    (root / "f.py").write_bytes(b"orig")
    journal = apply_to_target(
        root=root,
        patches=[FilePatch("f.py", _digest(b"orig"), b"worked")],
        grant=ApplyGrant("source_apply", "subj", ("f.py",)),
        journal_dir=tmp_path / "journal",
    )
    (root / "f.py").write_bytes(b"user-edit-after")
    report = rollback_source(root=root, journal=journal)
    assert report.status == "reconciling"
    assert (root / "f.py").read_bytes() == b"user-edit-after"


def test_complete_012_lesson_failure_is_separate():
    report = _verified("sha256:src")
    assessment = assess_run(
        request_kind="change",
        delivery_mode="patch_only",
        verification=report,
        reviewed_digest="sha256:src",
        current_digest="sha256:src",
        source_changed=False,
        lesson_status="failed",
    )
    assert assessment.status == "complete"
    assert assessment.learning_status == "failed"
