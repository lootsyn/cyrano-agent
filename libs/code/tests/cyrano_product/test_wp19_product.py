"""WP19 product cases: code lane self-edit, wheel, migration."""

from __future__ import annotations

import zipfile

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.dcode.package_build import apply_copy
from deepagents_code.cyrano.improvement.code_lane import (
    BuildEvidence,
    guard_self_edit,
    plan_migration,
    prepare_code_workspace,
    prepare_runtime_candidate,
    run_code_checks,
)


def _wheel(tmp_path, members=("deepagents_code/cyrano/__init__.py",)):
    wheel = tmp_path / "candidate-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name in members:
            archive.writestr(name, b"# member\n")
    return wheel


# -- B-* ---------------------------------------------------------------


def test_b_selfedit_live_write_denied_redirected_to_proposal():
    decision = guard_self_edit("deepagents_code/cyrano/plugins/extension.py")
    assert decision.allowed is False
    assert decision.proposal_route == "code_proposal"
    assert guard_self_edit("docs/notes.md").allowed is True


def test_b_wheel_source_pass_clean_import_fail_is_incomplete(tmp_path):
    wheel = _wheel(tmp_path, members=())
    evidence = run_code_checks(
        source_tests_passed=True,
        wheel_path=wheel,
        required_resources=("deepagents_code/cyrano/__init__.py",),
    )
    assert evidence.source_tests_passed is True
    assert evidence.wheel_ok is False
    assert evidence.complete is False
    assert evidence.missing_resources


def test_b_migration_incompatible_needs_restore_plan():
    with pytest.raises(CyranoError, match="ROLLBACK_PLAN_REQUIRED"):
        plan_migration(
            {
                "schema_change": "events-v2",
                "compatible_with_previous": False,
            },
            restore_plan=None,
        )
    plan = plan_migration(
        {
            "schema_change": "events-v2",
            "compatible_with_previous": False,
        },
        restore_plan="restore-snapshot-s9",
    )
    assert plan.promotable is True


def test_uh_learn_12_learning_write_denied_becomes_proposal():
    decision = guard_self_edit("deepagents_code/cyrano/plugins/extension.py")
    assert decision.allowed is False
    assert decision.reason == "LIVE_PROCESS_FILE"
    assert decision.proposal_route == "code_proposal"


# -- integration -------------------------------------------------------


def test_wp19_i01_isolated_workspace_leaves_source_untouched(tmp_path):
    payload = tmp_path / "payload"
    (payload / "deepagents_code" / "cyrano").mkdir(parents=True)
    (payload / "deepagents_code" / "cyrano" / "new.py").write_text(
        "x = 1\n", encoding="utf-8"
    )
    workspace = tmp_path / "workspace"
    manifest = prepare_code_workspace(payload, workspace)
    assert manifest.entries == 1
    live = tmp_path / "live"
    live.mkdir()
    (live / "deepagents_code").mkdir()
    plan = __import__(
        "deepagents_code.cyrano.dcode.package_build",
        fromlist=["plan_copy"],
    ).plan_copy(payload, live)
    apply_copy(plan)
    assert (live / "deepagents_code" / "cyrano" / "new.py").exists()


def test_wp19_i03_incomplete_build_never_becomes_candidate(tmp_path):
    wheel = _wheel(tmp_path)
    with pytest.raises(CyranoError, match="BUILD_INCOMPLETE"):
        prepare_runtime_candidate(
            BuildEvidence(True, False, ("res",), False),
            wheel_path=wheel,
            evidence_refs=["ev1"],
        )
    candidate = prepare_runtime_candidate(
        BuildEvidence(True, True, (), True),
        wheel_path=wheel,
        evidence_refs=["ev1"],
    )
    assert candidate.state == "pending_review"
    assert candidate.wheel_digest.startswith("sha256:")


def test_review_dotdot_escape_denied():
    decision = guard_self_edit("x/../deepagents_code/core.py")
    assert decision.allowed is False
    assert decision.reason == "INVALID_PATH"
