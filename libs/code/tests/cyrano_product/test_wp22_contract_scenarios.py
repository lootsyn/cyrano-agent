"""WP22 contract scenarios: RF10 deployment assets and drills."""

import json
import sys
from pathlib import Path

from deepagents_code.cyrano.cli.launch import (
    check_tool_epoch,
    license_inventory,
    scan_package_contents,
    staged_migration,
    verify_wheel_assets,
)
from deepagents_code.cyrano.kernel.recovery import rollback_or_revoke
from deepagents_code.cyrano.kernel.releases import (
    Release,
    ReleaseLane,
    ReleaseSubject,
)
from deepagents_code.cyrano.kernel.rollout import bind_dispatch

CODE = Path(__file__).resolve().parents[2]
ROOT = CODE / "cyrano"


def _subject(subject_id: str, parent: str) -> ReleaseSubject:
    return ReleaseSubject(
        subject_id=subject_id,
        parent_id=parent,
        patch_digest=f"sha256:{subject_id}",
        evidence_refs=("ev-1",),
        approval_ref="ap-1",
    )


def _lane() -> ReleaseLane:
    base = Release("r1", "genesis", "sha256:r1", ("ap-0",))
    return ReleaseLane(base)


def test_r5_rf10_01_missing_wheel_asset_named_no_fallback():
    """R5-RF10-01: a missing wheel asset fails, naming the asset."""
    result = verify_wheel_assets(
        ["deepagents_code/cyrano/assets/manifest.json"],
        ["deepagents_code/cyrano/cli.py"],
    )
    assert result["complete"] is False
    assert result["missing"] == (
        "deepagents_code/cyrano/assets/manifest.json",
    )
    assert result["source_fallback"] is False


def test_r5_rf10_02_dev_material_rejected_from_wheel():
    """R5-RF10-02: source packs, keys and holdouts never ship."""
    result = scan_package_contents(
        [
            "secrets/api_key.pem",
            "eval/holdout/split-b.json",
            "config/service_token.json",
        ]
    )
    assert result["accepted"] is False
    assert len(result["rejected"]) == 3


def test_r5_rf10_03_missing_license_notice_blocks_release():
    """R5-RF10-03: a missing NOTICE blocks, process split aside."""
    result = license_inventory(
        [{"name": "serena", "license": "MIT", "requires_notice": True}]
    )
    assert result["complete"] is False
    assert result["decision"] == "blocked"
    ok = license_inventory(
        [
            {
                "name": "serena",
                "license": "MIT",
                "requires_notice": True,
                "notice": "NOTICE text",
            }
        ]
    )
    assert ok["complete"] is True


def test_r5_rf10_04_tool_epoch_pinned_on_version_swap():
    """R5-RF10-04: a mid-use tool swap needs a new probe."""
    state = check_tool_epoch("ruff-0.16.0", "ruff-0.17.0")
    assert state["epoch_version"] == "ruff-0.16.0"
    assert state["changed"] is True
    assert state["requires_new_probe"] is True
    same = check_tool_epoch("ruff-0.16.0", "ruff-0.16.0")
    assert same["requires_new_probe"] is False


def test_r5_rf10_05_migration_crash_preserves_old_generation():
    """R5-RF10-05: a crash mid-migration keeps the old generation."""
    records = [{"gen": 4, "v": i} for i in range(6)]

    def buggy(record):
        if record["v"] == 3:
            raise RuntimeError("disk full")
        return {"gen": 5, "v": record["v"]}

    result = staged_migration(records, buggy)
    assert result.committed is False
    assert result.original_preserved is True
    assert result.converted == 0


def test_r5_rf10_06_provider_revoke_stops_and_pauses():
    """R5-RF10-06: a revoked provider stops dispatch, pauses runs."""
    lane = _lane()
    subject = _subject("r2", "r1")
    promoted = lane.promote(subject, evaluated_digest=subject.patch_digest)
    live = promoted.release_id
    bound = bind_dispatch(
        lane,
        {
            "run_id": "run-old",
            "release_id": live,
            "pinned_release_id": live,
        },
    )
    assert bound.state == "bound"
    report = rollback_or_revoke(
        lane,
        revoke_release=live,
        reason="provider vulnerability",
        running_runs=({"run_id": "run-old", "release_id": live},),
    )
    assert lane.is_revoked(live) is True
    assert report.new_dispatch_stopped is True
    assert "run-old" in report.impacted_sessions
    paused = bind_dispatch(lane, {"run_id": "run-old", "release_id": live})
    assert paused.state == "paused"
    assert paused.reason == "REVOKED_RELEASE"


def test_con_mig_07_rollback_never_touches_user_code():
    """CON-MIG-07: release-pointer rollback leaves user code alone."""
    lane = _lane()
    subject = _subject("r2", "r1")
    lane.promote(subject, evaluated_digest=subject.patch_digest)
    report = rollback_or_revoke(
        lane,
        target_release="r1",
        reason="R2 regression",
        running_runs=(),
    )
    assert lane.live.release_id == "r1"
    assert report.user_code_reverted is False


def test_wp22_i03_scorecard_computed_from_real_evidence():
    """WP22-I03: the scorecard is computed from actual evidence."""
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import release_check

        assert release_check.main() == 0
    finally:
        sys.path.remove(str(ROOT / "scripts"))
    card = json.loads((ROOT / "evidence/product-scorecard.json").read_text())
    assert card["official_score"] is None
    assert card["verified_points"] >= 0
    statuses = {c["status"] for c in card["criteria"]}
    assert statuses <= {"evaluated", "not_evaluated"}
    for row in card["criteria"]:
        if row["status"] == "not_evaluated":
            assert row["points"] == 0
        else:
            assert row["evidence_refs"]


def test_wp22_i01_quality_gate_ran_with_real_tools():
    """WP22-I01: the quality gate records real tool runs."""
    report = json.loads((ROOT / "evidence/quality.json").read_text())
    assert report["line_audit_exit"] == 0
    assert report["status"] == "passed"
    tool_names = {t["name"] for t in report["tools"]}
    assert tool_names == {"ruff", "ty"}
    assert report["full_PEP8_compliance_claimed"] is False


def test_wp22_i02_readiness_report_lists_unrun_drills():
    """WP22-I02: unexecuted drills are reported, never hidden."""
    report = json.loads((ROOT / "evidence/release-readiness.json").read_text())
    gates = report["required_gates"]
    assert gates["quality_gate"] == "passed"
    drill_gates = (
        "permission_bypass_drill",
        "disk_full_drill",
        "key_rotation_drill",
        "backup_restore_drill",
        "install_nonmutation_drill",
        "clean_env_install",
        "governed_screens",
        "live_effectiveness",
    )
    for gate in drill_gates:
        assert gates[gate] in {"passed", "failed", "blocked", "not_run"}
        if gates[gate] != "passed":
            assert gate in report["unmet_gates"]
    assert gates["live_effectiveness"] != "passed"
    assert report["release_eligible"] is False


def test_release_check_is_deterministic_and_honest():
    """The readiness report never inflates preparation into product."""
    report = json.loads((ROOT / "evidence/release-readiness.json").read_text())
    assert "live effectiveness evidence" in report["does_not_establish"]
    packaging = report["packaging"]
    assert packaging["excluded"] >= 0
    wheel = packaging["wheel"]
    if wheel.get("built"):
        assert wheel["asset_check"]["complete"] is True
        assert wheel["forbidden_entries"] == []
